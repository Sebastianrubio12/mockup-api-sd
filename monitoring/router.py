"""
Router del módulo de monitoreo.

Expone:
- GET /production-dashboard          -> la vista HTML (contenido embebible, sin sidebar)
- GET /integration/api/monitoring    -> el JSON de datos que consume la vista

Se integra en la app anfitriona con:

    from monitoring import monitoring_router
    app.include_router(monitoring_router)
"""

import os

from fastapi import APIRouter, Query
from fastapi.responses import FileResponse

from .service import build_monitoring_payload, ALLOWED_RANGE_MINUTES

MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_PATH = os.path.join(MODULE_DIR, "templates", "dashboard.html")

router = APIRouter(tags=["monitoring"])


@router.get("/production-dashboard", include_in_schema=False)
def production_dashboard():
    """Sirve la vista del dashboard (contenido de página, sin sidebar propia)."""
    return FileResponse(TEMPLATE_PATH)


@router.get("/integration/api/monitoring")
def api_monitoring(
    range_minutes: int = Query(
        360,
        description="Ventana histórica en minutos para la gráfica y el event log (5, 15, 30, 60, 180, 360).",
    ),
):
    """
    Endpoint principal del dashboard: devuelve metricas por ENDPOINT/company,
    event log, alarmas y series temporales.

    range_minutes controla la ventana histórica (últimos N minutos, tope 360 = 6h).
    Si llega un valor no permitido, se ajusta al más cercano soportado.

    Al migrar a AWS solo se reemplaza la implementación en service.py; este router
    no cambia (solo reenvía el rango pedido).
    """
    # Saneamos el rango a uno de los permitidos (evita valores arbitrarios).
    if range_minutes not in ALLOWED_RANGE_MINUTES:
        range_minutes = min(ALLOWED_RANGE_MINUTES, key=lambda m: abs(m - range_minutes))

    try:
        # MIENTRAS NO HAY BACKEND: datos de prueba (mock).
        return build_monitoring_payload(range_minutes=range_minutes)
    except Exception as error:
        # Si la conexion a AWS falla, el dashboard lo muestra en un banner rojo.
        return {
            "success": False,
            "message": f"Error de AWS: {str(error)}",
            "range_minutes": range_minutes,
            "endpoints": [],
            "companies": [],
            "event_log": [],
            "alarms": [],
            "series": [],
        }
