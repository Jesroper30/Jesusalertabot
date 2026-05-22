#!/usr/bin/env python3
"""
Bot de alertas P2P USDT/COP en Binance.

Lógica:
- ALERTA A: vendedor NO verificado con precio <= spot * (1 - DESCUENTO_ALERTA_A).
- ALERTA B: competidor #1 verificado (filtro 1M COP) con precio <= spot * (1 - DESCUENTO_ALERTA_B).

Uso:
    python bot_alertas_p2p.py                # corre el loop normal
    python bot_alertas_p2p.py --test         # manda mensaje de prueba a Telegram y sale
    python bot_alertas_p2p.py -v             # modo verbose (loguea TODOS los anuncios)
    python bot_alertas_p2p.py --once         # un solo ciclo y sale (útil para depurar)
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pytz
import requests
from dotenv import load_dotenv

import config

# ---------- Constantes ----------
COLOMBIA_TZ = pytz.timezone("America/Bogota")
BASE_DIR = Path(__file__).parent.resolve()
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

BINANCE_P2P_URL = "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search"
TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"

COOLDOWN_FILE = BASE_DIR / "cooldown_state.json"

HEADERS_BROWSER = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
}


# ---------- Logging ----------
def configurar_logging(verbose: bool = False) -> logging.Logger:
    """Configura logging a archivo diario y a consola."""
    # En Windows la consola por defecto es cp1252 y truena con emojis/flechas.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    fecha = datetime.now(COLOMBIA_TZ).strftime("%Y-%m-%d")
    log_file = LOG_DIR / f"{fecha}.log"

    nivel = logging.DEBUG if verbose else logging.INFO

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(nivel)

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S")

    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setFormatter(fmt)
    root.addHandler(fh)

    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    root.addHandler(sh)

    return logging.getLogger("bot_p2p")


# ---------- Spot USD/COP ----------
def _spot_yahoo() -> Optional[float]:
    """Yahoo Finance (USDCOP=X). Real-time-ish, gratis, sin key."""
    try:
        r = requests.get(
            "https://query1.finance.yahoo.com/v8/finance/chart/USDCOP=X",
            headers=HEADERS_BROWSER,
            timeout=config.TIMEOUT_HTTP,
        )
        r.raise_for_status()
        return float(r.json()["chart"]["result"][0]["meta"]["regularMarketPrice"])
    except Exception as e:
        logging.warning(f"Spot Yahoo falló: {e}")
        return None


def _spot_erapi() -> Optional[float]:
    """open.er-api.com — gratis, sin key, refresco diario."""
    try:
        r = requests.get(
            "https://open.er-api.com/v6/latest/USD",
            headers=HEADERS_BROWSER,
            timeout=config.TIMEOUT_HTTP,
        )
        r.raise_for_status()
        return float(r.json()["rates"]["COP"])
    except Exception as e:
        logging.warning(f"Spot open.er-api falló: {e}")
        return None


def _spot_trm_datos_gov() -> Optional[float]:
    """TRM oficial vía datos.gov.co (Superfinanciera). Diario, último publicado."""
    try:
        r = requests.get(
            "https://www.datos.gov.co/resource/32sa-8pi3.json?$order=vigenciadesde DESC&$limit=1",
            headers=HEADERS_BROWSER,
            timeout=config.TIMEOUT_HTTP,
        )
        r.raise_for_status()
        data = r.json()
        if data:
            return float(data[0]["valor"])
    except Exception as e:
        logging.warning(f"Spot TRM datos.gov.co falló: {e}")
    return None


def obtener_spot() -> tuple[Optional[float], str]:
    """
    Intenta obtener spot USD/COP en orden:
        1) Yahoo Finance (real-time-ish)
        2) open.er-api.com (diario)
        3) TRM datos.gov.co (diario oficial)
    Devuelve (precio, fuente) o (None, "ninguna") si todas fallan.
    """
    for nombre, fn in (
        ("Yahoo", _spot_yahoo),
        ("ER-API", _spot_erapi),
        ("TRM", _spot_trm_datos_gov),
    ):
        precio = fn()
        if precio:
            return precio, nombre
    return None, "ninguna"


# ---------- Binance P2P ----------
def consultar_binance(
    trade_type: str,
    trans_amount: str = "",
    pay_types: list[str] | None = None,
) -> list[dict]:
    """
    Llama al endpoint público de Binance P2P.

    OJO: en la API de Binance, trade_type se mide desde el punto de vista
    del que consulta, no del anunciante.

    trade_type:
        "BUY"  -> "yo quiero COMPRAR USDT" -> devuelve anuncios de VENDEDORES
                  (pestaña "Comprar" de la web). Ordenados del más barato al más caro.
        "SELL" -> "yo quiero VENDER USDT"  -> devuelve anuncios de COMPRADORES
                  (pestaña "Vender" de la web). Ordenados del que más paga al que menos.
    trans_amount:
        "" para sin filtro, o str con monto en COP (p.ej. "1000000")
    pay_types:
        None o [] = sin filtro de método de pago. Lista con identificadores
        (p.ej. ["BancolombiaSA", "Nequi"]) filtra a anuncios que aceptan al menos uno.
    """
    payload = {
        "asset": "USDT",
        "countries": [],
        "fiat": "COP",
        "page": 1,
        "payTypes": pay_types or [],
        "publisherType": None,
        "rows": config.ANUNCIOS_POR_CONSULTA,
        "tradeType": trade_type,
        "transAmount": trans_amount,
    }
    r = requests.post(
        BINANCE_P2P_URL,
        json=payload,
        headers={**HEADERS_BROWSER, "Content-Type": "application/json"},
        timeout=config.TIMEOUT_HTTP,
    )
    r.raise_for_status()
    data = r.json()
    if data.get("code") != "000000":
        raise RuntimeError(f"Binance respondió error: {data.get('message')}")
    return data.get("data") or []


def es_verificado(anuncio: dict) -> bool:
    """En Binance P2P, 'Comerciante verificado' corresponde a userType == 'merchant'."""
    return (anuncio.get("advertiser") or {}).get("userType") == "merchant"


# ---------- Telegram ----------
def enviar_telegram(mensaje: str, token: str, chat_id: str) -> bool:
    """Manda un mensaje al chat configurado. Devuelve True si Telegram acepta."""
    try:
        r = requests.post(
            TELEGRAM_API_URL.format(token=token),
            json={
                "chat_id": chat_id,
                "text": mensaje,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=config.TIMEOUT_HTTP,
        )
        if not r.ok:
            logging.error(f"Telegram respondió {r.status_code}: {r.text}")
            return False
        return True
    except Exception as e:
        logging.error(f"Error mandando a Telegram: {e}")
        return False


# ---------- Cooldown / Anti-spam ----------
class GestorCooldown:
    """
    Por cada 'clave' guardamos:
    - si la condición estaba activa el chequeo anterior
    - cuándo se mandó la última alerta

    debe_alertar(clave, condicion):
      - Si la condición es False  -> marca inactivo y devuelve False.
      - Si la condición pasó de False a True -> alerta (transición).
      - Si la condición sigue True y pasó el cooldown -> alerta.
      - En otro caso -> no alerta.
    """

    def __init__(self, minutos: int):
        self.delta = timedelta(minutes=minutos)
        self.ultimo: dict[str, datetime] = {}
        self.activo_antes: dict[str, bool] = {}

    def debe_alertar(self, clave: str, condicion: bool) -> bool:
        ahora = datetime.now(COLOMBIA_TZ)
        if not condicion:
            self.activo_antes[clave] = False
            return False

        antes = self.activo_antes.get(clave, False)
        self.activo_antes[clave] = True

        ult = self.ultimo.get(clave)
        if not antes or ult is None or (ahora - ult) >= self.delta:
            self.ultimo[clave] = ahora
            return True
        return False

    def cargar(self, path: Path) -> None:
        """Carga estado desde JSON. Útil para correr en GitHub Actions (sin estado en memoria)."""
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            self.ultimo = {
                k: datetime.fromisoformat(v)
                for k, v in (data.get("ultimo") or {}).items()
            }
            self.activo_antes = dict(data.get("activo_antes") or {})
            logging.info(f"Cooldown restaurado: {len(self.ultimo)} entradas")
        except Exception as e:
            logging.warning(f"No se pudo cargar cooldown_state.json: {e}")

    def guardar(self, path: Path) -> None:
        """Persiste estado a JSON."""
        try:
            data = {
                "ultimo": {k: v.isoformat() for k, v in self.ultimo.items()},
                "activo_antes": self.activo_antes,
            }
            path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as e:
            logging.warning(f"No se pudo guardar cooldown_state.json: {e}")


# ---------- Horario ----------
def en_horario_activo() -> bool:
    """True si la hora Colombia está en [HORA_INICIO, HORA_FIN). Cruza medianoche si fin < inicio."""
    hora = datetime.now(COLOMBIA_TZ).hour
    inicio, fin = config.HORA_INICIO, config.HORA_FIN
    if inicio <= fin:
        return inicio <= hora < fin
    return hora >= inicio or hora < fin


# ---------- Formato mensajes ----------
def _fmt_metodos(adv: dict) -> str:
    return ", ".join(
        (m.get("tradeMethodName") or m.get("identifier") or "—")
        for m in (adv.get("tradeMethods") or [])
    ) or "—"


def formatear_alerta_a(anuncio: dict, spot: float) -> str:
    adv = anuncio["adv"]
    advertiser = anuncio["advertiser"]
    precio = float(adv["price"])
    descuento_pct = (1 - precio / spot) * 100
    nick = advertiser.get("nickName", "?")
    rating = float(advertiser.get("monthFinishRate") or 0) * 100
    ordenes = advertiser.get("monthOrderCount", "?")
    disponible = float(adv.get("surplusAmount") or 0)
    user_no = advertiser.get("userNo", "")
    return (
        "🚨 <b>ALERTA A — VENDEDOR BARATO (No Verificado)</b>\n"
        f"💰 Precio: <b>{precio:,.2f}</b> COP/USDT\n"
        f"📉 Descuento: <b>-{descuento_pct:.2f}%</b> bajo spot ({spot:,.2f} COP)\n"
        f"👤 Vendedor: {nick} (sin verificar)\n"
        f"⭐ Rating: {rating:.1f}% / {ordenes} órdenes\n"
        f"💵 Disponible: {disponible:,.2f} USDT\n"
        f"💳 Métodos: {_fmt_metodos(adv)}\n"
        f"🔗 https://p2p.binance.com/es/advertiserDetail?advertiserNo={user_no}"
    )


def formatear_alerta_b(anuncio: dict, spot: float) -> str:
    adv = anuncio["adv"]
    advertiser = anuncio["advertiser"]
    precio = float(adv["price"])
    descuento_pct = (1 - precio / spot) * 100
    nick = advertiser.get("nickName", "?")
    user_no = advertiser.get("userNo", "")
    rating = float(advertiser.get("monthFinishRate") or 0) * 100
    ordenes = advertiser.get("monthOrderCount", "?")
    return (
        "💡 <b>ALERTA B — BUEN MOMENTO PARA PUBLICAR ANUNCIO</b>\n"
        f"📊 Spot: <b>{spot:,.2f}</b> COP\n"
        f"🥇 Competencia #1: <b>{nick}</b> (verificado, filtro 1M)\n"
        f"💰 Paga: <b>{precio:,.2f}</b> COP/USDT\n"
        f"📉 Descuento del #1: <b>-{descuento_pct:.2f}%</b> bajo spot\n"
        f"⭐ Rating: {rating:.1f}% / {ordenes} órdenes\n"
        f"🔗 https://p2p.binance.com/es/advertiserDetail?advertiserNo={user_no}\n"
        "✅ Buen momento para publicar tu anuncio de compra"
    )


# ---------- Lógica de cada alerta ----------
def chequear_alerta_a(
    spot: float, cooldown: GestorCooldown, token: str, chat_id: str, verbose: bool
) -> None:
    """Recorre vendedores NO verificados y alerta si alguno está bajo el umbral."""
    umbral = spot * (1 - config.DESCUENTO_ALERTA_A)
    # Para ver VENDEDORES de USDT (yo soy comprador) → API recibe "BUY"
    anuncios = consultar_binance(
        trade_type="BUY",
        pay_types=config.METODOS_PAGO_FILTRO,
    )
    no_verificados = [a for a in anuncios if not es_verificado(a)]

    if verbose:
        for a in anuncios:
            precio = float(a["adv"]["price"])
            nick = a["advertiser"].get("nickName", "?")
            ver = "verif" if es_verificado(a) else "sin verif"
            logging.debug(f"  VENDEDOR {nick} ({ver}) -> {precio:,.2f}")

    enviadas = 0
    for a in no_verificados:
        precio = float(a["adv"]["price"])
        cumple = precio <= umbral
        adv_no = a["adv"].get("advNo") or a["advertiser"].get("userNo") or ""
        clave = f"A:{adv_no}"
        if cooldown.debe_alertar(clave, cumple):
            if enviar_telegram(formatear_alerta_a(a, spot), token, chat_id):
                enviadas += 1
                logging.info(
                    f"📨 Alerta A enviada: {a['advertiser'].get('nickName','?')} "
                    f"@ {precio:,.2f} (umbral {umbral:,.2f})"
                )

    logging.info(
        f"Alerta A: spot={spot:,.2f} umbral={umbral:,.2f} "
        f"no_verif={len(no_verificados)}/{len(anuncios)} → {enviadas} enviada(s)"
    )


def chequear_alerta_b(
    spot: float, cooldown: GestorCooldown, token: str, chat_id: str, verbose: bool
) -> None:
    """Toma el #1 verificado con filtro 1M COP. Alerta si está bajo el umbral."""
    umbral = spot * (1 - config.DESCUENTO_ALERTA_B)
    # Para ver COMPRADORES de USDT (mi competencia) → API recibe "SELL"
    anuncios = consultar_binance(
        trade_type="SELL",
        trans_amount=str(config.MONTO_MINIMO_ALERTA_B),
        pay_types=config.METODOS_PAGO_FILTRO,
    )
    verificados = [a for a in anuncios if es_verificado(a)]

    if verbose:
        for a in anuncios[:10]:
            precio = float(a["adv"]["price"])
            nick = a["advertiser"].get("nickName", "?")
            ver = "verif" if es_verificado(a) else "sin verif"
            logging.debug(f"  COMPRADOR {nick} ({ver}) -> {precio:,.2f}")

    if not verificados:
        logging.info("Alerta B: no hay verificados con filtro 1M COP en esta página.")
        cooldown.debe_alertar("B", False)
        return

    primero = verificados[0]
    precio_1 = float(primero["adv"]["price"])
    cumple = precio_1 <= umbral
    logging.info(
        f"Alerta B: spot={spot:,.2f} umbral={umbral:,.2f} "
        f"#1_verif={precio_1:,.2f} → {'DISPARA' if cumple else 'no'}"
    )

    if cooldown.debe_alertar("B", cumple):
        if enviar_telegram(formatear_alerta_b(primero, spot), token, chat_id):
            logging.info(f"📨 Alerta B enviada (#1 verificado @ {precio_1:,.2f})")


