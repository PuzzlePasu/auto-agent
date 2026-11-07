import os
import json
import logging
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

from app.database.repository import DatabaseRepository
from app.database.models import CarListing, SearchLog
from app.providers.demo import DemoProvider
from app.providers.apify import ApifyProvider

logger = logging.getLogger(__name__)


class PriceService:
    @staticmethod
    def calculate_price_metrics(price_history: list, current_price: float) -> dict:
        if not price_history or len(price_history) <= 1:
            return {
                "initial_price": current_price,
                "current_price": current_price,
                "price_drop_total": 0.0,
                "price_drop_percent": 0.0,
                "changes_count": 0,
                "summary": "Bisher stabiler Preis"
            }

        initial_price = price_history[0].price
        drop = initial_price - current_price
        drop_pct = round((drop / initial_price) * 100, 1) if initial_price > 0 else 0.0

        if drop > 0:
            summary = f"Preissenkung: -{int(drop):,} € (-{drop_pct}%) seit Erstbeobachtung".replace(",", ".")
        elif drop < 0:
            summary = f"Preiserhöhung: +{int(abs(drop)):,} € seit Erstbeobachtung".replace(",", ".")
        else:
            summary = f"{len(price_history) - 1} Preisanpassungen dokumentiert"

        return {
            "initial_price": initial_price,
            "current_price": current_price,
            "price_drop_total": drop,
            "price_drop_percent": drop_pct,
            "changes_count": len(price_history) - 1,
            "summary": summary
        }


