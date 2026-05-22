#!/usr/bin/env python3
"""
Script de DEMOSTRACIÓN.

Toma los precios REALES en este momento de Binance P2P COP y manda a Telegram
las alertas A y B con los mejores candidatos actuales, ignorando los umbrales.
Sirve para ver cómo se verá la notificación cuando llegue de verdad.

Uso:
    py demo_alerta.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(BASE_DIR))
load_dotenv(BASE_DIR / ".env")

from bot_alertas_p2p import (  # noqa: E402
    consultar_binance,
    enviar_telegram,
    es_verificado,
    formatear_alerta_a,
    formatear_alerta_b,
    obtener_spot,
)
import config  # noqa: E402


def main() -> int:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        print("Falta TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID en .env")
        return 1

    spot, fuente = obtener_spot()
    if not spot:
        print("No se pudo obtener spot.")
        return 1
    print(f"Spot {fuente}: {spot:,.2f} COP/USD")

    enviados = 0

    # --- DEMO Alerta A: vendedor NO verificado más barato (sin importar umbral) ---
    # API "BUY" = "yo quiero comprar" → me devuelve anuncios de VENDEDORES
    sell_ads = consultar_binance(
        trade_type="BUY",
        pay_types=config.METODOS_PAGO_FILTRO,
    )
    no_verif = [a for a in sell_ads if not es_verificado(a)]
    no_verif.sort(key=lambda a: float(a["adv"]["price"]))
    if no_verif:
        mejor_a = no_verif[0]
        precio = float(mejor_a["adv"]["price"])
        umbral = spot * (1 - config.DESCUENTO_ALERTA_A)
        diferencia = umbral - precio
        encabezado = (
            "🧪 <b>DEMO — ASÍ SE VERÍA ALERTA A</b>\n"
            f"(Es solo demo. El precio actual es {precio:,.2f}, "
            f"el umbral real es {umbral:,.2f}. "
            f"Faltan {-diferencia:,.2f} COP por bajar para que dispare sola.)\n"
            "─────────────────────\n"
        )
        msg = encabezado + formatear_alerta_a(mejor_a, spot)
        if enviar_telegram(msg, token, chat_id):
            enviados += 1
            print(f"Demo A enviada (vendedor no verif. más barato: {precio:,.2f})")

    # --- DEMO Alerta B: competencia #1 verificada filtro 1M ---
    # API "SELL" = "yo quiero vender" → me devuelve anuncios de COMPRADORES (mi competencia)
    buy_ads = consultar_binance(
        trade_type="SELL",
        trans_amount=str(config.MONTO_MINIMO_ALERTA_B),
        pay_types=config.METODOS_PAGO_FILTRO,
    )
    verif = [a for a in buy_ads if es_verificado(a)]
    if verif:
        primero = verif[0]
        precio = float(primero["adv"]["price"])
        umbral = spot * (1 - config.DESCUENTO_ALERTA_B)
        diferencia = umbral - precio
        encabezado = (
            "🧪 <b>DEMO — ASÍ SE VERÍA ALERTA B</b>\n"
            f"(Es solo demo. El #1 verif está a {precio:,.2f}, "
            f"el umbral real es {umbral:,.2f}. "
            f"Faltan {-diferencia:,.2f} COP por bajar para que dispare sola.)\n"
            "─────────────────────\n"
        )
        msg = encabezado + formatear_alerta_b(primero, spot)
        if enviar_telegram(msg, token, chat_id):
            enviados += 1
            print(f"Demo B enviada (#1 verificado: {precio:,.2f})")

    print(f"Total enviadas: {enviados}")
    return 0 if enviados else 1


if __name__ == "__main__":
    sys.exit(main())
