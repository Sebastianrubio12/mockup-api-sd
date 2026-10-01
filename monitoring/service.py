"""
Capa de datos del dashboard de monitoreo.

================== MIGRACION A AWS (hacer con el equipo de backend) ==================
Este es el ÚNICO archivo que hay que tocar al conectar datos reales. El frontend
(templates/dashboard.html) y el router NO cambian: solo hay que reemplazar el
cuerpo de _generate_monitoring_payload() por datos reales, respetando EXACTAMENTE
el mismo formato del diccionario que se retorna
(endpoints / companies / event_log / alarms / series).

PASO 0 - Confirmar con backend de donde salen los datos de esos dashboards:
    ¿CloudWatch Metrics? ¿CloudWatch Logs Insights? ¿DynamoDB? Puede ser una mezcla.

PASO 1 - Autenticacion (perfil local o rol IAM segun defina backend):
    # sesion_aws = boto3.Session(profile_name='servicedesk-dev')

PASO 2 - Crear el/los cliente(s) segun la fuente elegida:
    # cw    = sesion_aws.client('cloudwatch', region_name='us-east-2')  # metricas/alarmas
    # logs  = sesion_aws.client('logs',       region_name='us-east-2')  # event log (Logs Insights)
    # ddb   = sesion_aws.client('dynamodb',   region_name='us-east-2')  # si viene de una tabla

PASO 3 - Extraer los datos reales y mapearlos al MISMO formato que
         _generate_monitoring_payload().

--------------------------------------------------------------------------------------
FILTRO POR API / POR COMPANY (lo que pidio el jefe)
--------------------------------------------------------------------------------------
El dashboard permite ver los servicios de dos formas:
  - "Todas las APIs" (general): muestra TODOS los servicios, con sus metricas
    consolidadas (la suma de todas las companies).
  - "Por company": al elegir una company, muestra SOLO las APIs que esa company
    usa, con las metricas de ESA company.

Para soportarlo, el payload trae:
  - endpoints[]: metricas GLOBALES por API (modo "Todas las APIs").
  - companies[]: por cada company, la lista de APIs que usa y sus metricas
    (modo "Por company"). El filtrado ocurre en el frontend a partir de esto,
    asi que no hay que llamar a AWS de nuevo al cambiar el filtro.

Al conectar AWS, backend debe poder desglosar las metricas por company. En
CloudWatch eso normalmente se logra con una dimension "CompanyId"/"Customer"
en las metricas, o agrupando en Logs Insights por company_name.
======================================================================================
"""

import random
import threading
import time
from datetime import datetime, timedelta

# import boto3  # <- descomentar al conectar AWS


# --------------------------------------------------------------------------
# CACHE EN MEMORIA (clave para el COSTO al conectar AWS)
# --------------------------------------------------------------------------
# El frontend refresca en intervalos y puede haber varios usuarios/pestañas
# abiertos a la vez. Sin caché, CADA request golpearía CloudWatch/Logs Insights
# y eso se paga por consulta. Con la caché, AWS se consulta como mucho una vez
# cada CACHE_TTL_SECONDS sin importar cuántos clientes pidan datos.
#
# CloudWatch agrega métricas por minuto, así que un TTL de ~25-30s da datos
# "frescos" sin costo extra. Ajustable según lo que definan con backend.
CACHE_TTL_SECONDS = 25

# Rangos históricos que ofrece el selector, EN MINUTOS. Permite ventanas cortas
# (5, 15, 30 min) además de las largas (1h=60, 3h=180, 6h=360). TOPE = 6 horas:
# el jefe no quiere ver más allá de las últimas 6h. 6h es el valor por defecto.
ALLOWED_RANGE_MINUTES = [5, 15, 30, 60, 180, 360]
DEFAULT_RANGE_MINUTES = 360

# La caché es POR RANGO: cada ventana (5m, 15m, 1h, 6h...) se cachea aparte
# porque son consultas distintas a AWS. Cambiar de rango no invalida los demás.
_cache_lock = threading.Lock()
_cache = {}  # range_minutes -> {"payload": ..., "expires_at": ...}


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

