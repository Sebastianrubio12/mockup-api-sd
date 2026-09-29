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
6. **Sin estado global ni dependencias ocultas.** El módulo no guarda estado en
   memoria compartida; cada request arma su payload. Fácil de mover o testear.

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

## 4. Qué muestra el dashboard

- **Health strip:** un anillo de salud global (verde/amarillo/rojo según % de
  éxito) más el conteo de servicios Healthy / Degradados / Críticos.
- **Fila de KPIs:** número de servicios, requests totales, errores totales, tasa
  de error promedio y alarmas activas.
- **Gráfica** de tasa de error vs tasa de éxito en el tiempo.
- **Panel de alarmas** (RTR, SPOT, Quoting) con estado `OK` o `ALARM`.
- **Lista de servicios monitoreados** (una fila por endpoint) con estado de
  salud, tasa de error, barra de éxito y desglose de códigos HTTP (401/400/500).
- **Tabla de Event Log** con los eventos recientes (company, customer, tipo de
  evento, código de estado, mensaje, número de errores).

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

## 6. Cómo funciona el "Actualizar" y su alcance

- El dashboard se **actualiza solo cada 10 segundos**: vuelve a pedir los datos
  al backend y repinta la pantalla. También hay un botón "Actualizar" manual.
- **Alcance (importante):** el frontend **no limita** cuántos datos muestra.
  Pinta *todo* lo que el backend le entregue. Hoy el mock manda una muestra
  pequeña, pero cuando se conecte AWS y lleguen todas las companies, customers y
  endpoints reales, el dashboard los mostrará **todos automáticamente**, sin
  cambiar nada en la interfaz. Las tablas y KPIs se ajustan solos a la cantidad
  de datos recibidos.

> **Aclaración honesta:** hoy NO es tiempo real. Es un refresco cada 10 segundos.
> Cuando se conecte AWS será "casi en vivo": tan actualizado como cada 10 s, con
> datos verdaderos. Ese intervalo se puede subir o bajar según se necesite.

---

## 7. Qué falta (el trabajo con backend)

Solo hay que trabajar dentro de **`monitoring/service.py`**, en la función
`build_monitoring_payload()`. Ahí quedó documentado, paso a paso, dónde y cómo se
conectará AWS. El objetivo es reemplazar los datos de prueba por datos reales
respetando **exactamente el mismo formato** del diccionario que se retorna.

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

### Recomendaciones para controlar el costo

- **Subir el intervalo de refresco** (ej. cada 30–60 s en vez de 10 s) reduce
  mucho el número de consultas.
- **Usar caché**: no re-consultar AWS en cada refresco, sino guardar el último
  resultado unos segundos y que varios usuarios compartan esa lectura.
- **Limitar el Event Log**: acotar la ventana de tiempo y la cantidad de
  resultados por consulta.

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

---

## 12. Resumen para la reunión (versión corta)

- ✅ **Parte aislada y súper adaptable:** todo lo que migra vive en `monitoring/`
  (paquete autocontenido); `main.py` es solo demo y se descarta al integrar.
- ✅ Dashboard convertido en **módulo enchufable**, listo para integrarse en la
  app "Service Desk Management" copiando una carpeta + una línea.
- ✅ Interfaz **sin sidebar** (la app anfitriona ya la aporta) y con la **paleta
  de la app**; estilos aislados con prefijo `.pd-` para no chocar con el tema.
- ✅ Salud representada con **hex-grid estilo Dynatrace** (un hexágono por
  servicio, coloreado por estado) en vez del anillo.
- ✅ Funciona con datos de prueba, así que el diseño se puede **revisar y aprobar
  ya**, sin esperar a AWS.
- ✅ Integración = **una línea**: `app.include_router(monitoring_router)`.
- ⏳ **Pendiente:** conectar los datos reales de AWS, tocando **solo**
  `monitoring/service.py`.
- 🔑 **Se necesita:** definir la fuente de datos, nombres reales y permisos de
  solo lectura en AWS.
- 💲 **Costo:** bajo pero existe; se controla con refresco más espaciado y caché.
  Confirmar cifras con AWS.
