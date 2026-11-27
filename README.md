# Smart Lukas · agente de cobro para freelancers (nombre provisional)

Agente que ayuda a freelancers colombianos que cobran en dólares a decidir **cuándo y cuánto convertir a pesos**.
Compara tres rutas, elige la que deja más pesos dentro de las reglas que tú pusiste, te pide permiso antes de lo importante
y al final te explica en palabras simples qué hizo, por qué y cuánta plata ganaste. Hackathon · reto de **Belo** (banca agéntica en Latinoamérica).

---

## 1. El problema y la solución

**El problema.** Un freelancer recibe 1.000 USD y lo normal es convertir todo el mismo día. Pierde dinero por el momento de la conversión,
deja plata quieta que podría rendir y no tiene reglas claras para no gastarse lo de impuestos.

**La solución.** Un agente que:

1. Separa lo que no se toca: impuestos (se guardan en USDT) y un colchón en USD.
2. Compara 3 rutas para el resto:
   - **A · Todo hoy**: convierte todo el día 1.
   - **B · Lo justo hoy, el resto rindiendo**: convierte hoy solo lo de los gastos fijos; el resto queda en USDT rindiendo y se convierte en 4 tramos semanales.
   - **C · Mitad y mitad**: mitad el día 1 y mitad el día 15.
3. Elige la ruta con **más pesos finales** que cumpla tu política.
4. Pasa cada operación por reglas deterministas: **automática**, **requiere aprobación** o **bloqueada**, siempre con un motivo.
5. Te muestra: **"Ahorraste $X pesos frente a convertir todo el día 1"**.

> **Principio clave:** las decisiones y los montos los calcula código determinista. La IA solo redacta explicaciones y **nunca cambia montos**.

## 2. Cómo cumple el reto

| Requisito del reto | Cómo lo cumplimos |
|---|---|
| **Reglas claras definidas por la persona** | `motor/politica.yaml`: límites por operación y por día, % de impuestos, colchón, gastos fijos, vencimiento de solicitudes, máximo de interrupciones. Se ve y se edita en la pantalla *Política*. |
| **Control humano** | Lo que supera los límites va a la *Bandeja*. Las solicitudes vencen (sin respuesta no se ejecuta nada), máximo 3 interrupciones al día. Respuestas: *Solo esta vez*, *Siempre en este rango*, *Nunca* (las dos últimas enseñan al agente). |
| **Transparencia** | Cada operación lleva un motivo con la regla y los números. Pantalla *Cierre del mes*: ahorro frente a "Todo hoy" y explicación en lenguaje simple. Etiqueta visible **"Datos simulados"**. |

## 3. Demo: el caso de Laura

Laura es diseñadora freelance en Bogotá.

| Dato | Valor |
|---|---|
| Pago recibido | 1.000 USD el día 1 |
| Gastos fijos | Arriendo 1.800.000 COP (día 5) · Internet 120.000 COP (día 10) |
| Impuestos | 15 % → 150 USD a USDT |
| Colchón | 200 USD (nunca se convierte) |
| Límites sin aprobación | 300 USD por operación · 500 USD por día |
| Bandeja | Solicitudes vencen en 60 s · máximo 3 interrupciones al día |
| Belo simulado | Spread 1 % · rendimiento USDT 10 % anual |

Paso a paso:

1. **Llega el pago**: 1.000 USD. Se separan 150 USD de impuestos y 200 USD de colchón → quedan **650 USD** para decidir.
2. **Rutas** (con la TRM sintética de `fixtures/`): A = $2.605.532 · **B = $2.612.480** · C = $2.608.276. Gana B.
3. **Operaciones**: B convierte hoy 450 USD (arriendo) y 30 USD (internet); 170 USD pasan a USDT y salen en 4 tramos (días 8, 15, 22, 29).
   - 450 USD → 🟡 *requiere aprobación*: "450 USD supera el límite de 300 USD por operación".
   - Internet y tramos → 🟢 *auto*.
4. **Bandeja**: Laura responde *Siempre en este rango* → el agente aprende "conversión de arriendo hasta 500 USD" y la próxima vez es automática.
5. **Cierre del mes**: "Ahorraste **$6.949 pesos** frente a convertir todo el día 1", con la explicación.

## 4. Arquitectura

