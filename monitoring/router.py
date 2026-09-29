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

from fastapi import APIRouter
from fastapi.responses import FileResponse

from .service import build_monitoring_payload

MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_PATH = os.path.join(MODULE_DIR, "templates", "dashboard.html")

router = APIRouter(tags=["monitoring"])


@router.get("/production-dashboard", include_in_schema=False)
def production_dashboard():
    """Sirve la vista del dashboard (contenido de página, sin sidebar propia)."""
    return FileResponse(TEMPLATE_PATH)


@router.get("/integration/api/monitoring")
def api_monitoring():
    """
    Endpoint principal del dashboard: devuelve metricas por ENDPOINT,
    event log, alarmas y series temporales.

    Al migrar a AWS solo se reemplaza la implementación de build_monitoring_payload()
    en service.py; este router no cambia.
    """
    try:
        # MIENTRAS NO HAY BACKEND: datos de prueba (mock).
        return build_monitoring_payload()
    except Exception as error:
        # Si la conexion a AWS falla, el dashboard lo muestra en un banner rojo.
        return {
            "success": False,
            "message": f"Error de AWS: {str(error)}",
            "endpoints": [],
            "event_log": [],
            "alarms": [],
            "series": [],
        }
