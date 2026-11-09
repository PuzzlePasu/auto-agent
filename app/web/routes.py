import os
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List
from fastapi import APIRouter, Request, Query, Form
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from app.database.repository import DatabaseRepository
from app.services.search import SearchService
from app.services.pdf_export import PdfExportService

logger = logging.getLogger(__name__)

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
CONFIG_PATH = BASE_DIR.parent.parent / "config.json"

repo = DatabaseRepository()
search_service = SearchService(repo)


# -------------------------------------------------------------
# 1. DASHBOARD
# -------------------------------------------------------------
@router.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    make: str = Query(None),
    model: str = Query(None),
    min_score: float = Query(None),
    max_price: float = Query(None),
    max_mileage: int = Query(None),
    min_year: int = Query(None),
    provider: str = Query(None),
    sort_by: str = Query("best_deal"),
    tab: str = Query("active")
):
    cars = repo.get_all_cars(only_active=(tab != "inactive"), canonical_only=True)

    if tab == "inactive":
        cars = [c for c in cars if not c.is_active]
    elif tab == "favorites":
        cars = [c for c in cars if c.is_favorite and c.is_active]
    elif tab == "price_drops":
        cars = [c for c in cars if c.is_active and len(repo.get_price_history(c.id)) > 1]
    else:
        cars = [c for c in cars if c.is_active]

    if make:
        cars = [c for c in cars if c.make.lower() == make.lower()]
    if model:
        cars = [c for c in cars if model.lower() in c.model.lower()]
    if min_score is not None:
        cars = [c for c in cars if c.deal_score >= min_score]
    if max_price is not None:
        cars = [c for c in cars if c.price <= max_price]
    if max_mileage is not None:
        cars = [c for c in cars if c.mileage <= max_mileage]
    if min_year is not None:
        cars = [c for c in cars if c.first_registration_year >= min_year]
    if provider:
        cars = [c for c in cars if c.provider.lower() == provider.lower()]

    if sort_by == "best_deal":
        cars.sort(key=lambda x: x.deal_score, reverse=True)
    elif sort_by == "lowest_price":
        cars.sort(key=lambda x: x.price)
    elif sort_by == "lowest_mileage":
        cars.sort(key=lambda x: x.mileage)
    elif sort_by == "highest_power":
        cars.sort(key=lambda x: x.power_hp, reverse=True)
    elif sort_by == "lowest_distance":
        cars.sort(key=lambda x: x.distance_km)
    elif sort_by == "newest_listing":
        cars.sort(key=lambda x: x.first_seen, reverse=True)

    all_active = repo.get_all_cars(only_active=True, canonical_only=True)
    top_deals = sorted(all_active, key=lambda x: x.deal_score, reverse=True)[:3]
    recent_logs = repo.get_recent_logs(5)

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "cars": cars,
            "top_deals": top_deals,
            "current_tab": tab,
            "sort_by": sort_by,
            "filters": {
                "make": make or "",
                "model": model or "",
                "min_score": min_score or "",
                "max_price": max_price or "",
                "max_mileage": max_mileage or "",
                "min_year": min_year or "",
                "provider": provider or ""
            },
            "recent_logs": recent_logs,
            "total_active_count": len(all_active)
        }
    )


# -------------------------------------------------------------
# 2. DETAILANSICHT
# -------------------------------------------------------------
@router.get("/car/{car_id}", response_class=HTMLResponse)
async def car_details(request: Request, car_id: int):
    car = repo.get_car_by_id(car_id)
    if not car:
        return HTMLResponse(content="Fahrzeug nicht gefunden", status_code=404)

    price_history = repo.get_price_history(car_id)
    first_dt = datetime.strptime(car.first_seen, "%Y-%m-%d %H:%M:%S") if car.first_seen else datetime.utcnow()
    days_online = max(1, (datetime.utcnow() - first_dt).days)
    price_metrics = search_service.price_service.calculate_price_metrics(price_history, car.price)

    desired_features = []
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                desired_features = cfg.get("scoring_rules", {}).get("desired_features", [])
        except Exception as e:
            logger.error(f"Fehler beim Laden der desired_features: {e}")

    return templates.TemplateResponse(
        request=request,
        name="car_detail.html",
        context={
            "car": car,
            "price_history": price_history,
            "days_online": days_online,
            "price_metrics": price_metrics,
            "desired_features": desired_features
        }
    )


