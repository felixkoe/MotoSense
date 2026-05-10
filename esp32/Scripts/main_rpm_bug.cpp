#include <Adafruit_MAX31865.h>

static const int RTD_CS   = 5;
static const int RTD_MOSI = 23;
static const int RTD_MISO = 19;
static const int RTD_SCK  = 18;

#define RREF     430.0f
#define RNOMINAL 100.0f

const float TEMP_OFFSET = -10.0f;
const float TEMP_MIN    = -50.0f;
const float TEMP_MAX    = 250.0f;

Adafruit_MAX31865 rtd = Adafruit_MAX31865(RTD_CS, RTD_MOSI, RTD_MISO, RTD_SCK);

void setup() {
  Serial.begin(115200);
  delay(200);
  rtd.begin(MAX31865_2WIRE);
}

void loop() {
  float   tRaw        = rtd.temperature(RNOMINAL, RREF);
  float   tKorr       = tRaw + TEMP_OFFSET;
  uint8_t fault       = rtd.readFault();
  bool    implausibel = (tKorr < TEMP_MIN || tKorr > TEMP_MAX);

  Serial.print("Roh: ");
  Serial.print(tRaw, 2);
  Serial.print(" °C  |  Korrigiert: ");
  Serial.print(tKorr, 2);
  Serial.print(" °C");

  if (fault) {
    Serial.print("  |  FAULT 0x");
    Serial.print(fault, HEX);
    rtd.clearFault();
  } else if (implausibel) {
    Serial.print("  |  IMPLAUSIBEL");
  } else {
    Serial.print("  |  OK");
  }

  Serial.println();
  delay(1000);
}