# PROMPT PARA CLAUDE CODE — Bot de Alertas P2P USDT

Copia y pega TODO el contenido de abajo en Claude Code:

---

## CONTEXTO

Soy comerciante P2P verificado de USDT en Binance Colombia. Compro USDT en pesos colombianos (COP) y los vendo a una empresa llamada Zulu. Necesito un script en Python que me alerte por Telegram cuando haya oportunidades de compra o de publicación de anuncio en Binance P2P USDT/COP.

## OBJETIVO

Construir un script Python que se ejecute localmente en mi PC Windows, corra cada 60 segundos en horario 6:00 AM – 1:00 AM (19 horas activas al día), y mande alertas a mi Telegram cuando se cumplan ciertas condiciones de precio.

## FUENTES DE DATOS

1. **Precio spot USD/COP en tiempo real**: tomar de SetFX (https://www.set-fx.com/). Si SetFX no tiene API pública, usar fallback de otra fuente confiable como Banco República TRM o exchange forex (ej: API gratuita de exchangerate-api o investing.com). Documentar qué fuente queda usando.

2. **Anuncios Binance P2P**: usar la API pública de Binance P2P (endpoint `https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search`). Es público, NO requiere API key. Hacer POST con filtros para USDT/COP.

## LÓGICA DE LAS 2 ALERTAS

### ALERTA A — Vendedor barato (para que YO compre tomando el anuncio)

- Filtrar anuncios de **venta** de USDT (yo soy comprador).
- Solo considerar vendedores **NO verificados** (sin badge de "Comerciante verificado").
- Si el precio de algún vendedor NO verificado es **≤ spot × (1 − 0.013)** (es decir, descuento de **1.3% o más** bajo spot), mandar alerta a Telegram.

**Mensaje de Telegram para Alerta A:**
```
🚨 ALERTA A - VENDEDOR BARATO (No Verificado)
💰 Precio: {precio} COP/USDT
📉 Descuento: -{%}% bajo spot ({spot} COP)
👤 Vendedor: {nick} (sin verificar)
⭐ Rating: {rating}% / {ordenes} órdenes
💵 Disponible: {disponible} USDT
💳 Métodos: {metodos}
🔗 https://p2p.binance.com/es/advertiserDetail?advertiserNo={ad_no}
```

### ALERTA B — Oportunidad para publicar mi propio anuncio

- Filtrar anuncios de **compra** de USDT (los que compran, mi competencia).
- Solo considerar comerciantes **verificados** (con badge).
- Aplicar filtro de monto mínimo: 1,000,000 COP (transAmount = 1000000).
- Tomar el **anuncio #1** de esa lista filtrada (el que paga más, el más competitivo).
- Si el precio del #1 es **≤ spot × (1 − 0.015)** (es decir, descuento de **1.5% o más** bajo spot), mandar alerta a Telegram. Lógica: la competencia ya está pagando muy barato → hay vendedores dispuestos a vender bajo → buen momento para publicar mi anuncio.

**Mensaje de Telegram para Alerta B:**
```
💡 ALERTA B - BUEN MOMENTO PARA PUBLICAR ANUNCIO
📊 Spot SetFX: {spot} COP
🥇 Competencia #1 (verificado, filtro 1M): {precio} COP
📉 Descuento del #1: -{%}% bajo spot
✅ Buen momento para publicar tu anuncio de compra
```

## CONFIGURACIÓN GENERAL

- **Frecuencia**: cada 60 segundos.
- **Horario activo**: 6:00 AM – 1:00 AM hora Colombia (UTC-5). Fuera de ese horario, el script duerme y no consulta nada.
- **Anti-spam**: si la misma alerta se cumple varias veces seguidas, NO mandar mensaje duplicado cada minuto. Implementar cooldown: una vez mandada una alerta para cierta condición, no volver a mandarla hasta que pase al menos 15 minutos o hasta que la condición deje de cumplirse y vuelva a cumplirse.
- **Logging**: cada chequeo debe loguear en consola con timestamp lo que está midiendo (spot, precio #1, decisión).
- **Manejo de errores**: si la API de Binance o SetFX falla, NO crashear el script. Loguear el error, esperar 60 segundos y reintentar. Si falla 5 veces seguidas, mandar mensaje a Telegram avisando del fallo.

## TELEGRAM

Crear archivo `.env` (o `config.py`) con dos variables que el usuario llenará después:
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

El script debe leer estas variables al iniciar. Si están vacías, debe abortar con mensaje claro: "Configura TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID en el archivo .env".

## ESTRUCTURA DEL PROYECTO

```
USDT/
  bot_alertas_p2p.py     # script principal
  config.py              # variables de configuración (token, chat_id, umbrales)
  requirements.txt       # dependencias
  README.md              # cómo instalar y correr
  logs/                  # carpeta donde guarda logs diarios
```

## DEPENDENCIAS

- `requests` (para llamadas HTTP a Binance y SetFX)
- `python-telegram-bot` o llamada HTTP directa a la API de Telegram (lo que sea más simple, prefiero llamada directa con requests)
- `python-dotenv` (para leer .env)
- `pytz` (para manejo de zona horaria Colombia)
- `beautifulsoup4` y `lxml` solo si SetFX requiere scraping

## CRITERIOS DE CALIDAD

1. **Código limpio**, comentado en español, organizado en funciones.
2. **README.md** con instrucciones paso a paso para que un usuario sin experiencia técnica:
   - Instale Python (si no lo tiene)
   - Instale las dependencias con `pip install -r requirements.txt`
   - Configure su `.env` con TOKEN y CHAT_ID
   - Arranque el script con `python bot_alertas_p2p.py`
3. **Pruebas**: incluir un modo `--test` que mande un mensaje de prueba a Telegram al arrancar para validar configuración.
4. **Modo verbose**: con flag `-v` o `--verbose` debe mostrar TODOS los anuncios que ve aunque no cumplan la condición, para que yo pueda calibrar umbrales.

## EJEMPLOS DE CÁLCULO PARA VALIDAR

**Spot SetFX**: 3,650 COP/USD

**Alerta A**:
- Umbral: 3,650 × (1 − 0.013) = 3,602.55
- Vendedor NO verificado a 3,598 → 3,598 ≤ 3,602.55 → ✅ DISPARA ALERTA
- Vendedor NO verificado a 3,610 → 3,610 > 3,602.55 → ❌ NO DISPARA
- Vendedor VERIFICADO a 3,590 → es verificado → ❌ NO DISPARA (filtro)

**Alerta B**:
- Umbral: 3,650 × (1 − 0.015) = 3,595.25
- #1 verificado filtro 1M paga 3,640 → 3,640 > 3,595.25 → ❌ NO DISPARA
- #1 verificado filtro 1M paga 3,590 → 3,590 ≤ 3,595.25 → ✅ DISPARA ALERTA
- #1 verificado filtro 1M paga 3,580 → 3,580 ≤ 3,595.25 → ✅ DISPARA ALERTA

## ENTREGABLE FINAL

Quiero los archivos listos para correr. Después de generarlos, dame las instrucciones exactas que tengo que ejecutar (comandos copiables) para tenerlo andando en mi PC Windows.

## NOTA IMPORTANTE

La API pública de Binance P2P puede tener rate limits. Si detectas que cada 60s satura, ajusta a 90 o 120s y avísame. NO uses API key privada — esto es 100% lectura pública.
