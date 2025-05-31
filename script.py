import json
import time
import os
from websocket import create_connection, WebSocketTimeoutException
import requests
import config

# Configuración inicial
TELEGRAM_BOT_TOKEN = config.TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID = config.TELEGRAM_CHAT_ID
updown = ''

# =========================================
# Funciones principales (Actualizadas)
# =========================================

def clear_screen():
    """Limpia la pantalla según el sistema operativo."""
    os.system('cls' if os.name == 'nt' else 'clear')

def get_current_time():
    """Devuelve la hora actual en formato HH:MM:ss (24 horas)."""
    return time.strftime("%H:%M:%S")

def send_telegram_alert(message: str):
    """Envía alertas a Telegram con manejo de errores robusto."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        response = requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "Markdown"
        })
        response.raise_for_status()
    except Exception as e:
        print(f"[{get_current_time()}] ⚠️ Error enviando alerta: {str(e)}")
        return False

def get_websocket_connection(symbol: str):
    """Crea una conexión WebSocket para un símbolo específico."""
    ws_url = "wss://stream.bybit.com/v5/public/linear"
    try:
        ws = create_connection(ws_url, timeout=5)
        ws.send(json.dumps({
            "op": "subscribe",
            "args": [f"tickers.{symbol}"]
        }))
        return ws
    except Exception as e:
        print(f"[{get_current_time()}] 🔌 Error de conexión: {str(e)}")
        return None

def is_valid_symbol(symbol: str) -> bool:
    """Verifica si el símbolo existe en Bybit."""
    url = "https://api.bybit.com/v5/market/instruments-info?category=linear"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        # Verificar si el símbolo existe en la lista de instrumentos
        for item in data["result"]["list"]:
            if item["symbol"] == symbol:
                return True
        return False
    except Exception as e:
        print(f"[{get_current_time()}] ❌ Error al verificar símbolo: {str(e)}")
        return False
    
def get_current_price(symbol: str) -> float:
    """Obtiene el precio actual de un símbolo desde WebSocket una sola vez."""
    ws = get_websocket_connection(symbol)
    if not ws:
        print(f"[{get_current_time()}] ❌ No se pudo conectar al WebSocket.")
        return None

    while True:
        try:
            data = json.loads(ws.recv())
            if "topic" in data and "data" in data and data["topic"] == f"tickers.{symbol}":
                ws.close()
                return float(data["data"]["lastPrice"])
        except Exception as e:
            print(f"[{get_current_time()}] ❌ Error recibiendo datos: {str(e)}")
            ws.close()
            return None
        
def monitor_price(symbol: str, target_price: float, updown: str ):
    """Monitorea el precio hasta alcanzar el objetivo."""
    alert_triggered = False
    while True:
        ws = None
        try:
            ws = get_websocket_connection(symbol)
            if not ws:
                time.sleep(5)
                continue

            clear_screen()
            print(f"[{get_current_time()}] 🔎 Alerta Activada! {symbol}...")
            print(f"[{get_current_time()}] Objetivo {'ARRIBA ⬆️ ' if updown == 'U' else 'ABAJO ⬇️ '} del precio actual.")
            print(f"[{get_current_time()}] Objetivo a llevar: ${target_price:,.6f}")

            while True:
                data = json.loads(ws.recv())
                
                if "topic" in data and "data" in data and data["topic"] == f"tickers.{symbol}":
                    current_price = float(data["data"]["lastPrice"])
                    print(f"[{get_current_time()}] Precio actual: ${current_price:,.6f}", end="\r")

                    if updown == "D": 
                        if current_price <= target_price and not alert_triggered:
                            message = (
                                f"🚨 **ALERTA DE PRECIO - {get_current_time()}**\n"
                                f"*{symbol}* alcanzó *${target_price:,.6f}*\n"
                                f"Precio actual: *${current_price:,.6f}*"
                            )
                            if send_telegram_alert(message) == False:
                                return
                            #print(send_telegram_alert(message))
                            print(f"\n\n[{get_current_time()}] ⚠️ ¡Alerta activada! DOWN")
                            alert_triggered = True
                            return  # Regresa al menú principal

                    else:
                        if current_price > target_price and not alert_triggered:
                            message = (
                                f"🚨 *Alerta de Precio Activada*\n"
                                #f"🕒 *Hora:* {get_current_time()}\n"
                                f"📈 *Símbolo:* `{symbol}`\n"
                                f"🎯 *Precio Objetivo:* ${target_price:,.6f}\n"
                            )

                            if send_telegram_alert(message) == False:
                                return
                            #print(send_telegram_alert(message))
                            print(f"\n\n[{get_current_time()}] ⚠️ ¡Alerta activada! UP")
                            alert_triggered = True
                            return  # Regresa al menú principal

        except WebSocketTimeoutException:
            print(f"\n[{get_current_time()}] ⌛ Tiempo de espera agotado")
        except Exception as e:
            #print(f"\n[{get_current_time()}] ❌ Error: {str(e)}")
            if ws:
                ws.close()
            time.sleep(2)

# =========================================
# Menú interactivo
# =========================================

def main_menu():
    """Maneja la interfaz de usuario y flujo principal."""
    clear_screen()
    print("=== BYBIT PRICE ALERT (v4.0) ===")
    
    # Configurar símbolo inicial
    while True:
        symbol = input("Ingrese el símbolo a monitorear (ej: BTC): ").strip().upper()
        symbol = symbol + 'USDT'
        
        # Validar el símbolo
        if not is_valid_symbol(symbol):
            print(f"\n[{get_current_time()}] ❌ El símbolo {symbol} no existe en Bybit. Intente nuevamente.")
            time.sleep(2)
            clear_screen()
            continue
        break
     
    while True:
        try:
            # Solicitar nuevo target
            #clear_screen()
            target = float(input(
                f"\n[{get_current_time()}] Ingrese precio objetivo para {symbol} (0 para salir): $"
            ))
            
            if target == 0:
                print("\n👋 ¡Hasta luego!")
                break

            #updown = input("Ingrese su el objetivo esta por encima o por debajo del precio actual (u:up d:down):").strip().upper()
            
            #if updown not in ('U', 'D'):
            #    print("\n👋 ¡Hasta luego!")
            #    break

            current_price = get_current_price(symbol)
            if current_price is None:
                print("\n⚠️ No se pudo obtener el precio actual.")
                continue

            updown = 'U' if target > current_price else 'D'

            # Iniciar monitoreo
            print(f"\n[{get_current_time()}] ⚡ Iniciando monitoreo...")
            monitor_price(symbol, target, updown)

        except ValueError:
            print("\n⚠️ Error: Debes ingresar un número válido")
            time.sleep(2)
            
        except KeyboardInterrupt:
            print("\n👋 ¡Hasta luego!")
            break

# =========================================
# Ejecución principal
# =========================================
if __name__ == "__main__":
    main_menu()