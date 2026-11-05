from typing import List, Tuple
from app.database.models import CarListing

class DeduplicationService:
    def deduplicate(self, cars: List[CarListing]) -> Tuple[List[CarListing], int]:
        duplicates_count = 0
        canonical_cars: List[CarListing] = []
        
        # mobile.de (Priorität 1) zuerst verarbeiten
        sorted_cars = sorted(cars, key=lambda c: 1 if c.provider == "mobile.de" else 2)
        
        for candidate in sorted_cars:
            matched = next((canon for canon in canonical_cars if self._is_dup(candidate, canon)), None)
            if matched:
                duplicates_count += 1
                candidate.canonical_id = matched.id or 999999
                diff = candidate.price - matched.price
                msg = f"{matched.provider} ist {abs(int(diff)):,} EUR günstiger." if diff > 0 else (
                    f"{candidate.provider} ist {abs(int(diff)):,} EUR günstiger." if diff < 0 else "Identischer Preis auf beiden Plattformen."
                )
                matched.duplicate_info = {
                    "has_duplicate": True,
                    "other_provider": candidate.provider,
                    "other_price": candidate.price,
                    "other_url": candidate.url,
                    "price_diff": diff,
                    "message": msg.replace(",", ".")
                }
            else:
                canonical_cars.append(candidate)
        return canonical_cars, duplicates_count

    def _is_dup(self, a: CarListing, b: CarListing) -> bool:
        if a.make.lower() != b.make.lower() or a.model.lower() != b.model.lower():
            return False
        if a.first_registration_year != b.first_registration_year:
            return False
        if abs(a.mileage - b.mileage) > 1000 or abs(a.power_hp - b.power_hp) > 5:
            return False
        if a.postal_code and b.postal_code and a.postal_code == b.postal_code:
            return True
        if a.dealer_name and b.dealer_name and (a.dealer_name.lower() in b.dealer_name.lower() or b.dealer_name.lower() in a.dealer_name.lower()):
            return True
        return abs(a.price - b.price) / min(a.price, b.price) < 0.05 and abs(a.mileage - b.mileage) < 500