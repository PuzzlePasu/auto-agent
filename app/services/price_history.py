from typing import List, Dict, Any
from app.database.models import PriceRecord

class PriceHistoryService:
    """
    Berechnet Metriken zur Preisentwicklung eines Fahrzeugs.
    """
    @staticmethod
    def calculate_price_metrics(history: List[PriceRecord], current_price: float) -> Dict[str, Any]:
        if not history:
            return {
                "initial_price": current_price,
                "current_price": current_price,
                "price_drop_total": 0.0,
                "price_drop_percent": 0.0,
                "summary": "Erstpreis (noch keine Änderungen dokumentiert)"
            }

        initial_price = history[0].price
        price_drop = initial_price - current_price
        drop_percent = round((price_drop / initial_price) * 100, 1) if initial_price > 0 else 0.0

        if price_drop > 0:
            summary = f"Preis seit Beobachtungsbeginn um {int(price_drop):,} EUR gefallen (-{drop_percent}%).".replace(",", ".")
        elif price_drop < 0:
            summary = f"Preis seit Beobachtungsbeginn um {abs(int(price_drop)):,} EUR gestiegen (+{abs(drop_percent)}%).".replace(",", ".")
        else:
            summary = "Preis seit Beobachtungsbeginn stabil."

        return {
            "initial_price": initial_price,
            "current_price": current_price,
            "price_drop_total": price_drop,
            "price_drop_percent": drop_percent,
            "summary": summary
        }