```
┌──────────────────────────────────────────────────────────┐
│ Interfaz (Streamlit)          app.py · ui/               │
└───────────────┬──────────────────────────┬───────────────┘
                │                          │
┌───────────────▼──────────┐   ┌───────────▼──────────────┐
│ Bandeja de aprobaciones  │   │ Motor (determinista)     │
│ aprobaciones/            │   │ motor/ política · rutas  │
│                          │   │ decisor · explicador     │
└───────────────┬──────────┘   └───────────┬──────────────┘
                └────────────┬─────────────┘
              ┌──────────────▼──────────────┐
              │ core/  (el contrato)        │
              │ modelos.py · puertos.py     │
              └──────────────┬──────────────┘
                             │  BancoPort · MercadoPort · Reloj
      ┌──────────────┬───────┴──────┬──────────────┬─────────────┐
      ▼              ▼              ▼              ▼             ▼
   fakes/      banco/simulado  banco/mercado  banco/belo_api  banco/belo_mcp
  (fixtures)   (banco falso)   (TRM CSV)      (REST Belo)     (MCP Belo)
                                   │              │             │
                                   ▼              └──────┬──────┘
                           datos abiertos (TRM)        Belo
```

**Puertos y adaptadores.** `core/puertos.py` define *qué* necesita el agente de un banco (`BancoPort`), del mercado (`MercadoPort`) y del tiempo (`Reloj`).
Cada adaptador implementa *cómo*: hoy con fakes o con un banco simulado; mañana con Belo. `banco/fabrica.py` elige el adaptador según
`BANCO_MODO` en el `.env`. El motor, la bandeja y la interfaz nunca importan un adaptador directamente, así que **conectar Belo es llenar un archivo**.

## 5. Estructura de carpetas

| Carpeta / archivo | Qué hay | Responsable |
|---|---|---|
| `core/` | Contrato: modelos Pydantic y puertos | **Compartido** (solo se agregan campos) |
| `fixtures/` | Datos de ejemplo del caso Laura (JSON) | **Compartido** |
| `fakes/` | BancoFalso, MercadoFalso, RelojFalso y cargadores | **Compartido** |
| `banco/` | Banco simulado, mercado TRM, reloj, registro SQLite, fábrica, adaptadores Belo | Persona 1 |
| `motor/` | Política (YAML), rutas, decisor, explicador | Persona 2 |
| `aprobaciones/` | Bandeja de aprobaciones | Persona 3 |
| `ui/`, `app.py` | Pantallas Streamlit y despliegue | Persona 3 |
| `tests/` | Contrato, motor, bandeja, core | Cada quien sus tests |

## 6. El contrato (`core/`)

**Modelos** (`core/modelos.py`): `Saldo`, `Cotizacion` (tasa SIN spread + spread aparte), `Rendimiento`, `Movimiento`, `Operacion`,
`Resultado`, `Ruta`, `Veredicto`, `Propuesta`, `Solicitud`, `CambioPolitica`, `GastoFijo`, `Politica`.

**Puertos** (`core/puertos.py`):

| Puerto | Métodos |
|---|---|
| `BancoPort` | `saldos()`, `cotizacion(desde, hacia)`, `rendimiento(moneda)`, `ejecutar(op)` (idempotente por `op.id`), `movimientos()` |
| `MercadoPort` | `historico(desde, hacia, dias)` |
| `Reloj` | `hoy()`, `ahora()` |

**Reglas del contrato**

- Dinero **siempre `Decimal`**, nunca `float`.
- Cada `Operacion` tiene un **id único** (`nuevo_id()`); ejecutar dos veces el mismo id no repite nada.
- Todo dato del banco/mercado lleva **`fuente`** (`"simulado"` o `"belo"`).
- Fechas y horas en **UTC**.
- Porcentajes: `spread` y `tasa_anual` como fracción (0.01 = 1 %); `impuestos_pct` en puntos (15 = 15 %).
- Solo se **agregan** campos; nunca se borran ni renombran.

## 7. Reglas

### Decisor (`motor/decisor.py`) — en este orden, gana la primera que aplique

| # | Condición | Resultado |
|---|---|---|
| 1 | Hay regla aprendida **"bloquear"** para ese tipo y categoría | 🔴 bloqueada |
| 2 | Hay regla aprendida **"permitir_hasta"** y el monto cabe | 🟢 auto |
| 3 | La operación deja el USD por debajo del **colchón** | 🔴 bloqueada |
| 4 | Supera **auto_max_usd_por_operacion** | 🟡 requiere aprobación |
| 5 | Lo acumulado del día supera **auto_max_usd_por_dia** | 🟡 requiere aprobación |
| 6 | Si no | 🟢 auto |

El motivo siempre dice la regla y los números.

### Bandeja (`aprobaciones/bandeja.py`)

| Situación | Resultado |
|---|---|
| Nueva solicitud y quedan interrupciones hoy | `pendiente`, vence = ahora + 60 s |
| Nueva solicitud y ya hubo 3 interrupciones hoy | `en_cola` |
| Nadie responde a tiempo | `vencida` y **no se ejecuta nada** |
| "Solo esta vez" | `aprobada`, la política no cambia |
| "Siempre en este rango" | `aprobada` + regla `permitir_hasta` (monto redondeado a la siguiente centena: 450 → 500) |
| "Nunca" | `rechazada` + regla `bloquear` |

## 8. Instalación y ejecución

Requiere Python 3.11+.

