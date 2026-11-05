from typing import Dict, Any, List
from app.database.models import CarListing

class ScoringService:
    def __init__(self, weights: Dict[str, float] = None, desired_features: List[Dict[str, Any]] = None):
        self.weights = weights or {
            "market_price": 0.25, "features": 0.20, "mileage": 0.15,
            "age": 0.10, "power": 0.10, "distance": 0.10, "price_trend": 0.10
        }
        self.desired_features = desired_features or []

    def calculate_scores(self, car: CarListing, market_stats: Dict[str, Any], price_drop_total: float, days_online: int) -> Dict[str, Any]:
        sub = {}
        pros, cons = [], []

        # 1. Marktpreis (25%)
        diff_pct = market_stats.get("diff_percent", 0.0)
        sub["market_price"] = round(max(10.0, min(100.0, 80.0 - (diff_pct * 3.5))), 1)
        if market_stats.get("diff_to_median", 0) < -500:
            pros.append(f"{abs(int(market_stats['diff_to_median'])):,} EUR unter Vergleichsmedian ({abs(diff_pct)}% Ersparnis)".replace(",", "."))
        elif market_stats.get("diff_to_median", 0) > 800:
            cons.append(f"{int(market_stats['diff_to_median']):,} EUR über Vergleichsmedian".replace(",", "."))

        # 2. Ausstattung (20%)
        matched = 0
        total_tracked = max(1, len(self.desired_features))
        feats_lower = [f.lower() for f in car.features] + [car.title.lower()]
        for df in self.desired_features:
            if any(kw in text for kw in df.get("keywords", []) for text in feats_lower):
                matched += 1
        sub["features"] = round((matched / total_tracked) * 100.0, 1)
        if matched == total_tracked:
            pros.append("Alle wichtigen Wunschmerkmale vorhanden (ACC, LED, CarPlay, Sitzheizung)")
        elif matched >= 2:
            pros.append(f"{matched} von {total_tracked} Wunschmerkmalen vorhanden")
        else:
            cons.append(f"Nur {matched} von {total_tracked} Wunschmerkmalen dokumentiert")

        # 3. Laufleistung (15%)
        km = car.mileage
        sub["mileage"] = round(95.0 - (km / 35000) * 10 if km <= 35000 else (85.0 - ((km - 35000) / 25000) * 15 if km <= 60000 else max(20.0, 70.0 - ((km - 60000) / 20000) * 30)), 1)
        if km <= 45000: pros.append(f"Relativ geringe Laufleistung ({km:,} km)".replace(",", "."))
        elif km >= 70000: cons.append(f"Höhere Laufleistung ({km:,} km)".replace(",", "."))

        # 4. Alter (10%)
        age = max(0, 2026 - car.first_registration_year)
        sub["age"] = round(max(40.0, 100.0 - (age * 7.5)), 1)
        if age <= 3: pros.append(f"Junges Baujahr (EZ {car.first_registration_year})")

        # 5. Leistung (10%)
        hp = car.power_hp
        sub["power"] = round(95.0 + min(5.0, (hp - 190)) if hp >= 190 else (85.0 + ((hp - 170) / 20) * 10 if hp >= 170 else 75.0), 1)
        if hp >= 190: pros.append(f"Sportliche Motorisierung ({hp} PS)")

        # 6. Entfernung (10%)
        d = car.distance_km
        sub["distance"] = round(98.0 - (d / 25) * 8 if d <= 25 else (90.0 - ((d - 25) / 35) * 15 if d <= 60 else (75.0 - ((d - 60) / 40) * 15 if d <= 100 else max(20.0, 60.0 - ((d - 100) / 50) * 20))), 1)
        if d <= 25: pros.append(f"Sehr nah am Heimatstandort ({round(d, 1)} km)")
        elif d > 75: cons.append(f"{round(d, 1)} km vom Heimatstandort entfernt")

        # 7. Standzeit & Trend (10%)
        trend = 75.0
        if price_drop_total > 0:
            trend += min(25.0, (price_drop_total / 1000.0) * 15.0)
            pros.append(f"Preis bereits um {int(price_drop_total):,} EUR reduziert".replace(",", "."))
        elif days_online > 30:
            trend -= min(30.0, ((days_online - 30) / 10.0) * 6.0)
            cons.append(f"Bereits {days_online} Tage online ohne Preissenkung")
        sub["price_trend"] = round(max(10.0, min(100.0, trend)), 1)

        # Gesamtwert
        total = sum(sub[k] * self.weights.get(k, 0.1) for k in sub)
        return {"deal_score": round(max(0.0, min(100.0, total)), 1), "sub_scores": sub, "pros": pros, "cons": cons}