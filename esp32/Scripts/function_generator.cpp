/*
 * MotoSense – Eigenständiger Drehzahl-Signalgenerator (zweiter ESP32)
 *
 * Erzeugt auf einem GPIO ein Rechtecksignal, das eine Drehzahl simuliert –
 * unabhängig vom Haupt-ESP32. Praktisch als dauerhaftes Testgerät, um die
 * fertige RPM-Schaltung (Pickup-Klemme + 74HC14 + Optokoppler) jederzeit
 * ohne Motorrad zu prüfen.
 *
 * Verkabelung:
 *   SIG_PIN (GPIO25) über 1k-Widerstand an Knoten K1
 *     (dort wo sonst der Pickup vom Zündkabel anliegt)
 *   GND dieses ESP32 <-> GND der Schaltung / des Haupt-ESP32
 *     (bei beiden Boards am selben Rechner meist über USB schon gegeben,
 *      sonst explizit mit einem Draht verbinden)
 *
 * Bedienung über Serial Monitor (115200 Baud):
 *   Zahl + Enter   -> diese Drehzahl dauerhaft ausgeben (0 = Stillstand)
 *   'a' + Enter    -> automatischer Sweep 0 -> 11000 -> 0 1/min
 *
 * Kein WLAN, kein MQTT, keine anderen Sensoren.
 */

#include <Arduino.h>

static const int SIG_PIN = 25;

// Software-Toggle über micros() statt LEDC, weil LEDC bei sehr niedrigen
// Frequenzen (z.B. 0,5 Hz Leerlauf) unzuverlässig rundet oder klemmt.
int           targetRpm    = 0;
unsigned long halfPeriodUs = 0;   // 0 = Signal aus
unsigned long lastToggleUs = 0;
bool          sigState     = false;

void setTestRpm(int rpm) {
  targetRpm = rpm;
  if (rpm <= 0) {
    halfPeriodUs = 0;
    sigState = false;
    digitalWrite(SIG_PIN, LOW);
  } else {
    // Halbe Periode in µs: 30.000.000 / rpm
    // (1 Puls pro Umdrehung, wie am echten Pickup)
    halfPeriodUs = 30000000UL / (unsigned long)rpm;
    lastToggleUs = micros();
  }
}

// ---- Sweep-Parameter ----------------------------------------------------

const int          RPM_MIN_SWEEP = 0;
const int          RPM_MAX_SWEEP = 11000;
const int          RPM_STEP      = 500;
const unsigned long STEP_HOLD_MS = 2000;   // Haltezeit pro Stufe in ms

bool          autoMode      = true;
int           sweepDir      = 1;     // 1 = aufwärts, -1 = abwärts
unsigned long lastStepChange = 0;

// ---- Setup --------------------------------------------------------------

void setup() {
  Serial.begin(115200);
  delay(200);

  pinMode(SIG_PIN, OUTPUT);
  digitalWrite(SIG_PIN, LOW);

  setTestRpm(RPM_MIN_SWEEP);
  lastStepChange = millis();

  Serial.println("MotoSense Drehzahl-Signalgenerator gestartet.");
  Serial.println("Auto-Sweep: 0 -> 11000 -> 0 1/min, 500er Schritte, 2 s pro Stufe.");
  Serial.println("Zahl + Enter = manuell halten, 'a' + Enter = zurueck zum Sweep.");
}

// ---- Loop ---------------------------------------------------------------

unsigned long lastPrint = 0;

void loop() {
  // Im Auto-Modus die nächste Stufe schalten sobald die Haltezeit abgelaufen ist
  if (autoMode && millis() - lastStepChange >= STEP_HOLD_MS) {
    lastStepChange = millis();
    int next = targetRpm + sweepDir * RPM_STEP;
    if      (next >= RPM_MAX_SWEEP) { next = RPM_MAX_SWEEP; sweepDir = -1; }
    else if (next <= RPM_MIN_SWEEP) { next = RPM_MIN_SWEEP; sweepDir =  1; }
    setTestRpm(next);
  }

  // Testsignal nicht-blockierend erzeugen; lastToggleUs wird addiert statt
  // auf micros() gesetzt, um akkumulierten Drift zu vermeiden
  if (halfPeriodUs > 0 && micros() - lastToggleUs >= halfPeriodUs) {
    lastToggleUs += halfPeriodUs;
    sigState = !sigState;
    digitalWrite(SIG_PIN, sigState ? HIGH : LOW);
  }

  // Serial-Eingabe auswerten
  if (Serial.available()) {
    char c = Serial.peek();
    if (isDigit(c) || c == '-') {
      int v = Serial.parseInt();
      while (Serial.available()) Serial.read();   // CR/LF verwerfen
      autoMode = false;
      setTestRpm(v);
      Serial.print("Manuell gehalten: ");
      Serial.println(v);
    } else if (c == 'a' || c == 'A') {
      while (Serial.available()) Serial.read();
      autoMode = true;
      sweepDir = 1;
      setTestRpm(RPM_MIN_SWEEP);
      lastStepChange = millis();
      Serial.println("Zurück im Auto-Sweep (0 -> 11000 -> 0).");
    } else {
      Serial.read();   // einzelnes Steuerzeichen verwerfen
    }
  }

  // Status alle 200 ms ausgeben
  if (millis() - lastPrint >= 200) {
    lastPrint = millis();
    Serial.print(autoMode ? "[AUTO]    " : "[MANUELL] ");
    Serial.print("Ausgegebene Drehzahl: ");
    Serial.print(targetRpm);
    Serial.println(" 1/min");
  }
}