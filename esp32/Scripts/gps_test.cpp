/*
 * MotoSense – GPS-Testsketch (NEO-6M)
 *
 * Gibt jede Sekunde Satellitenzahl und Position auf dem Serial Monitor aus.
 * Dient zur Überprüfung von Verkabelung und Empfang vor dem Einbau ins
 * Gesamtsystem.
 */

#include <TinyGPSPlus.h>
#include <HardwareSerial.h>

TinyGPSPlus    gps;
HardwareSerial gpsSerial(2);   // UART2: RX=GPIO16, TX=GPIO17

#define GPS_RX 16
#define GPS_TX 17

void setup() {
  Serial.begin(115200);
  gpsSerial.begin(9600, SERIAL_8N1, GPS_RX, GPS_TX);
  Serial.println("GPS-Test gestartet...");
}

void loop() {
  // UART kontinuierlich leeren – nicht blockieren
  while (gpsSerial.available()) gps.encode(gpsSerial.read());

  static unsigned long lastPrint = 0;
  if (millis() - lastPrint < 1000) return;
  lastPrint = millis();

  Serial.print("Satelliten: ");
  Serial.println(gps.satellites.isValid() ? gps.satellites.value() : 0);

  if (gps.location.isValid()) {
    Serial.print("Breitengrad: ");
    Serial.println(gps.location.lat(), 6);
    Serial.print("Längengrad:  ");
    Serial.println(gps.location.lng(), 6);
  } else {
    Serial.println("Kein GPS-Fix");
  }

  Serial.println("--------------------");
}