# -------------------------------------------------------------
# 3. DIREKTVERGLEICH
# -------------------------------------------------------------
@router.get("/compare", response_class=HTMLResponse)
async def compare_cars(request: Request, id1: int = Query(None), id2: int = Query(None)):
    all_cars = repo.get_all_cars(only_active=True, canonical_only=True)

    car1 = repo.get_car_by_id(id1) if id1 else (all_cars[0] if len(all_cars) > 0 else None)
    car2 = repo.get_car_by_id(id2) if id2 else (all_cars[1] if len(all_cars) > 1 else (all_cars[0] if len(all_cars) > 0 else None))

    comparison_results = {}
    if car1 and car2:
        wins_c1, wins_c2 = [], []
        if car1.price < car2.price:
            wins_c1.append(f"Günstigerer Anschaffungspreis (-{int(car2.price - car1.price):,} EUR)")
        elif car2.price < car1.price:
            wins_c2.append(f"Günstigerer Anschaffungspreis (-{int(car1.price - car2.price):,} EUR)")

        if car1.mileage < car2.mileage:
            wins_c1.append(f"Geringere Laufleistung (-{car2.mileage - car1.mileage:,} km)")
        elif car2.mileage < car1.mileage:
            wins_c2.append(f"Geringere Laufleistung (-{car1.mileage - car2.mileage:,} km)")

        if car1.power_hp > car2.power_hp:
            wins_c1.append(f"Höhere Motorleistung (+{car1.power_hp - car2.power_hp} PS)")
        elif car2.power_hp > car1.power_hp:
            wins_c2.append(f"Höhere Motorleistung (+{car2.power_hp - car1.power_hp} PS)")

        if car1.distance_km < car2.distance_km:
            wins_c1.append(f"Geringere Distanz (-{round(car2.distance_km - car1.distance_km, 1)} km)")
        elif car2.distance_km < car1.distance_km:
            wins_c2.append(f"Geringere Distanz (-{round(car1.distance_km - car2.distance_km, 1)} km)")

        if car1.deal_score > car2.deal_score:
            wins_c1.append(f"Besserer Gesamt-Deal-Score ({car1.deal_score} vs {car2.deal_score})")
        elif car2.deal_score > car1.deal_score:
            wins_c2.append(f"Besserer Gesamt-Deal-Score ({car2.deal_score} vs {car1.deal_score})")

        comparison_results = {
            "wins_car1": wins_c1,
            "wins_car2": wins_c2,
            "overall_winner": car1 if car1.deal_score >= car2.deal_score else car2
        }

    return templates.TemplateResponse(
        request=request,
        name="compare.html",
        context={
            "all_cars": all_cars,
            "car1": car1,
            "car2": car2,
            "comparison": comparison_results
        }
    )


