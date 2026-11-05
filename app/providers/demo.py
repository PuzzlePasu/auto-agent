from typing import List, Dict, Any
from datetime import datetime, timedelta
from app.providers.base import BaseCarProvider
from app.database.models import CarListing

class DemoProvider(BaseCarProvider):
    """
    Demo-Provider für den sofortigen Testlauf ohne externen API-Key.
    Enthält Benchmark-Fahrzeuge für den Standort 97271 Kleinrinderfeld (100 km Radius):
    - Reine Benziner (keine Hybride/eTSI)
    - Bevorzugte Farben (Blau/Rot), keine weißen Autos
    - Reine Händlerangebote
    - Mehrere Bilder pro Fahrzeug für die Fotogalerie
    - Verbrauchs- und Ausstattungshighlights (Matrix, Massage, HUD, ACC)
    """
    def __init__(self):
        super().__init__(name="demo", priority=5)

    def search(self, config: Dict[str, Any]) -> List[CarListing]:
        now = datetime.utcnow()
        listings: List[CarListing] = []

        data = [
            # -------------------------------------------------------------
            # 1. Top-Deal: BMW 128ti in Misanorot (mobile.de)
            # -------------------------------------------------------------
            {
                "provider": "mobile.de",
                "external_id": "mob-bmw-128ti-rot-01",
                "url": "https://www.mobile.de/inserat/bmw-128ti-misanorot-m-sport/3948201",
                "make": "BMW",
                "model": "1er",
                "title": "BMW 128ti M Sport Steptronic Misanorot | Head-Up | Adaptive LED | Park Assist | 18 Zoll",
                "price": 24990.0,
                "mileage": 39500,
                "year": 2021,
                "month": 7,
                "power_hp": 190,
                "transmission": "Automatik",
                "fuel_type": "Benzin",
                "postal_code": "97070",
                "city": "Würzburg",
                "distance_km": 14.2,
                "dealer_name": "BMW Autohaus Rhein-Main GmbH",
                "features": [
                    "Head-Up Display",
                    "Adaptive LED",
                    "ACC / adaptiver Tempomat",
                    "Apple CarPlay",
                    "Sitzheizung",
                    "Mind. 2-Zonen Klimaautomatik",
                    "Parkassistent",
                    "Kabelloses Smartphone-Laden",
                    "Leichtmetallfelgen 18 Zoll",
                    "M Sportbremse"
                ],
                "images": [
                    "https://images.unsplash.com/photo-1555215695-3004980ad54e?w=1200&auto=format&fit=crop&q=80",
                    "https://images.unsplash.com/photo-1503376780353-7e6692767b70?w=1200&auto=format&fit=crop&q=80",
                    "https://images.unsplash.com/photo-1542282088-72c9c27ed0cd?w=1200&auto=format&fit=crop&q=80",
                    "https://images.unsplash.com/photo-1552519507-da3b142c6e3d?w=1200&auto=format&fit=crop&q=80"
                ],
                "days_ago": 18
            },

            # -------------------------------------------------------------
            # 1b. Duplikat zu 1 auf AutoScout24 (500 € teurer)
            # -------------------------------------------------------------
            {
                "provider": "autoscout24",
                "external_id": "as24-bmw-128ti-rot-01-dup",
                "url": "https://www.autoscout24.de/angebote/bmw-128ti-misanorot-m-sport-benzin-910283",
                "make": "BMW",
                "model": "1er",
                "title": "BMW 128ti Steptronic Misanorot M Sportpaket Head-Up LED HUD",
                "price": 25490.0,
                "mileage": 39500,
                "year": 2021,
                "month": 7,
                "power_hp": 190,
                "transmission": "Automatik",
                "fuel_type": "Benzin",
                "postal_code": "97070",
                "city": "Würzburg",
                "distance_km": 14.2,
                "dealer_name": "BMW Autohaus Rhein-Main GmbH",
                "features": [
                    "Head-Up Display",
                    "Adaptive LED",
                    "ACC / adaptiver Tempomat",
                    "Apple CarPlay",
                    "Sitzheizung",
                    "Mind. 2-Zonen Klimaautomatik",
                    "Parkassistent",
                    "Kabelloses Smartphone-Laden",
                    "Leichtmetallfelgen 18 Zoll"
                ],
                "images": [
                    "https://images.unsplash.com/photo-1555215695-3004980ad54e?w=1200&auto=format&fit=crop&q=80",
                    "https://images.unsplash.com/photo-1503376780353-7e6692767b70?w=1200&auto=format&fit=crop&q=80"
                ],
                "days_ago": 18
            },

            # -------------------------------------------------------------
            # 2. VW Golf 8 2.0 TSI GTI in Lapizblau Metallic (mobile.de)
            # -------------------------------------------------------------
            {
                "provider": "mobile.de",
                "external_id": "mob-vw-golf8-blau-02",
                "url": "https://www.mobile.de/inserat/volkswagen-golf-8-gti-lapizblau-iqlight-ergoactive/3819283",
                "make": "Volkswagen",
                "model": "Golf",
                "title": "Volkswagen Golf 2.0 TSI GTI DSG Lapizblau | IQ.Light Matrix | ergoActive Massage | Head-Up | 19 Zoll",
                "price": 25800.0,
                "mileage": 48200,
                "year": 2021,
                "month": 4,
                "power_hp": 190,
                "transmission": "Automatik",
                "fuel_type": "Benzin",
                "postal_code": "97941",
                "city": "Tauberbischofsheim",
                "distance_km": 21.5,
                "dealer_name": "Autohaus Main-Tauber GmbH & Co. KG",
                "features": [
                    "Matrix LED-Scheinwerfer",
                    "Massagesitz / ErgoActive",
                    "Head-Up Display",
                    "ACC / adaptiver Tempomat",
                    "Apple CarPlay",
                    "Sitzheizung",
                    "Mind. 2-Zonen Klimaautomatik",
                    "Kabelloses Smartphone-Laden",
                    "Parkassistent",
                    "Leichtmetallfelgen 19 Zoll"
                ],
                "images": [
                    "https://images.unsplash.com/photo-1541348263662-e0c8de4259ba?w=1200&auto=format&fit=crop&q=80",
                    "https://images.unsplash.com/photo-1549399542-7e3f8b79c341?w=1200&auto=format&fit=crop&q=80",
                    "https://images.unsplash.com/photo-1492144534655-ae79c964c9d7?w=1200&auto=format&fit=crop&q=80"
                ],
                "days_ago": 32
            },

            # -------------------------------------------------------------
            # 3. Cupra Leon 2.0 TSI in Tarragonarot Metallic (AutoScout24)
            # -------------------------------------------------------------
            {
                "provider": "autoscout24",
                "external_id": "as24-cupra-leon-rot-03",
                "url": "https://www.autoscout24.de/angebote/cupra-leon-20-tsi-dsg-tarragonarot-360cam-827361",
                "make": "Cupra",
                "model": "Leon",
                "title": "Cupra Leon 2.0 TSI DSG VZ-Line Tarragonarot | Matrix LED | 360 Grad Kamera | Beats | 19 Zoll",
                "price": 23490.0,
                "mileage": 52000,
                "year": 2021,
                "month": 9,
                "power_hp": 190,
                "transmission": "Automatik",
                "fuel_type": "Benzin",
                "postal_code": "97421",
                "city": "Schweinfurt",
                "distance_km": 48.0,
                "dealer_name": "Cupra Garage Franken Autohaus",
                "features": [
                    "Matrix LED-Scheinwerfer",
                    "360° Kamera / Umgebungskamera (Nice-to-Have)",
                    "ACC / adaptiver Tempomat",
                    "Apple CarPlay",
                    "Sitzheizung",
                    "Mind. 2-Zonen Klimaautomatik",
                    "Kabelloses Smartphone-Laden",
                    "Parkassistent",
                    "Leichtmetallfelgen 19 Zoll"
                ],
                "images": [
                    "https://images.unsplash.com/photo-1617814076367-b759c7d7e738?w=1200&auto=format&fit=crop&q=80",
                    "https://images.unsplash.com/photo-1502877338535-766e1452684a?w=1200&auto=format&fit=crop&q=80",
                    "https://images.unsplash.com/photo-1511919884226-fd3cad34687c?w=1200&auto=format&fit=crop&q=80"
                ],
                "days_ago": 12
            },

            # -------------------------------------------------------------
            # 4. Audi A3 Sportback 40 TFSI in Navarrablau Metallic (mobile.de)
            # -------------------------------------------------------------
            {
                "provider": "mobile.de",
                "external_id": "mob-audi-a3-blau-04",
                "url": "https://www.mobile.de/inserat/audi-a3-sportback-40-tfsi-navarrablau-matrix/3991204",
                "make": "Audi",
                "model": "A3",
                "title": "Audi A3 Sportback S line 40 TFSI S tronic Navarrablau | Matrix LED | Head-Up | Massage | 18 Zoll",
                "price": 26400.0,
                "mileage": 56000,
                "year": 2021,
                "month": 11,
                "power_hp": 190,
                "transmission": "Automatik",
                "fuel_type": "Benzin",
                "postal_code": "63739",
                "city": "Aschaffenburg",
                "distance_km": 68.4,
                "dealer_name": "Audi Zentrum Aschaffenburg GmbH",
                "features": [
                    "Matrix LED-Scheinwerfer",
                    "Massagesitz / ErgoActive",
                    "Head-Up Display",
                    "ACC / adaptiver Tempomat",
                    "Apple CarPlay",
                    "Sitzheizung",
                    "Mind. 2-Zonen Klimaautomatik",
                    "Kabelloses Smartphone-Laden",
                    "Parkassistent",
                    "Leichtmetallfelgen 18 Zoll"
                ],
                "images": [
                    "https://images.unsplash.com/photo-1603584173870-7f23fdae1b7a?w=1200&auto=format&fit=crop&q=80",
                    "https://images.unsplash.com/photo-1514316454349-750a7fd3da3a?w=1200&auto=format&fit=crop&q=80"
                ],
                "days_ago": 41
            },

            # -------------------------------------------------------------
            # 5. VW Golf 8 1.5 TSI Style in Anemonenblau Metallic (AutoScout24)
            # -------------------------------------------------------------
            {
                "provider": "autoscout24",
                "external_id": "as24-vw-golf-anemonenblau-05",
                "url": "https://www.autoscout24.de/angebote/volkswagen-golf-8-style-1-5-tsi-anemonenblau-matrix-massage-90182",
                "make": "Volkswagen",
                "model": "Golf",
                "title": "Volkswagen Golf Style 1.5 TSI Benzin Automatik Anemonenblau | IQ.Light | ergoActive Massage | Travel Assist",
                "price": 22990.0,
                "mileage": 38000,
                "year": 2021,
                "month": 8,
                "power_hp": 150,
                "transmission": "Automatik",
                "fuel_type": "Benzin",
                "postal_code": "97076",
                "city": "Würzburg",
                "distance_km": 16.0,
                "dealer_name": "VAG Autowelt Würzburg GmbH",
                "features": [
                    "Matrix LED-Scheinwerfer",
                    "Massagesitz / ErgoActive",
                    "Head-Up Display",
                    "ACC / adaptiver Tempomat",
                    "Apple CarPlay",
                    "Sitzheizung",
                    "Mind. 2-Zonen Klimaautomatik",
                    "Kabelloses Smartphone-Laden",
                    "Parkassistent",
                    "Leichtmetallfelgen 18 Zoll"
                ],
                "images": [
                    "https://images.unsplash.com/photo-1549399542-7e3f8b79c341?w=1200&auto=format&fit=crop&q=80",
                    "https://images.unsplash.com/photo-1541348263662-e0c8de4259ba?w=1200&auto=format&fit=crop&q=80",
                    "https://images.unsplash.com/photo-1492144534655-ae79c964c9d7?w=1200&auto=format&fit=crop&q=80"
                ],
                "days_ago": 24
            },

            # -------------------------------------------------------------
            # 6. Hyundai i30 N-Line 1.5 T-GDI in Sunset Red (mobile.de)
            # -------------------------------------------------------------
            {
                "provider": "mobile.de",
                "external_id": "mob-hyundai-i30-rot-06",
                "url": "https://www.mobile.de/inserat/hyundai-i30-n-line-1-5-t-gdi-sunset-red-carplay/3920194",
                "make": "Hyundai",
                "model": "i30",
                "title": "Hyundai i30 N-Line 1.5 T-GDI 7-DCT Sunset Red | Voll-LED | SmartSense ACC | Navi | 18 Zoll",
                "price": 21850.0,
                "mileage": 31000,
                "year": 2022,
                "month": 5,
                "power_hp": 160,
                "transmission": "Automatik",
                "fuel_type": "Benzin",
                "postal_code": "74072",
                "city": "Heilbronn",
                "distance_km": 89.0,
                "dealer_name": "Hyundai Autohaus Neckar GmbH",
                "features": [
                    "ACC / adaptiver Tempomat",
                    "Apple CarPlay",
                    "Sitzheizung",
                    "Mind. 2-Zonen Klimaautomatik",
                    "Kabelloses Smartphone-Laden",
                    "Parkassistent",
                    "Leichtmetallfelgen 18 Zoll"
                ],
                "images": [
                    "https://images.unsplash.com/photo-1619682817481-e994891cd1f5?w=1200&auto=format&fit=crop&q=80",
                    "https://images.unsplash.com/photo-1502877338535-766e1452684a?w=1200&auto=format&fit=crop&q=80"
                ],
                "days_ago": 5
            }
        ]

        for item in data:
            first_dt = now - timedelta(days=item["days_ago"])
            car = CarListing(
                provider=item["provider"],
                external_id=item["external_id"],
                url=item["url"],
                make=item["make"],
                model=item["model"],
                title=item["title"],
                price=item["price"],
                mileage=item["mileage"],
                first_registration_year=item["year"],
                first_registration_month=item["month"],
                power_hp=item["power_hp"],
                transmission=item["transmission"],
                fuel_type=item["fuel_type"],
                postal_code=item["postal_code"],
                city=item["city"],
                distance_km=item["distance_km"],
                dealer_name=item["dealer_name"],
                features=item["features"],
                image_url=item["images"][0] if item["images"] else "",
                images=item["images"],
                first_seen=first_dt.strftime("%Y-%m-%d %H:%M:%S"),
                last_seen=now.strftime("%Y-%m-%d %H:%M:%S"),
                is_active=True
            )
            listings.append(car)

        return listings