import os
import logging
import re
import math
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from apify_client import ApifyClient
from app.database.models import CarListing

logger = logging.getLogger(__name__)

# Standard-Referenzkoordinaten (z. B. Raum Würzburg)
REF_LAT = 49.7401
REF_LON = 9.9505


def sanitize_mobile_url(url: str) -> str:
    """Bereinigt mobile.de-Such-URLs für den memo23-Actor."""
    clean_url = url.strip()
    if not clean_url:
        return ""

    clean_url = clean_url.replace("https://m.mobile.de/", "https://suchen.mobile.de/")
    clean_url = clean_url.replace("http://m.mobile.de/", "https://suchen.mobile.de/")
    clean_url = clean_url.replace("https://mobile.de/", "https://suchen.mobile.de/")
    clean_url = clean_url.replace("http://mobile.de/", "https://suchen.mobile.de/")

    try:
        parsed = urlparse(clean_url)
        qs = parse_qs(parsed.query, keep_blank_values=True)

        # Sprache auf Deutsch fixieren
        qs["lang"] = ["de"]

        # Flüchtige Tracking-Keys entfernen
        for k in ["ref", "refId", "ssid", "searchId", "sorting.direction"]:
            qs.pop(k, None)

        if "fr" in qs:
            normalized_fr = []
            for val in qs["fr"]:
                cleaned_val = re.sub(r"^\d+-", "", val)
                if cleaned_val.isdigit() and ":" not in cleaned_val:
                    cleaned_val = f"{cleaned_val}:"
                normalized_fr.append(cleaned_val)
            qs["fr"] = normalized_fr

        new_query = urlencode(qs, doseq=True)
        return urlunparse(parsed._replace(query=new_query))
    except Exception as e:
        logger.warning(f"Konnte URL nicht bereinigen, nutze Fallback: {e}")
        return clean_url


