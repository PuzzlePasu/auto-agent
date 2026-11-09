import sqlite3
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict, Any
from app.database.models import CarListing

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "cars.db"


class DatabaseRepository:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cars (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    external_id TEXT UNIQUE NOT NULL,
                    provider TEXT NOT NULL,
                    url TEXT NOT NULL,
                    title TEXT NOT NULL,
                    make TEXT NOT NULL,
                    model TEXT NOT NULL,
                    price REAL NOT NULL,
                    mileage INTEGER NOT NULL,
                    first_registration_year INTEGER NOT NULL,
                    power_hp INTEGER NOT NULL,
                    fuel_type TEXT NOT NULL,
                    transmission TEXT NOT NULL,
                    dealer_name TEXT,
                    postal_code TEXT,
                    city TEXT,
                    distance_km REAL,
                    features_json TEXT,
                    deal_score REAL DEFAULT 0.0,
                    image_url TEXT DEFAULT '',
                    is_active INTEGER DEFAULT 1,
                    is_favorite INTEGER DEFAULT 0,
                    missing_runs INTEGER DEFAULT 0,
                    first_seen TEXT NOT NULL,
                    last_seen TEXT NOT NULL
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS price_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    car_id INTEGER NOT NULL,
                    price REAL NOT NULL,
                    recorded_at TEXT NOT NULL,
                    FOREIGN KEY (car_id) REFERENCES cars(id) ON DELETE CASCADE
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS system_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    level TEXT NOT NULL,
                    message TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_cars_external_id ON cars(external_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_cars_is_active ON cars(is_active)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_cars_deal_score ON cars(deal_score)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_price_history_car ON price_history(car_id)")

            conn.commit()

    def save_or_update_car(self, car: CarListing) -> str:
        now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        features_json = json.dumps(car.features, ensure_ascii=False)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, price, is_active FROM cars WHERE external_id = ?", (car.external_id,))
            row = cursor.fetchone()

            if row is None:
                cursor.execute("""
                    INSERT INTO cars (
                        external_id, provider, url, title, make, model,
                        price, mileage, first_registration_year, power_hp,
                        fuel_type, transmission, dealer_name, postal_code,
                        city, distance_km, features_json, deal_score, image_url,
                        is_active, is_favorite, missing_runs, first_seen, last_seen
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0, 0, ?, ?)
                """, (
                    car.external_id, car.provider, car.url, car.title, car.make, car.model,
                    car.price, car.mileage, car.first_registration_year, car.power_hp,
                    car.fuel_type, car.transmission, car.dealer_name, car.postal_code,
                    car.city, car.distance_km, features_json, car.deal_score, car.image_url,
                    now_str, now_str
                ))
                car_id = cursor.lastrowid
                car.id = car_id

                cursor.execute("""
                    INSERT INTO price_history (car_id, price, recorded_at)
                    VALUES (?, ?, ?)
                """, (car_id, car.price, now_str))

                conn.commit()
                return "new"

            car_id = row["id"]
            old_price = float(row["price"])
            car.id = car_id

            price_changed = abs(old_price - car.price) >= 1.0

            cursor.execute("""
                UPDATE cars SET
                    price = ?,
                    mileage = ?,
                    deal_score = ?,
                    is_active = 1,
                    missing_runs = 0,
                    last_seen = ?,
                    features_json = ?,
                    url = ?,
                    image_url = ?
                WHERE id = ?
            """, (
                car.price, car.mileage, car.deal_score, now_str,
                features_json, car.url, car.image_url, car_id
            ))

            if price_changed:
                cursor.execute("""
                    INSERT INTO price_history (car_id, price, recorded_at)
                    VALUES (?, ?, ?)
                """, (car_id, car.price, now_str))

            conn.commit()
            return "price_changed" if price_changed else "duplicate"

    def mark_missing_cars(self, current_listings: List[CarListing], threshold_runs: int = 3):
        current_ext_ids = {c.external_id for c in current_listings if c.external_id}
        all_active = self.get_all_cars(only_active=True, canonical_only=False)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            for car in all_active:
                if car.external_id not in current_ext_ids:
                    cursor.execute("UPDATE cars SET missing_runs = missing_runs + 1 WHERE id = ?", (car.id,))
                    cursor.execute("SELECT missing_runs FROM cars WHERE id = ?", (car.id,))
                    res = cursor.fetchone()
                    if res and res["missing_runs"] >= threshold_runs:
                        cursor.execute("UPDATE cars SET is_active = 0 WHERE id = ?", (car.id,))
                else:
                    cursor.execute("UPDATE cars SET missing_runs = 0 WHERE id = ?", (car.id,))
            conn.commit()

    def get_all_cars(self, only_active: bool = True, canonical_only: bool = True) -> List[CarListing]:
        query = "SELECT * FROM cars WHERE 1=1"
        if only_active:
            query += " AND is_active = 1"
        query += " ORDER BY deal_score DESC"

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            return [self._row_to_car_listing(row) for row in cursor.fetchall()]

    def get_car_by_id(self, car_id: int) -> Optional[CarListing]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM cars WHERE id = ?", (car_id,))
            row = cursor.fetchone()
            return self._row_to_car_listing(row) if row else None

    def get_price_history(self, car_id: int) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT price, recorded_at FROM price_history 
                WHERE car_id = ? ORDER BY recorded_at ASC
            """, (car_id,))
            return [{"price": float(r["price"]), "recorded_at": r["recorded_at"]} for r in cursor.fetchall()]

    def toggle_favorite(self, car_id: int) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT is_favorite FROM cars WHERE id = ?", (car_id,))
            row = cursor.fetchone()
            if not row:
                return False
            new_status = 0 if row["is_favorite"] else 1
            cursor.execute("UPDATE cars SET is_favorite = ? WHERE id = ?", (new_status, car_id))
            conn.commit()
            return bool(new_status)

    def update_deal_score(self, car_id: int, new_score: float):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE cars SET deal_score = ? WHERE id = ?", (new_score, car_id))
            conn.commit()

    def log_event(self, level: str, message: str):
        now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO system_logs (level, message, created_at) VALUES (?, ?, ?)", (level.upper(), message, now_str))
            conn.commit()

    def get_recent_logs(self, limit: int = 5) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT level, message, created_at FROM system_logs ORDER BY id DESC LIMIT ?", (limit,))
            return [{"level": r["level"], "message": r["message"], "created_at": r["created_at"]} for r in cursor.fetchall()]

    def _row_to_car_listing(self, row: sqlite3.Row) -> CarListing:
        features = []
        if row["features_json"]:
            try:
                features = json.loads(row["features_json"])
            except Exception:
                features = []

        car = CarListing(
            id=row["id"],
            external_id=row["external_id"],
            provider=row["provider"],
            url=row["url"],
            title=row["title"],
            make=row["make"],
            model=row["model"],
            price=float(row["price"]),
            mileage=int(row["mileage"]),
            first_registration_year=int(row["first_registration_year"]),
            power_hp=int(row["power_hp"]),
            fuel_type=row["fuel_type"],
            transmission=row["transmission"],
            dealer_name=row["dealer_name"] or "Händler",
            postal_code=row["postal_code"] or "97271",
            city=row["city"] or "Würzburg",
            distance_km=float(row["distance_km"]) if row["distance_km"] is not None else 25.0,
            features=features,
            deal_score=float(row["deal_score"] or 0.0),
            image_url=str(row["image_url"] or "")
        )

        car.is_active = bool(row["is_active"])
        car.is_favorite = bool(row["is_favorite"])
        car.first_seen = row["first_seen"]
        car.last_seen = row["last_seen"]

        return car