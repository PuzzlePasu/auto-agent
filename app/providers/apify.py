import os
import logging
import re
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from apify_client import ApifyClient
from app.database.models import CarListing

logger = logging.getLogger(__name__)


def sanitize_mobile_url(url: str) -> str:
    """
    Bereinigt und normalisiert mobile.de-Such-URLs für den Apify-Actor:
    - Schreibt m.mobile.de auf suchen.mobile.de um
    - Erzwingt immer den deutschen Sprachparameter &lang=de
    - Entfernt flüchtige Tracking- und Session-Parameter (ref, refId, ssid)
    - Normalisiert Erstzulassungsparameter (z. B. '2025' oder '1-2025' -> '2025:')
    - Behebt Encoding-Probleme bei Ortsnamen/Umlauten im gn-Parameter
    """
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

        # Sprache explizit auf Deutsch festlegen
        qs["lang"] = ["de"]

        # Tracking- & Session-Keys entfernen
        volatile_keys = ["ref", "refId", "ssid", "searchId", "sorting.direction"]
        for k in volatile_keys:
            qs.pop(k, None)

        # Erstzulassung formatieren: z. B. '2025' oder '1-2025' wird '2025:'
        if "fr" in qs:
            normalized_fr = []
            for val in qs["fr"]:
                cleaned_val = re.sub(r"^\d+-", "", val)
                if cleaned_val.isdigit() and ":" not in cleaned_val:
                    cleaned_val = f"{cleaned_val}:"
                normalized_fr.append(cleaned_val)
            qs["fr"] = normalized_fr

        # Falls gn vorhanden ist, PLZ in zip auslagern
        if "gn" in qs:
            gn_val = qs.pop("gn", [""])[0]
            plz_match = re.search(r"\b(\d{5})\b", gn_val)
            if plz_match and "zip" not in qs:
                qs["zip"] = [plz_match.group(1)]

        new_query = urlencode(qs, doseq=True)
        return urlunparse(parsed._replace(query=new_query))
    except Exception as e:
        logger.warning(f"Konnte URL nicht bereinigen, nutze Fallback: {e}")
        return clean_url


