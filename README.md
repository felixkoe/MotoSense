# MotoSense

Nachrüstbares Telemetrie-System für ältere Motorräder ohne Bordelektronik. Sensoren erfassen Öltemperatur, Drehzahl, Schräglage und GPS-Position – ein ESP32 verarbeitet die Daten und sendet sie per MQTT an einen Raspberry Pi. Über eine lokale Web-App lassen sich Fahrdaten in Echtzeit abrufen und vergangene Fahrten analysieren.

Entwickelt und getestet an einer Suzuki Bandit 1200 (GV77A, Bj. 2002).

## Umsetzung

Der ESP32 liest alle Sensoren aus und publiziert alle 100 ms ein JSON-Paket auf dem MQTT-Topic `motosense/data`. Der Raspberry Pi läuft als WLAN-Access-Point, empfängt die Daten über Mosquitto und stellt sie über ein Python/Dash-Dashboard bereit. Fahrtdaten werden in einer SQLite-Datenbank gespeichert.

## Technologiestack

| Bereich        | Technologie                         |
| -------------- | ----------------------------------- |
| Sensorik       | ESP32 (C/C++, Arduino / PlatformIO) |
| Kommunikation  | MQTT (Mosquitto)                    |
| Zentraleinheit | Raspberry Pi 4 (WLAN Access Point)  |
| Backend        | Python, paho-mqtt                   |
| Dashboard      | Plotly Dash, Dash Leaflet           |
| Datenbank      | SQLite                              |

## Sensoren

| Sensor                             | Messgröße                     | Schnittstelle    |
| ---------------------------------- | ----------------------------- | ---------------- |
| NEO-6M                             | GPS-Position, Geschwindigkeit | UART2            |
| MPU-6050                           | Schräglage, Neigung           | I2C              |
| MAX31865 + PT100                   | Öltemperatur                  | SPI              |
| Induktiver Pickup + 74HC14 + PC817 | Drehzahl                      | GPIO (Interrupt) |
