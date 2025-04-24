import os
import uuid
from datetime import timedelta, datetime
from flask import (
    Flask, request, render_template, jsonify,
    session, redirect, url_for, send_from_directory
)
from flask_socketio import SocketIO, emit
from utils.auth import auth_bp
from utils.db import users_collection
from PIL import Image
import random

#testaccount, theone, pass = T1h2e3%%One
# ─── Flask setup ─────────────────────────────────────────────────────────────
app = Flask(__name__)
app.register_blueprint(auth_bp)
app.secret_key = "very_secret_key"
app.permanent_session_lifetime = timedelta(days=1)
app.config.update(SESSION_COOKIE_HTTPONLY=True)

# ─── HTTP ROUTES ──────────────────────────────────────────────────────────────

@app.route("/images/<filename>")
def serve_image(filename):
    return send_from_directory(
        os.path.join(app.root_path, "images"),
        filename
    )

@app.route("/")
def home():
    return render_template("home.html")

@app.route("/change-avatar", methods=["GET", "POST"])
def avatar():
    if "username" not in session:
        return redirect(url_for("home", error="not_signed_in"))

    if request.method == "POST":
        file = request.files.get("avatar")
        if not file or file.filename == "":
            return "No file uploaded", 400

        ext = os.path.splitext(file.filename)[1].lower()
        unique_name = f"{uuid.uuid4()}{ext}"

        file_path = os.path.join(app.root_path, "images", unique_name)
        img = Image.open(file.stream).convert("RGBA")
        w, h = img.size
        side = min(w, h)
        cropped = img.crop((0, 0, side, side))
        cropped.save(file_path)

        session["avatar"] = unique_name
        users_collection.update_one(
            {"username": session["username"]},
            {"$set": {"avatar": unique_name}}
        )
        return redirect(url_for("avatar"))

    return render_template("change-avatar.html")

@app.route("/leaderboard")
def leaderboard():
    return render_template("leaderboard.html")

@app.route("/player-statistics")
def stats():
    return render_template("player-statistics.html")

@app.route("/achievements")
def achievements():
    if "username" not in session:
        return redirect(url_for("home", error="not_signed_in"))
    return render_template("achievements.html")

@app.route("/direct-messaging")
def messaging():
    if "username" not in session:
        return redirect(url_for("home", error="not_signed_in"))
    return render_template("direct-messaging.html")

@app.route("/play")
def play():
    if "username" not in session:
        return redirect(url_for("home", error="not_signed_in"))
    return render_template(
        "play.html",
        PLAYER_USERNAME=session["username"],
        PLAYER_AVATAR=session.get("avatar", "user.webp")
    )

@app.route("/api/users/@me")
def get_current_user():
    if "username" in session and users_collection.find_one({"username": session["username"]}):
        return jsonify({
            "id": True,
            "username": session["username"],
            "avatar": session.get("avatar", "user.webp")
        })
    return jsonify({"id": None})

# ─── WebSocket setup for /game namespace ──────────────────────────────────────

socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

# Game grid constants (must match client)
TILE_SIZE  = 50
GRID_COLS  = 500
GRID_ROWS  = 500
GRID_WIDTH = TILE_SIZE * GRID_COLS
GRID_HEIGHT= TILE_SIZE * GRID_ROWS

# Delay for tiles to transition 1→2
TILE_STATE_TRANSITION_DELAY = timedelta(seconds=2)

# In‑memory per‑board state
tile_states     = {1: {}, 2: {}, 3: {}}
tile_timestamps = {1: {}, 2: {}, 3: {}}
players         = {}  # sid → { x, y, username, avatar, board_level }

def _me():
    return {
        "username": session.get("username"),
        "avatar":   session.get("avatar", "user.webp")
    }

@socketio.on('connect', namespace='/game')
def ws_connect():
    sid = request.sid
    spawn_x = random.randint(0, GRID_WIDTH - TILE_SIZE)
    spawn_y = random.randint(0, GRID_HEIGHT - TILE_SIZE)
    
    players[sid] = {
        "x": spawn_x,
        "y": spawn_y,
        "board_level": 1,  # Always spawn on the top board (board_level 1)
        **_me()
    }
    
    # send nested tileStates: {1:{...}, 2:{...}, 3:{...}}
    emit('tile-init', {'tileStates': tile_states}, namespace='/game')
    emit('players', {'players': players}, namespace='/game', broadcast=True)

@socketio.on('move', namespace='/game')
def handle_move(data):
    sid = request.sid
    p = players.get(sid)
    if not p:
        return
    p['x'], p['y'] = data['x'], data['y']

    # check death on black tile
    key = f"{int(p['x']//TILE_SIZE)},{int(p['y']//TILE_SIZE)}"
    b   = p['board_level']
    if tile_states[b].get(key) == 2:
        if b < 3:
            p['board_level'] += 1
            emit('chat', {'text': f"{p['username']} fell to Board {b+1}!"}, namespace='/game', broadcast=True)
        else:
            emit('chat', {'text': f"{p['username']} was eliminated!"}, namespace='/game', broadcast=True)
            emit('eliminated', {'redirect': url_for('home')}, room=sid)

    emit('players', {'players': players}, namespace='/game', broadcast=True)

@socketio.on('tile', namespace='/game')
def handle_tile(data):
    key   = data['key']
    board = data.get('board', 1)
    now   = datetime.now()

    # 0 → 1
    if tile_states[board].get(key, 0) == 0:
        tile_states[board][key]     = 1
        tile_timestamps[board][key] = now
        emit('tile-update',
             {'key': key, 'state': 1, 'board': board},
             namespace='/game', broadcast=True)

    # 1 → 2 after delay on all boards
    for b in (1, 2, 3):
        due = []
        for k, st in list(tile_states[b].items()):
            ts = tile_timestamps[b].get(k)
            if st == 1 and ts and now - ts >= TILE_STATE_TRANSITION_DELAY:
                tile_states[b][k] = 2
                del tile_timestamps[b][k]
                due.append(k)
        for k in due:
            emit('tile-update',
                 {'key': k, 'state': 2, 'board': b},
                 namespace='/game', broadcast=True)

    # re‑broadcast the clicked tile
    emit('tile-update',
         {'key': key, 'state': tile_states[board].get(key, 0), 'board': board},
         namespace='/game', broadcast=True)

@socketio.on('disconnect', namespace='/game')
def ws_disconnect():
    players.pop(request.sid, None)
    emit('players', {'players': players}, namespace='/game', broadcast=True)

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=8080,  allow_unsafe_werkzeug=True)
