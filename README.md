# Bot de Alertas P2P USDT/COP (Binance)

Bot Python que monitorea los anuncios de Binance P2P USDT/COP cada 60 segundos y te avisa por Telegram cuando hay una buena oportunidad.

- **Alerta A — Vendedor barato**: te avisa cuando un vendedor **NO verificado** está vendiendo USDT por debajo del spot con el descuento que configures (default 1.3%). Para que tomes su anuncio.
- **Alerta B — Publicar anuncio**: te avisa cuando el competidor #1 verificado (filtro 1M COP) está pagando muy barato (default 1.5% bajo spot). Buen momento para publicar tu propio anuncio de compra.

---

## 1. Instalar Python (solo si no lo tienes)

1. Entra a [python.org/downloads](https://www.python.org/downloads/).
2. Descarga la última versión estable (3.10 o superior).
3. **MUY IMPORTANTE**: al instalar, marca la casilla **"Add Python to PATH"** antes de darle a Install.
4. Verifica abriendo PowerShell:

```powershell
python --version
```

Debe mostrar `Python 3.10.x` o superior.

---

## 2. Instalar las dependencias

Abre PowerShell y entra a la carpeta del proyecto:

```powershell
cd "C:\Users\HP Z210\Documents\Claude\Projects\USDT"
pip install -r requirements.txt
```

---

## 3. Crear tu bot de Telegram y conseguir el TOKEN

1. Abre Telegram y busca **@BotFather**.
2. Mándale `/newbot`.
3. Elige un nombre (ej. `Mi Bot P2P`) y un username que termine en `bot` (ej. `mi_p2p_usdt_bot`).
4. Te dará un **token** parecido a `1234567890:ABC...`. Cópialo, te sirve para el `.env`.

## 4. Conseguir tu CHAT_ID

1. En Telegram busca **@userinfobot**.
2. Mándale cualquier mensaje (ej. `/start`).
3. Te responde con tu **Id**. Ese número es tu `TELEGRAM_CHAT_ID`.
4. **Antes de arrancar el bot**, mándale `/start` a tu bot recién creado (paso 3) para que tenga permiso de escribirte.

---

## 5. Configurar tu `.env`

En la carpeta del proyecto vas a ver un archivo `.env.example`. Cópialo con el nombre `.env`:

```powershell
copy .env.example .env
notepad .env
```

Pega los dos valores que conseguiste:

```
TELEGRAM_BOT_TOKEN=1234567890:ABCdef...
TELEGRAM_CHAT_ID=987654321
```

Guarda y cierra.

---

## 6. Probar la configuración

```powershell
python bot_alertas_p2p.py --test
```

Te debe llegar un mensaje a Telegram: **"Test bot P2P — Configuración correcta"**. Si no llega:
- Revisa que el `TOKEN` esté bien copiado.
- Revisa que hayas mandado `/start` al bot creado.
- Revisa que el `CHAT_ID` sea numérico.

---

## 7. Arrancar el bot

```powershell
python bot_alertas_p2p.py
```

Deja la ventana abierta. El bot:
- Corre cada **60 segundos**.
- Solo está activo de **6:00 AM a 1:00 AM** hora Colombia.
- Loguea todo a `logs/AAAA-MM-DD.log`.
- Tiene **cooldown de 15 minutos** por alerta para no spamearte.

Para parar: `Ctrl + C`.

### Modo verbose (para calibrar)

Si quieres ver TODOS los anuncios que va leyendo (aunque no cumplan la condición):

```powershell
python bot_alertas_p2p.py -v
```

### Un solo ciclo (depuración)

```powershell
python bot_alertas_p2p.py --once -v
```

Hace un solo chequeo, imprime todo en consola y sale. Útil para verificar que la API responde.

---

## 8. Calibrar umbrales

Si crees que el descuento por defecto (1.3% / 1.5%) es muy estricto o muy flojo, edita `config.py`:

```python
DESCUENTO_ALERTA_A = 0.013   # cámbialo a 0.010 = 1.0% para alertas más frecuentes
DESCUENTO_ALERTA_B = 0.015   # cámbialo a 0.020 = 2.0% para alertas más estrictas
```

Otros parámetros que puedes tocar ahí: `INTERVALO_SEGUNDOS`, `HORA_INICIO`, `HORA_FIN`, `COOLDOWN_MINUTOS`, `MONTO_MINIMO_ALERTA_B`.

---

## Fuente del spot USD/COP

El script intenta tres fuentes públicas, en este orden:

1. **Yahoo Finance** (`USDCOP=X`) — real-time-ish, sin API key.
2. **open.er-api.com** — diario, gratis.
3. **TRM oficial vía datos.gov.co** — diario, oficial.

SetFX no se usa directamente porque requiere login. Yahoo es lo más cercano a lo que ves en SetFX en términos de actualización.

---

## Estructura del proyecto

```
USDT/
├── bot_alertas_p2p.py     # script principal
├── config.py              # umbrales, horario, cooldown
├── requirements.txt       # dependencias
├── .env                   # TU token y chat_id (NO compartir)
├── .env.example           # plantilla
├── .gitignore
├── README.md
└── logs/                  # logs diarios (se crea solo)
```

---

## Problemas comunes

| Problema | Solución |
|---|---|
| `pip` no reconocido | Reinstala Python marcando "Add to PATH" |
| Telegram no llega | Mándale `/start` a tu bot antes de correr |
| `Binance respondió error` | Espera 1-2 minutos. Si persiste, sube `INTERVALO_SEGUNDOS` a 90 o 120 en `config.py` |
| Spot Yahoo falla seguido | Usa el fallback automático (ER-API / TRM). Verifica conexión |
| El bot se queda dormido | Es normal entre 1:00 AM y 6:00 AM (fuera de horario activo) |

---

## Bonus: correr el bot 24/7 GRATIS en GitHub Actions (sin PC prendido)

GitHub Actions ejecuta el script cada 5 min en sus servidores sin que tu PC esté prendido. Cuota gratis ilimitada para repos públicos.

**Tradeoff:** chequeo cada 5 min en vez de 60s. Tus tokens van en GitHub Secrets (encriptados, nunca en el código).

### Pasos:
1. Crear cuenta en [github.com](https://github.com) si no tienes.
2. Crear un nuevo repositorio **público** (puede ser privado si tienes plan pago — público es gratis con minutos ilimitados).
3. Subir todo el código MENOS el `.env` (que está gitignored).
4. En el repo: `Settings → Secrets and variables → Actions → New repository secret`
   - Nombre: `TELEGRAM_BOT_TOKEN`, valor: tu token
   - Nombre: `TELEGRAM_CHAT_ID`, valor: tu chat id
5. GitHub Actions arranca automáticamente con el cron configurado en `.github/workflows/bot.yml`.

Detalles paso a paso, comandos copiables y troubleshooting → ver sección "GitHub Actions" más abajo o pregúntale a Claude Code.
