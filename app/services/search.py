import logging
import json
from pathlib import Path
from typing import List, Dict, Any, Optional

from app.database.models import CarListing
from app.database.repository import DatabaseRepository
from app.services.scoring import ScoringService
from app.services.price import PriceService
from app.providers.apify import ApifyProvider

logger = logging.getLogger(__name__)


class SearchService:
    def __init__(self, repo: Optional[DatabaseRepository] = None):
        self.repo = repo or DatabaseRepository()
        self.scoring_service = ScoringService()
        self.price_service = PriceService(self.repo)
        self.config_path = Path(__file__).resolve().parent.parent.parent / "config.json"

    def load_config(self) -> Dict[str, Any]:
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Fehler beim Laden von config.json: {e}")
        return {}

    def run_search_pipeline(self) -> Dict[str, Any]:
        """Führt den kompletten Scraping- und Bewertungs-Workflow aus."""
        config = self.load_config()
        provider = ApifyProvider()

        logger.info("Starte Scraping-Pipeline via Apify...")
        raw_listings = provider.search(config)
        logger.info(f"Provider apify lieferte {len(raw_listings)} Roh-Inserate.")

        # 1:1 Übernahme ohne lokale Filter
        filtered_listings = self._filter_listings(raw_listings, config)

        new_count = 0
        price_change_count = 0
        duplicate_count = 0

        # Scoring & Speichern
        scoring_weights = config.get("scoring_weights", {})
        scoring_rules = config.get("scoring_rules", {})

        for car in filtered_listings:
            # Score berechnen (Ausstattung, Preis, etc.)
            car.deal_score = self.scoring_service.calculate_deal_score(
                car, scoring_weights, scoring_rules
            )

            # In Datenbank persistieren
            status = self.repo.save_or_update_car(car)
            if status == "new":
                new_count += 1
            elif status == "price_changed":
                price_change_count += 1
            else:
                duplicate_count += 1

        # Inaktive Fahrzeuge markieren, die in diesem Lauf nicht mehr auftauchten
        inactivity_threshold = scoring_rules.get("inactivity_threshold_runs", 3)
        self.repo.mark_missing_cars(current_listings=filtered_listings, threshold_runs=inactivity_threshold)

        result_summary = {
            "total_fetched": len(raw_listings),
            "valid": len(filtered_listings),
            "new": new_count,
            "price_changes": price_change_count,
            "duplicates": duplicate_count
        }

        logger.info(
            f"Suchlauf beendet: {result_summary['valid']} valide Treffer, "
            f"{result_summary['new']} neu, {result_summary['price_changes']} Preisänderungen, "
            f"{result_summary['duplicates']} Dubletten/unverändert."
        )

        return result_summary

    def _filter_listings(self, listings: List[CarListing], config: Dict[str, Any]) -> List[CarListing]:
        """Übernimmt alle Inserate direkt ohne lokale Ausschlusskriterien."""
        valid_listings = [car for car in listings if car and car.price > 500]
        logger.info(f"{len(valid_listings)} von {len(listings)} Inseraten übernommen (Filterung erfolgt rein über mobile.de URL).")
        return valid_listings

    def rescore_all_listings(self) -> int:
        """Berechnet alle Deals in der Datenbank mit den aktuellen Gewichten neu."""
        config = self.load_config()
        scoring_weights = config.get("scoring_weights", {})
        scoring_rules = config.get("scoring_rules", {})

        all_cars = self.repo.get_all_cars(only_active=False, canonical_only=False)
        updated_count = 0

        for car in all_cars:
            new_score = self.scoring_service.calculate_deal_score(
                car, scoring_weights, scoring_rules
            )
            if car.deal_score != new_score:
                car.deal_score = new_score
                self.repo.update_deal_score(car.id, new_score)
                updated_count += 1

        logger.info(f"Re-Scoring abgeschlossen: {updated_count} Fahrzeuge neu berechnet.")
        return updated_count