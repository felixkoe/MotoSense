/*
 * MotoSense – ESP32 Sensor-Firmware
 *
 * GPS (NEO-6M, UART2) · IMU (MPU-6050, I2C) · Temperatur (MAX31865/PT100, VSPI)
 * · Drehzahl (induktiv, Interrupt an GPIO27)
 *
 * Publisht alle 100 ms (10 Hz) eine JSON-Nachricht auf "motosense/data"
 * im selben Format wie fake_esp.py, damit das Dashboard unverändert läuft.
 *
 * Board: esp32dev (ESP32-WROOM-32)
 */

#include <WiFi.h>
#include <PubSubClient.h>
#include <Wire.h>
#include <HardwareSerial.h>
#include <TinyGPSPlus.h>
#include <MPU6050_light.h>
#include <Adafruit_MAX31865.h>

// ---- Konfiguration (anpassen!) ------------------------------------------

const char*    WIFI_SSID   = "MotoSense";
const char*    WIFI_PASS   = "motosense123";
const char*    MQTT_HOST   = "192.168.4.1";
const uint16_t MQTT_PORT   = 1883;
const char*    MQTT_TOPIC  = "motosense/data";
const char*    MQTT_CLIENT = "motosense-esp32";

// ---- Pin-Belegung -------------------------------------------------------

// GPS an UART2 (TX/RX gekreuzt: GPS-TX an ESP-RX und umgekehrt)
static const int GPS_RX = 16;
static const int GPS_TX = 17;

// IMU an I2C
static const int I2C_SDA = 21;
static const int I2C_SCL = 22;

// MAX31865 an VSPI
static const int RTD_CS   = 5;
static const int RTD_MOSI = 23;
static const int RTD_MISO = 19;
static const int RTD_SCK  = 18;

// Drehzahl (Optokoppler-Ausgang)
static const int RPM_PIN = 27;

// ---- Temperatursensor ---------------------------------------------------

// Das verbaute Board trägt einen 430-Ohm-Referenzwiderstand (Aufdruck "431")
// und ist daher eine PT100-Platine, keine PT1000 – RREF und RNOMINAL entsprechend.
#define RREF     430.0f
#define RNOMINAL 100.0f

// Kalibrierungsoffset: wird zur Rohtemperatur addiert.
// Positiv = Sensor zeigt zu wenig, negativ = zu viel.
const float TEMP_OFFSET = -10.0f;

// Plausibilitätsgrenzen; Werte außerhalb deuten auf einen Messfehler hin
// (z.B. Sonde nicht angeschlossen). Prüfung erfolgt nach Offset-Korrektur.
const float TEMP_MIN = -50.0f;
const float TEMP_MAX = 250.0f;

// ---- Objekte ------------------------------------------------------------

WiFiClient        espClient;
PubSubClient      mqtt(espClient);
TinyGPSPlus       gps;
HardwareSerial    gpsSerial(2);
MPU6050           mpu(Wire);
Adafruit_MAX31865 rtd = Adafruit_MAX31865(RTD_CS, RTD_MOSI, RTD_MISO, RTD_SCK);

// ---- Drehzahl -----------------------------------------------------------

// 1 Puls pro Kurbelwellenumdrehung (Wasted-Spark, Abnahme an einem Zündkabel)
// => RPM = 60.000.000 / Pulsintervall[µs]
volatile unsigned long lastPulseUs        = 0;
volatile unsigned long pulseIntervalUs    = 0;
volatile unsigned long lastGoodIntervalUs = 0;

const unsigned long RPM_MIN_INTERVAL_US = 2000;   // Entprellung (entspricht ~30.000 1/min)
const unsigned long RPM_TIMEOUT_US      = 500000; // 0,5 s ohne Puls -> 0 1/min

void IRAM_ATTR onRpmPulse() {
  unsigned long now = micros();
  unsigned long dt  = now - lastPulseUs;

  if (dt <= RPM_MIN_INTERVAL_US) return;

  // Plausibilitätsfilter: ein neues Intervall unter 60 % des vorherigen
  // würde eine Drehzahlverdopplung innerhalb einer Umdrehung bedeuten –
  // physikalisch nicht möglich. Filtert Störimpulse ohne echte
  // Beschleunigungsvorgänge zu beeinträchtigen.
  if (lastGoodIntervalUs > 0 && dt * 10UL < lastGoodIntervalUs * 6UL) {
    return;
  }

  pulseIntervalUs    = dt;
  lastGoodIntervalUs = dt;
  lastPulseUs        = now;
}

int readRpm() {
  unsigned long interval, last;
  // volatile-Variablen atomar kopieren, damit loop() einen konsistenten
  // Snapshot bekommt ohne mitten in einem ISR-Schreibvorgang zu lesen
  noInterrupts();
  interval = pulseIntervalUs;
  last     = lastPulseUs;
  interrupts();

  if (interval == 0)                        return 0;
  if (micros() - last > RPM_TIMEOUT_US)     return 0;
  return (int)(60000000UL / interval);
}

// ---- Sensor-Zustand -----------------------------------------------------

// GPS-Felder werden beim ersten gültigen Fix überschrieben;
// bis dahin bleibt der Startwert (Marienplatz München) stehen.
double curLat   = 48.137154;
double curLng   = 11.576124;
double curSpeed = 0.0;
int    curSats  = 0;
float  curTemp  = 0.0;

