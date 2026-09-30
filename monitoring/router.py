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

from .service import build_monitoring_payload, ALLOWED_RANGE_HOURS

MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_PATH = os.path.join(MODULE_DIR, "templates", "dashboard.html")

router = APIRouter(tags=["monitoring"])


@router.get("/production-dashboard", include_in_schema=False)
def production_dashboard():
    """Sirve la vista del dashboard (contenido de página, sin sidebar propia)."""
    return FileResponse(TEMPLATE_PATH)


@router.get("/integration/api/monitoring")
def api_monitoring(
    range_hours: int = Query(
        6,
        description="Ventana histórica en horas para la gráfica y el event log (1, 3, 6, 12, 24).",
    ),
):
    """
    Endpoint principal del dashboard: devuelve metricas por ENDPOINT/company,
    event log, alarmas y series temporales.

    range_hours controla la ventana histórica (histórico de las últimas N horas).
    Si llega un valor no permitido, se ajusta al más cercano soportado.

    Al migrar a AWS solo se reemplaza la implementación en service.py; este router
    no cambia (solo reenvía el rango pedido).
    """
    # Saneamos el rango a uno de los permitidos (evita valores arbitrarios).
    if range_hours not in ALLOWED_RANGE_HOURS:
        range_hours = min(ALLOWED_RANGE_HOURS, key=lambda h: abs(h - range_hours))

    try:
        # MIENTRAS NO HAY BACKEND: datos de prueba (mock).
        return build_monitoring_payload(range_hours=range_hours)
    except Exception as error:
        # Si la conexion a AWS falla, el dashboard lo muestra en un banner rojo.
        return {
            "success": False,
            "message": f"Error de AWS: {str(error)}",
            "range_hours": range_hours,
            "endpoints": [],
            "companies": [],
            "event_log": [],
            "alarms": [],
            "series": [],
        }
