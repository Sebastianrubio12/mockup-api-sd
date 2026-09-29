from fastapi import FastAPI
from fastapi.responses import Response, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import os
import random
from datetime import datetime, timedelta
import uvicorn
import boto3  # Importamos la librería de AWS

app = FastAPI(title="API Monitoring Dashboard")

# Permitimos que el frontend (aunque se sirva en otro puerto) consuma la API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --------------------------------------------------------------------------
# CATALOGO DE ENDPOINTS MONITOREADOS
# Refleja las APIs reales de tu dashboard de CloudWatch (RTR, SPOT, E2Open...)
# --------------------------------------------------------------------------
MONITORED_ENDPOINTS = [
    {"name": "RTR API", "path": "/rtr-api/api/novisphere/carrier/", "group": "RTR"},
    {"name": "SPOT API", "path": "/api/rpa/company_id/{id}/calculate/customer_id/", "group": "SPOT"},
    {"name": "E2Open Orchestrator", "path": "/lambda/e2open-orchestrator", "group": "E2OPEN"},
    {"name": "SPOT Mediator", "path": "/spot/mediator/quote", "group": "SPOT"},
    {"name": "Event Processor", "path": "/integration/api/state/feedReadState", "group": "INTEGRATION"},
]

# Tipos de evento / respuesta representativos (NO son una lista de clientes,
# solo ejemplos del tipo de mensaje que produce cada endpoint).
ERROR_SAMPLES = [
    ("MCLEOD_RESPONSE", 403, "Access to this API has been disallowed"),
    ("DAT_RESPONSE", 429, "Your account has been blocked after multiple consecutive login attempts"),
    ("TRANSPLACE_RESPONSE", 400, "Please enter a valid bid amount for auction"),
    ("ARRIVE_RESPONSE", 400, "For multi-stop cross-border shipments, the first and last stops must match"),
    ("E2OPEN_SPOTMARKET_RESPONSE", 400, "Offer is not active"),
    ("SPWAY_TENDER_RESPONSE", 400, "Tender is no longer available for reply"),
    ("DCL_RESPONSE", 200, "Scac not defined for company"),
    ("CA_RESPONSE", 200, "Validation error"),
]


def _mock_company(i):
    """Genera un nombre de company/customer de relleno.

    Es SOLO un placeholder para que la UI tenga datos mientras no hay conexion.
    Al conectar AWS se traeran TODAS las companies/customers reales del dashboard,
    sin lista fija ni filtro.
    """
    return (f"Company {i:03d}", f"Customer {i:03d}")


def build_monitoring_payload():
    """Genera el snapshot de monitoreo por endpoint (simulado hasta conectar AWS)."""
    now = datetime.utcnow()
    endpoints = []

    for ep in MONITORED_ENDPOINTS:
        total_requests = random.randint(800, 9500)
        err_401 = random.randint(0, 250)
        err_400 = random.randint(0, 120)
        err_500 = random.randint(0, 90)
        total_errors = err_401 + err_400 + err_500
        error_rate = round((total_errors / total_requests) * 100, 2) if total_requests else 0
        success_rate = round(100 - error_rate, 2)

        endpoints.append({
            "name": ep["name"],
            "path": ep["path"],
            "group": ep["group"],
            "total_requests": total_requests,
            "errors": {
                "http_401": err_401,
                "http_400": err_400,
                "http_500": err_500,
                "total": total_errors,
            },
            "error_rate": error_rate,
            "success_rate": success_rate,
            "status": "critical" if error_rate > 10 else ("warning" if error_rate > 3 else "healthy"),
        })

    # EVENT LOG: eventos individuales por endpoint
    event_log = []
    for i in range(14):
        summary, status_code, message = random.choice(ERROR_SAMPLES)
        company, customer = _mock_company(random.randint(1, 400))
        event_log.append({
            "timestamp": (now - timedelta(minutes=random.randint(0, 180))).isoformat() + "Z",
            "company_name": company,
            "customer_name": customer,
            "event_summary": summary,
            "status_code": status_code,
            "message": message,
            "error_count": random.randint(1, 200),
        })
    event_log.sort(key=lambda e: e["timestamp"], reverse=True)

    # ALARMAS (como en el panel RTR-SPOT-QUOTING ALARMS)
    alarms = [
        {"name": "RTR 401", "state": "OK", "metric": "RTR 401s"},
        {"name": "RTR_SD400_Threshold", "state": "OK", "metric": "RTR 400s"},
        {"name": "SPOT Api 500 responses or higher", "state": "ALARM" if any(e["errors"]["http_500"] > 60 for e in endpoints) else "OK", "metric": "SPOT 500s"},
        {"name": "SPOT Api >= 400 Threshold Alarm", "state": "OK", "metric": "SPOT 400s"},
    ]

    # Serie temporal para la gráfica de tasa de error/exito (ultimas 12 muestras)
    series = []
    for i in range(12):
        t = now - timedelta(minutes=(11 - i) * 15)
        series.append({
            "time": t.strftime("%H:%M"),
            "error_rate": round(random.uniform(0, 12), 2),
            "success_rate": round(random.uniform(88, 100), 2),
        })

    return {
        "success": True,
        "generated_at": now.isoformat() + "Z",
        "endpoints": endpoints,
        "event_log": event_log,
        "alarms": alarms,
        "series": series,
    }