# -------------------------------------------------------------
# 4. EINSTELLUNGEN & CONFIG-MANAGEMENT
# -------------------------------------------------------------
@router.get("/settings", response_class=HTMLResponse)
async def settings_view(request: Request):
    config_dict = {}
    config_raw = "{}"
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                config_dict = json.load(f)
                config_raw = json.dumps(config_dict, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Fehler beim Laden von config.json: {e}")
            config_raw = f"// Fehler beim Laden der Datei: {e}"

    # Prüfen, ob mobile.de URLs via Docker-Umgebungsvariable vorgegeben sind
    env_urls_raw = os.getenv("MOBILE_SEARCH_URLS", "").strip()
    urls_from_env = False
    active_urls = []

    if env_urls_raw:
        active_urls = [
            u.strip() for u in env_urls_raw.replace(";", "\n").replace(",", "\n").splitlines()
            if u.strip().startswith("http")
        ]
        if active_urls:
            urls_from_env = True

    if not urls_from_env:
        active_urls = config_dict.get("search_criteria", {}).get("search_page_urls", [])

    return templates.TemplateResponse(
        request=request,
        name="settings.html",
        context={
            "config": config_dict,
            "config_raw": config_raw,
            "active_urls": active_urls,
            "urls_from_env": urls_from_env,
            "saved": request.query_params.get("saved") == "true",
            "error": request.query_params.get("error")
        }
    )


@router.post("/settings/save")
async def settings_save(
    request: Request,
    edit_mode: str = Form("fields"),
    search_page_urls_text: str = Form(""),
    target_consumption: float = Form(6.2),
    inactivity_runs: int = Form(3),
    weight_market: float = Form(22.0),
    weight_features: float = Form(23.0),
    weight_consumption: float = Form(10.0),
    weight_color: float = Form(5.0),
    weight_mileage: float = Form(15.0),
    weight_distance: float = Form(10.0),
    weight_age: float = Form(8.0),
    weight_power: float = Form(7.0),
    desired_features_json: str = Form("[]"),
    feature_aliases_json: str = Form("{}"),
    preferred_colors_json: str = Form("[]"),
    run_search_after: bool = Form(False),
    raw_json: str = Form("")
):
    try:
        if edit_mode == "raw":
            parsed_data = json.loads(raw_json)
        else:
            parsed_data = {}
            if CONFIG_PATH.exists():
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    parsed_data = json.load(f)

            crit = parsed_data.setdefault("search_criteria", {})
            weights = parsed_data.setdefault("scoring_weights", {})
            rules = parsed_data.setdefault("scoring_rules", {})

            # 1. mobile.de Such-URLs aus Textarea speichern (nur wenn nicht schreibgeschützt durch ENV)
            if not os.getenv("MOBILE_SEARCH_URLS", "").strip():
                clean_urls = [
                    line.strip()
                    for line in search_page_urls_text.splitlines()
                    if line.strip().startswith("http")
                ]
                crit["search_page_urls"] = clean_urls

            # 2. desired_features (Basis für 100% Ausstattungs-Score)
            try:
                parsed_desired = json.loads(desired_features_json)
                if isinstance(parsed_desired, list):
                    rules["desired_features"] = [f.strip() for f in parsed_desired if f.strip()]
            except Exception:
                pass

            # 3. feature_aliases (Synonyme für ACC, Matrix LED etc.)
            try:
                parsed_aliases = json.loads(feature_aliases_json)
                if isinstance(parsed_aliases, dict):
                    rules["feature_aliases"] = parsed_aliases
            except Exception:
                pass

            # 4. Wunschfarben & Verbrauchs-Target
            try:
                parsed_colors = json.loads(preferred_colors_json)
                if isinstance(parsed_colors, list):
                    rules["preferred_colors"] = [c.strip().lower() for c in parsed_colors if c.strip()]
            except Exception:
                pass

            rules["target_consumption_l100km"] = target_consumption
            rules["inactivity_threshold_runs"] = inactivity_runs

            # 5. Score-Gewichtungen
            weights["market_price"] = weight_market / 100.0
            weights["features"] = weight_features / 100.0
            weights["consumption"] = weight_consumption / 100.0
            weights["color_preference"] = weight_color / 100.0
            weights["mileage"] = weight_mileage / 100.0
            weights["distance"] = weight_distance / 100.0
            weights["age"] = weight_age / 100.0
            weights["power"] = weight_power / 100.0

        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(parsed_data, f, indent=2, ensure_ascii=False)

        # Alle Bestandsfahrzeuge direkt mit den neuen Kriterien offline neu bewerten
        search_service.rescore_all_listings()

        if run_search_after:
            search_service.run_search_pipeline()
            return RedirectResponse(url="/?saved=true", status_code=303)

        return RedirectResponse(url="/settings?saved=true", status_code=303)

    except json.JSONDecodeError as err:
        logger.error(f"JSONDecodeError beim Speichern der Konfiguration: {err}")
        return RedirectResponse(url=f"/settings?error=Ungueltiges+JSON:+{err.msg}", status_code=303)
    except Exception as e:
        logger.error(f"Fehler beim Speichern der Konfiguration: {e}", exc_info=True)
        return RedirectResponse(url=f"/settings?error={str(e)}", status_code=303)


# -------------------------------------------------------------
# 5. PDF-EXPORTE
# -------------------------------------------------------------
@router.get("/car/{car_id}/pdf")
async def download_car_pdf(car_id: int):
    car = repo.get_car_by_id(car_id)
    if not car:
        return HTMLResponse(content="Fahrzeug nicht gefunden", status_code=404)

    price_history = repo.get_price_history(car_id)
    first_dt = datetime.strptime(car.first_seen, "%Y-%m-%d %H:%M:%S") if car.first_seen else datetime.utcnow()
    days_online = max(1, (datetime.utcnow() - first_dt).days)
    price_metrics = search_service.price_service.calculate_price_metrics(price_history, car.price)

    pdf_bytes = PdfExportService.generate_car_report(car, price_metrics, days_online)

    score_tag = f"score{int(round(car.deal_score))}"
    safe_make_model = f"{car.make}-{car.model}".replace(" ", "_").lower()
    filename = f"auto-agent-{score_tag}-{safe_make_model}-{car.id}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@router.get("/compare/pdf")
async def download_compare_pdf(id1: int = Query(...), id2: int = Query(...)):
    car1 = repo.get_car_by_id(id1)
    car2 = repo.get_car_by_id(id2)
    if not car1 or not car2:
        return HTMLResponse(content="Eines oder beide Fahrzeuge wurden nicht gefunden", status_code=404)

    wins_c1, wins_c2 = [], []
    if car1.price < car2.price:
        wins_c1.append(f"Günstigerer Anschaffungspreis (-{int(car2.price - car1.price):,} EUR)")
    elif car2.price < car1.price:
        wins_c2.append(f"Günstigerer Anschaffungspreis (-{int(car1.price - car2.price):,} EUR)")

    if car1.mileage < car2.mileage:
        wins_c1.append(f"Geringere Laufleistung (-{car2.mileage - car1.mileage:,} km)")
    elif car2.mileage < car1.mileage:
        wins_c2.append(f"Geringere Laufleistung (-{car1.mileage - car2.mileage:,} km)")

    if car1.power_hp > car2.power_hp:
        wins_c1.append(f"Höhere Motorleistung (+{car1.power_hp - car2.power_hp} PS)")
    elif car2.power_hp > car1.power_hp:
        wins_c2.append(f"Höhere Motorleistung (+{car2.power_hp - car1.power_hp} PS)")

    if car1.distance_km < car2.distance_km:
        wins_c1.append(f"Geringere Distanz (-{round(car2.distance_km - car1.distance_km, 1)} km)")
    elif car2.distance_km < car1.distance_km:
        wins_c2.append(f"Geringere Distanz (-{round(car1.distance_km - car2.distance_km, 1)} km)")

    if car1.deal_score > car2.deal_score:
        wins_c1.append(f"Besserer Gesamt-Deal-Score ({car1.deal_score} vs {car2.deal_score})")
    elif car2.deal_score > car1.deal_score:
        wins_c2.append(f"Besserer Gesamt-Deal-Score ({car2.deal_score} vs {car1.deal_score})")

    comparison_results = {
        "wins_car1": wins_c1,
        "wins_car2": wins_c2,
        "overall_winner": car1 if car1.deal_score >= car2.deal_score else car2
    }

    pdf_bytes = PdfExportService.generate_comparison_report(car1, car2, comparison_results)

    c1_tag = f"score{int(round(car1.deal_score))}-{car1.make}-{car1.model}".replace(" ", "_").lower()
    c2_tag = f"score{int(round(car2.deal_score))}-{car2.make}-{car2.model}".replace(" ", "_").lower()
    filename = f"vergleich-{c1_tag}-vs-{c2_tag}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


# -------------------------------------------------------------
# 6. API-AKTIONEN
# -------------------------------------------------------------
@router.post("/api/favorite/{car_id}")
async def toggle_favorite(car_id: int):
    new_status = repo.toggle_favorite(car_id)
    return {"success": True, "is_favorite": new_status}


@router.post("/api/search-now")
async def trigger_search():
    search_service.run_search_pipeline()
    return RedirectResponse(url="/", status_code=303)


@router.post("/api/rescore")
async def trigger_rescore():
    count = search_service.rescore_all_listings()
    logger.info(f"Re-Scoring über Webinterface abgeschlossen ({count} Autos aktualisiert).")
    return RedirectResponse(url="/settings?saved=true", status_code=303)