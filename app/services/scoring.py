import re
from typing import Dict, Any, List
from app.database.models import CarListing

class ScoringService:
    """
    Transparente mathematische Deal-Score Engine (0 - 100).
    Berücksichtigt Marktpreis, Ausstattung (Kern & Bonus), Verbrauch,
    Farbe (Blau/Rot-Präferenz), Laufleistung, Alter, Leistung, Distanz und Trend.
    """
    def __init__(self, config: Dict[str, Any] = None):
        cfg = config or {}
        criteria = cfg.get("search_criteria", {})
        self.weights = cfg.get("scoring_weights", {
            "market_price": 0.22,
            "features": 0.23,
            "consumption": 0.10,
            "color_preference": 0.05,
            "mileage": 0.15,
            "age": 0.08,
            "power": 0.07,
            "distance": 0.05,
            "price_trend": 0.05
        })
        self.desired_features = criteria.get("desired_features", [])
        self.preferred_colors = criteria.get("filters", {}).get("preferred_colors", ["blau", "rot", "blue", "red"])
        self.target_consumption = criteria.get("fuel_consumption", {}).get("target_l_100km", 6.8)
        self.max_consumption = criteria.get("fuel_consumption", {}).get("max_combined_l_100km", 7.5)

    def calculate_scores(
        self,
        car: CarListing,
        market_stats: Dict[str, Any],
        price_drop_total: float,
        days_online: int
    ) -> Dict[str, Any]:
        sub_scores: Dict[str, float] = {}
        pros: List[str] = []
        cons: List[str] = []

        all_text = f"{car.title} {' '.join(car.features)} {car.dealer_name}".lower()

        # ---------------------------------------------------------
        # 1. Marktpreis / Deal-Sub-Score (22%)
        # ---------------------------------------------------------
        diff_pct = market_stats.get("diff_percent", 0.0)
        market_score = 80.0 - (diff_pct * 3.5)
        market_score = max(10.0, min(100.0, market_score))
        sub_scores["market_price"] = round(market_score, 1)

        diff_eur = market_stats.get("diff_to_median", 0.0)
        if diff_eur < -500:
            pros.append(f"{abs(int(diff_eur)):,} EUR unter Vergleichsmedian ({abs(diff_pct)}% Ersparnis)".replace(",", "."))
        elif diff_eur > 800:
            cons.append(f"{int(diff_eur):,} EUR über Vergleichsmedian".replace(",", "."))

        # ---------------------------------------------------------
        # 2. Ausstattungsumfang & Sonderwünsche (23%)
        # ---------------------------------------------------------
        core_matched = 0
        core_total = 0
        bonus_points = 0.0

        for df in self.desired_features:
            is_bonus = df.get("weight_tier") == "bonus"
            keywords = df.get("keywords", [])
            has_feature = any(kw.lower() in all_text for kw in keywords)

            if is_bonus:
                if has_feature:
                    bonus_points += 10.0
                    pros.append(f"Highlight: {df.get('name', '360° Kamera')} vorhanden")
            else:
                core_total += 1
                if has_feature:
                    core_matched += 1

        base_feat_score = (core_matched / max(1, core_total)) * 90.0
        final_feat_score = min(100.0, base_feat_score + bonus_points)
        sub_scores["features"] = round(final_feat_score, 1)

        if core_matched == core_total:
            pros.append("Nahezu alle Wunschmerkmale an Bord (Matrix, Massage, HUD, Wireless, ACC)")
        elif core_matched >= 5:
            pros.append(f"{core_matched} von {core_total} Hauptausstattungsmerkmalen vorhanden")
        else:
            cons.append(f"Nur {core_matched} von {core_total} Wunschmerkmalen dokumentiert")

        # ---------------------------------------------------------
        # 3. Spritverbrauch (10%)
        # ---------------------------------------------------------
        # Extrahiere Angabe wie "6.4 l/100km" aus Text, sonst realistische Abschätzung
        l_100km = self._extract_consumption(all_text, car.power_hp)
        if l_100km <= self.target_consumption:
            cons_score = 95.0 + max(0.0, (self.target_consumption - l_100km) * 5.0)
            pros.append(f"Günstiger Benzinverbrauch (~{round(l_100km, 1)} l/100km)")
        elif l_100km <= self.max_consumption:
            cons_score = 80.0 + ((self.max_consumption - l_100km) / (self.max_consumption - self.target_consumption)) * 15.0
        else:
            cons_score = max(35.0, 75.0 - ((l_100km - self.max_consumption) * 18.0))
            cons.append(f"Höherer Verbrauch (~{round(l_100km, 1)} l/100km)")
        sub_scores["consumption"] = round(min(100.0, cons_score), 1)

        # ---------------------------------------------------------
        # 4. Farbbewertung (5%) - Bevorzugt Blau und Rot
        # ---------------------------------------------------------
        found_color = None
        for c in self.preferred_colors:
            if c.lower() in all_text:
                found_color = c.capitalize()
                break

        if found_color:
            color_score = 100.0
            pros.append(f"Bevorzugte Lackierung ({found_color})")
        else:
            color_score = 65.0  # Neutrale Farben (Grau/Schwarz/Silber)
        sub_scores["color_preference"] = round(color_score, 1)

        # ---------------------------------------------------------
        # 5. Laufleistung (15%)
        # ---------------------------------------------------------
        km = car.mileage
        if km <= 35000:
            mileage_score = 95.0 - (km / 35000) * 10
            pros.append(f"Relativ geringe Laufleistung ({km:,} km)".replace(",", "."))
        elif km <= 60000:
            mileage_score = 85.0 - ((km - 35000) / 25000) * 15
        else:
            mileage_score = max(20.0, 70.0 - ((km - 60000) / 20000) * 30)
            cons.append(f"Höhere Laufleistung ({km:,} km)".replace(",", "."))
        sub_scores["mileage"] = round(mileage_score, 1)

        # ---------------------------------------------------------
        # 6. Alter / Baujahr (8%)
        # ---------------------------------------------------------
        curr_year = 2026
        age_years = max(0, curr_year - car.first_registration_year)
        age_score = max(40.0, 100.0 - (age_years * 7.5))
        sub_scores["age"] = round(age_score, 1)
        if age_years <= 3:
            pros.append(f"Junges Baujahr (EZ {car.first_registration_year})")

        # ---------------------------------------------------------
        # 7. Motorleistung (7%) (Bereich 150 - 200 PS)
        # ---------------------------------------------------------
        hp = car.power_hp
        if hp >= 190:
            power_score = 95.0 + min(5.0, (hp - 190))
            pros.append(f"Sportliche Motorleistung ({hp} PS)")
        elif hp >= 170:
            power_score = 85.0 + ((hp - 170) / 20) * 10
            pros.append(f"Gute Motorisierung mit {hp} PS")
        elif hp >= 150:
            power_score = 75.0 + ((hp - 150) / 20) * 10
        else:
            power_score = 55.0
            cons.append(f"Unter Mindestwunschleistung ({hp} PS)")
        sub_scores["power"] = round(power_score, 1)

        # ---------------------------------------------------------
        # 8. Distanz zum Heimatort (5%) (97271 Kleinrinderfeld)
        # ---------------------------------------------------------
        dist = car.distance_km
        if dist <= 25:
            dist_score = 98.0 - (dist / 25) * 8
            pros.append(f"Nah am Heimatort ({round(dist, 1)} km)")
        elif dist <= 60:
            dist_score = 90.0 - ((dist - 25) / 35) * 15
        elif dist <= 100:
            dist_score = 75.0 - ((dist - 60) / 40) * 15
            cons.append(f"{round(dist, 1)} km Entfernung")
        else:
            dist_score = max(20.0, 60.0 - ((dist - 100) / 50) * 20)
            cons.append(f"Außerhalb des 100 km Radius ({round(dist, 1)} km)")
        sub_scores["distance"] = round(dist_score, 1)

        # ---------------------------------------------------------
        # 9. Preistrend & Standzeit (5%)
        # ---------------------------------------------------------
        trend_score = 75.0
        if price_drop_total > 0:
            trend_score += min(25.0, (price_drop_total / 1000.0) * 15.0)
            pros.append(f"Bereits um {int(price_drop_total):,} EUR reduziert".replace(",", "."))
        elif days_online > 30:
            trend_score -= min(30.0, ((days_online - 30) / 10.0) * 6.0)
            cons.append(f"Seit {days_online} Tagen ohne Preisnachlass online")
        elif days_online <= 3:
            trend_score += 10.0
            pros.append("Ganz frisches Inserat (unter 3 Tage)")
        sub_scores["price_trend"] = round(max(10.0, min(100.0, trend_score)), 1)

        # ---------------------------------------------------------
        # Gesamtwert berechnen
        # ---------------------------------------------------------
        total = 0.0
        for key, score_val in sub_scores.items():
            w = self.weights.get(key, 0.05)
            total += score_val * w

        total_score = round(max(0.0, min(100.0, total)), 1)

        return {
            "deal_score": total_score,
            "sub_scores": sub_scores,
            "pros": pros,
            "cons": cons
        }

    def _extract_consumption(self, text: str, hp: int) -> float:
        # Sucht nach Mustern wie '6,3 l' oder '6.5l/100km'
        match = re.search(r'(\d+[\.,]\d+)\s*(?:l/100km|l\s*kombiniert|liter)', text)
        if match:
            try:
                return float(match.group(1).replace(",", "."))
            except ValueError:
                pass
        # Realistische Näherung für 1.5-2.0 TSI/TFSI/BMW Benziner Automatik
        if hp >= 190:
            return 7.1
        elif hp >= 170:
            return 6.7
        return 6.3