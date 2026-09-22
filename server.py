from flask import Flask, request, jsonify, send_from_directory
import random
import string
import threading
import time
import os

app = Flask(__name__, static_folder=".", static_url_path="")

rooms = {}
lock = threading.Lock()

# ქულების ციკლი
POINT_CYCLE = [10, 20, 30, 40, 50]


def make_code():
    while True:
        code = "".join(random.choices(string.digits, k=6))
        if code not in rooms:
            return code


def current_points(room):
    return POINT_CYCLE[room["points_index"] % len(POINT_CYCLE)]


def state(room):
    players = list(room["players"].values())

    ranks = {
        pid: i + 1
        for i, pid in enumerate(room["order"])
    }

    return {
        "code": room["code"],
        "round": room["round"],
        "points": current_points(room),
        "order": room["order"],
        "rank_map": ranks,
        "resolved": room["resolved"],
        "players": players
    }


@app.get("/")
def index():
    return send_from_directory(".", "index.html")


@app.get("/<path:path>")
def static_file(path):
    return send_from_directory(".", path)


# -----------------------------------
# STATE
# -----------------------------------

@app.get("/api/state")
def get_state():
    code = request.args.get("code", "").strip()

    with lock:
        room = rooms.get(code)

        if not room:
            return jsonify(
                error="ოთახი ვერ მოიძებნა"
            ), 404

        return jsonify(state(room))


# -----------------------------------
# CREATE GAME
# -----------------------------------

@app.post("/api/create")
def create():
    with lock:
        code = make_code()

        host_id = (
            "h_" +
            "".join(
                random.choices(
                    string.ascii_letters + string.digits,
                    k=16
                )
            )
        )

        rooms[code] = {
            "code": code,
            "host_id": host_id,

            "round": 1,

            # 0 = 10
            # 1 = 20
            # 2 = 30
            # 3 = 40
            # 4 = 50
            "points_index": 0,

            # მიმდინარე რაუნდის დაჭერების რიგი
            "order": [],

            # მიმდინარე რაუნდში უკვე შეფასებული მოთამაშეები
            "resolved": [],

            # მოთამაშეები
            "players": {},

            "created": time.time()
        }

        return jsonify(
            code=code,
            host_id=host_id,
            points=current_points(rooms[code])
        )


# -----------------------------------
# JOIN GAME
# -----------------------------------

@app.post("/api/join")
def join():
    data = request.get_json() or {}

    code = str(
        data.get("code", "")
    ).strip()

    name = str(
        data.get("name", "")
    ).strip()[:40]

    player_id = str(
        data.get("player_id", "")
    ).strip()

    if len(code) != 6 or not code.isdigit():
        return jsonify(
            error="კოდი უნდა იყოს 6 ციფრი"
        ), 400

    if not name:
        return jsonify(
            error="შეიყვანე სახელი"
        ), 400

    with lock:
        room = rooms.get(code)

        if not room:
            return jsonify(
                error="ასეთი თამაში არ არსებობს"
            ), 404

        # თუ მოთამაშეს უკვე აქვს player_id,
        # refresh-ის შემდეგ იგივე მოთამაშე აღდგეს
        if player_id and player_id in room["players"]:

            room["players"][player_id]["name"] = name

            return jsonify(
                player_id=player_id,
                code=code,
                score=room["players"][player_id]["score"]
            )

        # ახალი მოთამაშე
        pid = (
            "p_" +
            "".join(
                random.choices(
                    string.ascii_letters + string.digits,
                    k=16
                )
            )
        )

        room["players"][pid] = {
            "id": pid,
            "name": name,
            "score": 0
        }

        return jsonify(
            player_id=pid,
            code=code,
            score=0
        )


# -----------------------------------
# HOST CHECK
# -----------------------------------

def check_host(room, host_id):
    return (
        bool(host_id)
        and room["host_id"] == host_id
    )


# -----------------------------------
# BUZZ
# -----------------------------------

@app.post("/api/buzz")
def buzz():
    data = request.get_json() or {}

    code = str(
        data.get("code", "")
    ).strip()

    pid = str(
        data.get("player_id", "")
    ).strip()

    with lock:
        room = rooms.get(code)

        if not room:
            return jsonify(
                error="ოთახი ვერ მოიძებნა"
            ), 404

        if pid not in room["players"]:
            return jsonify(
                error="მოთამაშე ვერ მოიძებნა"
            ), 404

        # ერთ რაუნდში ერთ მოთამაშეს მხოლოდ ერთხელ შეუძლია დაჭერა
        if pid not in room["order"]:

            room["order"].append(pid)

            rank = len(room["order"])

        else:

            rank = room["order"].index(pid) + 1

        return jsonify(
            ok=True,
            rank=rank
        )


