# fake_esp.py – simuliert eine komplette Motorrad-Fahrt für Dashboard-Tests.
#
# Aufruf:
#   python fake_esp.py            # Standard: 5x Zeitraffer
#   python fake_esp.py 10         # 10x Zeitraffer (schneller)
#   python fake_esp.py 1          # Echtzeit
#   python fake_esp.py 5 once     # Fahrt einmal abspielen, dann beenden

import json
import math
import random
import sys
import time

import paho.mqtt.client as mqtt

# Zeitraffer-Faktor und optionales Einmal-Abspielen aus Kommandozeilenargumenten
SPEEDUP = float(sys.argv[1]) if len(sys.argv) > 1 else 5.0
ONCE    = len(sys.argv) > 2 and sys.argv[2] == "once"

DT = 0.1  # simulierte Schrittweite in Sekunden -> entspricht 10 Hz wie der ESP

START_LAT, START_LNG = 48.137154, 11.576124  # Startpunkt: Marienplatz München

# Fahrprofil: (Dauer in s, Ziel-Speed km/h, Kurvigkeit 0..1, Bezeichnung)
# Die Kurvigkeit steuert, wie stark die Strecke in der jeweiligen Phase lenkt.
PHASES = [
    (4,   0,   0.0,  "Leerlauf"),
    (8,   45,  0.1,  "Anfahren"),
    (12,  50,  0.4,  "Stadtverkehr"),
    (10,  95,  0.15, "Beschleunigen"),
    (25,  85,  0.9,  "Kurvenstrecke"),
    (15,  110, 0.2,  "Schnelle Landstraße"),
    (12,  50,  0.5,  "Ortsdurchfahrt"),
    (8,   0,   0.1,  "Abbremsen"),
    (4,   0,   0.0,  "Stillstand"),
]


def run_once(client):
    lat, lng  = START_LAT, START_LNG
    heading   = 1.2   # Fahrtrichtung in Radiant
    speed     = 0.0   # aktuelle Geschwindigkeit in km/h
    t         = 0.0   # simulierte Gesamtzeit in Sekunden
    temp      = 70.0  # Motor startet kalt und wärmt sich auf

    for dur, target, curviness, name in PHASES:
        steps       = int(dur / DT)
        curve_phase = random.uniform(0, math.tau)  # zufälliger Phasenstart pro Abschnitt

        for i in range(steps):
            t += DT

            # Geschwindigkeit träge ans Ziel angleichen;
            # Bremsen geht schneller als Beschleunigen
            rate   = 0.06 if target >= speed else 0.12
            speed += (target - speed) * rate
            speed  = max(0.0, speed + random.uniform(-0.6, 0.6))

            # Streckenkrümmung aus einer überlagerten Sinusfunktion;
            # kurvige Phasen haben hohe curviness, Geraden kaum
            curve_phase += DT * (1.5 + curviness)
            steer = (curviness * math.sin(curve_phase)
                     + 0.15 * curviness * math.sin(curve_phase * 2.3))
            heading += steer * DT * 1.2

            # Schräglage wächst mit Tempo und Lenkeinschlag;
            # unter 3 km/h steht das Motorrad aufrecht
            lean_target = steer * min(speed, 120) * 0.55
            if speed < 3:
                lean_target = 0.0
            roll = round(lean_target + random.uniform(-1.2, 1.2), 1)
            roll = max(-55.0, min(55.0, roll))

            # Nicken: Beschleunigen hebt die Front, Bremsen taucht ein
            accel = target - speed
            pitch = round(max(-8, min(8, accel * 0.08)) + random.uniform(-0.4, 0.4), 1)

            # Drehzahl aus Geschwindigkeit ableiten; beim Anfahren höhere
            # Drehzahl bei noch geringem Tempo (niedrigerer Gang)
            if speed < 1:
                rpm = int(1050 + random.uniform(-40, 40))
            else:
                gear_factor = 50.0 if speed > 35 else 90.0
                rpm = int(1100 + speed * gear_factor
                          + 400 * max(0, accel) * 0.1
                          + random.uniform(-120, 120))
            rpm = max(900, min(11000, rpm))

            # Motortemperatur nähert sich langsam dem Betriebspunkt an
            temp += (94.0 - temp) * 0.01 + random.uniform(-0.15, 0.15)

            # GPS-Position anhand von Heading und Geschwindigkeit fortschreiben;
            # grobe Grad-pro-km-Näherung für den Breitengrad von München
            dist_km = speed / 3600.0 * DT
            dlat    = dist_km / 111.0 * math.cos(heading)
            dlng    = dist_km / (111.0 * math.cos(math.radians(lat))) * math.sin(heading)
            lat    += dlat
            lng    += dlng

            data = {
                "ts":    int(t * 1000),
                "rpm":   rpm,
                "speed": round(speed, 1),
                "lat":   round(lat, 6),
                "lng":   round(lng, 6),
                "sats":  random.randint(7, 12),
                "roll":  roll,
                "pitch": pitch,
                "temp":  round(temp, 1),
            }
            client.publish("motosense/data", json.dumps(data))

            print(f"[{name:22s}] t={t:5.1f}s  v={speed:5.1f} km/h  "
                  f"rpm={rpm:5d}  lean={roll:+5.1f}deg  T={temp:4.1f}C",
                  end="\r", flush=True)

            time.sleep(DT / SPEEDUP)

    print("\nFahrt beendet.                                              ")


def main():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.connect("localhost", 1883, 60)
    client.loop_start()
    print(f"Simuliere Fahrt ({SPEEDUP:g}x Zeitraffer, "
          f"{'einmalig' if ONCE else 'in Schleife'})  –  Strg+C zum Beenden\n")
    try:
        while True:
            run_once(client)
            if ONCE:
                break
            print("Neustart der Fahrt in 3 s ...\n")
            time.sleep(3)
    except KeyboardInterrupt:
        print("\nAbgebrochen.")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()