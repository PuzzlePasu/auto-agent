import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class PriceService:
    def __init__(self, repo=None):
        self.repo = repo

    def calculate_price_metrics(self, price_history: List[Any], current_price: float) -> Dict[str, Any]:
        """
        Berechnet Preishistorien-Kennzahlen wie Preisdifferenz, 
        Tiefstpreis, Höchstpreis und prozentuale Änderung.
        """
        if not price_history:
            return {
                "initial_price": current_price,
                "lowest_price": current_price,
                "highest_price": current_price,
                "price_drop_amount": 0.0,
                "price_drop_percent": 0.0,
                "has_dropped": False,
                "history_points": []
            }

        prices = []
        history_points = []

        for record in price_history:
            # Unterstützt sowohl ORM/Model-Objekte als auch Dictionaries oder Tupel
            if isinstance(record, dict):
                p = float(record.get("price", current_price))
                d = str(record.get("recorded_at") or record.get("created_at") or "")
            elif hasattr(record, "price"):
                p = float(record.price)
                d = str(getattr(record, "recorded_at", "") or getattr(record, "created_at", ""))
            elif isinstance(record, (list, tuple)) and len(record) >= 2:
                p = float(record[1])
                d = str(record[0])
            else:
                continue

            prices.append(p)
            history_points.append({"date": d, "price": p})

        if not prices:
            prices = [current_price]

        initial_price = prices[0]
        lowest_price = min(prices + [current_price])
        highest_price = max(prices + [current_price])
        price_drop_amount = initial_price - current_price
        price_drop_percent = round((price_drop_amount / initial_price) * 100, 1) if initial_price > 0 else 0.0

        return {
            "initial_price": initial_price,
            "lowest_price": lowest_price,
            "highest_price": highest_price,
            "price_drop_amount": max(0.0, price_drop_amount),
            "price_drop_percent": max(0.0, price_drop_percent),
            "has_dropped": price_drop_amount > 0,
            "history_points": history_points
        }