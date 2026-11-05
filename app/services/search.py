import json
import logging
import os
from datetime import datetime
from app.database.repository import DatabaseRepository
from app.database.models import SearchLog
from app.providers.apify import ApifyProvider
from app.providers.demo import DemoProvider
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

    def run_search_pipeline(self) -> SearchLog:
        with open(self.config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
            
        start_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        mode = os.getenv("PROVIDER_MODE", "demo").lower()
        provider = ApifyProvider() if mode == "apify" else DemoProvider()
        
        raw_cars = provider.search(config)
        new_cnt, price_change_cnt = 0, 0
        seen_keys = set()

        for c in raw_cars:
            seen_keys.add((c.provider, c.external_id))
            existing = self.repo.get_car_by_external_id(c.provider, c.external_id)
            if not existing:
                c.id = self.repo.save_car(c)
                new_cnt += 1
            else:
                c.id = existing.id
                c.first_seen = existing.first_seen
                c.is_favorite = existing.is_favorite
                if abs(existing.price - c.price) >= 1.0:
                    self.repo.add_price_record(c.id, c.price)
                    price_change_cnt += 1
                    if existing.price - c.price >= 500:
                        self.notif.notify_top_deal(c, reason=f"PREISREDUZIERUNG (-{int(existing.price - c.price)} €)")
                self.repo.save_car(c)

        # Verschwundene Inserate erfassen
        deact_cnt = 0
        for car in self.repo.get_all_cars(only_active=True, canonical_only=False):
            if (car.provider, car.external_id) not in seen_keys:
                car.consecutive_missing_runs += 1
                if car.consecutive_missing_runs >= config.get("rules", {}).get("inactivity_threshold_runs", 3):
                    car.is_active = False
                    deact_cnt += 1
                self.repo.save_car(car)

        # Dubletten & Deal-Score aktualisieren
        active_cars = self.repo.get_all_cars(only_active=True, canonical_only=False)
        _, dup_cnt = self.dedup.deduplicate(active_cars)
        scorer = ScoringService(config.get("scoring_weights"), config.get("search_criteria", {}).get("desired_features"))

        for car in active_cars:
            history = self.repo.get_price_history(car.id)
            metrics = self.price_service.calculate_price_metrics(history, car.price)
            f_dt = datetime.strptime(car.first_seen, "%Y-%m-%d %H:%M:%S")
            days = max(1, (datetime.utcnow() - f_dt).days)
            m_stats = self.market.analyze_car(car, active_cars)
            car.market_stats = m_stats

            res = scorer.calculate_scores(car, m_stats, metrics["price_drop_total"], days)
            car.deal_score, car.sub_scores, car.pros, car.cons = res["deal_score"], res["sub_scores"], res["pros"], res["cons"]
            self.repo.save_car(car)

            if car.deal_score >= 90 and days <= 1:
                self.notif.notify_top_deal(car, reason="TOP DEAL")

        log = SearchLog(
            start_time=start_time, end_time=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            provider=provider.name, total_found=len(raw_cars), new_found=new_cnt,
            price_changes=price_change_cnt, duplicates_detected=dup_cnt, deactivated_count=deact_cnt
        )
        self.repo.log_search_run(log)
        return log