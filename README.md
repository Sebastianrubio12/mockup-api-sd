# Dashboard de Monitoreo de APIs (Service Desk)

Documento de resumen del proyecto para revisión con el equipo.

---

## 1. Qué se construyó

Un dashboard web propio para monitorear el estado de los endpoints/APIs
(RTR, SPOT, E2Open, etc.), como alternativa a las pantallas de AWS CloudWatch.

Tiene dos piezas:

- **Backend (`main.py`)**: una API en Python con FastAPI. Sirve la página del
  dashboard y expone un endpoint que entrega los datos de monitoreo en JSON.
- **Frontend (`dashboard.html`)**: la interfaz visual. Consume ese JSON y lo
  pinta en tarjetas, gráficas y tablas.

Están separados a propósito: la interfaz ya quedó terminada, y cuando el equipo
de backend conecte los datos reales de AWS, la parte visual **no se toca**.

---

## 2. Qué muestra el dashboard

- **Fila de KPIs** (arriba): número de endpoints, requests totales, errores
  totales, tasa de error promedio y alarmas activas.
- **Gráfica** de tasa de error vs tasa de éxito en el tiempo.
- **Panel de alarmas** (RTR, SPOT, Quoting) con estado `OK` o `ALARM`.
- **Una tarjeta por endpoint** con su tasa de error, desglose de códigos HTTP
  (401 / 400 / 500) y total de requests.
- **Tabla de Event Log** con los eventos recientes (company, customer, tipo de
  evento, código de estado, mensaje, número de errores).

---

## 3. Estado actual: datos de prueba, no reales todavía

Hoy el dashboard funciona con **datos simulados (mock)**. Los números se generan
de forma aleatoria para que la interfaz se vea completa y funcional. Esto sirve
para **revisar y aprobar el diseño** antes de conectar la fuente real.

> La migración de datos reales está **pendiente a propósito**. Se hará junto con
> el equipo de backend, porque primero hay que definir de dónde salen exactamente
> esos datos en AWS.

---

## 4. Cómo funciona el "Actualizar" y su alcance

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

## 5. Qué falta (el trabajo con backend)

En el código (`main.py`, dentro del endpoint `api_monitoring()`) quedó
documentado, paso a paso, **dónde y cómo** se conectará AWS. El único punto que
hay que cambiar es **una línea** del backend: donde hoy devuelve datos de prueba,
mañana devolverá los datos reales de AWS ya con el formato correcto.

El equipo de backend necesita definir tres cosas:

1. **De dónde salen los datos:** CloudWatch Metrics, CloudWatch Logs Insights, o
   DynamoDB (o una mezcla).
2. **Los nombres reales** de los recursos (log groups, tablas, alarmas).
3. **Los permisos de AWS** (ver sección 6).

---

## 6. Permisos de AWS necesarios

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

## 7. ¿Extraer estos datos de AWS tiene costo?

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

## 8. Cómo ejecutarlo localmente

Requisitos: Python instalado.

```bash
pip install fastapi uvicorn boto3
python main.py
```

Luego abrir en el navegador: **http://localhost:8000/**

---

## 9. Resumen para la reunión (versión corta)

- ✅ Interfaz visual del dashboard **terminada** y funcionando con datos de prueba.
- ✅ Backend en FastAPI que sirve la página y expone el endpoint de datos.
- ✅ El diseño se puede **revisar y aprobar ya**, sin esperar a AWS.
- ⏳ **Pendiente:** conectar los datos reales de AWS (se hace con backend).
- 🔑 **Se necesita:** definir la fuente de datos, nombres reales y permisos de
  solo lectura en AWS.
- 💲 **Costo:** bajo pero existe; se controla con refresco más espaciado y caché.
  Confirmar cifras con AWS.
