"""
Módulo de monitoreo de APIs (Service Desk).

Este paquete encapsula todo lo necesario para el "Production Dashboard":
- service.py : lógica de datos (hoy mock, mañana AWS). Es el ÚNICO archivo
               que el equipo de backend debe tocar al conectar datos reales.
- router.py  : el APIRouter con la vista y el endpoint JSON.
- templates/ : la vista HTML (contenido embebible, sin sidebar propia).

Para integrarlo en la app anfitriona basta con:

    from monitoring import monitoring_router
    app.include_router(monitoring_router)
"""

from .router import router as monitoring_router

__all__ = ["monitoring_router"]
