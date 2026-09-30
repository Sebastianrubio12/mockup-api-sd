# Production Dashboard · Módulo de Monitoreo de APIs (Service Desk)

Documento de resumen del proyecto para revisión con el equipo.

---

## 1. Qué se construyó

Un **módulo** de dashboard para monitorear el estado de los endpoints/APIs
(RTR, SPOT, E2Open, etc.), pensado para vivir **dentro de la app
"Service Desk Management"** como una página más (el item "Production Dashboard"
de la barra lateral), como alternativa a las pantallas de AWS CloudWatch.

Está diseñado como **módulo enchufable**, no como app independiente:

- **La app anfitriona ya aporta su sidebar y su topbar.** Por eso este módulo
  es solo el **contenido de la página** (no trae navegación propia).
- Toda la lógica de datos (lo que conectará a AWS) queda **aislada en un solo
  archivo** para que el equipo de backend sepa exactamente qué tocar.

> ⚠️ **Este repo es una PARTE AISLADA a propósito.** Es un mockup/prototipo
> autónomo que sirve para revisar y aprobar el diseño **antes** de meterlo al
> Service Desk. Está construido para **migrar sin fricción** al módulo principal:
> nada aquí asume que es una app suelta, y todo lo específico de la demo
> (`main.py`) está separado de lo que sí viaja al Service Desk (`monitoring/`).

---

## 0. Principios de adaptabilidad (por qué migra sin dolor)

El módulo se hizo siguiendo estas reglas para que integrarlo al Service Desk sea
copiar la carpeta `monitoring/` y añadir una línea:

1. **Todo lo que migra vive en `monitoring/`.** Es un paquete autocontenido
   (router + servicio + template). `main.py` NO forma parte del módulo: es solo
   el arranque de la demo y se descarta al integrar.
2. **Contrato de datos único y estable.** La vista solo depende del JSON de
   `/integration/api/monitoring`. Mientras `service.py` respete ese formato, se
   puede cambiar la fuente (mock → CloudWatch → DynamoDB) sin tocar nada más.
3. **Frontend aislado del anfitrión.** El HTML se monta dentro de
   `<div class="pd-root">` y **todos los estilos llevan prefijo `.pd-`**, así no
   pisan ni son pisados por el CSS del Service Desk. No hay estilos globales.
4. **Sin navegación propia.** No hay sidebar ni topbar: es contenido de página,
   para caer directo en el área de contenido del Service Desk.
5. **Rutas agrupadas en un `APIRouter`.** Se integran con una sola llamada
   `include_router`, sin tocar el `main` del Service Desk salvo esa línea.
6. **Único estado compartido: una caché en memoria acotada.** La única memoria
   compartida es la caché con TTL de `service.py` (ver sección 6), pensada para
   no golpear AWS en cada request. Es autocontenida, sin dependencias externas
   (ni Redis ni similar) y fácil de mover o testear.

---

## 2. Estructura del proyecto

```
mockup-sd-API/
├── main.py                     # Arranque SOLO para demo local (no se usa en la app real)
├── monitoring/                 # ← EL MÓDULO
│   ├── __init__.py             # Expone monitoring_router
│   ├── router.py               # Rutas: la vista + el endpoint JSON
│   ├── service.py              # Lógica de datos (mock hoy → AWS mañana)
│   └── templates/
│       └── dashboard.html      # La vista (contenido de página, sin sidebar)
├── requirements.txt
└── README.md
```

Responsabilidad de cada pieza:

| Archivo                          | Qué hace                                                        | ¿Lo toca backend al conectar AWS? |
|----------------------------------|-----------------------------------------------------------------|-----------------------------------|
| `monitoring/service.py`          | Genera los datos de monitoreo (hoy simulados)                   | **Sí, este es el único**          |
| `monitoring/router.py`           | Expone la vista y el endpoint `/integration/api/monitoring`     | No                                |
| `monitoring/templates/dashboard.html` | La interfaz visual                                         | No                                |
| `main.py`                        | Levanta una mini-app para ver el módulo aislado (demo)          | No (en la app real ni se usa)     |

---

## 2.1. Cómo funciona cada módulo por dentro

