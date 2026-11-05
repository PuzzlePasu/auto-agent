import statistics
from typing import List, Dict, Any
from app.database.models import CarListing

class MarketAnalysisService:
    def analyze_car(self, target: CarListing, universe: List[CarListing]) -> Dict[str, Any]:
        peers = [
            c for c in universe 
            if c.model.lower() == target.model.lower() and abs(c.first_registration_year - target.first_registration_year) <= 1
        ] or [c for c in universe if c.model.lower() == target.model.lower()] or universe

        prices = [p.price for p in peers if p.price > 0]
        if not prices:
            return {"peer_count": 0, "median_price": target.price, "diff_to_median": 0.0, "diff_percent": 0.0, "summary": "Keine Peers"}

        med = statistics.median(prices)
        mean = statistics.mean(prices)
        diff = round(target.price - med, 2)
        pct = round((diff / med) * 100, 1)

        summary = f"{abs(int(diff)):,} EUR ({abs(pct)}%) unter dem Marktmedian von {int(med):,} EUR.".replace(",", ".") if diff < 0 else (
            f"{int(diff):,} EUR ({pct}%) über dem Marktmedian von {int(med):,} EUR.".replace(",", ".") if diff > 0 else f"Exakt auf Marktniveau ({int(med):,} EUR)."
        )

        return {
            "peer_count": len(peers),
            "median_price": round(med, 2),
            "mean_price": round(mean, 2),
            "diff_to_median": diff,
            "diff_percent": pct,
            "summary": summary
        }