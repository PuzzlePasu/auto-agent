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
    - Entfernt flüchtige Tracking- und Session-Parameter (ref, refId, ssid), die den Parser stören
    - Normalisiert Erstzulassungsparameter (z. B. '1-2024' -> '2024:')
    - Behebt Encoding-Probleme bei Ortsnamen/Umlauten im gn-Parameter
    """
    clean_url = url.strip()
    if not clean_url:
        return ""

    # 1. Hostname vereinheitlichen
    clean_url = clean_url.replace("https://m.mobile.de/", "https://suchen.mobile.de/")
    clean_url = clean_url.replace("http://m.mobile.de/", "https://suchen.mobile.de/")
    clean_url = clean_url.replace("https://mobile.de/", "https://suchen.mobile.de/")
    clean_url = clean_url.replace("http://mobile.de/", "https://suchen.mobile.de/")

    try:
        parsed = urlparse(clean_url)
        qs = parse_qs(parsed.query, keep_blank_values=True)

        # 2. Tracking- & Session-Keys entfernen, die Parser-Fehler im Actor verursachen
        volatile_keys = ["ref", "refId", "ssid", "searchId", "sorting.direction"]
        for k in volatile_keys:
            qs.pop(k, None)

        # 3. Erstzulassung formatieren: aus '1-2024' wird '2024:'
        if "fr" in qs:
            normalized_fr = []
            for val in qs["fr"]:
                cleaned_val = re.sub(r"^\d+-", "", val)
                if cleaned_val.isdigit() and ":" not in cleaned_val:
                    cleaned_val = f"{cleaned_val}:"
                normalized_fr.append(cleaned_val)
            qs["fr"] = normalized_fr

        # 4. Falls gn (Ortsname mit Umlauten/Komma) vorhanden ist, PLZ in zip auslagern
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

    def get_search_urls(self, config: Dict[str, Any]) -> List[str]:
        """
        Ermittelt die aktiven Such-URLs:
        1. Priorität: Unraid Docker-Umgebungsvariable MOBILE_SEARCH_URLS
        2. Priorität: Fallback auf config.json (search_criteria.search_page_urls)
        Alle URLs werden durch sanitize_mobile_url normalisiert.
        """
        raw_urls = []
        env_urls = os.getenv("MOBILE_SEARCH_URLS", "").strip()

        if env_urls:
            raw_urls = [
                u.strip()
                for u in env_urls.replace(";", "\n").replace(",", "\n").splitlines()
                if u.strip().startswith("http")
            ]
            if raw_urls:
                logger.info(f"ApifyProvider: {len(raw_urls)} URL(s) aus Docker-ENV (MOBILE_SEARCH_URLS) geladen.")

        if not raw_urls:
            raw_urls = config.get("search_criteria", {}).get("search_page_urls", [])
            if raw_urls:
                logger.info(f"ApifyProvider: {len(raw_urls)} URL(s) aus config.json geladen.")

        if not raw_urls:
            logger.warning("ApifyProvider: Keine mobile.de Such-URLs gefunden (weder in ENV noch in config.json).")
            return []

        # Jede URL durch den Normalisierer schicken
        sanitized_urls = []
        for u in raw_urls:
            clean = sanitize_mobile_url(u)
            if clean:
                sanitized_urls.append(clean)
                logger.debug(f"Bereinigte mobile.de URL: {clean}")

        return sanitized_urls

    def search(self, config: Dict[str, Any]) -> List[CarListing]:
        if not self.client or not self.actor_id:
            logger.error("APIFY_API_TOKEN oder APIFY_ACTOR_ID fehlt in der Umgebung.")
            return []

        urls = self.get_search_urls(config)
        if not urls:
            logger.error("Abbruch: Keine gültigen searchPageURLs für den Apify-Actor vorhanden.")
            return []

        # Exakter Payload für den mobile.de Actor
        run_input = {
            "automaticPaging": True,
            "searchCategory": "Car",
            "searchPageURLs": urls
        }

        logger.info(f"Starte Apify-Actor '{self.actor_id}' mit {len(urls)} bereinigten Such-URL(s)...")

        try:
            run = self.client.actor(self.actor_id).call(run_input=run_input)
            dataset_id = run.get("defaultDatasetId")
            if not dataset_id:
                logger.error("Apify Actor lieferte keine defaultDatasetId zurück.")
                return []

            dataset_client = self.client.dataset(dataset_id)
            listings: List[CarListing] = []

            for item in dataset_client.iterate_items():
                car = self._map_to_car_listing(item)
                if car:
                    listings.append(car)

            logger.info(f"Apify Actor erfolgreich: {len(listings)} Inserate aus Dataset extrahiert.")
            return listings

        except Exception as e:
            logger.error(f"Fehler während des Apify-Scraping-Laufs: {e}", exc_info=True)
            return []

    def _map_to_car_listing(self, item: Dict[str, Any]) -> Optional[CarListing]:
        """Mappt das vom Apify-Actor gelieferte Inserats-JSON auf das CarListing-Datenmodell."""
        try:
            ext_id = str(item.get("id") or item.get("adId") or item.get("articleId") or hash(item.get("url", "")))
            title = str(item.get("title") or f"{item.get('make', '')} {item.get('model', '')}".strip() or "Unbekanntes Fahrzeug")

            # Preis parsen
            raw_price = item.get("price") or item.get("priceGross") or item.get("priceAmount") or 0
            if isinstance(raw_price, str):
                cleaned_price = re.sub(r"[^\d.,]", "", raw_price).replace(".", "").replace(",", ".")
                price = float(cleaned_price) if cleaned_price else 0.0
            else:
                price = float(raw_price)

            # Mindest-Plausibilität: Inserate ohne Preis verwerfen
            if price <= 500:
                return None

            # Kilometerstand
            raw_mileage = item.get("mileage") or item.get("mileageInKm") or item.get("kilometers") or 0
            if isinstance(raw_mileage, str):
                cleaned_mileage = re.sub(r"[^\d]", "", raw_mileage)
                mileage = int(cleaned_mileage) if cleaned_mileage else 0
            else:
                mileage = int(raw_mileage)

            # Erstzulassung
            raw_year = item.get("firstRegistration") or item.get("year") or 2020
            if isinstance(raw_year, str):
                year_match = re.search(r"\b(19\d\d|20\d\d)\b", raw_year)
                year = int(year_match.group(1)) if year_match else 2020
            else:
                year = int(raw_year)

            # Leistung in PS
            raw_power = item.get("power") or item.get("powerHp") or item.get("hp") or 150
            if isinstance(raw_power, str):
                ps_match = re.search(r"(\d+)\s*ps", raw_power, re.IGNORECASE)
                if ps_match:
                    power_hp = int(ps_match.group(1))
                else:
                    digits = re.findall(r"\d+", raw_power)
                    power_hp = int(digits[0]) if digits else 150
            else:
                power_hp = int(raw_power)

            # Ausstattungsmerkmale extrahieren
            raw_features = item.get("features") or item.get("attributes") or item.get("equipment") or []
            if isinstance(raw_features, str):
                features = [f.strip() for f in raw_features.split(",") if f.strip()]
            elif isinstance(raw_features, list):
                features = [str(f).strip() for f in raw_features if str(f).strip()]
            else:
                features = []

            # Hersteller und Modell ableiten
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
                distance_km=float(item.get("distance") or item.get("distanceInKm") or 25.0),
                features=features,
                deal_score=0.0
            )
        except Exception as e:
            logger.warning(f"Konnte Inserat-Eintrag nicht mappen: {e}")
            return None