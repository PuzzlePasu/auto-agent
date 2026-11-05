# 🚗 Auto-Agent

> Dein persönlicher, automatisierter Gebrauchtwagen-Kaufberater und Deal-Scout.

**Auto-Agent** durchsucht kontinuierlich Fahrzeugbörsen (**mobile.de** und **AutoScout24**), erkennt Duplikate, protokolliert Preisänderungen, berechnet transparente **Deal-Scores** anhand eines mathematischen Modells und stellt Inserate im Umkreis übersichtlich dar.

---

## 📋 Funktionsübersicht

* **Multiquellen-Crawler mit Provider-Muster:**
  * Modulare Architektur (`mobile_de.py`, `autoscout24.py`, `apify.py`, `demo.py`).
  * `mobile.de` dient als bevorzugte Quelle bei Duplikaten.
  * `AutoScout24` fließt vollkommen gleichberechtigt in Marktvergleich und Preisstatistik ein.
  * Sofort einsatzbereiter `DemoProvider` für Tests ohne API-Schlüssel oder Live-Crawler via Apify (Bearer Token).
* **Intelligente Dublettenerkennung:**
  * Gleicht Inserate beider Plattformen anhand von Modell, Baujahr, Leistung, Laufleistung und Standort ab.
  * Weist Preisdifferenzen transparent aus (z. B. *„mobile.de ist 500 € günstiger“*).
* **Mathematischer Deal-Score (0–100):**
  * Berechnet Teil-Scores nach festen, anpassbaren Gewichtungen:
    * Marktpreis / Ersparnis (25 %)
    * Ausstattungsumfang (20 %)
    * Laufleistung (15 %)
    * Fahrzeugalter (10 %)
    * Leistung in PS (10 %)
    * Distanz zum Standort (10 %)
    * Preistrend / Standzeit (10 %)
  * Generiert automatische Pro- und Contra-Listen für jedes Fahrzeug.
* **Preishistorie & Standzeitüberwachung:**
  * Dokumentiert jede Preisänderung mit Zeitstempel und Ersparnisberechnung.
  * Weist Standzeiten in Tagen aus.
  * Verschwundene Inserate werden erst nach konfigurierbaren Fehlversuchen deaktiviert (kein Datenverlust).
* **Fahrzeug-Direktvergleich:**
  * Gegenüberstellung zweier Fahrzeuge mit automatischem Kategoriensieger-Check und Kaufberater-Fazit.
* **Druckfertiger PDF-Export:**
  * **Einzelbericht:** A4-Prüfbericht pro Fahrzeug inklusive Teil-Scores und Historie.
  * **Direktvergleich:** A4-Vergleichsbogen im Querformat mit Gegenüberstellung und Gesamtfazit.
* **Benachrichtigungssystem:**
  * Webhook-Unterstützung für Discord sowie E-Mail-Versand (SMTP) bei Top-Deals oder Preissenkungen.

---

## 📁 Projektstruktur

```text
auto-agent/
├── .env                        # Umgebungsvariablen & API-Secrets
├── .env.example                # Vorlage für Umgebungsvariablen
├── config.json                 # Suchkriterien, Scoring-Gewichte, Ausstattungsmerkmale
├── Dockerfile                  # Container-Definition (Python 3.11-slim)
├── docker-compose.yml          # Docker-Stack mit persistentem Volume
├── requirements.txt            # Python-Abhängigkeiten
├── README.md                   # Projektdokumentation
├── data/                       # Persistentes SQLite-Datenbankverzeichnis
└── app/
    ├── __init__.py
    ├── main.py                 # FastAPI-App, Scheduler & Lifespan
    ├── database/
    │   ├── __init__.py
    │   ├── models.py           # Datenmodelle (CarListing, PriceRecord, etc.)
    │   └── repository.py       # SQLite-Datenbankzugriff
    ├── providers/
    │   ├── __init__.py
    │   ├── base.py             # Basisklasse für Datenprovider
    │   ├── mobile_de.py        # mobile.de Integration
    │   ├── autoscout24.py      # AutoScout24 Integration
    │   ├── apify.py            # Apify Scraper via Bearer-Token
    │   └── demo.py             # Lokale Benchmark-Daten
    ├── services/
    │   ├── __init__.py
    │   ├── deduplication.py    # Dublettenerkennung & Preisvergleich
    │   ├── market_analysis.py  # Marktmedian & Durchschnittsberechnung
    │   ├── scoring.py          # Deal-Score & Pro/Contra-Engine
    │   ├── price_history.py    # Historien- & Preistrend-Metriken
    │   ├── notifications.py    # Discord & E-Mail Dispatcher
    │   ├── pdf_export.py       # ReportLab PDF-Generator (A4 Hoch- & Querformat)
    │   └── search.py           # Pipeline-Orchestrierung
    └── web/
        ├── __init__.py
        ├── routes.py           # FastAPI Web- & API-Routen
        └── templates/
            ├── base.html       # Layout-Template & Dark-Mode Design
            ├── dashboard.html  # Hauptübersicht & Filter
            ├── car_detail.html # Detailanalyse mit Teil-Scores
            └── compare.html    # 2-Fahrzeuge-Direktvergleich