"""
Punto de arranque para ejecutar el dashboard de monitoreo de forma LOCAL (demo).

En la app real "Service Desk Management", este archivo NO se usa: allá basta con
incluir el router del módulo dentro de la app existente:

    from monitoring import monitoring_router
    app.include_router(monitoring_router)

Aquí montamos una mini-app solo para poder verlo y aprobarlo de forma aislada.
"""

import os

from fastapi import FastAPI
from fastapi.responses import RedirectResponse, Response
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from monitoring import monitoring_router

app = FastAPI(title="Service Desk · Production Dashboard (demo local)")

# Permitimos que el frontend (aunque se sirva en otro puerto) consuma la API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# El módulo de monitoreo aporta la vista y el endpoint de datos.
app.include_router(monitoring_router)


@app.get("/", include_in_schema=False)
def home():
    # En la demo, la raíz redirige a la vista del módulo.
    return RedirectResponse(url="/production-dashboard")


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    # Evita el 404 del navegador al pedir el favicon automáticamente.
    return Response(status_code=204)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