@app.get("/", include_in_schema=False)
def dashboard():
    # Sirve el dashboard visual en lugar de Swagger
    return FileResponse(os.path.join(BASE_DIR, "dashboard.html"))


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    # Evita el 404 del navegador al pedir el favicon automáticamente
    return Response(status_code=204)


@app.get("/integration/api/monitoring")
def api_monitoring():
    """
    Endpoint principal del dashboard: devuelve metricas por ENDPOINT,
    event log, alarmas y series temporales.

    ================== MIGRACION A AWS (hacer con el equipo de backend) ==================
    El frontend NO cambia. Solo hay que reemplazar la llamada a build_monitoring_payload()
    por datos reales, respetando EXACTAMENTE el mismo formato del diccionario que se
    retorna (endpoints / event_log / alarms / series).

    PASO 0 - Confirmar con backend de donde salen los datos de esos dashboards:
        ¿CloudWatch Metrics? ¿CloudWatch Logs Insights? ¿DynamoDB? Puede ser una mezcla.

    PASO 1 - Autenticacion (perfil local o rol IAM segun defina backend):
        # sesion_aws = boto3.Session(profile_name='servicedesk-dev')

    PASO 2 - Crear el/los cliente(s) segun la fuente elegida:
        # cw    = sesion_aws.client('cloudwatch', region_name='us-east-2')  # metricas/alarmas
        # logs  = sesion_aws.client('logs',       region_name='us-east-2')  # event log (Logs Insights)
        # ddb   = sesion_aws.client('dynamodb',   region_name='us-east-2')  # si viene de una tabla

    PASO 3 - Extraer los datos reales. Ejemplos de por donde iria cada seccion:

        # --- endpoints[] : metricas por API (requests y errores 401/400/500) ---
        # Desde CloudWatch Metrics (get_metric_data) por cada endpoint/namespace.
        #
        # --- alarms[] : estado de las alarmas RTR/SPOT/Quoting ---
        # resp_alarms = cw.describe_alarms(AlarmNamePrefix='RTR')  # o los nombres reales
        # alarms = [{"name": a["AlarmName"], "state": a["StateValue"]}  # OK / ALARM
        #           for a in resp_alarms["MetricAlarms"]]
        #
        # --- event_log[] : eventos del EVENT LOG (company, status_code, message...) ---
        # Con CloudWatch Logs Insights:
        # q = logs.start_query(
        #     logGroupName='NOMBRE_LOG_GROUP_REAL',
        #     startTime=int((datetime.utcnow()-timedelta(hours=3)).timestamp()),
        #     endTime=int(datetime.utcnow().timestamp()),
        #     queryString='fields @timestamp, company_name, customer_name, event.summary, '
        #                 'event.record.status_code, message, error_count | sort @timestamp desc',
        # )
        # ... poll get_query_results(queryId=q["queryId"]) hasta status Complete ...
        #
        # --- series[] : tasa de error/exito en el tiempo (para la grafica) ---
        # Se arma con get_metric_data agregando por intervalos de tiempo.

    PASO 4 - Mapear el resultado crudo al MISMO formato que build_monitoring_payload()
             y retornarlo. La estructura esperada por el dashboard es:
        {
          "success": True,
          "endpoints": [ {name, path, group, total_requests,
                          errors:{http_401,http_400,http_500,total},
                          error_rate, success_rate, status}, ... ],
          "event_log": [ {timestamp, company_name, customer_name,
                          event_summary, status_code, message, error_count}, ... ],
          "alarms":    [ {name, state}, ... ],           # state: "OK" | "ALARM"
          "series":    [ {time, error_rate, success_rate}, ... ],
        }
    ======================================================================================
    """
    try:
        # MIENTRAS NO HAY BACKEND: datos de prueba (mock).
        # Al migrar, borra la linea de abajo y retorna el payload real ya mapeado.
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


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
