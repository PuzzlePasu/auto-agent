import logging
import requests
from typing import List, Dict, Any
from app.providers.base import BaseCarProvider
from app.database.models import CarListing

logger = logging.getLogger(__name__)

class AutoScout24Provider(BaseCarProvider):
    """
    Dedizierter Provider für AutoScout24.
    Wird gleichberechtigt für Deal-Score und Marktpreis-Median herangezogen.
    """
    def __init__(self, base_url: str = "https://www.autoscout24.de/as24-home-ds/api/"):
        super().__init__(name="autoscout24", priority=2)
        self.base_url = base_url

    def search(self, config: Dict[str, Any]) -> List[CarListing]:
        listings: List[CarListing] = []
        search_criteria = config.get("search_criteria", {})
        filters = search_criteria.get("filters", {})
        location = search_criteria.get("location", {})

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "Accept-Language": "de-DE,de;q=0.9"
        }

        params = {
            "zip": location.get("postal_code", "97271"),
            "zipr": location.get("radius_km", 100),
            "price_to": filters.get("max_price", 27000),
            "fregfrom": filters.get("min_year", 2020),
            "kmto": filters.get("max_mileage", 80000),
            "powerfrom": filters.get("min_power_hp", 150),
            "powerto": filters.get("max_power_hp", 200),
            "gear": "A"
        }

        try:
            logger.info("Frage AutoScout24 Direkt-Endpunkt ab...")
            response = requests.get(self.base_url, headers=headers, params=params, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                for item in data.get("listings", []):
                    car = self._parse_as24_item(item)
                    if car:
                        listings.append(car)
                logger.info(f"AutoScout24 lieferte {len(listings)} Treffer.")
            else:
                logger.warning(f"AutoScout24 antwortete mit Statuscode {response.status_code}.")
        except requests.exceptions.RequestException as e:
            logger.error(f"Netzwerkfehler bei AutoScout24: {e}. Lauf wird fortgesetzt.")
        except Exception as e:
            logger.error(f"Fehler bei AutoScout24-Abfrage: {e}")

        return listings

    def _parse_as24_item(self, item: Dict[str, Any]) -> CarListing:
        try:
            item_id = str(item.get("id", ""))
            return CarListing(
                provider="autoscout24",
                external_id=item_id,
                url=f"https://www.autoscout24.de/angebote/{item_id}",
                make=item.get("vehicle", {}).get("make", ""),
                model=item.get("vehicle", {}).get("model", ""),
                title=item.get("title", ""),
                price=float(item.get("tracking", {}).get("price", 0.0)),
                mileage=int(item.get("tracking", {}).get("mileage", 0)),
                first_registration_year=int(item.get("vehicle", {}).get("year", 2021)),
                first_registration_month=1,
                power_hp=int(item.get("vehicle", {}).get("powerInHp", 190)),
                transmission="Automatik",
                fuel_type=item.get("vehicle", {}).get("fuelType", "Benzin"),
                postal_code=item.get("location", {}).get("zip", ""),
                city=item.get("location", {}).get("city", ""),
                distance_km=float(item.get("location", {}).get("distance", 0.0)),
                dealer_name=item.get("seller", {}).get("companyName", "Händler"),
                features=item.get("vehicle", {}).get("equipment", []),
                image_url=item.get("images", [""])[0] if item.get("images") else ""
            )
        except Exception:
            return None