```bash
python -m venv .venv
# Windows:  .venv\Scripts\activate
# Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # Windows: copy .env.example .env
streamlit run app.py
pytest
```

Con `BANCO_MODO=fakes` (por defecto) la app abre con los datos de ejemplo. Las pantallas cuyo módulo aún no existe muestran
un aviso con el responsable en vez de romperse.

## 9. Cómo trabajamos

- Ramas: **`banco`** (Persona 1), **`motor`** (Persona 2), **`interfaz`** (Persona 3).
- Cada quien trabaja **solo en sus carpetas**.
- `core/`, `fixtures/` y `fakes/` **no se cambian sin avisar** al equipo; solo se agregan campos.
- Se integra a `main` en **dos momentos**: a mitad del día y al final, siempre con `pytest` pasando.
- A medida que implementas, **quita el `skip`** de tus tests.
- **Nunca** subir el `.env`.

## 10. Tareas por persona

### Persona 1 · Banco y datos (`banco/`)

- [ ] `reloj.py` · `RelojSimulado` con `hoy`, `ahora` (UTC), `avanzar`, `avanzar_segundos`.
- [ ] `mercado.py` · `MercadoCSV.historico` lee `banco/datos/trm.csv` (TRM real) con fallback a fixtures.
- [ ] `simulado.py` · `BancoSimulado`: los 5 métodos + `recibir_pago` + `aplicar_rendimiento_diario`, con la fórmula `COP = USD × TRM × (1 − spread)`.
- [ ] `registro.py` · `Registro` SQLite con `guardar` y `ya_ejecutada`.
- [ ] `fabrica.py` · rama `simulado` funcionando.
- **Terminado cuando:** quitas el skip de `simulado` en `tests/test_contrato_banco.py` y pasa, y la app abre con `BANCO_MODO=simulado`.

### Persona 2 · Motor (`motor/`)

- [ ] `politica.py` · `cargar_politica`, `guardar_politica`, `aplicar_cambio` (sin mutar la original).
- [ ] `rutas.py` · `calcular_rutas` con las 3 rutas (resultado igual a `fixtures/propuesta.json` ± 1 COP).
- [ ] `decisor.py` · `evaluar` (6 reglas en orden, motivo con números) y `proponer`.
- [ ] `explicador.py` · `explicar` con plantillas; IA opcional con fallback a plantilla.
- **Terminado cuando:** todos los tests de `tests/test_motor.py` pasan sin skip. Ejemplos: 450 USD → `requiere_aprobacion` mencionando 300; tras `permitir_hasta` arriendo 500 → `auto`.

### Persona 3 · Bandeja e interfaz (`aprobaciones/`, `ui/`, `app.py`)

- [ ] `bandeja.py` · `Bandeja` completa según la tabla de reglas, usando el `Reloj` inyectado.
- [ ] `ui/` · diseño final de las 6 pantallas (quitar los `st.info("Persona 3: pendiente diseño final")`).
- [ ] Cuenta regresiva en la bandeja (`streamlit-autorefresh`) y aplicar el `CambioPolitica` a la política.
- [ ] Despliegue (Streamlit Community Cloud).
- **Terminado cuando:** todos los tests de `tests/test_bandeja.py` pasan sin skip (la 4.ª solicitud del día queda `en_cola`; a los 61 s queda `vencida`) y la demo de Laura se recorre de punta a punta.

## 11. Cómo conectar Belo cuando llegue el acceso

1. Llenar `banco/belo_api.py` (REST) **o** `banco/belo_mcp.py` (MCP). Cada método tiene un comentario con la herramienta/endpoint que debe traducir.
2. Poner las credenciales en `.env` y cambiar `BANCO_MODO=api` o `BANCO_MODO=mcp`; completar esa rama en `banco/fabrica.py`.
3. Quitar el skip del adaptador en `tests/test_contrato_banco.py` y correr `pytest tests/test_contrato_banco.py`.
4. Si Belo tiene su propia aprobación de transacciones, `ejecutar()` la usa. **Nuestra bandeja decide cuándo pedir permiso; Belo ejecuta.**

No hay que tocar `motor/`, `aprobaciones/` ni `ui/`.

## 12. Datos

- **Simulado:** el banco, los saldos, el spread (1 %), el rendimiento del USDT (10 % anual) y las cotizaciones de `fixtures/` (TRM sintética alrededor de 4.000).
- **Real:** la TRM histórica de datos abiertos de Colombia (datos.gov.co), cuando se pone el CSV en `banco/datos/` (ver su README).
- **No se usan datos reales de usuarios.** Laura es un caso inventado.

## 13. Equipo

| Rol | Nombre |
|---|---|
| Persona 1 · Banco y datos | _(nombre)_ |
| Persona 2 · Motor | _(nombre)_ |
| Persona 3 · Bandeja e interfaz | _(nombre)_ |