# Companies de ejemplo (placeholder). Al conectar AWS, esta lista sale de los
# datos reales; NO es una lista fija. Cada company usa un subconjunto de APIs.
MOCK_COMPANIES = [
    "Ryan Transportation",
    "Ardentx",
    "Venture Logistics",
    "Trinity Logistics",
    "The Crane",
    "Motus Freight",
    "Mode Global",
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


def _status_for(error_rate):
    return "critical" if error_rate > 10 else ("warning" if error_rate > 3 else "healthy")


def _endpoint_metrics(ep, scale=1.0):
    """Genera métricas simuladas para una API.

    'scale' permite que las métricas por-company sean más pequeñas que las
    globales (una company es una porción del tráfico total de la API).
    """
    total_requests = max(1, int(random.randint(800, 9500) * scale))
    err_401 = int(random.randint(0, 250) * scale)
    err_400 = int(random.randint(0, 120) * scale)
    err_500 = int(random.randint(0, 90) * scale)
    total_errors = err_401 + err_400 + err_500
    error_rate = round((total_errors / total_requests) * 100, 2) if total_requests else 0
    success_rate = round(100 - error_rate, 2)
    return {
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
        "status": _status_for(error_rate),
    }


def build_monitoring_payload(range_minutes=DEFAULT_RANGE_MINUTES):
    """Punto de entrada CON CACHÉ que usa el router.

    range_minutes es la ventana histórica pedida (5, 15, 30, 60, 180 o 360).
    Devuelve el snapshot cacheado de ESE rango si sigue vigente; si expiró, lo
    regenera una sola vez (protegido por lock para que ráfagas de requests
    concurrentes no disparen varias consultas a AWS a la vez).

    Al conectar AWS, lo pesado (las llamadas a CloudWatch/Logs) vive dentro de
    _generate_monitoring_payload(); esta capa de caché las amortigua tal cual.
    """
    # Blindaje: si llega algo fuera de lo permitido, caemos al más cercano.
    if range_minutes not in ALLOWED_RANGE_MINUTES:
        range_minutes = min(ALLOWED_RANGE_MINUTES, key=lambda m: abs(m - range_minutes))

    now_ts = time.time()

    # Camino rápido: caché vigente para este rango, sin lock (lectura barata).
    entry = _cache.get(range_minutes)
    if entry and now_ts < entry["expires_at"]:
        return entry["payload"]

    with _cache_lock:
        # Re-chequeo dentro del lock: otro hilo pudo haber refrescado ya.
        now_ts = time.time()
        entry = _cache.get(range_minutes)
        if entry and now_ts < entry["expires_at"]:
            return entry["payload"]

        payload = _generate_monitoring_payload(range_minutes)
        _cache[range_minutes] = {"payload": payload, "expires_at": now_ts + CACHE_TTL_SECONDS}
        return payload


def _generate_monitoring_payload(range_minutes=DEFAULT_RANGE_MINUTES):
    """Genera el snapshot de monitoreo (simulado hasta conectar AWS).

    range_minutes acota el histórico: la serie temporal y el event log cubren
    los últimos 'range_minutes' minutos.

    AQUÍ es donde, al migrar, irán las consultas reales a AWS. Todo lo caro
    (CloudWatch / Logs Insights / DynamoDB) va dentro de esta función; la caché
    de build_monitoring_payload() se encarga de no llamarla en cada request.
    Al conectar AWS, 'range_minutes' define el startTime/endTime de las consultas
    (CloudWatch get_metric_data / Logs Insights start_query).
    """
    now = datetime.utcnow()
    window_minutes = range_minutes

    # 1) MÉTRICAS GLOBALES POR API (modo "Todas las APIs")
    endpoints = [_endpoint_metrics(ep) for ep in MONITORED_ENDPOINTS]

    # 2) MÉTRICAS POR COMPANY (modo "Por company")
    #    Cada company usa un subconjunto de las APIs. Para el mock repartimos
    #    APIs al azar; al conectar AWS esto sale de los datos reales.
    companies = []
    for company_name in MOCK_COMPANIES:
        # entre 2 y todas las APIs, elegidas al azar (subconjunto de esta company)
        k = random.randint(2, len(MONITORED_ENDPOINTS))
        used_apis = random.sample(MONITORED_ENDPOINTS, k)
        # scale < 1: una company es una porción del tráfico total de cada API
        company_endpoints = [_endpoint_metrics(ep, scale=random.uniform(0.08, 0.4)) for ep in used_apis]
        companies.append({
            "name": company_name,
            "endpoints": company_endpoints,
        })
    companies.sort(key=lambda c: c["name"])

    # 3) EVENT LOG: eventos individuales dentro de la ventana histórica pedida.
    #    Más eventos si el rango es más amplio (escala con los minutos, acotado).
    event_count = min(40, max(5, 6 + window_minutes // 20))
    event_log = []
    for _ in range(event_count):
        summary, status_code, message = random.choice(ERROR_SAMPLES)
        company = random.choice(MOCK_COMPANIES)
        event_log.append({
            "timestamp": (now - timedelta(minutes=random.randint(0, window_minutes))).isoformat() + "Z",
            "company_name": company,
            "customer_name": f"Customer {random.randint(1, 400):03d}",
            "event_summary": summary,
            "status_code": status_code,
            "message": message,
            "error_count": random.randint(1, 200),
        })
    event_log.sort(key=lambda e: e["timestamp"], reverse=True)

    # 4) ALARMAS (como en el panel RTR-SPOT-QUOTING ALARMS)
    alarms = [
        {"name": "RTR 401", "state": "OK", "metric": "RTR 401s"},
        {"name": "RTR_SD400_Threshold", "state": "OK", "metric": "RTR 400s"},
        {"name": "SPOT Api 500 responses or higher", "state": "ALARM" if any(e["errors"]["http_500"] > 60 for e in endpoints) else "OK", "metric": "SPOT 500s"},
        {"name": "SPOT Api >= 400 Threshold Alarm", "state": "OK", "metric": "SPOT 400s"},
    ]

    # 5) Serie temporal para la grafica de tasa de error/exito, cubriendo TODA
    #    la ventana histórica pedida. Usamos ~12 puntos siempre (el intervalo
    #    entre muestras crece con el rango: 1h -> 5min, 6h -> 30min).
    points = 12
    step_minutes = window_minutes / points
    # En ventanas cortas (<30 min) los puntos caen dentro del mismo minuto, así
    # que mostramos HH:MM:SS para que las etiquetas no se repitan; en ventanas
    # largas basta HH:MM.
    time_fmt = "%H:%M:%S" if window_minutes < 30 else "%H:%M"
    series = []
    for i in range(points):
        t = now - timedelta(minutes=(points - 1 - i) * step_minutes)
        series.append({
            "time": t.strftime(time_fmt),
            "error_rate": round(random.uniform(0, 12), 2),
            "success_rate": round(random.uniform(88, 100), 2),
        })

    return {
        "success": True,
        "generated_at": now.isoformat() + "Z",
        "range_minutes": range_minutes,
        "endpoints": endpoints,
        "companies": companies,
        "event_log": event_log,
        "alarms": alarms,
        "series": series,
    }