# -----------------------------------
# SCORE
# -----------------------------------

@app.post("/api/score")
def score():
    data = request.get_json() or {}

    code = str(
        data.get("code", "")
    ).strip()

    host_id = str(
        data.get("host_id", "")
    ).strip()

    sign = str(
        data.get("sign", "")
    ).strip()

    if sign not in ("plus", "minus"):
        return jsonify(
            error="არასწორი ქულის მოქმედება"
        ), 400

    with lock:

        room = rooms.get(code)

        if not room:
            return jsonify(
                error="ოთახი ვერ მოიძებნა"
            ), 404

        if not check_host(room, host_id):
            return jsonify(
                error="მხოლოდ წამყვანს შეუძლია"
            ), 403

        # შემდეგი მოთამაშე რიგში
        index = len(room["resolved"])

        if index >= len(room["order"]):
            return jsonify(
                error="შესაფასებელი მოთამაშე აღარ არის"
            ), 400

        player_id = room["order"][index]

        points = current_points(room)

        if player_id not in room["players"]:
            return jsonify(
                error="მოთამაშე ვერ მოიძებნა"
            ), 404

        # + ან -
        if sign == "plus":
            room["players"][player_id]["score"] += points
        else:
            room["players"][player_id]["score"] -= points

        # ვინ და როგორ შეფასდა
        room["resolved"].append({
            "id": player_id,
            "sign": sign,
            "points": points
        })

        return jsonify(
            ok=True,
            player_id=player_id,
            sign=sign,
            points=points,
            score=room["players"][player_id]["score"]
        )


# -----------------------------------
# NEXT ROUND
# -----------------------------------

@app.post("/api/next-round")
def next_round():
    data = request.get_json() or {}

    code = str(
        data.get("code", "")
    ).strip()

    host_id = str(
        data.get("host_id", "")
    ).strip()

    with lock:

        room = rooms.get(code)

        if not room:
            return jsonify(
                error="ოთახი ვერ მოიძებნა"
            ), 404

        if not check_host(room, host_id):
            return jsonify(
                error="მხოლოდ წამყვანს შეუძლია"
            ), 403

        # ახალი რაუნდი
        room["round"] += 1

        # შემდეგი ქულა
        room["points_index"] = (
            room["points_index"] + 1
        ) % len(POINT_CYCLE)

        # მიმდინარე რაუნდის მონაცემების გასუფთავება
        room["order"] = []
        room["resolved"] = []

        return jsonify(
            ok=True,
            round=room["round"],
            points=current_points(room)
        )


# -----------------------------------
# MANUAL SCORE
# -----------------------------------
# ძველი ფუნქცია შენარჩუნებულია,
# თუ მომავალში დაგვჭირდება ხელით ჩასწორება.

@app.post("/api/set-score")
def set_score():
    data = request.get_json() or {}

    try:
        score_value = int(
            data["score"]
        )
    except (
        KeyError,
        TypeError,
        ValueError
    ):
        return jsonify(
            error="ქულა უნდა იყოს მთელი რიცხვი"
        ), 400

    code = str(
        data.get("code", "")
    ).strip()

    host_id = str(
        data.get("host_id", "")
    ).strip()

    player_id = str(
        data.get("player_id", "")
    ).strip()

    with lock:

        room = rooms.get(code)

        if not room:
            return jsonify(
                error="ოთახი ვერ მოიძებნა"
            ), 404

        if not check_host(room, host_id):
            return jsonify(
                error="მხოლოდ წამყვანს შეუძლია"
            ), 403

        if player_id not in room["players"]:
            return jsonify(
                error="მოთამაშე ვერ მოიძებნა"
            ), 404

        room["players"][player_id]["score"] = score_value

        return jsonify(
            ok=True,
            score=score_value
        )


# -----------------------------------
# RESET ALL SCORES
# -----------------------------------

@app.post("/api/reset-leaderboard")
def reset_leaderboard():
    data = request.get_json() or {}

    code = str(
        data.get("code", "")
    ).strip()

    host_id = str(
        data.get("host_id", "")
    ).strip()

    with lock:

        room = rooms.get(code)

        if not room:
            return jsonify(
                error="ოთახი ვერ მოიძებნა"
            ), 404

        if not check_host(room, host_id):
            return jsonify(
                error="მხოლოდ წამყვანს შეუძლია"
            ), 403

        for player in room["players"].values():
            player["score"] = 0

        return jsonify(
            ok=True
        )


# -----------------------------------
# HEALTH
# -----------------------------------

@app.get("/health")
def health():
    return "OK"


# -----------------------------------
# START
# -----------------------------------

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(
            os.environ.get(
                "PORT",
                8000
            )
        )
    )