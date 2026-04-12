#include <TinyGPSPlus.h>
#include <HardwareSerial.h>
#include <MPU6050_light.h>
#include <Wire.h>

TinyGPSPlus gps;
HardwareSerial gpsSerial(2);   // UART2: RX=16, TX=17
MPU6050 mpu(Wire);

unsigned long lastPrint = 0;

void setup() {
  Serial.begin(115200);

  gpsSerial.begin(9600, SERIAL_8N1, 16, 17);

  Wire.begin(21, 22);          // SDA=21, SCL=22
  byte status = mpu.begin();
  Serial.print("MPU status: ");
  Serial.println(status);      // 0 = ok
  if (status != 0) {
    Serial.println("MPU6050 nicht gefunden!");
    while (1) delay(10);
  }

  Serial.println("Kalibrierung - bitte ruhig liegen lassen...");
  delay(1000);
  mpu.calcOffsets();           // Offsets bei Stillstand berechnen
  Serial.println("Fertig.");
}

void loop() {
  // GPS-UART kontinuierlich leeren (nicht blockieren!)
  while (gpsSerial.available() > 0) {
    gps.encode(gpsSerial.read());
  }

  // MPU laufend aktualisieren (fuer den Filter wichtig)
  mpu.update();

  // alle 500 ms ausgeben
  if (millis() - lastPrint >= 500) {
    lastPrint = millis();

    // --- Zeile 1: GPS ---
    Serial.print("GPS  | ");
    if (gps.location.isValid()) {
      Serial.print("Lat: ");    Serial.print(gps.location.lat(), 6);
      Serial.print("  Lng: ");   Serial.print(gps.location.lng(), 6);
      Serial.print("  Sats: ");  Serial.print(gps.satellites.value());
      Serial.print("  Speed: "); Serial.print(gps.speed.kmph(), 1);
      Serial.print(" km/h");
    } else {
      Serial.print("kein Fix (Sats: ");
      Serial.print(gps.satellites.value());
      Serial.print(")");
    }
    Serial.println();

    // --- Zeile 2: MPU6050 ---
    Serial.print("IMU  | ");
    Serial.print("Roll: ");    Serial.print(mpu.getAngleX(), 1);
    Serial.print("  Pitch: ");  Serial.print(mpu.getAngleY(), 1);
    Serial.print("  Yaw: ");    Serial.print(mpu.getAngleZ(), 1);
    Serial.print(" deg  |  Accel(g) X: "); Serial.print(mpu.getAccX(), 2);
    Serial.print(" Y: "); Serial.print(mpu.getAccY(), 2);
    Serial.print(" Z: "); Serial.print(mpu.getAccZ(), 2);
    Serial.print("  |  Gyro(dps) X: "); Serial.print(mpu.getGyroX(), 2);
    Serial.print(" Y: "); Serial.print(mpu.getGyroY(), 2);
    Serial.print(" Z: "); Serial.print(mpu.getGyroZ(), 2);
    Serial.println();
    Serial.println();   // Leerzeile zur Trennung der Bloecke
  }
}