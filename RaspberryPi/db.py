# db.py – SQLite-Datenhaltung für MotoSense-Fahrten.
#
# Zwei Tabellen:
#   rides        – eine Zeile pro Fahrt (Metadaten + Zusammenfassung)
#   trackpoints  – viele Zeilen pro Fahrt (ein Messpunkt je ~200 ms)

import os
import sqlite3
import threading
import time

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "motosense.db")

# Mindestabstand zwischen zwei gespeicherten Punkten.
# 0.2 s = 5 Hz – passt zum UI-Tick-Intervall im Dashboard.
SAMPLE_INTERVAL = 0.2

# Punkte werden im RAM gesammelt und erst ab dieser Menge gebündelt
# in die DB geschrieben, um häufige Einzelschreibzugriffe auf die SD-Karte
# des Raspberry Pi zu vermeiden.
FLUSH_EVERY = 25


# ---- Schema --------------------------------------------------------------

def init_db():
    # Legt die Tabellen an, falls sie noch nicht existieren.
    con = sqlite3.connect(DB_PATH)
    con.executescript("""
        CREATE TABLE IF NOT EXISTS rides (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT,
            started_at  REAL NOT NULL,
            ended_at    REAL,
            duration_s  REAL,        -- reine Fahrtzeit ohne Pausen
            distance_km REAL,
            max_speed   REAL,
            max_rpm     INTEGER,
            max_lean_l  REAL,
            max_lean_r  REAL,
            point_count INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS trackpoints (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            ride_id  INTEGER NOT NULL,
            t        REAL NOT NULL,   -- Sekunden seit Fahrtbeginn
            lat      REAL,
            lng      REAL,
            speed    REAL,
            rpm      INTEGER,
            roll     REAL,
            pitch    REAL,
            temp     REAL,
            FOREIGN KEY (ride_id) REFERENCES rides(id)
        );
        CREATE INDEX IF NOT EXISTS idx_tp_ride ON trackpoints(ride_id);
    """)
    con.commit()
    con.close()


def _connect():
    # check_same_thread=False erlaubt Zugriff aus MQTT-Thread und
    # Dash-Callbacks gleichzeitig; die Synchronisation übernimmt der
    # Lock im RideRecorder.
    return sqlite3.connect(DB_PATH, check_same_thread=False)


# ---- Lese-Funktionen (für das Dashboard) ---------------------------------

def list_rides():
    # Alle Fahrten aus der DB, neueste zuerst.
    con = _connect()
    con.row_factory = sqlite3.Row
    rows = con.execute("SELECT * FROM rides ORDER BY started_at DESC").fetchall()
    con.close()
    return [dict(r) for r in rows]


def get_ride(ride_id):
    # Metadaten einer einzelnen Fahrt, oder None falls nicht vorhanden.
    con = _connect()
    con.row_factory = sqlite3.Row
    row = con.execute("SELECT * FROM rides WHERE id=?", (ride_id,)).fetchone()
    con.close()
    return dict(row) if row else None


def get_trackpoints(ride_id):
    # Alle Messpunkte einer Fahrt, chronologisch sortiert.
    con = _connect()
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT t, lat, lng, speed, rpm, roll, pitch, temp "
        "FROM trackpoints WHERE ride_id=? ORDER BY t", (ride_id,)).fetchall()
    con.close()
    return [dict(r) for r in rows]


def delete_ride(ride_id):
    # Löscht eine Fahrt samt allen zugehörigen Trackpoints.
    con = _connect()
    con.execute("DELETE FROM trackpoints WHERE ride_id=?", (ride_id,))
    con.execute("DELETE FROM rides WHERE id=?", (ride_id,))
    con.commit()
    con.close()


# ---- Hilfsfunktion -------------------------------------------------------

def _haversine_km(lat1, lng1, lat2, lng2):
    # Luftlinien-Distanz zwischen zwei GPS-Koordinaten in km.
    from math import radians, sin, cos, sqrt, atan2
    r = 6371.0
    dlat = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)
    a = (sin(dlat / 2) ** 2
         + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2)
    return r * 2 * atan2(sqrt(a), sqrt(1 - a))


# ---- Recorder ------------------------------------------------------------

