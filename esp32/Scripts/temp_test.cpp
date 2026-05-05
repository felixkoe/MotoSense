#include <Adafruit_MAX31865.h>

// CS, MOSI, MISO, SCK – Software-SPI (Pins wie in deiner Doku)
Adafruit_MAX31865 rtd = Adafruit_MAX31865(5, 23, 19, 18);

#define RREF      4300.0   // Referenzwiderstand auf dem Board (Aufdruck "4301")
#define RNOMINAL  1000.0   // PT1000

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("MAX31865 Test startet...");

  if (!rtd.begin(MAX31865_2WIRE)) {
    Serial.println("FEHLER: begin() schlägt fehl – SPI-Verbindung/Chip nicht erreichbar!");
  } else {
    Serial.println("begin() ok.");
  }
}

void loop() {
  uint16_t raw = rtd.readRTD();
  float ratio = raw / 32768.0;
  float resistance = RREF * ratio;
  float temp = rtd.temperature(RNOMINAL, RREF);

  Serial.print("RAW: ");        Serial.print(raw);
  Serial.print("  R: ");        Serial.print(resistance, 2); Serial.print(" Ohm");
  Serial.print("  Temp: ");     Serial.print(temp, 2);        Serial.println(" °C");

  uint8_t fault = rtd.readFault();
  if (fault) {
    Serial.print("FAULT 0x"); Serial.println(fault, HEX);
    if (fault & MAX31865_FAULT_HIGHTHRESH)  Serial.println(" -> RTD High Threshold");
    if (fault & MAX31865_FAULT_LOWTHRESH)   Serial.println(" -> RTD Low Threshold");
    if (fault & MAX31865_FAULT_REFINLOW)    Serial.println(" -> REFIN- > 0.85 x VBIAS");
    if (fault & MAX31865_FAULT_REFINHIGH)   Serial.println(" -> REFIN- < 0.85 x VBIAS, FORCE- offen");
    if (fault & MAX31865_FAULT_RTDINLOW)    Serial.println(" -> RTDIN- < 0.85 x VBIAS, FORCE- offen");
    if (fault & MAX31865_FAULT_OVUV)        Serial.println(" -> Über-/Unterspannung");
    rtd.clearFault();
  }

  delay(1000);
}