Explicación pieza por pieza de qué hace cada archivo y cómo se conectan entre sí.
El flujo de una petición es: **navegador → `router.py` → `service.py` → JSON →
`dashboard.html` repinta**.

### `monitoring/__init__.py` — la puerta del paquete

Es lo que convierte la carpeta `monitoring/` en un paquete importable y **expone
una sola cosa hacia afuera**: `monitoring_router`. Gracias a esto, la app
anfitriona solo necesita `from monitoring import monitoring_router` sin conocer la
estructura interna. Todo lo demás (service, template) queda encapsulado.

### `monitoring/router.py` — las rutas (capa web)

Define un `APIRouter` con **dos endpoints** y nada de lógica de datos:

- `GET /production-dashboard` → devuelve el archivo `dashboard.html` (la vista que
  se enlaza al item de la sidebar del Service Desk).
- `GET /integration/api/monitoring` → llama a `build_monitoring_payload()` y
  devuelve el JSON. Si esa llamada falla, en vez de romper responde un JSON con
  `success: false` y listas vacías, y el frontend muestra un banner rojo.

Es una capa fina a propósito: **no sabe de dónde salen los datos**, solo los pide
y los entrega. Por eso no se toca al conectar AWS.

### `monitoring/service.py` — los datos (capa de negocio)

El corazón del módulo y **el único archivo que backend toca al conectar AWS**.
Tiene tres partes:

1. **`build_monitoring_payload()` — capa de caché.** Es la que llama el router.
   Si hay un snapshot en caché vigente (TTL 25 s) lo devuelve al instante; si
   expiró, regenera **una sola vez** (protegido con lock para que varias
   peticiones simultáneas no disparen varias consultas a AWS). Esta capa es la
   que controla el costo. **No se toca al migrar.**
2. **`_generate_monitoring_payload()` — armado del snapshot.** Hoy genera datos
   simulados (endpoints, event log, alarmas, series). **Aquí** es donde irán las
   consultas reales a CloudWatch / Logs Insights / DynamoDB al migrar, respetando
   el mismo formato de retorno.
3. **Catálogo y helpers** (`MONITORED_ENDPOINTS`, `ERROR_SAMPLES`, `_mock_company`):
   definen qué servicios se muestran y generan datos de relleno realistas
   mientras no hay AWS.

### `monitoring/templates/dashboard.html` — la vista (capa de presentación)

Todo el frontend en un solo archivo (HTML + CSS + JS), pensado para **embeberse**
dentro del Service Desk:

- **HTML/CSS:** el contenido de la página, sin sidebar (la app anfitriona la
  aporta). Todos los estilos van prefijados con `.pd-` para no chocar con el tema
  del Service Desk.
- **JS de render:** funciones `pdRender*` que reciben el JSON y pintan cada bloque
  (health strip con el **hex-grid adaptativo**, KPIs, gráfica, alarmas, lista de
  servicios y tabla de event log). Todo se ajusta solo a la cantidad de datos.
- **JS de refresco:** `pdLoadData()` pide el JSON cada 30 s con anti-solapamiento,
  timeout, backoff ante errores y pausa cuando la pestaña no está visible
  (ver sección 6).

### `main.py` — arranque SOLO para la demo local

Levanta una mini-app FastAPI, activa CORS, monta el `monitoring_router` y hace que
la raíz `/` redirija al dashboard. Sirve para **ver y aprobar el módulo aislado**.
**No forma parte del módulo** y se descarta al integrar al Service Desk (allá el
router se monta en la app existente).

---

## 3. Cómo se integra en la app real

En la app "Service Desk Management" **no se usa `main.py`**. Basta con incluir el
router del módulo dentro de la app existente:

```python
from monitoring import monitoring_router

app.include_router(monitoring_router)
```

Eso registra automáticamente:

- `GET /production-dashboard` → la vista del dashboard (para el item de la sidebar).
- `GET /integration/api/monitoring` → el JSON que consume la vista.

Notas de integración del frontend:

- La vista está construida como **contenido embebible**: todo el HTML vive dentro
  de `<div class="pd-root">` y **todos los estilos están prefijados con `.pd-`**
  para no colisionar con los estilos de la app anfitriona.
