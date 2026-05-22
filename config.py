"""
Parámetros del bot. Modifica estos valores si quieres calibrar umbrales,
frecuencia, horario o cooldown sin tocar el código principal.
"""

# Umbrales de descuento bajo spot. 0.013 = 1.3%
DESCUENTO_ALERTA_A = 0.013  # Vendedor NO verificado: 1.3% bajo spot
DESCUENTO_ALERTA_B = 0.015  # Competencia verificada #1: 1.5% bajo spot

# Filtro de monto mínimo en COP para Alerta B (transAmount en la API)
MONTO_MINIMO_ALERTA_B = 1_000_000

# Métodos de pago a filtrar (vacío [] = sin filtro, acepta todos).
# Identificadores que usa la API de Binance para Colombia:
#   "BancolombiaSA", "Nequi", "Daviplata", "DaviviendaSA",
#   "BancodeBogota", "BBVABank", "BreBKeys"
# Por defecto Bancolombia + Nequi (los que tú usas).
METODOS_PAGO_FILTRO = ["BancolombiaSA", "Nequi"]

# Frecuencia entre chequeos (segundos). Sube a 90/120 si te limitan.
INTERVALO_SEGUNDOS = 60

# Horario activo en hora Colombia (UTC-5). Formato 24h.
# Cruza medianoche: 6 → 1 significa 6:00 AM hasta 1:00 AM del día siguiente.
HORA_INICIO = 6
HORA_FIN = 1

# Cooldown anti-spam: minutos antes de repetir la misma alerta para la misma condición.
COOLDOWN_MINUTOS = 15

# Fallos consecutivos antes de mandar aviso por Telegram.
FALLOS_PARA_AVISAR = 5

# Cuántos anuncios pedir a Binance por chequeo (máx. 20).
ANUNCIOS_POR_CONSULTA = 20

# Timeout de cada llamada HTTP (segundos).
TIMEOUT_HTTP = 10
