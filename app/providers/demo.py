from typing import List, Dict, Any
from datetime import datetime, timedelta
from app.providers.base import BaseCarProvider
from app.database.models import CarListing

class DemoProvider(BaseCarProvider):
    def __init__(self):
        super().__init__(name="demo", priority=5)

    def search(self, config: Dict[str, Any]) -> List[CarListing]:
        now = datetime.utcnow()
        # Repräsentative Marktdaten für Kleinrinderfeld (inklusive Duplikat zur Verifikation)
        data = [
            {
                "provider": "mobile.de",
                "external_id": "mob-bmw-128ti-01",
                "url": "https://www.mobile.de/inserat/bmw-128ti/101",
                "make": "BMW", "model": "128ti",
                "title": "BMW 128ti Steptronic M Sport | ACC | Laser/LED | Live Cockpit Prof",
                "price": 24990.0, "mileage": 39500, "year": 2021, "power": 190,
                "city": "Würzburg", "plz": "97070", "dist": 14.2, "dealer": "BMW Autohaus Rhein-Main",
                "features": ["ACC / adaptiver Tempomat", "LED-Scheinwerfer", "Apple CarPlay", "Sitzheizung"],
                "img": "https://images.unsplash.com/photo-1555215695-3004980ad54e?w=800", "days_ago": 18
            },
            {
                "provider": "autoscout24",
                "external_id": "as24-bmw-128ti-01-dup",
                "url": "https://www.autoscout24.de/angebote/bmw-128ti/102",
                "make": "BMW", "model": "128ti",
                "title": "BMW 128ti Steptronic M Sportpaket ACC LED CarPlay",
                "price": 25490.0, "mileage": 39500, "year": 2021, "power": 190,
                "city": "Würzburg", "plz": "97070", "dist": 14.2, "dealer": "BMW Autohaus Rhein-Main",
                "features": ["ACC / adaptiver Tempomat", "LED-Scheinwerfer", "Apple CarPlay", "Sitzheizung"],
                "img": "https://images.unsplash.com/photo-1555215695-3004980ad54e?w=800", "days_ago": 18
            },
            {
                "provider": "mobile.de",
                "external_id": "mob-golf8-gti-02",
                "url": "https://www.mobile.de/inserat/golf-8-gti/103",
                "make": "Volkswagen", "model": "Golf GTI",
                "title": "Volkswagen Golf VIII GTI DSG IQ.Light Matrix ACC CarPlay Kamera",
                "price": 25800.0, "mileage": 48200, "year": 2021, "power": 190,
                "city": "Tauberbischofsheim", "plz": "97941", "dist": 21.5, "dealer": "Autohaus Main-Tauber",
                "features": ["ACC / adaptiver Tempomat", "LED-Scheinwerfer", "Apple CarPlay", "Sitzheizung"],
                "img": "https://images.unsplash.com/photo-1541348263662-e0c8de4259ba?w=800", "days_ago": 32
            },
            {
                "provider": "autoscout24",
                "external_id": "as24-cupra-leon-03",
                "url": "https://www.autoscout24.de/angebote/cupra-leon/104",
                "make": "Cupra", "model": "Leon",
                "title": "Cupra Leon 2.0 TSI DSG VZ-Line LED ACC BeatsAudio 19Zoll",
                "price": 23490.0, "mileage": 52000, "year": 2021, "power": 190,
                "city": "Schweinfurt", "plz": "97421", "dist": 48.0, "dealer": "Cupra Garage Franken",
                "features": ["ACC / adaptiver Tempomat", "LED-Scheinwerfer", "Apple CarPlay", "Sitzheizung"],
                "img": "https://images.unsplash.com/photo-1617814076367-b759c7d7e738?w=800", "days_ago": 12
            },
            {
                "provider": "mobile.de",
                "external_id": "mob-audi-a3-04",
                "url": "https://www.mobile.de/inserat/audi-a3/105",
                "make": "Audi", "model": "A3",
                "title": "Audi A3 Sportback S line 40 TFSI S tronic Matrix LED ACC Virtual",
                "price": 26400.0, "mileage": 56000, "year": 2021, "power": 190,
                "city": "Aschaffenburg", "plz": "63739", "dist": 68.4, "dealer": "Audi Zentrum",
                "features": ["ACC / adaptiver Tempomat", "LED-Scheinwerfer", "Apple CarPlay", "Sitzheizung"],
                "img": "https://images.unsplash.com/photo-1603584173870-7f23fdae1b7a?w=800", "days_ago": 41
            },
            {
                "provider": "autoscout24",
                "external_id": "as24-mb-a200-05",
                "url": "https://www.autoscout24.de/angebote/mb-a-klasse/106",
                "make": "Mercedes-Benz", "model": "A-Klasse",
                "title": "Mercedes-Benz A 200 AMG Line 7G-DCT Widescreen Multibeam LED Distronic",
                "price": 25900.0, "mileage": 44000, "year": 2021, "power": 163,
                "city": "Bamberg", "plz": "96052", "dist": 82.0, "dealer": "SternPartner Franken",
                "features": ["ACC / adaptiver Tempomat", "LED-Scheinwerfer", "Apple CarPlay", "Sitzheizung"],
                "img": "https://images.unsplash.com/photo-1618843479313-40f8afb4b4d8?w=800", "days_ago": 7
            },
            {
                "provider": "mobile.de",
                "external_id": "mob-hyundai-i30-06",
                "url": "https://www.mobile.de/inserat/hyundai-i30/107",
                "make": "Hyundai", "model": "i30 N",
                "title": "Hyundai i30 N-Line 1.5 T-GDI 7-DCT SmartSense Voll-LED CarPlay",
                "price": 21850.0, "mileage": 31000, "year": 2022, "power": 160,
                "city": "Heilbronn", "plz": "74072", "dist": 89.0, "dealer": "Hyundai Neckar",
                "features": ["ACC / adaptiver Tempomat", "LED-Scheinwerfer", "Apple CarPlay", "Sitzheizung"],
                "img": "https://images.unsplash.com/photo-1619682817481-e994891cd1f5?w=800", "days_ago": 5
            }
        ]

        cars = []
        for d in data:
            first_dt = now - timedelta(days=d["days_ago"])
            cars.append(CarListing(
                provider=d["provider"], external_id=d["external_id"], url=d["url"],
                make=d["make"], model=d["model"], title=d["title"], price=d["price"],
                mileage=d["mileage"], first_registration_year=d["year"], power_hp=d["power"],
                transmission="Automatik", fuel_type="Benzin", postal_code=d["plz"], city=d["city"],
                distance_km=d["dist"], dealer_name=d["dealer"], features=d["features"], image_url=d["img"],
                first_seen=first_dt.strftime("%Y-%m-%d %H:%M:%S"),
                last_seen=now.strftime("%Y-%m-%d %H:%M:%S")
            ))
        return cars