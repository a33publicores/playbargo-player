from flask import Flask, jsonify, request

app = Flask(__name__)

@app.route("/")
def home():
    return "PlayBar Go Player API"

@app.route("/player/status")
def player_status():
    cliente = request.args.get("cliente", "A33")

    return jsonify({
        "ok": True,
        "actual": {
            "videoId": "demo1",
            "titulo": "Video de prueba",
            "video_url": "https://www.w3schools.com/html/mov_bbb.mp4"
        },
        "siguiente": {
            "titulo": "Próximo video"
        }
    })

@app.route("/player/ended", methods=["POST"])
def player_ended():
    data = request.json
    cliente = data.get("cliente")
    print(f"Video finalizado para {cliente}")

    return jsonify({"ok": True})

if _name_ == "_main_":
    app.run(host="0.0.0.0", port=5000)
