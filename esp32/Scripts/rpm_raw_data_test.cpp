/*
 * MotoSense - GPIO27 Drehzahl-Rohdaten-Test
 * --------------------------------------------
 */

#include <Arduino.h>

static const int RPM_PIN = 27;

volatile unsigned long lastPulseUs     = 0;
volatile unsigned long pulseIntervalUs = 0;
volatile unsigned long pulseCount      = 0;
const unsigned long RPM_MIN_INTERVAL_US = 2000;

void IRAM_ATTR onRpmPulse() {
  unsigned long now = micros();
  unsigned long dt  = now - lastPulseUs;
  if (dt > RPM_MIN_INTERVAL_US) {
    pulseIntervalUs = dt;
    lastPulseUs     = now;
    pulseCount++;
  }
}

void setup() {
  Serial.begin(115200);
  delay(200);
  pinMode(RPM_PIN, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(RPM_PIN), onRpmPulse, FALLING);
  Serial.println("GPIO27 Rohdaten-Test gestartet.");
}

unsigned long lastPrint = 0;

void loop() {
  if (millis() - lastPrint >= 300) {
    lastPrint = millis();

    noInterrupts();
    unsigned long cnt      = pulseCount;
    unsigned long interval = pulseIntervalUs;
    interrupts();

    int level = digitalRead(RPM_PIN);

    Serial.print("Pegel GPIO27: ");
    Serial.print(level);
    Serial.print("  Pulse gezaehlt: ");
    Serial.print(cnt);
    Serial.print("  letztes Intervall: ");
    Serial.print(interval);
    Serial.print(" us  (~");
    Serial.print(interval > 0 ? (60000000UL / interval) : 0);
    Serial.println(" 1/min)");
  }
}