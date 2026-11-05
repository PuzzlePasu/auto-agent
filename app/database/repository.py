import sqlite3
import json
import os
from datetime import datetime
from typing import List, Optional, Dict, Any
from app.database.models import CarListing, PriceRecord, SearchLog

class DatabaseRepository:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or os.getenv("DATABASE_PATH", "data/cars.db")
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        self.init_db()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS cars (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider TEXT NOT NULL,
                external_id TEXT NOT NULL,
                url TEXT NOT NULL,
                make TEXT NOT NULL,
                model TEXT NOT NULL,
                title TEXT NOT NULL,
                price REAL NOT NULL,
                mileage INTEGER NOT NULL,
                first_registration_year INTEGER NOT NULL,
                first_registration_month INTEGER DEFAULT 1,
                power_hp INTEGER NOT NULL,
                transmission TEXT NOT NULL,
                fuel_type TEXT NOT NULL,
                postal_code TEXT,
                city TEXT,
                distance_km REAL DEFAULT 0,
                dealer_name TEXT,
                features TEXT,
                image_url TEXT,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                is_active INTEGER DEFAULT 1,
                consecutive_missing_runs INTEGER DEFAULT 0,
                is_favorite INTEGER DEFAULT 0,
                canonical_id INTEGER,
                duplicate_info TEXT,
                deal_score REAL DEFAULT 0,
                sub_scores TEXT,
                market_stats TEXT,
                pros TEXT,
                cons TEXT,
                UNIQUE(provider, external_id)
            )
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                car_id INTEGER NOT NULL,
                price REAL NOT NULL,
                recorded_at TEXT NOT NULL,
                FOREIGN KEY (car_id) REFERENCES cars(id)
            )
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS search_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                provider TEXT NOT NULL,
                total_found INTEGER DEFAULT 0,
                new_found INTEGER DEFAULT 0,
                price_changes INTEGER DEFAULT 0,
                duplicates_detected INTEGER DEFAULT 0,
                deactivated_count INTEGER DEFAULT 0,
                errors TEXT
            )
            """)
            conn.commit()

    def get_all_cars(self, only_active: bool = False, canonical_only: bool = True) -> List[CarListing]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            conditions = []
            if only_active:
                conditions.append("is_active = 1")
            if canonical_only:
                conditions.append("canonical_id IS NULL")
                
            query = "SELECT * FROM cars"
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            query += " ORDER BY deal_score DESC, price ASC"
            
            cursor.execute(query)
            return [self._row_to_car(row) for row in cursor.fetchall()]

    def get_car_by_id(self, car_id: int) -> Optional[CarListing]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM cars WHERE id = ?", (car_id,))
            row = cursor.fetchone()
            return self._row_to_car(row) if row else None

    def get_car_by_external_id(self, provider: str, external_id: str) -> Optional[CarListing]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM cars WHERE provider = ? AND external_id = ?", (provider, external_id))
            row = cursor.fetchone()
            return self._row_to_car(row) if row else None

    def save_car(self, car: CarListing) -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            if car.id is None:
                cursor.execute("""
                INSERT INTO cars (
                    provider, external_id, url, make, model, title, price, mileage,
                    first_registration_year, first_registration_month, power_hp,
                    transmission, fuel_type, postal_code, city, distance_km,
                    dealer_name, features, image_url, first_seen, last_seen,
                    is_active, consecutive_missing_runs, is_favorite, canonical_id,
                    duplicate_info, deal_score, sub_scores, market_stats, pros, cons
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    car.provider, car.external_id, car.url, car.make, car.model, car.title,
                    car.price, car.mileage, car.first_registration_year, car.first_registration_month,
                    car.power_hp, car.transmission, car.fuel_type, car.postal_code, car.city,
                    car.distance_km, car.dealer_name, json.dumps(car.features), car.image_url,
                    car.first_seen or now, car.last_seen or now, 1 if car.is_active else 0,
                    car.consecutive_missing_runs, 1 if car.is_favorite else 0, car.canonical_id,
                    json.dumps(car.duplicate_info) if car.duplicate_info else None,
                    car.deal_score, json.dumps(car.sub_scores), json.dumps(car.market_stats),
                    json.dumps(car.pros), json.dumps(car.cons)
                ))
                car.id = cursor.lastrowid
                cursor.execute("INSERT INTO price_history (car_id, price, recorded_at) VALUES (?, ?, ?)",
                               (car.id, car.price, car.first_seen or now))
            else:
                cursor.execute("""
                UPDATE cars SET
                    url = ?, title = ?, price = ?, mileage = ?, power_hp = ?,
                    postal_code = ?, city = ?, distance_km = ?, dealer_name = ?,
                    features = ?, image_url = ?, last_seen = ?, is_active = ?,
                    consecutive_missing_runs = ?, is_favorite = ?, canonical_id = ?,
                    duplicate_info = ?, deal_score = ?, sub_scores = ?, market_stats = ?,
                    pros = ?, cons = ?
                WHERE id = ?
                """, (
                    car.url, car.title, car.price, car.mileage, car.power_hp,
                    car.postal_code, car.city, car.distance_km, car.dealer_name,
                    json.dumps(car.features), car.image_url, car.last_seen or now,
                    1 if car.is_active else 0, car.consecutive_missing_runs,
                    1 if car.is_favorite else 0, car.canonical_id,
                    json.dumps(car.duplicate_info) if car.duplicate_info else None,
                    car.deal_score, json.dumps(car.sub_scores), json.dumps(car.market_stats),
                    json.dumps(car.pros), json.dumps(car.cons), car.id
                ))
            conn.commit()
            return car.id

    def add_price_record(self, car_id: int, price: float, timestamp: str = None):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            recorded_at = timestamp or datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("INSERT INTO price_history (car_id, price, recorded_at) VALUES (?, ?, ?)",
                           (car_id, price, recorded_at))
            conn.commit()

    def get_price_history(self, car_id: int) -> List[PriceRecord]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM price_history WHERE car_id = ? ORDER BY recorded_at ASC", (car_id,))
            return [PriceRecord(id=r["id"], car_id=r["car_id"], price=r["price"], recorded_at=r["recorded_at"]) for r in cursor.fetchall()]

    def toggle_favorite(self, car_id: int) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT is_favorite FROM cars WHERE id = ?", (car_id,))
            row = cursor.fetchone()
            if not row:
                return False
            new_val = 0 if row["is_favorite"] else 1
            cursor.execute("UPDATE cars SET is_favorite = ? WHERE id = ?", (new_val, car_id))
            conn.commit()
            return bool(new_val)

    def log_search_run(self, log: SearchLog) -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO search_logs (
                start_time, end_time, provider, total_found, new_found,
                price_changes, duplicates_detected, deactivated_count, errors
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                log.start_time, log.end_time, log.provider, log.total_found,
                log.new_found, log.price_changes, log.duplicates_detected,
                log.deactivated_count, log.errors
            ))
            conn.commit()
            return cursor.lastrowid

    def get_recent_logs(self, limit: int = 10) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM search_logs ORDER BY id DESC LIMIT ?", (limit,))
            return [dict(r) for r in cursor.fetchall()]

    def _row_to_car(self, row: sqlite3.Row) -> CarListing:
        return CarListing(
            id=row["id"], provider=row["provider"], external_id=row["external_id"],
            url=row["url"], make=row["make"], model=row["model"], title=row["title"],
            price=row["price"], mileage=row["mileage"], first_registration_year=row["first_registration_year"],
            first_registration_month=row["first_registration_month"], power_hp=row["power_hp"],
            transmission=row["transmission"], fuel_type=row["fuel_type"], postal_code=row["postal_code"] or "",
            city=row["city"] or "", distance_km=row["distance_km"] or 0.0, dealer_name=row["dealer_name"] or "",
            features=json.loads(row["features"]) if row["features"] else [], image_url=row["image_url"] or "",
            first_seen=row["first_seen"], last_seen=row["last_seen"], is_active=bool(row["is_active"]),
            consecutive_missing_runs=row["consecutive_missing_runs"], is_favorite=bool(row["is_favorite"]),
            canonical_id=row["canonical_id"], duplicate_info=json.loads(row["duplicate_info"]) if row["duplicate_info"] else None,
            deal_score=row["deal_score"] or 0.0, sub_scores=json.loads(row["sub_scores"]) if row["sub_scores"] else {},
            market_stats=json.loads(row["market_stats"]) if row["market_stats"] else {},
            pros=json.loads(row["pros"]) if row["pros"] else [], cons=json.loads(row["cons"]) if row["cons"] else []
        )