class SearchService:
    def __init__(self, repo: DatabaseRepository, config_path: Optional[Path] = None):
        self.repo = repo
        self.config_path = config_path or (Path(__file__).resolve().parent.parent.parent / "config.json")
        self.price_service = PriceService()

    def load_config(self) -> Dict[str, Any]:
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Fehler beim Lesen der config.json: {e}")
        return {}

    def get_active_provider(self):
        mode = os.getenv("PROVIDER_MODE", "demo").strip().lower()
        if mode == "apify":
            return ApifyProvider()
        return DemoProvider()

    @staticmethod
    def _matches_alias(term: str, target_text: str) -> bool:
        """
        Prüft robust, ob ein Alias im Text vorkommt:
        - Kurze Kürzel (z.B. ACC, HUD, DCC) verlangen strikte Wortgrenzen (\b).
        - Begriffe mit Sonderzeichen (z.B. 'iq.light', 'stop&go') werden sauber maskiert.
        """
        clean_term = term.strip().lower()
        if not clean_term:
            return False

        if len(clean_term) <= 4 and clean_term.isalnum():
            pattern = rf"\b{re.escape(clean_term)}\b"
        else:
            pattern = rf"(?<![a-z0-9]){re.escape(clean_term)}(?![a-z0-9])"

        return bool(re.search(pattern, target_text, re.IGNORECASE))

    def run_search_pipeline(self):
        start_time = datetime.utcnow()
        config = self.load_config()
        provider = self.get_active_provider()

        logger.info(f"Starte Auto-Agent Suchlauf mit: {provider.name}")

        try:
            raw_listings = provider.search(config)
        except Exception as e:
            logger.error(f"Fehler beim Aufruf des Providers {provider.name}: {e}", exc_info=True)
            raw_listings = []

        logger.info(f"Provider {provider.name} lieferte {len(raw_listings)} Roh-Inserate.")

        # 1. Strikte Filterung anwenden
        filtered_listings = self._filter_listings(raw_listings, config)
        logger.info(
            f"{len(filtered_listings)} von {len(raw_listings)} Inseraten entsprechen allen Kriterien "
            f"(Benziner, kein Hybrid, kein Weiß, Händler)."
        )

        # 2. Markt-Median & Metriken berechnen
        median_price, mean_price = self._calculate_market_metrics(filtered_listings)

        # 3. Scoring & Merkmals-Normalisierung
        scored_listings = []
        for car in filtered_listings:
            self._score_car(car, median_price, mean_price, config)
            scored_listings.append(car)

        # 4. Dubletten-Erkennung
        self._detect_duplicates(scored_listings)

        # 5. Speichern & Preishistorie pflegen
        new_found = 0
        price_changes = 0
        duplicates_detected = 0
        seen_external_ids = set()

        for car in scored_listings:
            seen_external_ids.add((car.provider, car.external_id))
            if car.duplicate_info:
                duplicates_detected += 1

            existing = self.repo.get_car_by_external_id(car.provider, car.external_id)
            if existing is None:
                car.first_seen = start_time.strftime("%Y-%m-%d %H:%M:%S")
                car.last_seen = start_time.strftime("%Y-%m-%d %H:%M:%S")
                car.is_active = True
                car.consecutive_missing_runs = 0
                self.repo.save_car(car)
                new_found += 1
            else:
                car.id = existing.id
                car.first_seen = existing.first_seen
                car.last_seen = start_time.strftime("%Y-%m-%d %H:%M:%S")
                car.is_active = True
                car.consecutive_missing_runs = 0
                car.is_favorite = existing.is_favorite

                if abs(existing.price - car.price) > 1.0:
                    self.repo.add_price_record(car.id, car.price, car.last_seen)
                    price_changes += 1

                self.repo.save_car(car)

        # 6. Verschwundene Inserate erfassen
        deactivated_count = self._handle_missing_listings(seen_external_ids, config)

        end_time = datetime.utcnow()
        logger.info(
            f"Suchlauf beendet: {len(scored_listings)} valide Treffer, "
            f"{new_found} neu, {price_changes} Preisänderungen, {duplicates_detected} Dubletten."
        )

        # 7. Suchlauf protokollieren
        log = SearchLog(
            id=None,
            start_time=start_time.strftime("%Y-%m-%d %H:%M:%S"),
            end_time=end_time.strftime("%Y-%m-%d %H:%M:%S"),
            provider=provider.name,
            total_found=len(scored_listings),
            new_found=new_found,
            price_changes=price_changes,
            duplicates_detected=duplicates_detected,
            deactivated_count=deactivated_count,
            errors=""
        )
        self.repo.log_search_run(log)

    def rescore_all_listings(self) -> int:
        """
        Lädt die aktuelle config.json und bewertet alle aktiven Fahrzeuge in der
        SQLite-Datenbank neu, ohne externe Scraper oder APIs aufzurufen.
        """
        config = self.load_config()
        all_active_cars = self.repo.get_all_cars(only_active=True, canonical_only=False)

        if not all_active_cars:
            logger.info("Keine aktiven Fahrzeuge zum Neubewerten vorhanden.")
            return 0

        median_price, mean_price = self._calculate_market_metrics(all_active_cars)

        for car in all_active_cars:
            self._score_car(car, median_price, mean_price, config)
            self.repo.save_car(car)

        logger.info(f"{len(all_active_cars)} Fahrzeuge mit neuen Kriterien erfolgreich neu bewertet.")
        return len(all_active_cars)

    def _filter_listings(self, listings: List[CarListing], config: Dict[str, Any]) -> List[CarListing]:
        filters = config.get("search_criteria", {}).get("filters", {})
        max_price = filters.get("max_price", 27000)
        max_mileage = filters.get("max_mileage", 80000)
        min_year = filters.get("min_year", 2020)
        min_power = filters.get("min_power_hp", 150)
        max_power = filters.get("max_power_hp", 200)
        dealer_only = filters.get("dealer_only", True)
        exclude_hybrids = filters.get("exclude_hybrids", True)
        excluded_colors = [c.lower() for c in filters.get("exclude_colors", [])]

        valid = []
        hybrid_keywords = ["hybrid", "mhev", "mild-hybrid", "mild hybrid", "phev", "plug-in", "48v", "etsi", "gte"]

        for car in listings:
            # 1. Budget & Fahrleistung
            if car.price > max_price or car.price <= 1000:
                continue
            if car.mileage > max_mileage:
                continue
            if car.first_registration_year < min_year:
                continue
            if not (min_power <= car.power_hp <= max_power):
                continue

            # 2. Reiner Benziner (keine Hybride mit Regex-Wortgrenzen)
            full_text = f"{car.title} {car.fuel_type} {' '.join(car.features)}".lower()
            if exclude_hybrids and any(self._matches_alias(hk, full_text) for hk in hybrid_keywords):
                continue
            if "benzin" not in car.fuel_type.lower() and "petrol" not in car.fuel_type.lower():
                continue

            # 3. Weiß ausschließen
            if any(self._matches_alias(ec, full_text) for ec in excluded_colors):
                continue

            # 4. Nur Händlerangebote
            if dealer_only:
                seller = (car.dealer_name or "").lower()
                if "privat" in seller or seller == "":
                    continue

            valid.append(car)

        return valid

    def _calculate_market_metrics(self, listings: List[CarListing]) -> tuple:
        if not listings:
            return 24500.0, 24500.0
        prices = sorted([c.price for c in listings])
        n = len(prices)
        median = (prices[n // 2] if n % 2 != 0 else (prices[n // 2 - 1] + prices[n // 2]) / 2)
        mean = sum(prices) / n
        return float(median), float(mean)

    def _score_car(self, car: CarListing, median_price: float, mean_price: float, config: Dict[str, Any]):
        weights = config.get("scoring_weights", {})
        rules = config.get("scoring_rules", {})
        aliases = rules.get("feature_aliases", {})
        preferred_colors = [c.lower() for c in rules.get("preferred_colors", ["blau", "rot"])]

        # A) Ausstattungs-Score via Regex-Wortgrenzen
        combined_text = f"{car.title} {' '.join(car.features)}".lower()
        matched_features = []

        for std_name, syn_list in aliases.items():
            checks = [std_name] + syn_list
            if any(self._matches_alias(term, combined_text) for term in checks):
                matched_features.append(std_name)

        car.features = matched_features
        total_wanted = max(1, len(aliases))
        score_features = round((len(matched_features) / total_wanted) * 100.0, 1)

        # B) Marktpreis-Score (Verhältnis zum Median)
        diff_median = car.price - median_price
        diff_pct = round((diff_median / median_price) * 100, 1)
        score_market = max(0.0, min(100.0, 50.0 - (diff_pct * 3.0)))

        # C) Laufleistungs-Score
        score_mileage = max(0.0, min(100.0, 100.0 - (car.mileage / 800.0)))

        # D) Spritverbrauchs-Score
        cons_match = re.search(r"(\d+[.,]\d+)\s*(l|liter)", combined_text)
        cons_val = float(cons_match.group(1).replace(",", ".")) if cons_match else rules.get("target_consumption_l100km", 6.2)
        score_consumption = max(0.0, min(100.0, 100.0 - ((cons_val - 5.5) * 35.0)))

        # E) Alters-Score (Baujahr)
        age_years = max(0, datetime.utcnow().year - car.first_registration_year)
        score_age = max(0.0, min(100.0, 100.0 - (age_years * 18.0)))

        # F) Motorleistung
        score_power = max(0.0, min(100.0, ((car.power_hp - 150) / 50.0) * 100.0))

        # G) Farb-Präferenz
        is_fav_color = any(self._matches_alias(fc, combined_text) for fc in preferred_colors)
        score_color = 100.0 if is_fav_color else 40.0

        # H) Distanz-Score
        score_distance = max(0.0, min(100.0, 100.0 - (car.distance_km * 0.8)))

        # Gesamt-Deal-Score gewichten
        total_score = (
            score_features * weights.get("features", 0.23) +
            score_market * weights.get("market_price", 0.22) +
            score_mileage * weights.get("mileage", 0.15) +
            score_consumption * weights.get("consumption", 0.10) +
            score_distance * weights.get("distance", 0.10) +
            score_age * weights.get("age", 0.08) +
            score_power * weights.get("power", 0.07) +
            score_color * weights.get("color_preference", 0.05)
        )

        car.deal_score = round(max(0.0, min(100.0, total_score)), 1)
        car.sub_scores = {
            "features": round(score_features, 1),
            "market_price": round(score_market, 1),
            "mileage": round(score_mileage, 1),
            "consumption": round(score_consumption, 1),
            "distance": round(score_distance, 1),
            "age": round(score_age, 1),
            "power": round(score_power, 1),
            "color_preference": round(score_color, 1)
        }

        # Markt-Statistiken aufbereiten
        summary_text = (
            f"Liegt {abs(int(diff_median)):,} € unter dem Median ({abs(diff_pct)}% Ersparnis)"
            if diff_median < 0 else
            f"Liegt {int(diff_median):,} € über dem Median (+{diff_pct}%)"
        ).replace(",", ".")

        car.market_stats = {
            "median_price": median_price,
            "mean_price": round(mean_price, 2),
            "diff_to_median": round(diff_median, 2),
            "diff_percent": diff_pct,
            "peer_count": len([c for c in [car]]),
            "summary": summary_text
        }

        # Pros & Cons generieren
        pros, cons = [], []
        if diff_median <= -1000:
            pros.append(f"Hervorragender Preis ({abs(int(diff_median)):,} € unter Marktwert)".replace(",", "."))
        if is_fav_color:
            pros.append("Bevorzugte Wunschlackierung (Blau / Rot)")
        if "Matrix LED-Scheinwerfer" in matched_features:
            pros.append("Matrix LED / Adaptives Licht vorhanden")
        if "Massagesitz / ErgoActive" in matched_features:
            pros.append("Ergonomie-/Massagesitz verbaut")
        if "ACC / adaptiver Tempomat" in matched_features:
            pros.append("Abstandstempomat / Travel Assist an Bord")
        if car.mileage < 40000:
            pros.append(f"Geringe Gesamtlaufleistung ({car.mileage:,} km)".replace(",", "."))
        if car.distance_km < 30:
            pros.append(f"Kurze Anfahrt ({round(car.distance_km, 1)} km)")

        if diff_median > 1000:
            cons.append(f"Höherer Preis (+{int(diff_median):,} € über Median)".replace(",", "."))
        if car.distance_km > 75:
            cons.append(f"Längere Anfahrt ({round(car.distance_km, 1)} km)")
        if "Head-Up Display" not in matched_features:
            cons.append("Kein Head-Up Display dokumentiert")
        if not is_fav_color:
            cons.append("Standardlackierung (nicht Blau/Rot)")

        car.pros = pros if pros else ["Solide Gesamtausstattung"]
        car.cons = cons if cons else ["Keine relevanten Mängel"]

    def _detect_duplicates(self, listings: List[CarListing]):
        """Erkennt identische Fahrzeuge auf mehreren Plattformen (z.B. mobile.de & AutoScout24)."""
        n = len(listings)
        for i in range(n):
            for j in range(i + 1, n):
                c1, c2 = listings[i], listings[j]
                if c1.make.lower() == c2.make.lower() and c1.model.lower() == c2.model.lower():
                    same_specs = (
                        c1.power_hp == c2.power_hp and
                        abs(c1.mileage - c2.mileage) <= 50 and
                        c1.first_registration_year == c2.first_registration_year and
                        c1.postal_code == c2.postal_code
                    )
                    if same_specs:
                        cheaper, expensive = (c1, c2) if c1.price <= c2.price else (c2, c1)
                        expensive.canonical_id = cheaper.id
                        diff = expensive.price - cheaper.price
                        expensive.duplicate_info = {
                            "is_duplicate": True,
                            "original_provider": cheaper.provider,
                            "price_diff": diff,
                            "message": f"Auch auf {cheaper.provider} gefunden (-{int(diff)} €)"
                        }

    def _handle_missing_listings(self, seen_ids: set, config: Dict[str, Any]) -> int:
        threshold = config.get("scoring_rules", {}).get("inactivity_threshold_runs", 3)
        all_cars = self.repo.get_all_cars(only_active=True, canonical_only=False)
        deactivated = 0

        for car in all_cars:
            if (car.provider, car.external_id) not in seen_ids:
                car.consecutive_missing_runs += 1
                if car.consecutive_missing_runs >= threshold:
                    car.is_active = False
                    deactivated += 1
                self.repo.save_car(car)

        return deactivated