import json
import logging
import os
from datetime import datetime
from typing import List, Dict, Any

from app.database.repository import DatabaseRepository
from app.database.models import CarListing, SearchLog
from app.providers.apify import ApifyProvider
from app.providers.demo import DemoProvider
from app.providers.mobile_de import MobileDeProvider
from app.providers.autoscout24 import AutoScout24Provider
from app.services.deduplication import DeduplicationService
from app.services.market_analysis import MarketAnalysisService
from app.services.scoring import ScoringService
from app.services.price_history import PriceHistoryService
from app.services.notifications import NotificationService

logger = logging.getLogger(__name__)

class SearchService:
    def __init__(self, repo: DatabaseRepository, config_path: str = "config.json"):
        self.repo = repo
        self.config_path = config_path
        self.dedup = DeduplicationService()
        self.market = MarketAnalysisService()
        self.price_service = PriceHistoryService()
        self.notif = NotificationService()

    def load_config(self) -> Dict[str, Any]:
        if os.path.exists(self.config_path):
            with open(self.config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def get_providers(self) -> list:
        mode = os.getenv("PROVIDER_MODE", "demo").lower()
        if mode == "apify":
            return [ApifyProvider()]
        elif mode == "live_direct":
            return [MobileDeProvider(), AutoScout24Provider()]
        return [DemoProvider()]

    def is_car_acceptable(self, car: CarListing, filters: Dict[str, Any]) -> bool:
        """
        Prüft strikte Ausschlusskriterien:
        - Reiner Benziner (kein Diesel, kein Gas/Elektro)
        - Kein Hybrid (MHEV, PHEV, eTSI, GTE, Plug-in etc.)
        - Keine Privatverkäufe
        - Keine weißen Fahrzeuge
        """
        all_text = f"{car.title} {' '.join(car.features)} {car.dealer_name} {car.fuel_type}".lower()

        # 1. Kraftstoffprüfung
        expected_fuel = filters.get("fuel_type", "Benzin").lower()
        if expected_fuel not in car.fuel_type.lower() and expected_fuel not in all_text:
            return False

        # 2. Hybrid-Ausschluss
        if filters.get("exclude_hybrids", True):
            hybrid_keywords = filters.get("hybrid_negative_keywords", [
                "hybrid", "mhev", "phev", "plug-in", "plugin", "e-hybrid", "gte", "etsi"
            ])
            if any(kw.lower() in all_text for kw in hybrid_keywords):
                logger.info(f"Fahrzeug {car.title} verworfen: Hybrid/eTSI erkannt.")
                return False

        # 3. Keine Privatverkäufe
        if filters.get("exclude_private_sellers", True):
            dealer_lower = (car.dealer_name or "").lower()
            if not dealer_lower or "privat" in dealer_lower or "private" in dealer_lower:
                logger.info(f"Fahrzeug {car.title} verworfen: Privatverkauf.")
                return False

        # 4. Ausschluss weißer Fahrzeuge
        excluded_colors = filters.get("exclude_colors", ["weiß", "weiss", "white", "oryxweiß", "alpinweiß"])
        if any(c.lower() in all_text for c in excluded_colors):
            logger.info(f"Fahrzeug {car.title} verworfen: Weißer Lack.")
            return False

        return True

    def run_search_pipeline(self) -> SearchLog:
        config = self.load_config()
        criteria = config.get("search_criteria", {})
        filters = criteria.get("filters", {})

        start_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        providers = self.get_providers()
        provider_names = ", ".join([p.name for p in providers])

        logger.info(f"Starte Auto-Agent Suchlauf mit: {provider_names}")

        all_raw: List[CarListing] = []
        errors: List[str] = []

        for p in providers:
            try:
                res = p.search(config)
                all_raw.extend(res)
                logger.info(f"Provider {p.name} lieferte {len(res)} Roh-Inserate.")
            except Exception as e:
                err = f"Fehler bei {p.name}: {str(e)}"
                logger.error(err)
                errors.append(err)

        # ---------------------------------------------------------
        # Strikte Filterung anwenden
        # ---------------------------------------------------------
        filtered_listings = [c for c in all_raw if self.is_car_acceptable(c, filters)]
        logger.info(f"{len(filtered_listings)} von {len(all_raw)} Inseraten entsprechen allen Kriterien (Benziner, kein Hybrid, kein Weiß, Händler).")

        new_count = 0
        price_change_count = 0
        current_run_keys = set()

        for item in filtered_listings:
            current_run_keys.add((item.provider, item.external_id))
            existing = self.repo.get_car_by_external_id(item.provider, item.external_id)

            if not existing:
                item.id = self.repo.save_car(item)
                new_count += 1
            else:
                item.id = existing.id
                item.first_seen = existing.first_seen
                item.is_favorite = existing.is_favorite
                item.consecutive_missing_runs = 0
                item.is_active = True

                # Preisänderung protokollieren
                if abs(existing.price - item.price) >= 1.0:
                    self.repo.add_price_record(existing.id, item.price)
                    price_change_count += 1
                    drop_thresh = config.get("rules", {}).get("notification_price_drop_threshold", 500)
                    if existing.price - item.price >= drop_thresh:
                        self.notif.notify_top_deal(item, reason=f"PREISREDUZIERUNG (-{int(existing.price - item.price)} EUR)")

                self.repo.save_car(item)

        # ---------------------------------------------------------
        # Inaktivitätsprüfung für verschwundene Inserate
        # ---------------------------------------------------------
        threshold = config.get("rules", {}).get("inactivity_threshold_runs", 3)
        deactivated_count = 0
        all_active_db = self.repo.get_all_cars(only_active=True, canonical_only=False)

        for car in all_active_db:
            if (car.provider, car.external_id) not in current_run_keys:
                car.consecutive_missing_runs += 1
                if car.consecutive_missing_runs >= threshold:
                    car.is_active = False
                    deactivated_count += 1
                    logger.info(f"Fahrzeug #{car.id} ({car.title}) nach {car.consecutive_missing_runs} fehlenden Läufen deaktiviert.")
                self.repo.save_car(car)

        # ---------------------------------------------------------
        # Dublettenerkennung & Deal-Score Berechnung
        # ---------------------------------------------------------
        active_cars = self.repo.get_all_cars(only_active=True, canonical_only=False)
        _, dup_count = self.dedup.deduplicate(active_cars)
        scorer = ScoringService(config=config)

        for car in active_cars:
            history = self.repo.get_price_history(car.id)
            metrics = self.price_service.calculate_price_metrics(history, car.price)

            first_dt = datetime.strptime(car.first_seen, "%Y-%m-%d %H:%M:%S") if car.first_seen else datetime.utcnow()
            days_online = max(1, (datetime.utcnow() - first_dt).days)

            market_stats = self.market.analyze_car(car, active_cars)
            car.market_stats = market_stats

            scoring_res = scorer.calculate_scores(
                car=car,
                market_stats=market_stats,
                price_drop_total=metrics["price_drop_total"],
                days_online=days_online
            )

            car.deal_score = scoring_res["deal_score"]
            car.sub_scores = scoring_res["sub_scores"]
            car.pros = scoring_res["pros"]
            car.cons = scoring_res["cons"]

            self.repo.save_car(car)

            score_thresh = config.get("rules", {}).get("notification_deal_score_threshold", 90)
            if car.deal_score >= score_thresh and days_online <= 1:
                self.notif.notify_top_deal(car, reason=f"TOP DEAL ({car.deal_score}/100)")

        end_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = SearchLog(
            start_time=start_time,
            end_time=end_time,
            provider=provider_names,
            total_found=len(filtered_listings),
            new_found=new_count,
            price_changes=price_change_count,
            duplicates_detected=dup_count,
            deactivated_count=deactivated_count,
            errors="; ".join(errors)
        )
        self.repo.log_search_run(log_entry)
        logger.info(f"Suchlauf beendet: {len(filtered_listings)} valide Treffer, {new_count} neu, {price_change_count} Preisänderungen, {dup_count} Dubletten.")
        return log_entry