from datetime import datetime
from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from app.database.repository import DatabaseRepository
from app.services.search import SearchService
from fastapi.responses import Response
from app.services.pdf_export import PdfExportService

router = APIRouter()
templates = Jinja2Templates(directory="app/web/templates")
repo = DatabaseRepository()
search_service = SearchService(repo)

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

@router.get("/car/{car_id}", response_class=HTMLResponse)
async def car_details(request: Request, car_id: int):
    car = repo.get_car_by_id(car_id)
    if not car:
        return HTMLResponse(content="Fahrzeug nicht gefunden", status_code=404)

    price_history = repo.get_price_history(car_id)
    first_dt = datetime.strptime(car.first_seen, "%Y-%m-%d %H:%M:%S") if car.first_seen else datetime.utcnow()
    days_online = max(1, (datetime.utcnow() - first_dt).days)
    price_metrics = search_service.price_service.calculate_price_metrics(price_history, car.price)

    return templates.TemplateResponse("car_detail.html", {
        "request": request,
        "car": car,
        "price_history": price_history,
        "days_online": days_online,
        "price_metrics": price_metrics
    })

@router.get("/compare", response_class=HTMLResponse)
async def compare_cars(request: Request, id1: int = Query(None), id2: int = Query(None)):
    all_cars = repo.get_all_cars(only_active=True, canonical_only=True)
    car1 = repo.get_car_by_id(id1) if id1 else (all_cars[0] if len(all_cars) > 0 else None)
    car2 = repo.get_car_by_id(id2) if id2 else (all_cars[1] if len(all_cars) > 1 else None)

    comparison_results = {}
    if car1 and car2:
        wins_c1, wins_c2 = [], []
        if car1.price < car2.price: wins_c1.append(f"Günstigerer Anschaffungspreis (-{int(car2.price - car1.price):,} EUR)")
        elif car2.price < car1.price: wins_c2.append(f"Günstigerer Anschaffungspreis (-{int(car1.price - car2.price):,} EUR)")

        if car1.mileage < car2.mileage: wins_c1.append(f"Geringere Laufleistung (-{car2.mileage - car1.mileage:,} km)")
        elif car2.mileage < car1.mileage: wins_c2.append(f"Geringere Laufleistung (-{car1.mileage - car2.mileage:,} km)")

        if car1.power_hp > car2.power_hp: wins_c1.append(f"Höhere Motorleistung (+{car1.power_hp - car2.power_hp} PS)")
        elif car2.power_hp > car1.power_hp: wins_c2.append(f"Höhere Motorleistung (+{car2.power_hp - car1.power_hp} PS)")

        if car1.distance_km < car2.distance_km: wins_c1.append(f"Geringere Distanz (-{round(car2.distance_km - car1.distance_km, 1)} km)")
        elif car2.distance_km < car1.distance_km: wins_c2.append(f"Geringere Distanz (-{round(car1.distance_km - car2.distance_km, 1)} km)")

        if car1.deal_score > car2.deal_score: wins_c1.append(f"Besserer Gesamt-Deal-Score ({car1.deal_score} vs {car2.deal_score})")
        elif car2.deal_score > car1.deal_score: wins_c2.append(f"Besserer Gesamt-Deal-Score ({car2.deal_score} vs {car1.deal_score})")

        comparison_results = {
            "wins_car1": wins_c1,
            "wins_car2": wins_c2,
            "overall_winner": car1 if car1.deal_score >= car2.deal_score else car2
        }

    return templates.TemplateResponse("compare.html", {
        "request": request,
        "all_cars": all_cars,
        "car1": car1,
        "car2": car2,
        "comparison": comparison_results
    })

@router.post("/api/favorite/{car_id}")
async def toggle_favorite(car_id: int):
    new_status = repo.toggle_favorite(car_id)
    return {"success": True, "is_favorite": new_status}

@router.post("/api/search-now")
async def trigger_search():
    search_service.run_search_pipeline()
    return RedirectResponse(url="/", status_code=303)

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
    
    # Dateiname formatieren (z.B. auto-agent-bmw-128ti-101.pdf)
    safe_title = f"{car.make}-{car.model}-{car.id}".replace(" ", "_").lower()
    filename = f"auto-agent-{safe_title}.pdf"

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

    # Identische Sieger-Logik wie in compare_cars
    wins_c1, wins_c2 = [], []
    if car1.price < car2.price: wins_c1.append(f"Günstigerer Anschaffungspreis (-{int(car2.price - car1.price):,} EUR)")
    elif car2.price < car1.price: wins_c2.append(f"Günstigerer Anschaffungspreis (-{int(car1.price - car2.price):,} EUR)")

    if car1.mileage < car2.mileage: wins_c1.append(f"Geringere Laufleistung (-{car2.mileage - car1.mileage:,} km)")
    elif car2.mileage < car1.mileage: wins_c2.append(f"Geringere Laufleistung (-{car1.mileage - car2.mileage:,} km)")

    if car1.power_hp > car2.power_hp: wins_c1.append(f"Höhere Motorleistung (+{car1.power_hp - car2.power_hp} PS)")
    elif car2.power_hp > car1.power_hp: wins_c2.append(f"Höhere Motorleistung (+{car2.power_hp - car1.power_hp} PS)")

    if car1.distance_km < car2.distance_km: wins_c1.append(f"Geringere Distanz (-{round(car2.distance_km - car1.distance_km, 1)} km)")
    elif car2.distance_km < car1.distance_km: wins_c2.append(f"Geringere Distanz (-{round(car1.distance_km - car2.distance_km, 1)} km)")

    if car1.deal_score > car2.deal_score: wins_c1.append(f"Besserer Gesamt-Deal-Score ({car1.deal_score} vs {car2.deal_score})")
    elif car2.deal_score > car1.deal_score: wins_c2.append(f"Besserer Gesamt-Deal-Score ({car2.deal_score} vs {car1.deal_score})")

    comparison_results = {
        "wins_car1": wins_c1,
        "wins_car2": wins_c2,
        "overall_winner": car1 if car1.deal_score >= car2.deal_score else car2
    }

    pdf_bytes = PdfExportService.generate_comparison_report(car1, car2, comparison_results)
    
    filename = f"vergleich-{car1.make}-{car1.model}-vs-{car2.make}-{car2.model}.pdf".replace(" ", "_").lower()

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )