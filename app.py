# app.py
# Reproductor PlayBar Go - Backend Railway
# Copia y pega TODO este archivo completo en app.py

from flask import Flask, request, jsonify
from flask_cors import CORS
import gspread
from google.oauth2.service_account import Credentials
import os
import requests

COOKIES = os.getenv("YOUTUBE_COOKIES")

if COOKIES:
    with open("/tmp/cookies.txt", "w", encoding="utf-8") as f:
        f.write(COOKIES)

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

def obtener_video_url(video_id):
    try:
        import yt_dlp

        youtube_url = f"https://www.youtube.com/watch?v={video_id}"

        ydl_opts = {
            "format": "22/18/best[acodec!=none]/best",
                "quiet": True,
                "noplaylist": True,
                "nocheckcertificate": True,
                "cookiefile": "/tmp/cookies.txt",
}

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(youtube_url, download=False)

            # Cuando yt-dlp combina audio+video, expone la URL en requested_formats.
            requested = info.get("requested_formats")
            if requested and len(requested) >= 1:
                # Si hay URL combinada disponible
                if info.get("url"):
                    return info["url"]

            if info.get("url"):
                return info["url"]

            # Fallback: mejor formato con video
            formatos = info.get("formats", [])
            formatos_con_video = [
                f for f in formatos
                if f.get("url") and f.get("vcodec") != "none"
            ]

            if formatos_con_video:
                formatos_con_video.sort(
                    key=lambda x: x.get("height") or 0,
                    reverse=True
                )
                return formatos_con_video[0]["url"]

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

        # Próximas 3 canciones en cola
        cola = []

        for j in range(idx_actual + 1, len(datos)):
            estado = str(datos[j].get("Estado", "")).strip().lower()

            if estado == "agregado":
                cola.append({
                "titulo": datos[j].get("titulo", ""),
                "videoId": (
                    datos[j].get("videoId")
                    or datos[j].get("videoid")
                    or ""
                )
            })
            if len(cola) >= 3:
                break

        return jsonify({
            "ok": True,
            "actual": {
                "titulo": actual.get("titulo", ""),
                "canal": actual.get("canal", ""),
                "videoId": video_id,
                "video_url": video_url
            },
            "cola": cola
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
        # Leer JSON de forma segura
        data = request.get_json(silent=True) or {}
        cliente = data.get("cliente", "A33")

        hoja = obtener_hoja(cliente)
        datos = hoja.get_all_records()

        fila_actual = None
        fila_siguiente = None

        # 1. Buscar canción actual en reproducción
        for i, fila in enumerate(datos, start=2):
            estado2 = str(fila.get("Estado2", "")).strip().lower()

            if estado2 == "en reproduccion":
                fila_actual = i
                break

        # 2. Marcar actual como Reproducido
        if fila_actual:
            hoja.update_cell(fila_actual, 8, "Reproducido")

        # 3. Buscar siguiente canción
        for i, fila in enumerate(datos, start=2):
            estado = str(fila.get("Estado", "")).strip().lower()
            estado2 = str(fila.get("Estado2", "")).strip()

            if estado == "agregado" and estado2 == "":
                fila_siguiente = i
                break

        # 4. Activar siguiente
        if fila_siguiente:
            hoja.update_cell(fila_siguiente, 8, "En reproduccion")

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
