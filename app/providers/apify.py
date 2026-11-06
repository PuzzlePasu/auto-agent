import os
import logging
import requests
from typing import List, Dict, Any
from app.providers.base import BaseCarProvider
from app.database.models import CarListing

logger = logging.getLogger(__name__)

class ApifyProvider(BaseCarProvider):
    def __init__(self, api_token: str = None):
        super().__init__(name="apify", priority=1)
        self.api_token = (api_token or os.getenv("APIFY_TOKEN", "")).strip()
        self.base_url = "https://api.apify.com/v2"

    def search(self, config: Dict[str, Any]) -> List[CarListing]:
        if not self.api_token:
            logger.error("Kein APIFY_TOKEN in den Umgebungsvariablen gefunden! Abbruch.")
            return []

        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }
        
        # Apify verlangt für User/Actor eine Tilde (~) im URL-Pfad statt eines Slashs (/)
        raw_actor = os.getenv("APIFY_ACTOR_ID", "epctex/mobile-de-scraper").strip()
        actor_id = raw_actor.replace("/", "~")
        
        search_criteria = config.get("search_criteria", {})
        filters = search_criteria.get("filters", {})
        location = search_criteria.get("location", {})
        models = search_criteria.get("models", [])

        # Start-URLs für mobile.de oder direkte Filter generieren
        # epctex/mobile-de-scraper akzeptiert startUrls oder Suchfilter
        mobile_url = (
            f"https://suchen.mobile.de/fahrzeuge/search.html?"
            f"dam=0&isSearchRequest=true&vc=Car"
            f"&ft=PETROL"
            f"&tr=AUTOMATIC_GEAR"
            f"&minPowerAsArray={filters.get('min_power_hp', 150)}&maxPowerAsArray={filters.get('max_power_hp', 200)}"
            f"&maxPrice={filters.get('max_price', 27000)}"
            f"&minFirstRegistrationDate={filters.get('min_year', 2020)}"
            f"&maxMileage={filters.get('max_mileage', 80000)}"
            f"&zipcode={location.get('postal_code', '97271')}&zipcodeRadius={location.get('radius_km', 100)}"
        )

        payload = {
            "startUrls": [{"url": mobile_url}],
            "maxItems": 40,
            "proxy": {
                "useApifyProxy": True,
                "apifyProxyGroups": ["RESIDENTIAL"]
            }
        }

        url = f"{self.base_url}/acts/{actor_id}/run-sync-get-dataset-items"
        logger.info(f"Sende Suchauftrag an Apify Actor '{actor_id}' (kann 30-90 Sekunden dauern)...")

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=180)
            
            if response.status_code != 200:
                logger.error(f"Apify API Fehler HTTP {response.status_code}: {response.text}")
                return []

            raw_items = response.json()
            if not isinstance(raw_items, list):
                logger.error(f"Unerwartete Apify-Antwort (keine Liste): {raw_items}")
                return []

            logger.info(f"Erfolgreich {len(raw_items)} Roh-Fahrzeuge von Apify empfangen.")
            
            listings: List[CarListing] = []
            for item in raw_items:
                car = self._map_item(item, location)
                if car:
                    listings.append(car)

            return listings

        except requests.exceptions.Timeout:
            logger.error("Zeitüberschreitung (Timeout) beim Warten auf den Apify-Scraper nach 180 Sekunden.")
            return []
        except Exception as e:
            logger.error(f"Apify Abruf fehlgeschlagen: {e}", exc_info=True)
            return []

    def _map_item(self, item: Dict[str, Any], location: Dict[str, Any]) -> CarListing:
        # Extrahiere Bild-Array
        raw_images = item.get("images") or item.get("photos") or []
        if isinstance(raw_images, str):
            raw_images = [raw_images]
        img_url = raw_images[0] if raw_images else (item.get("imageUrl") or "")

        # Preis bereinigen
        raw_price = item.get("price")
        if isinstance(raw_price, dict):
            price_val = float(raw_price.get("amount", 0.0))
        elif isinstance(raw_price, (int, float)):
            price_val = float(raw_price)
        else:
            price_val = 0.0

        if price_val <= 0:
            return None

        # Titel & Marke
        title = item.get("title") or item.get("name") or "Angebot"
        make = item.get("make") or ("Volkswagen" if "Golf" in title else "Unbekannt")
        model = item.get("model") or ("Golf" if "Golf" in title else "Kompakt")

        return CarListing(
            provider="mobile.de",
            external_id=str(item.get("id") or item.get("adId") or hash(item.get("url", ""))),
            url=item.get("url") or item.get("link") or "https://www.mobile.de",
            make=make,
            model=model,
            title=title,
            price=price_val,
            mileage=int(item.get("mileage") or item.get("km") or 0),
            first_registration_year=int(item.get("firstRegistrationYear") or item.get("year") or 2021),
            power_hp=int(item.get("powerHp") or item.get("hp") or 150),
            transmission="Automatik",
            fuel_type="Benzin",
            postal_code=str(item.get("postalCode") or location.get("postal_code", "97271")),
            city=item.get("city") or location.get("city", ""),
            distance_km=float(item.get("distance") or 15.0),
            dealer_name=item.get("dealerName") or item.get("seller") or "Autohaus",
            features=item.get("features") or item.get("equipment") or [],
            image_url=img_url,
            images=raw_images,
            is_active=True
        )