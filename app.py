from flask import Flask, request, jsonify
from flask_cors import CORS
import gspread
from google.oauth2.service_account import Credentials
import os
import json

# ==========================================================
# CONFIGURACIÓN FLASK
# ==========================================================
app = Flask(_name_)
CORS(app)

# ==========================================================
# CONFIGURACIÓN GOOGLE SHEETS
# ==========================================================
SHEET_ID = "1F1SMAyyY1iUKRX5QjiyrrMmv7W4z27gBsRMS8ZVGNS0"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]


def conectar_google():
    """
    Conecta con Google Sheets usando la variable de entorno
    GOOGLE_CREDENTIALS en Railway.
    """
    cred_json = os.getenv("GOOGLE_CREDENTIALS")

    if not cred_json:
        raise Exception(
            "No se encontró la variable GOOGLE_CREDENTIALS en Railway."
        )

    info = json.loads(cred_json)
    creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    return gspread.authorize(creds)


gc = conectar_google()


# ==========================================================
# FUNCIONES AUXILIARES
# ==========================================================
def obtener_hoja(nombre_hoja):
    return gc.open_by_key(SHEET_ID).worksheet(nombre_hoja)


def obtener_cliente_por_codigo(codigo):
    """
    Busca en la hoja CLIENTES el registro cuyo Código coincida.
    Retorna el valor de la columna Nombre (ej. A33).
    """
    hoja = obtener_hoja("CLIENTES")
    registros = hoja.get_all_records()

    codigo = str(codigo).strip().upper()

    for fila in registros:
        codigo_fila = str(fila.get("Código", "")).strip().upper()
        if codigo_fila == codigo:
            return str(fila.get("Nombre", "")).strip()

    return None


def obtener_estado2(row):
    """
    Obtiene el valor de Estado2 desde la fila (índice 7).
    """
    if len(row) > 7:
        return str(row[7]).strip()
    return ""


def set_estado2(hoja, fila, valor):
    """
    Columna H = 8 (Estado2)
    """
    hoja.update_cell(fila, 8, valor)


def obtener_cancion_actual_y_siguiente(cliente):
    """
    Busca:
    - En Reproduccion / En Reproducción
    - Siguiente
    """
    hoja = obtener_hoja(cliente)
    datos = hoja.get_all_values()

    actual = None
    siguiente = None

    # Saltar encabezado (fila 1)
    for i in range(2, len(datos) + 1):
        row = datos[i - 1]
        estado2 = obtener_estado2(row).lower()

        if estado2 in ["en reproduccion", "en reproducción"]:
            actual = {
                "fila": i,
                "titulo": row[3] if len(row) > 3 else "",
                "canal": row[4] if len(row) > 4 else "",
                "videoId": row[5] if len(row) > 5 else "",
                "video_url": (
                    f"https://www.youtube.com/watch?v={row[5]}"
                    if len(row) > 5 and row[5]
                    else ""
                ),
            }

        elif estado2 == "siguiente":
            siguiente = {
                "fila": i,
                "titulo": row[3] if len(row) > 3 else "",
                "videoId": row[5] if len(row) > 5 else "",
            }

        if actual and siguiente:
            break

    return actual, siguiente


def avanzar_siguiente(cliente):
    """
    Marca la actual como Reproducida y la siguiente como En Reproducción.
    """
    hoja = obtener_hoja(cliente)
    datos = hoja.get_all_values()

    fila_actual = None
    fila_siguiente = None

    for i in range(2, len(datos) + 1):
        row = datos[i - 1]
        estado2 = obtener_estado2(row).lower()

        if estado2 in ["en reproduccion", "en reproducción"]:
            fila_actual = i

        elif estado2 == "siguiente":
            fila_siguiente = i

    if fila_actual:
        set_estado2(hoja, fila_actual, "Reproducida")

    if fila_siguiente:
        set_estado2(hoja, fila_siguiente, "En Reproducción")

    return True


# ==========================================================
# VARIABLES DE CONTROL DJ
# ==========================================================
dj_estado = {
    "action": "play"  # play, pause, next, previous
}


# ==========================================================
# RUTA PRINCIPAL
# ==========================================================
@app.route("/")
def home():
    return "PlayBar Go Player API funcionando"


# ==========================================================
# STATUS DEL REPRODUCTOR
# ==========================================================
@app.route("/player/status")
def player_status():
    """
    Ejemplos:
    /player/status?cliente=A33
    /player/status?cliente=8523
    """
    codigo = request.args.get("cliente")

    if not codigo:
        return jsonify({
            "ok": False,
            "error": "Parámetro cliente requerido"
        }), 400

    cliente = obtener_cliente_por_codigo(codigo)

    # Si no existe como código, asumir que ya enviaron el nombre (A33)
    if not cliente:
        cliente = str(codigo).strip()

    try:
        actual, siguiente = obtener_cancion_actual_y_siguiente(cliente)

        if not actual:
            return jsonify({
                "ok": True,
                "actual": None,
                "siguiente": siguiente,
                "control": dj_estado
            })

        return jsonify({
            "ok": True,
            "actual": actual,
            "siguiente": siguiente,
            "control": dj_estado
        })

    except Exception as e:
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500


# ==========================================================
# AVANZAR A LA SIGUIENTE CANCIÓN
# ==========================================================
@app.route("/player/next", methods=["POST"])
def player_next():
    data = request.get_json(silent=True) or {}
    cliente = data.get("cliente", "A33")

    try:
        avanzar_siguiente(cliente)

        dj_estado["action"] = "play"

        return jsonify({
            "ok": True,
            "message": "Avanzado a la siguiente canción"
        })

    except Exception as e:
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500


# ==========================================================
# CONTROL DJ
# ==========================================================
@app.route("/player/control", methods=["POST"])
def player_control():
    """
    body JSON:
    {
        "action": "pause"
    }

    Acciones:
    - play
    - pause
    - next
    - previous
    """
    data = request.get_json(silent=True) or {}
    action = data.get("action", "play")

    if action not in ["play", "pause", "next", "previous"]:
        return jsonify({
            "ok": False,
            "error": "Acción inválida"
        }), 400

    dj_estado["action"] = action

    return jsonify({
        "ok": True,
        "action": action
    })


# ==========================================================
# EJECUCIÓN LOCAL
# ==========================================================
if _name_ == "_main_":
    puerto = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=puerto)