// ---- Zeitsteuerung ------------------------------------------------------

unsigned long lastPublish   = 0;
unsigned long lastTempRead  = 0;
unsigned long lastReconnect = 0;

const unsigned long PUBLISH_INTERVAL = 100;   // 10 Hz
const unsigned long TEMP_INTERVAL    = 1000;  // 1 Hz – temperature() blockiert ~70 ms

// ---- Netzwerk -----------------------------------------------------------

void setupWifi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.print("WLAN");
  unsigned long t0 = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t0 < 15000) {
    delay(250);
    Serial.print(".");
  }
  Serial.println(WiFi.status() == WL_CONNECTED ? " verbunden" : " Timeout");
}

bool mqttReconnect() {
  if (mqtt.connect(MQTT_CLIENT)) {
    Serial.println("MQTT verbunden");
    return true;
  }
  Serial.print("MQTT Fehler, rc=");
  Serial.println(mqtt.state());
  return false;
}

// ---- Setup --------------------------------------------------------------

void setup() {
  Serial.begin(115200);
  delay(200);

  gpsSerial.begin(9600, SERIAL_8N1, GPS_RX, GPS_TX);

  Wire.begin(I2C_SDA, I2C_SCL);
  byte status = mpu.begin();
  Serial.print("MPU status: ");
  Serial.println(status);  // 0 = ok
  if (status == 0) {
    Serial.println("MPU-Kalibrierung – Board ruhig und flach halten...");
    delay(1000);
    mpu.calcOffsets();
    Serial.println("Kalibrierung fertig.");
  } else {
    Serial.println("MPU6050 nicht gefunden – Verkabelung/Adresse prüfen!");
  }

  rtd.begin(MAX31865_2WIRE);

  pinMode(RPM_PIN, INPUT_PULLUP);
  // lastPulseUs mit micros() initialisieren, damit das erste Pulsintervall
  // nicht fälschlicherweise die gesamte Zeit seit Systemstart beträgt
  // und den Plausibilitätsfilter blockiert.
  lastPulseUs = micros();
  attachInterrupt(digitalPinToInterrupt(RPM_PIN), onRpmPulse, FALLING);

  setupWifi();
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
}

// ---- Loop ---------------------------------------------------------------

void loop() {
  // GPS-UART kontinuierlich leeren – niemals blockieren, damit der Puffer
  // nicht überläuft und Frames verloren gehen
  while (gpsSerial.available() > 0) gps.encode(gpsSerial.read());

  // IMU laufend aktualisieren – der Komplementärfilter braucht regelmäßige
  // Aufrufe, sonst driftet der Winkel
  mpu.update();

  // MQTT-Verbindung halten; bei Verbindungsverlust nicht-blockierend
  // reconnecten, um GPS-Lesen und IMU-Update nicht aufzuhalten
  if (WiFi.status() == WL_CONNECTED) {
    if (mqtt.connected()) {
      mqtt.loop();
    } else if (millis() - lastReconnect > 2000) {
      lastReconnect = millis();
      mqttReconnect();
    }
  } else if (millis() - lastReconnect > 5000) {
    lastReconnect = millis();
    WiFi.reconnect();
  }

  // Temperatur nur 1x pro Sekunde lesen, da der MAX31865 eine 1-Shot-Wandlung
  // durchführt und temperature() dabei ~70 ms blockiert
  if (millis() - lastTempRead >= TEMP_INTERVAL) {
    lastTempRead = millis();

    float   tRaw       = rtd.temperature(RNOMINAL, RREF);
    float   tKorr      = tRaw + TEMP_OFFSET;
    uint8_t fault      = rtd.readFault();
    bool    implausibel = (tKorr < TEMP_MIN || tKorr > TEMP_MAX);

    if (fault) rtd.clearFault();

    // Nur plausible, fehlerfreie Werte übernehmen; sonst alten Wert behalten
    if (!fault && !implausibel) curTemp = tKorr;
  }

  // GPS-Werte übernehmen sobald gültig, sonst letzten bekannten Wert behalten
  if (gps.location.isValid())   { curLat = gps.location.lat(); curLng = gps.location.lng(); }
  if (gps.speed.isValid())        curSpeed = gps.speed.kmph();
  if (gps.satellites.isValid())   curSats  = gps.satellites.value();

  // Alle 100 ms JSON-Paket zusammenbauen und publishen
  if (millis() - lastPublish >= PUBLISH_INTERVAL) {
    lastPublish = millis();

    int   rpm   = readRpm();
    float roll  = mpu.getAngleX();
    float pitch = mpu.getAngleY();

    char payload[256];
    snprintf(payload, sizeof(payload),
      "{\"ts\":%lu,\"rpm\":%d,\"speed\":%.1f,\"lat\":%.6f,\"lng\":%.6f,"
      "\"sats\":%d,\"roll\":%.1f,\"pitch\":%.1f,\"temp\":%.1f}",
      millis(), rpm, curSpeed, curLat, curLng, curSats, roll, pitch, curTemp);

    if (mqtt.connected()) mqtt.publish(MQTT_TOPIC, payload);
    Serial.println(payload);
  }
}