- La paleta de colores está alineada con la app (azul-marino + acento azul/púrpura),
  no con un tema externo.

---

## 4. Qué muestra el dashboard (y la idea de cada sección)

El dashboard está ordenado de **arriba hacia abajo por nivel de detalle**: primero
el pantallazo general (¿está todo bien?) y luego se va bajando al detalle (¿qué
servicio, qué error, qué evento?). La idea es que en 3 segundos sepas si hay
problema, y si lo hay, puedas bajar a ver dónde.

- **Health strip (arriba del todo) — "¿está todo bien de un vistazo?"**
  Un **hex-grid adaptativo estilo Dynatrace**: un hexágono por servicio, coloreado
  verde/amarillo/rojo según su estado, más el % de salud global y el conteo de
  Healthy / Degradados / Críticos. **Idea:** dar el semáforo general del entorno
  sin leer números. Si todo está verde, no hay que mirar más abajo. El panal se
  arma solo según cuántos servicios haya (sin huecos) y no se deforma.

- **Fila de KPIs — "los números clave en grande."**
  Servicios monitoreados, requests totales, errores totales, tasa de error
  promedio y alarmas activas. **Idea:** las 5 métricas que resumen el estado en
  cifras, para acompañar el semáforo de arriba con magnitudes concretas.

- **Gráfica de error vs éxito — "¿esto viene mejorando o empeorando?"**
  La tasa de error y la de éxito a lo largo del tiempo (últimos ~180 min).
  **Idea:** dar contexto de tendencia. Un 5% de error no es lo mismo si venía
  subiendo que si ya está bajando; la gráfica muestra esa dirección.

- **Panel de alarmas (RTR, SPOT, Quoting) — "¿saltó algo que ya vigilábamos?"**
  Lista de alarmas con estado `OK` o `ALARM`. **Idea:** reflejar las alarmas que
  el equipo ya definió como importantes (las mismas de CloudWatch), para no tener
  que interpretar métricas crudas: si algo crítico se rompe, aquí se pone en rojo.

- **Lista de servicios monitoreados — "¿cuál servicio es el que falla?"**
  Una fila por endpoint con su estado, tasa de error, barra de éxito y desglose de
  códigos HTTP (401/400/500). **Idea:** el nivel de detalle por servicio. Cuando
  el health strip marca rojo, aquí identificas exactamente qué endpoint y con qué
  tipo de error (auth, cliente o servidor).

- **Tabla de Event Log (abajo) — "¿qué pasó exactamente y a quién?"**
  Eventos recientes con company, customer, tipo de evento, código de estado,
  mensaje y número de errores. **Idea:** el máximo detalle, evento por evento,
  para investigar un caso puntual (qué cliente, qué mensaje devolvió la API).

---

## 5. Estado actual: datos de prueba, no reales todavía

Hoy el dashboard funciona con **datos simulados (mock)**, generados en
`monitoring/service.py`. Los números son aleatorios para que la interfaz se vea
completa y funcional. Esto sirve para **revisar y aprobar el diseño** antes de
conectar la fuente real.

> La migración de datos reales está **pendiente a propósito**. Se hará junto con
> el equipo de backend, porque primero hay que definir de dónde salen exactamente
> esos datos en AWS.

---

## 6. Cómo funciona el "Actualizar" (optimizado para el costo de AWS)

El refresco está pensado en **dos capas** para que la página cargue rápido y se
sienta viva, pero **sin disparar la factura de AWS** cuando haya muchos servicios
o varios usuarios con el dashboard abierto.

**Frontend (cuántas veces se pide):**

- Auto-refresh cada **30 segundos** (antes 10 s). CloudWatch agrega métricas por
  minuto, así que pedir cada 10 s no daba datos nuevos y sí multiplicaba el costo.
- **Se pausa cuando la pestaña no está visible** y reanuda al volver: nadie
  mirando = cero consultas a AWS.
- **No solapa peticiones** (si una sigue en curso, no lanza otra) y el botón
  "Actualizar" se deshabilita mostrando "Actualizando…".
