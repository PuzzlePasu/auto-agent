import logging
import re
from typing import Dict, Any, List
from app.database.models import CarListing

logger = logging.getLogger(__name__)


class ScoringService:
    def calculate_deal_score(
        self,
        car: CarListing,
        weights: Dict[str, float],
        rules: Dict[str, Any]
    ) -> float:
        """
        Berechnet den Gesamt-Deal-Score (0-100) auf Basis der gewichteten Teil-Scores.
        """
        w_features = weights.get("features", 0.23)
        w_market = weights.get("market_price", 0.22)
        w_mileage = weights.get("mileage", 0.15)
        w_consumption = weights.get("consumption", 0.10)
        w_distance = weights.get("distance", 0.10)
        w_age = weights.get("age", 0.08)
        w_power = weights.get("power", 0.07)
        w_color = weights.get("color_preference", 0.05)

        score_features = self._score_features(car, rules)
        score_price = self._score_price(car)
        score_mileage = self._score_mileage(car)
        score_consumption = self._score_consumption(car, rules)
        score_distance = self._score_distance(car)
        score_age = self._score_age(car)
        score_power = self._score_power(car)
        score_color = self._score_color(car, rules)

        total_score = (
            score_features * w_features
            + score_price * w_market
            + score_mileage * w_mileage
            + score_consumption * w_consumption
            + score_distance * w_distance
            + score_age * w_age
            + score_power * w_power
            + score_color * w_color
        )

        return round(float(total_score), 1)

    def _score_features(self, car: CarListing, rules: Dict[str, Any]) -> float:
        """
        Bewertet die Ausstattungsmerkmale (0-100).
        Vergleicht gefundene Ausstattungsmerkmale und Titel mit desired_features
        unter Berücksichtigung von feature_aliases.
        """
        desired = rules.get("desired_features", [])
        if not desired:
            return 50.0

        aliases = rules.get("feature_aliases", {})
        
        # Sammle alle Textmerkmale des Autos in Kleinbuchstaben
        car_text_pool = [car.title.lower()] + [str(f).lower() for f in car.features]
        matched_count = 0

        for feat in desired:
            feat_lower = feat.lower()
            synonyms = aliases.get(feat, [feat_lower])
            
            # Prüfen, ob Merkmal direkt oder über Synonym existiert
            matched = False
            for text in car_text_pool:
                if any(syn.lower() in text for syn in synonyms):
                    matched = True
                    break

            if matched:
                matched_count += 1

        # Quote berechnen (100% wenn alle desired_features gefunden wurden)
        return min(100.0, (matched_count / len(desired)) * 100.0)

    def _score_price(self, car: CarListing) -> float:
        """
        Bewertet den Anschaffungspreis (0-100).
        Je weiter unter 27.000 €, desto höher der Score.
        """
        if car.price <= 0:
            return 0.0
        
        # Referenz: <= 20.000 € -> 100 Punkte, >= 28.000 € -> 30 Punkte
        if car.price <= 20000:
            return 100.0
        if car.price >= 30000:
            return 20.0

        # Linearer Verlauf zwischen 20.000 und 30.000
        return max(0.0, 100.0 - ((car.price - 20000) / 10000) * 80.0)

    def _score_mileage(self, car: CarListing) -> float:
        """
        Bewertet den Kilometerstand (0-100).
        """
        if car.mileage <= 15000:
            return 100.0
        if car.mileage >= 100000:
            return 10.0

        return max(0.0, 100.0 - ((car.mileage - 15000) / 85000) * 90.0)

    def _score_consumption(self, car: CarListing, rules: Dict[str, Any]) -> float:
        """
        Bewertet den geschätzten/angegebenen Kraftstoffverbrauch (0-100).
        """
        target = float(rules.get("target_consumption_l100km", 6.2))
        # Da mobile.de Verbrauchsdaten oft nicht in Inseratstiteln stehen,
        # setzen wir standardmäßig 80 Punkte für moderne 1.5/2.0 TSI Benzinmotoren.
        return 80.0

    def _score_distance(self, car: CarListing) -> float:
        """
        Bewertet die Entfernung zum Standort (0-100).
        0 km = 100 Punkte, 100 km = 50 Punkte, >150 km = 20 Punkte.
        """
        dist = car.distance_km or 50.0
        if dist <= 15:
            return 100.0
        if dist >= 120:
            return 30.0

        return max(0.0, 100.0 - ((dist - 15) / 105) * 70.0)

    def _score_age(self, car: CarListing) -> float:
        """
        Bewertet das Fahrzeugalter anhand des Baujahrs (0-100).
        """
        year = car.first_registration_year or 2020
        if year >= 2024:
            return 100.0
        if year == 2023:
            return 90.0
        if year == 2022:
            return 75.0
        if year == 2021:
            return 60.0
        if year == 2020:
            return 45.0
        return 20.0

    def _score_power(self, car: CarListing) -> float:
        """
        Bewertet die Motorleistung (0-100).
        Zielkorridor: 150 - 200 PS.
        """
        hp = car.power_hp or 150
        if hp >= 190:
            return 100.0
        if hp >= 150:
            return 85.0
        if hp >= 130:
            return 60.0
        return 30.0

    def _score_color(self, car: CarListing, rules: Dict[str, Any]) -> float:
        """
        Bewertet die Lackfarbe (0-100).
        Gibt Bonus-Punkte für Treffer in preferred_colors (z.B. Blau, Rot).
        """
        preferred = rules.get("preferred_colors", ["blau", "rot"])
        car_text = f"{car.title} {' '.join(car.features)}".lower()

        for col in preferred:
            if col.lower() in car_text:
                return 100.0

        return 40.0