# ---------- Main loop ----------
def ciclo(spot_cooldown: GestorCooldown, token: str, chat_id: str, verbose: bool) -> None:
    """Un solo ciclo del bot."""
    spot, fuente = obtener_spot()
    if not spot:
        raise RuntimeError("No se pudo obtener spot de ninguna fuente")
    logging.info(f"Spot {fuente}: {spot:,.2f} COP/USD")

    chequear_alerta_a(spot, spot_cooldown, token, chat_id, verbose)
    chequear_alerta_b(spot, spot_cooldown, token, chat_id, verbose)


def main() -> int:
    parser = argparse.ArgumentParser(description="Bot alertas P2P USDT/COP")
    parser.add_argument("--test", action="store_true", help="Manda mensaje de prueba a Telegram y sale.")
    parser.add_argument("--once", action="store_true", help="Corre un solo ciclo y sale (depuración).")
    parser.add_argument("-v", "--verbose", action="store_true", help="Loguea TODOS los anuncios.")
    args = parser.parse_args()

    log = configurar_logging(verbose=args.verbose)
    load_dotenv(BASE_DIR / ".env")

    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

    if not token or not chat_id:
        log.error("Configura TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID en el archivo .env")
        return 1

    if args.test:
        ok = enviar_telegram(
            "✅ <b>Test bot P2P</b>\nConfiguración correcta. El bot puede mandarte mensajes.",
            token,
            chat_id,
        )
        log.info("Test enviado correctamente." if ok else "Test FALLÓ. Revisa token y chat_id.")
        return 0 if ok else 1

    log.info("=" * 60)
    log.info("Bot de alertas P2P USDT/COP iniciado")
    log.info(f"Horario activo: {config.HORA_INICIO}:00 → {config.HORA_FIN}:00 (Colombia)")
    log.info(f"Frecuencia: cada {config.INTERVALO_SEGUNDOS}s")
    log.info(f"Umbral A: -{config.DESCUENTO_ALERTA_A*100:.2f}% (no verificados)")
    log.info(
        f"Umbral B: -{config.DESCUENTO_ALERTA_B*100:.2f}% "
        f"(verificados, filtro {config.MONTO_MINIMO_ALERTA_B:,} COP)"
    )
    log.info("=" * 60)

    cooldown = GestorCooldown(config.COOLDOWN_MINUTOS)
    cooldown.cargar(COOLDOWN_FILE)
    fallos = 0
    aviso_enviado = False

    if args.once:
        try:
            ciclo(cooldown, token, chat_id, args.verbose)
        finally:
            cooldown.guardar(COOLDOWN_FILE)
        return 0

    while True:
        try:
            if not en_horario_activo():
                hora = datetime.now(COLOMBIA_TZ).strftime("%H:%M")
                log.info(f"Fuera de horario activo ({hora}). Durmiendo 5 minutos.")
                time.sleep(300)
                continue

            ciclo(cooldown, token, chat_id, args.verbose)
            cooldown.guardar(COOLDOWN_FILE)
            fallos = 0
            aviso_enviado = False

        except KeyboardInterrupt:
            log.info("Interrumpido por usuario. Saliendo.")
            cooldown.guardar(COOLDOWN_FILE)
            return 0
        except Exception as e:
            fallos += 1
            log.error(f"Error en ciclo ({fallos}/{config.FALLOS_PARA_AVISAR}): {e}")
            if fallos >= config.FALLOS_PARA_AVISAR and not aviso_enviado:
                enviar_telegram(
                    f"⚠️ <b>Bot P2P en fallo</b>\n{fallos} errores seguidos.\nÚltimo: {e}",
                    token,
                    chat_id,
                )
                aviso_enviado = True

        time.sleep(config.INTERVALO_SEGUNDOS)


if __name__ == "__main__":
    sys.exit(main())