# Verwaltet den Lebenszyklus einer Fahrtaufnahme.
#
# Zustände:
#   idle       – keine aktive Fahrt
#   recording  – Punkte werden gespeichert
#   paused     – Fahrt unterbrochen, Punkte werden verworfen
#
# Typischer Ablauf:
#   start()  → legt Zeile in rides an, Zustand = recording
#   pause()  → Zustand = paused, Restpuffer wird geschrieben
#   resume() → Zustand = recording
#   stop()   → Restpuffer schreiben, Zusammenfassung in rides aktualisieren
#
# sample(state) wird vom MQTT-Thread bei jeder eingehenden Nachricht
# aufgerufen. Die Methode entscheidet anhand von SAMPLE_INTERVAL selbst,
# ob der Punkt tatsächlich gespeichert wird.
class RideRecorder:

    def __init__(self):
        self.lock = threading.Lock()
        self.status = "idle"
        self.ride_id = None
        self.started_at = None
        self._active_since = None   # Zeitstempel des letzten resume()/start()
        self._accumulated = 0.0     # aufsummierte Fahrtzeit ohne Pausen
        self._last_sample = 0.0     # Zeitstempel des letzten gespeicherten Punkts
        self._buffer = []           # noch nicht in die DB geschriebene Punkte
        # laufende Zusammenfassung für den abschließenden rides-Update
        self._dist = 0.0
        self._last_pos = None
        self._max_speed = 0.0
        self._max_rpm = 0
        self._max_lean_l = 0.0
        self._max_lean_r = 0.0
        self._count = 0

    # ---- Steuerung (aus Dash-Callbacks) ----------------------------------

    def start(self, name=None):
        # Legt eine neue Fahrt an und wechselt in den Zustand recording.
        with self.lock:
            if self.status != "idle":
                return self.ride_id
            now = time.time()
            con = _connect()
            cur = con.execute(
                "INSERT INTO rides (name, started_at) VALUES (?, ?)",
                (name or time.strftime("Fahrt %d.%m. %H:%M"), now))
            con.commit()
            self.ride_id = cur.lastrowid
            con.close()
            self.started_at = now
            self._active_since = now
            self._accumulated = 0.0
            self._last_sample = 0.0
            self._buffer = []
            self._dist = 0.0
            self._last_pos = None
            self._max_speed = 0.0
            self._max_rpm = 0
            self._max_lean_l = 0.0
            self._max_lean_r = 0.0
            self._count = 0
            self.status = "recording"
            return self.ride_id

    def pause(self):
        # Unterbricht die Aufnahme; die verstrichene Zeit wird gesichert.
        with self.lock:
            if self.status != "recording":
                return
            self._accumulated += time.time() - self._active_since
            self._active_since = None
            self.status = "paused"
            self._flush_locked()

    def resume(self):
        # Setzt eine pausierte Aufnahme fort.
        with self.lock:
            if self.status != "paused":
                return
            self._active_since = time.time()
            self.status = "recording"

    def stop(self):
        # Beendet die Aufnahme, schreibt den Restpuffer und aktualisiert
        # die Zusammenfassungsspalten in der rides-Tabelle.
        with self.lock:
            if self.status == "idle":
                return None
            if self.status == "recording" and self._active_since:
                self._accumulated += time.time() - self._active_since
            self._flush_locked()
            rid = self.ride_id
            con = _connect()
            con.execute(
                "UPDATE rides SET ended_at=?, duration_s=?, distance_km=?, "
                "max_speed=?, max_rpm=?, max_lean_l=?, max_lean_r=?, "
                "point_count=? WHERE id=?",
                (time.time(), round(self._accumulated, 1),
                 round(self._dist, 3), round(self._max_speed, 1),
                 self._max_rpm, round(self._max_lean_l, 1),
                 round(self._max_lean_r, 1), self._count, rid))
            con.commit()
            con.close()
            self.status = "idle"
            self.ride_id = None
            return rid

    # ---- Datenzufluss (aus MQTT-Thread) ----------------------------------

    def sample(self, st):
        # Nimmt den aktuellen State-Dict entgegen und speichert bei Bedarf
        # einen Trackpoint. Wird bei jeder MQTT-Nachricht aufgerufen (~10 Hz),
        # schreibt aber nur alle SAMPLE_INTERVAL Sekunden einen Punkt.
        with self.lock:
            if self.status != "recording":
                return
            now = time.time()
            if now - self._last_sample < SAMPLE_INTERVAL:
                return
            self._last_sample = now

            t = round(now - self.started_at, 2)
            lat, lng = st.get("lat"), st.get("lng")
            speed = st.get("speed", 0) or 0
            rpm   = st.get("rpm",   0) or 0
            roll  = st.get("roll",  0) or 0

            self._buffer.append((self.ride_id, t, lat, lng, speed, rpm,
                                 roll, st.get("pitch", 0), st.get("temp", 0)))

            # Distanz, Maximalwerte und Zähler laufend aktualisieren,
            # damit stop() keine Nachberechnung über alle Punkte braucht.
            if self._last_pos and lat and lng:
                self._dist += _haversine_km(
                    self._last_pos[0], self._last_pos[1], lat, lng)
            if lat and lng:
                self._last_pos = (lat, lng)
            self._max_speed = max(self._max_speed, speed)
            self._max_rpm   = max(self._max_rpm,   rpm)
            if roll  > self._max_lean_l:
                self._max_lean_l =  roll
            if -roll > self._max_lean_r:
                self._max_lean_r = -roll
            self._count += 1

            if len(self._buffer) >= FLUSH_EVERY:
                self._flush_locked()

    # ---- intern ----------------------------------------------------------

    def _flush_locked(self):
        # Schreibt den Puffer gebündelt in die DB. Caller hält self.lock.
        if not self._buffer:
            return
        con = _connect()
        con.executemany(
            "INSERT INTO trackpoints "
            "(ride_id, t, lat, lng, speed, rpm, roll, pitch, temp) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", self._buffer)
        con.commit()
        con.close()
        self._buffer = []

    def info(self):
        # Gibt den aktuellen Status für die UI zurück.
        with self.lock:
            elapsed = self._accumulated
            if self.status == "recording" and self._active_since:
                elapsed += time.time() - self._active_since
            return {
                "status":      self.status,
                "ride_id":     self.ride_id,
                "elapsed_s":   elapsed,
                "distance_km": self._dist,
                "points":      self._count,
            }


# Globale Instanz, die von dashboard.py importiert wird.
# init_db() beim Modulimport aufrufen, damit die Tabellen beim ersten Start
# automatisch angelegt werden.
recorder = RideRecorder()
init_db()