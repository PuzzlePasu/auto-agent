import logging
import requests
from typing import List, Dict, Any
from app.providers.base import BaseCarProvider
from app.database.models import CarListing

logger = logging.getLogger(__name__)

class MobileDeProvider(BaseCarProvider):
    """
    Dedizierter Provider für mobile.de.
    Besitzt Priorität 1 (wird bei Dubletten als Hauptangebot bevorzugt).
    """
    def __init__(self, base_url: str = "https://m.mobile.de/svc/s/"):
        super().__init__(name="mobile.de", priority=1)
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
            "ps": location.get("postal_code", "97271"),
            "rd": location.get("radius_km", 100),
            "maxPrice": filters.get("max_price", 27000),
            "fr": f"{filters.get('min_year', 2020)}:",
            "ml": f":{filters.get('max_mileage', 80000)}",
            "pw": f"{filters.get('min_power_hp', 150)}:{filters.get('max_power_hp', 200)}",
            "tr": "AUTOMATIC_GEAR"
        }

        try:
            logger.info("Frage mobile.de Direkt-Endpunkt ab...")
            response = requests.get(self.base_url, headers=headers, params=params, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                items = data.get("items", [])
                for item in items:
                    car = self._parse_mobile_item(item)
                    if car:
                        listings.append(car)
                logger.info(f"mobile.de lieferte {len(listings)} Treffer.")
            else:
                logger.warning(f"mobile.de antwortete mit Statuscode {response.status_code}. Zugriff über Web-Scraping/Proxy erforderlich.")
        except requests.exceptions.RequestException as e:
            logger.error(f"Netzwerkfehler bei mobile.de: {e}. Lauf wird fortgesetzt.")
        except Exception as e:
            logger.error(f"Unerwarteter Fehler beim Parsen von mobile.de: {e}")

        return listings

    def _parse_mobile_item(self, item: Dict[str, Any]) -> CarListing:
        try:
            item_id = str(item.get("id", ""))
            return CarListing(
                provider="mobile.de",
                external_id=item_id,
                url=f"https://suchen.mobile.de/fahrzeuge/details.html?id={item_id}",
                make=item.get("make", ""),
                model=item.get("model", ""),
                title=item.get("title", f"{item.get('make', '')} {item.get('model', '')}"),
                price=float(item.get("price", {}).get("grossAmount", 0.0)),
                mileage=int(item.get("mileage", {}).get("value", 0)),
                first_registration_year=int(item.get("firstRegistrationYear", 2021)),
                first_registration_month=int(item.get("firstRegistrationMonth", 1)),
                power_hp=int(item.get("powerHp", 190)),
                transmission="Automatik",
                fuel_type=item.get("fuelType", "Benzin"),
                postal_code=item.get("seller", {}).get("postalCode", "97271"),
                city=item.get("seller", {}).get("city", "Würzburg"),
                distance_km=float(item.get("distance", 0.0)),
                dealer_name=item.get("seller", {}).get("name", "Händler"),
                features=item.get("attributes", []),
                image_url=item.get("imageUrl", "")
            )
        except Exception:
            return None