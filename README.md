# MotoSense

Nachrüstbares System zur Erfassung und Anzeige von Motorraddaten für ältere Motorräder.

Sensoren am Fahrzeug (Öltemperatur, Drehzahl, Schräglage, GPS) werden über ESP32-Mikrocontroller erfasst und drahtlos an einen Raspberry Pi übertragen. Eine lokale Web-App ermöglicht ein Echtzeit-Dashboard sowie die Analyse vergangener Fahrten.

## Projektstruktur

```
MotoSense/
├── Docs/               # Projektdokumentation (Berichte, PDFs)
├── Firmware/           # ESP32-Firmware (C/C++ / Arduino / PlatformIO)
│   ├── src/            # Quellcode
│   ├── include/        # Header-Dateien
│   └── lib/            # Externe Bibliotheken
├── RaspberryPi/        # Software für den Raspberry Pi
│   ├── backend/        # Server-Anwendung (API, Datenverarbeitung)
│   │   ├── api/        # Endpunkte / Routen
│   │   └── models/     # Datenmodelle
│   └── database/       # Datenbankschema und Migrationen
├── App/             # Lokale Web-App (Echtzeit-Dashboard & Fahrtanalyse)
│   ├── src/
│   │   ├── components/ # UI-Komponenten
│   │   └── pages/      # Seiten (Dashboard, Fahrthistorie, ...)
│   └── public/         # Statische Assets
└── Hardware/           # Hardware-Unterlagen
    ├── Electronics/    # Schaltpläne, PCB-Layouts
    └── Mechanics/      # Mechanische Konstruktion
        ├── CAD/        # CAD-Modelle
        └── 3D-Print/   # STL-Dateien für den 3D-Druck
```

## Technologiestack

| Bereich | Technologie |
|---|---|
| Sensorik | ESP32 (C/C++, Arduino/PlatformIO) |
| Zentraleinheit | Raspberry Pi |
| Datenbank |  |
| App |  |
| Kommunikation | Mqtt |
