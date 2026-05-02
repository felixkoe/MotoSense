#include <HardwareSerial.h>
HardwareSerial gpsSerial(2);

void setup() {
  Serial.begin(115200);
  gpsSerial.begin(9600, SERIAL_8N1, 16, 17);
}

void loop() {
  while (gpsSerial.available()) {
    Serial.write(gpsSerial.read());
  }
}