class ApifyProvider:
    name = "apify"

    def __init__(self):
        self.token = os.getenv("APIFY_API_TOKEN")
        self.actor_id = os.getenv("APIFY_ACTOR_ID")
        self.client = ApifyClient(self.token) if self.token else None

    def _extract_float(self, val: Any, default: float = 0.0) -> float:
        """Extrahiert robust Zahlenwerte aus verschachtelten Dicts, Strings und Zahlen."""
        if val is None:
            return default
        if isinstance(val, (int, float)):
            return float(val)
        if isinstance(val, dict):
            for key in ["amount", "gross", "value", "price", "net", "total"]:
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
            logger.error("Abbruch: Keine gültigen searchPageURLs für den Apify-Actor vorhanden.")
            return []

        run_input = {
            "automaticPaging": True,
            "searchCategory": "Car",
            "searchPageURLs": urls,
            "language": "de"
        }

        logger.info(f"Starte Apify-Actor '{self.actor_id}' mit {len(urls)} URL(s)...")

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
                if hasattr(raw_item, "model_dump"):
                    item = raw_item.model_dump()
                elif hasattr(raw_item, "dict"):
                    item = raw_item.dict()
                elif isinstance(raw_item, dict):
                    item = raw_item
                else:
                    item = dict(raw_item)

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
            ext_id = str(item.get("id") or item.get("adId") or item.get("articleId") or hash(item.get("url", "")))
            title = str(item.get("title") or f"{item.get('make', '')} {item.get('model', '')}".strip() or "Unbekanntes Fahrzeug")

            # 1. Preis
            raw_price = item.get("price") or item.get("priceGross") or item.get("priceAmount") or 0
            price = self._extract_float(raw_price, default=0.0)
            if price <= 500:
                return None

            # 2. Kilometerstand (prüft Root, specifics und attributes)
            raw_mileage = (
                item.get("mileageInKm")
                or item.get("mileage")
                or item.get("kilometers")
                or item.get("mileageValue")
            )
            if not raw_mileage and isinstance(item.get("specifics"), dict):
                raw_mileage = item["specifics"].get("mileage")
            if not raw_mileage and isinstance(item.get("attributes"), dict):
                raw_mileage = item["attributes"].get("mileage")

            if isinstance(raw_mileage, dict):
                raw_mileage = raw_mileage.get("value") or raw_mileage.get("amount") or 0
            if isinstance(raw_mileage, str):
                cleaned_m = re.sub(r"[^\d]", "", raw_mileage)
                mileage = int(cleaned_m) if cleaned_m else 0
            else:
                mileage = int(raw_mileage or 0)

            # 3. Erstzulassung (prüft Root und specifics)
            raw_year = (
                item.get("firstRegistration")
                or item.get("registrationDate")
                or item.get("firstRegistrationDate")
                or item.get("year")
            )
            if not raw_year and isinstance(item.get("specifics"), dict):
                raw_year = item["specifics"].get("firstRegistration")

            year_match = re.search(r"\b(20\d\d|19\d\d)\b", str(raw_year or ""))
            year = int(year_match.group(1)) if year_match else 2024

            # 4. Motorleistung (PS)
            raw_power = item.get("power") or item.get("powerHp") or item.get("hp") or 150
            if isinstance(raw_power, dict):
                raw_power = raw_power.get("hp") or raw_power.get("powerHp") or 150
            if isinstance(raw_power, str):
                ps_match = re.search(r"(\d+)\s*ps", raw_power, re.IGNORECASE)
                if ps_match:
                    power_hp = int(ps_match.group(1))
                else:
                    digits = re.findall(r"\d+", raw_power)
                    power_hp = int(digits[0]) if digits else 150
            else:
                power_hp = int(raw_power or 150)

            # 5. Distanz
            raw_dist = item.get("distance") or item.get("distanceInKm") or 25.0
            distance_km = self._extract_float(raw_dist, default=25.0)

            # 6. Ausstattungsmerkmale (flacht Strings, Listen und Dictionaries ab)
            raw_features = item.get("features") or item.get("attributes") or item.get("equipment") or []
            features = []
            if isinstance(raw_features, str):
                features = [f.strip() for f in raw_features.split(",") if f.strip()]
            elif isinstance(raw_features, list):
                for f in raw_features:
                    if isinstance(f, str) and f.strip():
                        features.append(f.strip())
                    elif isinstance(f, dict):
                        val = f.get("label") or f.get("name") or f.get("value")
                        if val:
                            features.append(str(val).strip())

            # 7. Bild-URL (durchsucht alle gängigen Apify-/Mobile.de-Felder)
            image_url = ""
            img_candidates = [
                item.get("images"),
                item.get("imageUrls"),
                item.get("photos"),
                item.get("gallery"),
                item.get("media", {}).get("images") if isinstance(item.get("media"), dict) else None,
                item.get("thumbnail"),
                item.get("imageUrl"),
                item.get("image")
            ]

            for cand in img_candidates:
                if not cand:
                    continue
                if isinstance(cand, list) and len(cand) > 0:
                    first = cand[0]
                    if isinstance(first, str) and first.startswith("http"):
                        image_url = first
                        break
                    elif isinstance(first, dict):
                        image_url = first.get("url") or first.get("src") or first.get("uri") or ""
                        if image_url:
                            break
                elif isinstance(cand, str) and (cand.startswith("http") or cand.startswith("//")):
                    image_url = cand
                    break

            if image_url and image_url.startswith("//"):
                image_url = f"https:{image_url}"

            # 8. Marke und Modell
            make = item.get("make")
            model = item.get("model")
            if not make:
                parts = title.split()
                make = parts[0] if parts else "Unbekannt"
                model = " ".join(parts[1:3]) if len(parts) > 1 else "Unbekannt"
            elif not model:
                model = title.replace(make, "").strip() or "Modell"

            url = item.get("url") or item.get("adUrl") or item.get("link") or ""

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
                fuel_type=str(item.get("fuel") or item.get("fuelType") or "Benzin"),
                transmission=str(item.get("transmission") or "Automatik"),
                dealer_name=str(item.get("dealerName") or item.get("seller") or "Händler"),
                postal_code=str(item.get("postalCode") or item.get("zip") or "97271"),
                city=str(item.get("city") or item.get("location") or "Würzburg"),
                distance_km=distance_km,
                features=features,
                deal_score=0.0,
                image_url=image_url
            )
        except Exception as e:
            logger.warning(f"Konnte Inserat-Eintrag nicht mappen: {e}")
            return None