- **Timeout de 12 s** por petición: una llamada colgada no traba el ciclo.
- **Backoff exponencial** si la API falla (hasta 5 min): no sigue pegando cada
  30 s contra un endpoint caído (que en AWS igual costaría).

**Backend (que cada petición NO golpee AWS) — lo que de verdad controla el costo:**

- `service.py` guarda el último snapshot en una **caché en memoria con TTL de
  25 s**. Aunque 1 o 50 pestañas refresquen, AWS se consulta **como máximo una
  vez cada 25 s**. El costo deja de escalar con el número de usuarios.
- La caché usa un **lock**: si llegan varias peticiones justo al expirar, solo
  una regenera y las demás reusan ese resultado (evita ráfagas de consultas
  simultáneas a CloudWatch).

Los dos tiempos son ajustables: `PD_REFRESH_MS` en `dashboard.html` (frontend) y
`CACHE_TTL_SECONDS` en `service.py` (backend).

**Alcance (importante):** el frontend **no limita** cuántos datos muestra. Pinta
*todo* lo que el backend le entregue. Hoy el mock manda una muestra pequeña, pero
cuando se conecte AWS y lleguen todos los endpoints reales, el dashboard los
mostrará **todos automáticamente**, sin cambiar nada en la interfaz. Tablas, KPIs
y el hex-grid se ajustan solos a la cantidad de datos recibidos.

> **Aclaración honesta:** no es tiempo real. Es un refresco cada 30 s con una
> caché de 25 s detrás. Cuando se conecte AWS será "casi en vivo" con datos
> verdaderos, y esos intervalos se pueden subir o bajar según se necesite.

---

## 7. Qué falta (el trabajo con backend)

Solo hay que trabajar dentro de **`monitoring/service.py`**, en la función
`_generate_monitoring_payload()` (es la que arma el snapshot; ahí van las
consultas reales a AWS). Ahí quedó documentado, paso a paso, dónde y cómo se
conectará. El objetivo es reemplazar los datos de prueba por datos reales
respetando **exactamente el mismo formato** del diccionario que se retorna.

> **No tocar `build_monitoring_payload()`:** esa es la capa de caché (sección 6)
> que envuelve a `_generate_monitoring_payload()` y amortigua el costo de AWS.
> El router y el frontend siguen llamando a `build_monitoring_payload()` sin
> enterarse del cambio de fuente.

Formato esperado por el dashboard (no cambiar las llaves):

```python
{
  "success": True,
  "endpoints": [ {name, path, group, total_requests,
                  errors:{http_401,http_400,http_500,total},
                  error_rate, success_rate, status}, ... ],
  "event_log": [ {timestamp, company_name, customer_name,
                  event_summary, status_code, message, error_count}, ... ],
  "alarms":    [ {name, state, metric}, ... ],   # state: "OK" | "ALARM"
  "series":    [ {time, error_rate, success_rate}, ... ],
}
```

El equipo de backend necesita definir tres cosas:

1. **De dónde salen los datos:** CloudWatch Metrics, CloudWatch Logs Insights, o
   DynamoDB (o una mezcla).
2. **Los nombres reales** de los recursos (log groups, tablas, alarmas).
3. **Los permisos de AWS** (ver sección 8).

---

## 8. Permisos de AWS necesarios

Para leer estos datos, la aplicación necesitará credenciales de AWS con permisos
de **solo lectura** sobre los servicios de donde se extraigan:

| Servicio             | Permisos (solo lectura)                               | Para qué          |
|----------------------|-------------------------------------------------------|-------------------|
| CloudWatch Metrics   | `cloudwatch:GetMetricData`                            | Métricas          |
| CloudWatch Alarmas   | `cloudwatch:DescribeAlarms`                           | Estado de alarmas |
| CloudWatch Logs      | `logs:StartQuery`, `logs:GetQueryResults`            | Event Log         |
| DynamoDB (si aplica) | `dynamodb:Scan` o `dynamodb:Query`                   | Si viene de tabla |