def calculate_haversine_distance(lat1: float, lon1: float, lat2: float = REF_LAT, lon2: float = REF_LON) -> float:
    """Berechnet die Luftlinie in km zwischen zwei Koordinaten."""
    try:
        r = 6371.0
        d_lat = math.radians(lat2 - lat1)
        d_lon = math.radians(lon2 - lon1)
        a = (math.sin(d_lat / 2) ** 2 +
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lon / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return round(r * c, 1)
    except Exception:
        return 25.0


class ApifyProvider:
    name = "apify"

    def __init__(self):
        self.token = os.getenv("APIFY_API_TOKEN")
        # Standardmäßig auf memo23/mobile-de-scraper setzen
        self.actor_id = os.getenv("APIFY_ACTOR_ID", "memo23/mobile-de-scraper")
        self.client = ApifyClient(self.token) if self.token else None

    def _extract_float(self, val: Any, default: float = 0.0) -> float:
        if val is None:
            return default
        if isinstance(val, (int, float)):
            return float(val)
        if isinstance(val, dict):
            for key in ["amount", "value", "price", "gross", "net"]:
                if key in val:
                    return self._extract_float(val[key], default)
            return default
        if isinstance(val, str):
            cleaned = re.sub(r"[^\d.,]", "", val).replace(".", "").replace(",", ".")
            try:
                return float(cleaned) if cleaned else default
            except ValueError:
                return default
        return default

    def get_search_urls(self, config: Dict[str, Any]) -> List[str]:
        raw_urls = []
        env_urls = os.getenv("MOBILE_SEARCH_URLS", "").strip()

        if env_urls:
            raw_urls = [
                u.strip()
                for u in env_urls.replace(";", "\n").replace(",", "\n").splitlines()
                if u.strip().startswith("http")
            ]
            if raw_urls:
                logger.info(f"ApifyProvider: {len(raw_urls)} URL(s) aus Docker-ENV geladen.")

        if not raw_urls:
            raw_urls = config.get("search_criteria", {}).get("search_page_urls", [])
            if raw_urls:
                logger.info(f"ApifyProvider: {len(raw_urls)} URL(s) aus config.json geladen.")

        if not raw_urls:
            logger.warning("ApifyProvider: Keine mobile.de Such-URLs gefunden.")
            return []

        sanitized = []
        for u in raw_urls:
            clean = sanitize_mobile_url(u)
            if clean:
                sanitized.append(clean)
        return sanitized

    def search(self, config: Dict[str, Any]) -> List[CarListing]:
        if not self.client or not self.actor_id:
            logger.error("APIFY_API_TOKEN oder APIFY_ACTOR_ID fehlt in der Umgebung.")
            return []

        urls = self.get_search_urls(config)
        if not urls:
            logger.error("Abbruch: Keine gültigen URLs vorhanden.")
            return []

        # memo23 erwartet: startUrls als Liste von Objekten mit "url"-Key
        start_urls = [{"url": u} for u in urls]

        run_input = {
            "startUrls": start_urls,
            "maxItems": 1000,
            "monitoringMode": False,
            "maxConcurrency": 10
        }

        logger.info(f"Starte Apify-Actor '{self.actor_id}' mit {len(start_urls)} URL(s)...")

        try:
            run = self.client.actor(self.actor_id).call(run_input=run_input)

            dataset_id = getattr(run, "default_dataset_id", None) or getattr(run, "defaultDatasetId", None)
            if not dataset_id and isinstance(run, dict):
                dataset_id = run.get("defaultDatasetId") or run.get("default_dataset_id")

            if not dataset_id:
                logger.error("Apify Actor lieferte keine defaultDatasetId zurück.")
                return []

            dataset_client = self.client.dataset(dataset_id)
            listings: List[CarListing] = []

            for raw_item in dataset_client.iterate_items():
                item = raw_item if isinstance(raw_item, dict) else dict(raw_item)
                car = self._map_to_car_listing(item)
                if car:
                    listings.append(car)

            logger.info(f"Apify Actor erfolgreich: {len(listings)} Inserate aus Dataset extrahiert.")
            return listings

        except Exception as e:
            logger.error(f"Fehler während des Apify-Scraping-Laufs: {e}", exc_info=True)
            return []

    def _map_to_car_listing(self, item: Dict[str, Any]) -> Optional[CarListing]:
        try:
            # Gelöschte oder nicht mehr verfügbare Inserate überspringen
            if item.get("available") is False:
                return None

            ext_id = str(item.get("id") or item.get("adId") or "")
            if not ext_id:
                return None

            url = item.get("url") or f"https://suchen.mobile.de/fahrzeuge/details.html?id={ext_id}"
            title = str(item.get("title") or item.get("shortTitle") or "Unbekanntes Fahrzeug")

            # 1. Preis aus price.grs.amount (oder Fallback)
            price = 0.0
            price_obj = item.get("price")
            if isinstance(price_obj, dict):
                grs = price_obj.get("grs")
                if isinstance(grs, dict):
                    price = self._extract_float(grs.get("amount"), 0.0)
                else:
                    price = self._extract_float(price_obj.get("amount") or price_obj.get("value"), 0.0)
            elif price_obj:
                price = self._extract_float(price_obj, 0.0)

            if price <= 500:
                return None

            # Hilfs-Lookup: attributes-Array indizieren (nach tag)
            attr_map = {}
            if isinstance(item.get("attributes"), list):
                for a in item["attributes"]:
                    if isinstance(a, dict) and "tag" in a:
                        attr_map[a["tag"]] = a.get("value", "")

            # Hilfs-Lookup: basicInfo.attr
            basic_attr = {}
            if isinstance(item.get("basicInfo"), dict) and isinstance(item["basicInfo"].get("attr"), dict):
                basic_attr = item["basicInfo"]["attr"]

            # 2. Kilometerstand (basicInfo.attr.ml oder attributes[mileage])
            raw_ml = basic_attr.get("ml") or attr_map.get("mileage") or item.get("mileage") or ""
            cleaned_ml = re.sub(r"[^\d]", "", str(raw_ml))
            mileage = int(cleaned_ml) if cleaned_ml else 0

            # 3. Erstzulassung (basicInfo.attr.fr oder attributes[firstRegistration])
            raw_fr = basic_attr.get("fr") or attr_map.get("firstRegistration") or ""
            year_match = re.search(r"\b(20\d\d|19\d\d)\b", str(raw_fr))
            year = int(year_match.group(1)) if year_match else 2024

            # 4. Motorleistung (basicInfo.attr.pw oder attributes[power])
            # Bsp: "478 kW (650 hp)" oder "110 kW (150 PS)"
            raw_pw = basic_attr.get("pw") or attr_map.get("power") or ""
            power_hp = 0

            hp_match = re.search(r"(\d+)\s*(?:hp|ps)", str(raw_pw), re.IGNORECASE)
            if hp_match:
                power_hp = int(hp_match.group(1))
            else:
                kw_match = re.search(r"(\d+)\s*kw", str(raw_pw), re.IGNORECASE)
                if kw_match:
                    power_hp = int(round(float(kw_match.group(1)) * 1.35962))
                else:
                    digits = re.findall(r"\d+", str(raw_pw))
                    power_hp = int(digits[0]) if digits else 150

            # 5. Kraftstoff & Getriebe
            fuel_type = str(basic_attr.get("ft") or attr_map.get("fuel") or item.get("fuel") or "Benzin")
            transmission = str(attr_map.get("gearbox") or attr_map.get("transmission") or "Automatik")

            # 6. Händler, Ort, PLZ & Distanz
            contact = item.get("contact") if isinstance(item.get("contact"), dict) else {}
            dealer_name = str(contact.get("name") or "Händler")
            postal_code = str(basic_attr.get("z") or contact.get("address2") or "97271")
            plz_match = re.search(r"\b(\d{5})\b", postal_code)
            if plz_match:
                postal_code = plz_match.group(1)

            city = str(basic_attr.get("loc") or "")
            if not city and contact.get("address2"):
                city = contact["address2"].replace(postal_code, "").replace("DE-", "").strip()
            if not city:
                city = "Würzburg"

            # Distanz via Koordinaten berechnen
            distance_km = 25.0
            lat_long = contact.get("latLong")
            if isinstance(lat_long, dict) and "lat" in lat_long and "lon" in lat_long:
                distance_km = calculate_haversine_distance(float(lat_long["lat"]), float(lat_long["lon"]))

            # 7. Ausstattungsmerkmale (features-Array + Highlights)
            features = []
            raw_feats = item.get("features") or []
            if isinstance(raw_feats, list):
                features = [str(f).strip() for f in raw_feats if str(f).strip()]

            # 8. Bild-URL aus images: [{"uri": "img.classistatic.de/..."}]
            image_url = ""
            raw_imgs = item.get("images") or []
            if isinstance(raw_imgs, list) and len(raw_imgs) > 0:
                first_img = raw_imgs[0]
                if isinstance(first_img, dict):
                    uri = first_img.get("uri") or first_img.get("url") or ""
                elif isinstance(first_img, str):
                    uri = first_img
                else:
                    uri = ""

                if uri:
                    if uri.startswith("http://") or uri.startswith("https://"):
                        image_url = uri
                    elif uri.startswith("//"):
                        image_url = f"https:{uri}"
                    else:
                        image_url = f"https://{uri}"

            # 9. Marke & Modell
            make_obj = item.get("make")
            make = make_obj.get("localized") if isinstance(make_obj, dict) else str(item.get("makeKey") or "Unbekannt")

            model_obj = item.get("model")
            model = model_obj.get("localized") if isinstance(model_obj, dict) else str(item.get("modelKey") or "Modell")

            return CarListing(
                id=None,
                external_id=ext_id,
                provider="mobile.de",
                url=url,
                title=title,
                make=make,
                model=model,
                price=price,
                mileage=mileage,
                first_registration_year=year,
                power_hp=power_hp,
                fuel_type=fuel_type,
                transmission=transmission,
                dealer_name=dealer_name,
                postal_code=postal_code,
                city=city,
                distance_km=distance_km,
                features=features,
                deal_score=0.0,
                image_url=image_url
            )
        except Exception as e:
            logger.warning(f"Konnte memo23-Inserat nicht mappen: {e}")
            return None