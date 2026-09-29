"""
Capa de datos del dashboard de monitoreo.

================== MIGRACION A AWS (hacer con el equipo de backend) ==================
Este es el ÚNICO archivo que hay que tocar al conectar datos reales. El frontend
(templates/dashboard.html) y el router NO cambian: solo hay que reemplazar el
cuerpo de build_monitoring_payload() por datos reales, respetando EXACTAMENTE el
mismo formato del diccionario que se retorna (endpoints / event_log / alarms / series).

PASO 0 - Confirmar con backend de donde salen los datos de esos dashboards:
    ¿CloudWatch Metrics? ¿CloudWatch Logs Insights? ¿DynamoDB? Puede ser una mezcla.

PASO 1 - Autenticacion (perfil local o rol IAM segun defina backend):
    # sesion_aws = boto3.Session(profile_name='servicedesk-dev')

PASO 2 - Crear el/los cliente(s) segun la fuente elegida:
    # cw    = sesion_aws.client('cloudwatch', region_name='us-east-2')  # metricas/alarmas
    # logs  = sesion_aws.client('logs',       region_name='us-east-2')  # event log (Logs Insights)
    # ddb   = sesion_aws.client('dynamodb',   region_name='us-east-2')  # si viene de una tabla

PASO 3 - Extraer los datos reales (endpoints, alarms, event_log, series) y mapearlos
         al MISMO formato que build_monitoring_payload().
======================================================================================
"""

import random
from datetime import datetime, timedelta

# import boto3  # <- descomentar al conectar AWS


# --------------------------------------------------------------------------
# CATALOGO DE ENDPOINTS MONITOREADOS
# Refleja las APIs reales del dashboard de CloudWatch (RTR, SPOT, E2Open...)
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
    for _ in range(14):
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

    # Serie temporal para la grafica de tasa de error/exito (ultimas 12 muestras)
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
