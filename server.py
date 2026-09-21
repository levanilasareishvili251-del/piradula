from flask import Flask, request, jsonify, send_from_directory
import random, string, threading, time, os

app = Flask(__name__, static_folder=".", static_url_path="")
rooms = {}
lock = threading.Lock()

def make_code():
    while True:
        code = "".join(random.choices(string.digits, k=6))
        if code not in rooms:
            return code

def state(room):
    players = list(room["players"].values())
    ranks = {pid: i + 1 for i, pid in enumerate(room["order"])}
    return {
        "code": room["code"],
        "round": room["round"],
        "order": room["order"],
        "rank_map": ranks,
        "players": players
    }

@app.get("/")
def index():
    return send_from_directory(".", "index.html")

@app.get("/<path:path>")
def static_file(path):
    return send_from_directory(".", path)

@app.get("/api/state")
def get_state():
    code = request.args.get("code", "")
    with lock:
        room = rooms.get(code)
        if not room:
            return jsonify(error="ოთახი ვერ მოიძებნა"), 404
        return jsonify(state(room))

@app.post("/api/create")
def create():
    data = request.get_json() or {}
    with lock:
        code = make_code()
        host_id = "h_" + "".join(random.choices(string.ascii_letters + string.digits, k=12))
        rooms[code] = {
            "code": code, "host_id": host_id, "round": 1,
            "order": [], "players": {}, "created": time.time()
        }
        return jsonify(code=code, host_id=host_id)

@app.post("/api/join")
def join():
    data = request.get_json() or {}
    code = str(data.get("code", "")).strip()
    name = str(data.get("name", "")).strip()[:40]
    if len(code) != 6 or not code.isdigit():
        return jsonify(error="კოდი უნდა იყოს 6 ციფრი"), 400
    if not name:
        return jsonify(error="შეიყვანე სახელი"), 400

    with lock:
        room = rooms.get(code)
        if not room:
            return jsonify(error="ასეთი თამაში არ არსებობს"), 404
        pid = "p_" + "".join(random.choices(string.ascii_letters + string.digits, k=12))
        room["players"][pid] = {"id": pid, "name": name, "score": 0}
        return jsonify(player_id=pid, code=code)

def check_host(room, host_id):
    return room["host_id"] == host_id

@app.post("/api/buzz")
def buzz():
    data = request.get_json() or {}
    code, pid = data.get("code", ""), data.get("player_id", "")
    with lock:
        room = rooms.get(code)
        if not room or pid not in room["players"]:
            return jsonify(error="მოთამაშე ან ოთახი ვერ მოიძებნა"), 404
        if pid not in room["order"]:
            room["order"].append(pid)
        return jsonify(rank=room["order"].index(pid) + 1)

@app.post("/api/next-round")
def next_round():
    data = request.get_json() or {}
    with lock:
        room = rooms.get(data.get("code"))
        if not room or not check_host(room, data.get("host_id")):
            return jsonify(error="მხოლოდ წამყვანს შეუძლია"), 403
        room["round"] += 1
        room["order"] = []
        return jsonify(ok=True)

@app.post("/api/set-score")
def set_score():
    data = request.get_json() or {}
    try:
        score = int(data["score"])
    except (KeyError, TypeError, ValueError):
        return jsonify(error="ქულა უნდა იყოს მთელი რიცხვი"), 400
    with lock:
        room = rooms.get(data.get("code"))
        if not room or not check_host(room, data.get("host_id")):
            return jsonify(error="მხოლოდ წამყვანს შეუძლია"), 403
        pid = data.get("player_id")
        if pid not in room["players"]:
            return jsonify(error="მოთამაშე ვერ მოიძებნა"), 404
        room["players"][pid]["score"] = score
        return jsonify(ok=True)

@app.post("/api/reset-leaderboard")
def reset():
    data = request.get_json() or {}
    with lock:
        room = rooms.get(data.get("code"))
        if not room or not check_host(room, data.get("host_id")):
            return jsonify(error="მხოლოდ წამყვანს შეუძლია"), 403
        for p in room["players"].values():
            p["score"] = 0
        return jsonify(ok=True)

@app.get("/health")
def health():
    return "OK"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
