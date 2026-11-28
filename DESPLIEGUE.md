# Manual de despliegue local · Smart Lukas

Cómo instalar y correr la app en tu computador, con los datos simulados del caso de Laura.
Publicarla en la nube queda para más adelante.

> **En resumen** (si ya tienes Python 3.11 o más nuevo):
> ```bash
> python -m venv .venv
> .venv\Scripts\activate          # Windows · en Mac/Linux: source .venv/bin/activate
> pip install -r requirements.txt
> streamlit run app.py
> ```
> Se abre en el navegador en http://localhost:8501.

---

## 1. Requisitos

| Qué | Versión | Cómo revisarlo |
|---|---|---|
| **Python** | **3.11 o más nuevo** (obligatorio: Streamlit 1.67 no se instala en versiones anteriores) | `python --version` |
| **Git** | Cualquiera reciente | `git --version` |
| Navegador | Chrome, Edge, Firefox o Safari actualizados | — |

**No hace falta conda.** Sirve cualquier forma de tener Python 3.11+: el instalador de python.org, Anaconda/Miniconda o el Python del sistema.
Tampoco hay que instalar Streamlit aparte: lo instala `requirements.txt`, en la versión correcta.

Internet solo se necesita para instalar las dependencias. La app corre sin conexión; lo único que cambia es la tipografía,
porque Inter se carga desde Google Fonts y sin internet se usa la letra del sistema.

---

## 2. Descargar el proyecto

```bash
git clone https://github.com/caroandres356-eng/smart-lukas.git
cd smart-lukas
git checkout visualizacion
```

Si ya lo tienes clonado, solo actualiza:

```bash
git checkout visualizacion
git pull
```

---

## 3. Crear el entorno e instalar las dependencias

Usa **una** de las dos opciones. Un entorno aparte evita choques con las librerías de otros proyectos.

### Opción A · venv (recomendada: viene con Python)

```bash
python -m venv .venv
```

Actívalo según tu consola:

| Consola | Comando |
|---|---|
| Windows · PowerShell | `.venv\Scripts\Activate.ps1` |
| Windows · CMD | `.venv\Scripts\activate.bat` |
| Windows · Git Bash | `source .venv/Scripts/activate` |
| Mac / Linux | `source .venv/bin/activate` |

Verás `(.venv)` al inicio de la línea. Luego instala:

```bash
pip install -r requirements.txt
```

### Opción B · conda

```bash
conda create -n banca python=3.11
conda activate banca
pip install -r requirements.txt
```

> Cada vez que abras una consola nueva, **activa el entorno** antes de correr la app (`.venv\Scripts\activate` o `conda activate banca`).

---

## 4. Configurar el `.env`

Copia el archivo de ejemplo:

```bash
cp .env.example .env        # Mac/Linux y Git Bash
copy .env.example .env      # Windows (CMD o PowerShell)
```

Déjalo con `BANCO_MODO=fakes`. Así la app usa los datos de ejemplo de `fixtures/` (el caso de Laura).
Si no creas el `.env`, la app usa `fakes` igual, por defecto.

| `BANCO_MODO` | Qué usa | Estado |
|---|---|---|
| `fakes` | Datos de ejemplo de `fixtures/` | Funciona |
| `simulado` | Banco simulado (`banco/simulado.py`) | Pendiente (Persona 1) |
| `api` / `mcp` | Belo real | Cuando lleguen las credenciales |

`IA_PROVEEDOR=plantillas` (por defecto) redacta las explicaciones sin internet.

> **Nunca subas el `.env` al repositorio.** Puede tener llaves privadas.

---

## 5. Correr la app

Con el entorno activado, desde la carpeta del proyecto:

```bash
streamlit run app.py
```

Se abre sola en http://localhost:8501. Si no, abre esa dirección en el navegador.
Para detenerla: **Ctrl + C** en la consola.

### Qué deberías ver

Arriba, la navegación con 7 pantallas y la etiqueta **"Datos simulados"**:

| Pantalla | Qué muestra |
|---|---|
| **Panel** (inicio) | Indicadores, a dónde va el pago (Sankey), bandeja, pesos durante el mes, las 3 rutas, calendario y explicación |
| **Llega el pago** | Saldos, mercado del día y el reparto del pago |
| **Rutas** | Las 3 rutas, cómo se acumulan los pesos y las operaciones de cada una |
| **Operaciones** | Calendario del mes y lista de operaciones con su regla |
| **Bandeja** | Lo que espera tu permiso, con cuenta regresiva |
| **Política** | Límites, reservas, gastos fijos y reglas aprendidas |
| **Cierre** | Cuánto ganaste, la explicación y el resumen del mes |

Con los datos de ejemplo, el Panel debe decir **"+$6.976"** frente a «Todo hoy» y elegir la ruta **B · Lo justo hoy, el resto rindiendo**.

**Para probar:**
- Pasa el cursor por una operación del calendario para ver su detalle.
- En **Simulación** (arriba a la derecha), **+1 día** avanza el reloj y **+61 s** hace vencer una solicitud de la bandeja.

---

## 6. Correr las pruebas

```bash
pytest
```

Todas deben pasar. Las marcadas como `skipped` son de módulos que aún están pendientes (bandeja, banco simulado, Belo); eso es normal.

---

## 7. Actualizar después de un `git pull`

Cuando traigas cambios nuevos:

1. Detén la app con **Ctrl + C**.
2. Reinstala las dependencias, por si cambiaron: `pip install -r requirements.txt`.
3. Vuelve a levantarla: `streamlit run app.py`.

> **No confíes en la recarga automática de Streamlit después de un pull.** A veces conserva en memoria la versión vieja
> de algunos archivos y aparecen errores que no son reales (ver la primera fila de la sección 8).

---

## 8. Problemas comunes

| Síntoma | Causa | Solución |
|---|---|---|
| `ImportError: cannot import name ...` o `AttributeError: module ... has no attribute ...` justo después de un `git pull` | Streamlit siguió corriendo con la versión vieja de algunos módulos | **Ctrl + C** y `streamlit run app.py` (sección 7) |
| `ERROR: No matching distribution found for streamlit>=1.67` | Tu Python es anterior a 3.11 | Instala Python 3.11+ y crea el entorno de nuevo |
| `ModuleNotFoundError: No module named 'streamlit_echarts'` (u otro paquete) | Faltan dependencias nuevas o el entorno no está activado | Activa el entorno y corre `pip install -r requirements.txt` |
| `'streamlit' no se reconoce como un comando` | El entorno no está activado | Actívalo (sección 3) o usa `python -m streamlit run app.py` |
| PowerShell no deja activar el venv (`...no se puede cargar porque la ejecución de scripts está deshabilitada`) | Política de ejecución de Windows | Usa CMD (`.venv\Scripts\activate.bat`) o corre una vez `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| `Port 8501 is already in use` | Ya hay otra app de Streamlit abierta | Ciérrala, o usa otro puerto: `streamlit run app.py --server.port 8502` |
| Las gráficas del Panel salen vacías | La página cargó antes que las gráficas | Recarga el navegador (F5); si sigue, reinstala las dependencias |
| La letra se ve distinta a la de las capturas | No hay internet para cargar la fuente Inter | Es solo estético; con internet se ve igual |
| Un aviso amarillo dice "Pendiente: Persona X ..." | Ese módulo aún no está implementado; la app usa datos de ejemplo | Es normal por ahora; no rompe nada |

---

## 9. Lo que todavía es simulado

- Todos los datos (pago, tasas, saldos) son **datos simulados** del caso de Laura.
- El agente **no ejecuta** operaciones en un banco real. El calendario muestra lo que haría según las reglas y el reloj de simulación.
- La **bandeja** (`aprobaciones/bandeja.py`) aún no está conectada: muestra solicitudes de ejemplo.