> **Recomendación:** pedir un rol o usuario de AWS con permisos **solo de
> lectura** (nunca escritura ni borrado), limitado a esos recursos específicos.
> Así el dashboard puede leer y mostrar, pero no puede modificar nada en AWS.

---

## 9. ¿Extraer estos datos de AWS tiene costo?

Sí, puede tener costo, aunque para un dashboard suele ser bajo. Depende de la
fuente:

- **CloudWatch Logs Insights** (Event Log): se cobra por la **cantidad de datos
  escaneados** en cada consulta. Aquí está el mayor riesgo: si se consulta cada
  10 s y se escanean muchos logs cada vez, se acumula.
- **CloudWatch Metrics (`GetMetricData`)**: se cobra por número de métricas
  solicitadas por llamada. Refrescar seguido multiplica las llamadas.
- **CloudWatch Alarmas (`DescribeAlarms`)**: consultar el estado normalmente no
  tiene costo significativo. Las alarmas en sí tienen un costo mensual fijo por
  alarma, pero eso ya existe independientemente del dashboard.
- **DynamoDB**: se cobra por lectura consumida. Un `Scan` completo repetido cada
  pocos segundos es lo más caro; conviene evitarlo.

### Qué ya está implementado para controlar el costo

- ✅ **Intervalo de refresco espaciado** a 30 s (antes 10 s) y **pausa por
  visibilidad** de la pestaña. Ver sección 6.
- ✅ **Caché en memoria (TTL 25 s) con lock** en `service.py`: AWS se consulta
  como mucho una vez por ventana, sin importar cuántos usuarios refresquen. Esta
  es la pieza que más reduce el costo.
- ✅ **Backoff, timeout y anti-solapamiento** en el frontend para no insistir
  contra un endpoint lento o caído.

### Pendiente al conectar AWS

- **Limitar el Event Log** dentro de `_generate_monitoring_payload()`: acotar la
  ventana de tiempo y la cantidad de resultados por consulta de Logs Insights
  (es la fuente potencialmente más cara).
- **Afinar los tiempos** (`PD_REFRESH_MS` y `CACHE_TTL_SECONDS`) según el balance
  frescura/costo que defina el equipo.

> ⚠️ **Verificar los precios exactos** con el equipo de AWS o en la calculadora
> oficial de precios de AWS, porque varían por región y con el tiempo.

---

## 10. Cómo ejecutarlo localmente (demo)

Requisitos: Python instalado.

```bash
pip install -r requirements.txt
python main.py
```

Luego abrir en el navegador: **http://localhost:8000/**
(la raíz redirige a `/production-dashboard`).

> `main.py` es solo para ver el módulo de forma aislada. En la app real, el
> módulo se integra con `app.include_router(monitoring_router)` (ver sección 3).

---

## 11. Checklist de migración al Service Desk

Pasos concretos para llevar este módulo al proyecto principal:

1. **Copiar la carpeta `monitoring/`** completa dentro del proyecto del Service
   Desk (por ejemplo junto a los demás módulos/routers).
2. **Registrar el router** en el `main`/app del Service Desk:
   ```python
   from monitoring import monitoring_router
   app.include_router(monitoring_router)
   ```
3. **Enlazar el item de la sidebar** "Production Dashboard" del Service Desk a la
   ruta `/production-dashboard` (o servir la vista donde el Service Desk cargue
   sus páginas de contenido).
4. **Ajustar dependencias:** asegurarse de que `fastapi`, `uvicorn` y `boto3`
   (este último solo cuando se conecte AWS) estén en el `requirements` del
   Service Desk. Ya están listados en `requirements.txt` de este repo.
5. **Descartar `main.py`:** no se copia; era solo para la demo local.
6. **Conectar AWS:** implementar los datos reales en `monitoring/service.py`
   respetando el contrato de la sección 7. La vista y el router no se tocan.
7. **(Opcional) Revisar la paleta:** los colores ya están alineados con la app;
   si el Service Desk usa variables de tema propias, se pueden mapear a las
   variables `--pd-*` del bloque `.pd-root` en un solo lugar.

> Resultado: el dashboard queda como una página nativa más del Service Desk, sin
> reescribir nada y con un único punto de cambio pendiente (los datos de AWS).
