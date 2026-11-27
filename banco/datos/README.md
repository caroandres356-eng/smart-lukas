# Datos de mercado (TRM real)

Pon aquí el CSV de la TRM histórica con el nombre **`trm.csv`** (ruta: `banco/datos/trm.csv`).

- Fuente: datos abiertos de Colombia (datos.gov.co), conjunto "Tasa de Cambio Representativa del Mercado - Histórico" (Superintendencia Financiera).
- Descarga sugerida: `https://www.datos.gov.co/resource/32sa-8pi3.csv?$limit=60&$order=vigenciadesde DESC`
  (verificar el id del conjunto en el portal si cambia).
- Columnas esperadas: `valor`, `unidad`, `vigenciadesde`, `vigenciahasta`.
- `banco/mercado.py` (MercadoCSV) lo lee; si no existe, usa `fixtures/cotizaciones_30d.json` (sintético).

Es un dato público. **No** se guardan datos de usuarios reales en esta carpeta.
