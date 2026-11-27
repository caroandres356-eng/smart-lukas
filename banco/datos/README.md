# Datos de mercado (TRM real vía API Socrata)

`banco/mercado.py` (`MercadoSocrata` / alias `MercadoCSV`) consulta directamente la **API Socrata (SODA2)** de datos abiertos de Colombia (`datos.gov.co`), sin necesidad de descargar CSV manualmente:

- Fuente: datos abiertos de Colombia (`datos.gov.co`), conjunto "Tasa de Cambio Representativa del Mercado - Histórico" (Superintendencia Financiera).
- Endpoint JSON: `https://www.datos.gov.co/resource/32sa-8pi3.json`
- Autenticación recomendada: configura `SOCRATA_APP_TOKEN` en `.env` (se envía en la cabecera `X-App-Token` para evitar throttling; opcional para consultas bajas).
- Caché local: guarda las cotizaciones en `SOCRATA_CACHE_PATH` (por defecto `banco/datos/trm_cache.json`) para funcionar offline o sin reconsultar en cada refresh.
- Fallback: si no hay red y tampoco existe caché ni CSV local (`banco/datos/trm.csv`), usa `fixtures/cotizaciones_30d.json` (sintético).

Es un dato público. **No** se guardan datos de usuarios reales en esta carpeta.
