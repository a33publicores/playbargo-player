# app.py
# Reproductor PlayBar Go - Backend Railway
# Copia y pega TODO este archivo completo en app.py

from flask import Flask, request, jsonify
from flask_cors import CORS
import gspread
from google.oauth2.service_account import Credentials
import os
import requests

app = Flask(__name__)
CORS(app)

# ==========================================================
# CONFIGURACIÓN
# ==========================================================

# ID del Google Sheet:
# https://docs.google.com/spreadsheets/d/1F1SMAyyY1iUKRX5QjiyrrMmv7W4z27gBsRMS8ZVGNS0/edit
SHEET_ID = "1F1SMAyyY1iUKRX5QjiyrrMmv7W4z27gBsRMS8ZVGNS0"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# ==========================================================
# GOOGLE SHEETS
# ==========================================================

def conectar_google():
    import json

    contenido = os.environ.get("GOOGLE_CREDENTIALS")
    if not contenido:
        raise Exception("No existe la variable GOOGLE_CREDENTIALS")

    info = json.loads(contenido)

    creds = Credentials.from_service_account_info(
        info,
        scopes=SCOPES
    )

    gc = gspread.authorize(creds)
    return gc

def obtener_hoja(cliente):
    gc = conectar_google()
    ss = gc.open_by_key(SHEET_ID)
    return ss.worksheet(cliente)

# ==========================================================
# DESCARGA DIRECTA DEL VIDEO DESDE YOUTUBE
# ==========================================================

# REEMPLAZA ÚNICAMENTE ESTA FUNCIÓN EN app.py
# Busca la función: def obtener_video_url(video_id):
# y reemplázala completa por esta versión.

# REEMPLAZA COMPLETAMENTE la función obtener_video_url(video_id)
# por esta versión.

# REEMPLAZA COMPLETAMENTE la función obtener_video_url(video_id)
# por esta versión.

def obtener_video_url(video_id):
    """
    Obtiene una URL directa reproducible del video.
    """
    try:
        import yt_dlp

        youtube_url = f"https://www.youtube.com/watch?v={video_id}"

        ydl_opts = {
            "format": "best",
            "quiet": True,
            "noplaylist": True,
            "nocheckcertificate": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(youtube_url, download=False)

            # 1. Intentar URL principal
            if info.get("url"):
                return info["url"]

            # 2. Buscar mejor formato con video
            formatos = info.get("formats", [])

            # Priorizar formatos con video
            formatos_con_video = [
                f for f in formatos
                if f.get("url") and f.get("vcodec") != "none"
            ]

            if formatos_con_video:
                # Ordenar por resolución
                formatos_con_video.sort(
                    key=lambda x: x.get("height") or 0,
                    reverse=True
                )
                return formatos_con_video[0]["url"]

            # 3. Cualquier formato con URL
            for f in reversed(formatos):
                if f.get("url"):
                    return f["url"]

        return None

    except Exception as e:
        print("Error obteniendo URL con yt-dlp:", str(e))
        return None

# ==========================================================
# ENDPOINT PRINCIPAL
# ==========================================================

@app.route("/")
def home():
    return "PlayBar Go Player OK"

# ==========================================================
# ESTADO DEL REPRODUCTOR
# ==========================================================

@app.route("/player/status")
def player_status():
    try:
        cliente = request.args.get("cliente", "A33")

        hoja = obtener_hoja(cliente)
        datos = hoja.get_all_records()

        if not datos:
            return jsonify({
                "ok": False,
                "mensaje": "No hay datos"
            })

        # Buscar canción en reproducción
        actual = None
        idx_actual = -1

        for i, fila in enumerate(datos):
            estado2 = str(fila.get("Estado2", "")).strip().lower()

            if estado2 == "en reproduccion":
                actual = fila
                idx_actual = i
                break

        # Si no existe, tomar la primera canción agregada
        if actual is None:
            for i, fila in enumerate(datos):
                estado = str(fila.get("Estado", "")).strip().lower()

                if estado == "agregado":
                    actual = fila
                    idx_actual = i

                    # Marcar en la hoja como En reproduccion
                    hoja.update_cell(i + 2, 8, "En reproduccion")
                    break

        if actual is None:
            return jsonify({
                "ok": False,
                "mensaje": "No hay canciones pendientes"
            })

        video_id = actual.get("videoId") or actual.get("videoid")

        if not video_id:
            return jsonify({
                "ok": False,
                "mensaje": "No existe videoId"
            })

        video_url = obtener_video_url(video_id)

        if not video_url:
            return jsonify({
                "ok": False,
                "mensaje": "No se pudo obtener URL del video"
            })

        # Siguiente canción
        siguiente = None
        for j in range(idx_actual + 1, len(datos)):
            if str(datos[j].get("Estado", "")).strip().lower() == "agregado":
                siguiente = {
                    "titulo": datos[j].get("titulo", "")
                }
                break

        return jsonify({
            "ok": True,
            "actual": {
                "titulo": actual.get("titulo", ""),
                "canal": actual.get("canal", ""),
                "videoId": video_id,
                "video_url": video_url
            },
            "siguiente": siguiente
        })

    except Exception as e:
        import traceback
        traceback.print_exc()

        return jsonify({
            "ok": False,
            "mensaje": str(e)
        })

# ==========================================================
# PASAR A LA SIGUIENTE CANCIÓN
# ==========================================================

@app.route("/player/next", methods=["POST"])
def player_next():
    try:
        data = request.get_json(force=True)
        cliente = data.get("cliente", "A33")

        hoja = obtener_hoja(cliente)
        datos = hoja.get_all_records()

        fila_actual = None

        # Buscar actual
        for i, fila in enumerate(datos):
            estado2 = str(fila.get("Estado2", "")).strip().lower()
            if estado2 == "en reproduccion":
                fila_actual = i + 2
                break

        if fila_actual:
            # Limpiar Estado2
            hoja.update_cell(fila_actual, 8, "")

        # Buscar siguiente
        for i, fila in enumerate(datos):
            estado = str(fila.get("Estado", "")).strip().lower()
            estado2 = str(fila.get("Estado2", "")).strip().lower()

            if estado == "agregado" and estado2 == "":
                hoja.update_cell(i + 2, 8, "En reproduccion")
                break

        return jsonify({
            "ok": True
        })

    except Exception as e:
        import traceback
        traceback.print_exc()

        return jsonify({
            "ok": False,
            "mensaje": str(e)
        })

# ==========================================================
# INICIO
# ==========================================================

if __name__ == "_main_":
    puerto = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=puerto)
