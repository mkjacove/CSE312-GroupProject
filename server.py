import os
import uuid
from datetime import timedelta, datetime
from flask import (
    Flask, request, render_template, jsonify,
    session, redirect, url_for, send_from_directory,
    g
)
from flask_socketio import SocketIO, emit
from utils.db import users_collection
import imageio.v3 as iio
import random
import logging
import traceback
import re
from threading import Event

COUNTDOWN_START = 10
countdown_abort_event: Event | None = None

#testaccount, theone, pass = T1h2e3%%One
app = Flask(__name__)
app.secret_key = "very_secret_key"
app.permanent_session_lifetime = timedelta(days=1)
app.config.update(SESSION_COOKIE_HTTPONLY=True)

log_path = "/app/~log.log"
if not os.path.exists(log_path):
    open(log_path, "a").close()

log_handler = logging.FileHandler(log_path)
log_handler.setLevel(logging.INFO)
log_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
app.logger.addHandler(log_handler)
app.logger.setLevel(logging.INFO)

complete_log_path = "/app/~complete.log"
if not os.path.exists(complete_log_path):
    open(complete_log_path, "w").close()

complete_log_handler = logging.FileHandler(complete_log_path)
complete_log_handler.setLevel(logging.INFO)
complete_log_handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))
complete_logger = logging.getLogger("complete_logger")
complete_logger.addHandler(complete_log_handler)
complete_logger.setLevel(logging.INFO)

from utils.auth import auth_bp
app.register_blueprint(auth_bp)

lobby = []
game_in_progress = False
MIN_PLAYERS = 2  # Minimum number of players to start the game

# Serve images
@app.route("/images/<filename>")
def serve_image(filename):
    return send_from_directory(
        os.path.join(app.root_path, "images/"),filename)
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

        img = iio.imread(file.stream)

        # build unique filename
        ext = os.path.splitext(file.filename)[1].lower()
        unique_name = f"{uuid.uuid4()}{ext}"

        # Square crop
        h, w = img.shape[:2]
        side_length = min(h, w)
        cropped = img[0:side_length, 0:side_length]

        # Save
        file_path = os.path.join(app.root_path, "images/", unique_name)

        iio.imwrite(file_path, cropped)

        # update session & DB
        session["avatar"] = unique_name
        users_collection.update_one(
            {"username": session["username"]},
            {"$set": {"avatar": unique_name}})

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

# ---------- WebSocket setup for /game namespace ----------

socketio = SocketIO(app, cors_allowed_origins="*")

# Game grid settings (must match client!)
TILE_SIZE  = 50
GRID_COLS  = 500
GRID_ROWS  = 500
GRID_WIDTH = TILE_SIZE * GRID_COLS
GRID_HEIGHT= TILE_SIZE * GRID_ROWS

# Time interval for state transition (2 seconds)
TILE_STATE_TRANSITION_DELAY = timedelta(seconds=2)

# In‑memory game state
tile_states = {
    1: {},
    2: {},
    3: {}
}
tile_timestamps = {
    1: {},
    2: {},
    3: {}
}
players         = {}  # sid → { x, y, username, board_level, avatar }

def _me():
    return {
        "username": session.get("username"),
        "avatar":   session.get("avatar", "user.webp")
    }

def find_random_white_tile(board_level):
    """Find a random (x, y) on a white tile (state == 0)."""
    for _ in range(250):
        col = random.randint(0, GRID_COLS - 1)
        row = random.randint(0, GRID_ROWS - 1)
        key = f"{col},{row}"
        if key not in tile_states[board_level] or tile_states[board_level][key] == 0:
            x = col * TILE_SIZE + TILE_SIZE / 2
            y = row * TILE_SIZE + TILE_SIZE / 2
            return x, y
    # fallback: center if nothing found
    return GRID_WIDTH / 2, GRID_HEIGHT / 2

@socketio.on('connect', namespace='/game')
def ws_connect():
    global game_in_progress

    if game_in_progress:
        emit('chat', {'text': "The game is already in progress. Please wait for the next round."}, namespace='/game')
        return

    sid = request.sid

    player = {'sid': sid, 'username': session["username"],  'avatar': session.get("avatar", "user.webp")}
    lobby.append(player)

    emit('chat', {'text': f"{player['username']} has joined the lobby!"}, namespace='/game', broadcast=True)
    # Check if the game can start (at least MIN_PLAYERS)
    if len(lobby) >= MIN_PLAYERS:
        schedule_countdown()

def schedule_countdown():
    """Abort any running countdown, then start a fresh 10s countdown."""
    global countdown_abort_event

    # abort previous countdown if running
    if countdown_abort_event:
        countdown_abort_event.set()

    # new abort-event for this countdown
    countdown_abort_event = Event()
    # fire off the background task
    socketio.start_background_task(_countdown_worker, countdown_abort_event)

def _countdown_worker(abort_event: Event):
    """Emit 'countdown' every second, then call start_game() at 0."""
    remaining = COUNTDOWN_START
    while remaining > 0:
        socketio.emit('countdown', {'time': remaining}, namespace='/game')
        socketio.sleep(1)
        if abort_event.is_set():
            return
        remaining -= 1

    # final 0 and start
    socketio.emit('countdown', {'time': 0}, namespace='/game')
    start_game()

def start_game():
    global game_in_progress

    if len(lobby) < MIN_PLAYERS:
        return

    game_in_progress = True
    socketio.emit('chat', {'text': "The game is starting!"}, namespace='/game')
    socketio.emit('game_start', {}, namespace='/game')

    for player in lobby:
        sid= player['sid']
        spawn_x, spawn_y = find_random_white_tile(1)
        players[sid] = {
            "x": spawn_x,
            "y": spawn_y,
            "board_level": 1,
            'username': player['username'],
            'avatar': player['avatar']
        }
    socketio.emit('tile-init', {'tileStates': tile_states}, namespace='/game')
    socketio.emit('players', {'players': players}, namespace='/game')

@socketio.on('move', namespace='/game')
def handle_move(data):
    sid = request.sid
    if sid not in players:
        players[sid] = {'x': 0, 'y': 0, **_me()}
    players[sid].update({
        'x': data['x'],
        'y': data['y'],
        **_me()
    })
    emit('players', {'players': players}, namespace='/game', broadcast=True)

@socketio.on('tile', namespace='/game')
def handle_tile(data):
    sid = request.sid
    player = players.get(sid)
    if not player:
        return

    board = data['board']
    key = data['key']
    now = datetime.now()

    if tile_states[board].get(key, 0) == 0:
        tile_states[board][key] = 1
        tile_timestamps[board][key] = now
        emit('tile-update', {'key': key, 'state': 1, 'board': board},
             namespace='/game', broadcast=True)

    # 1 ➔ 2 after delay
    due = []
    for k, st in list(tile_states[board].items()):
        if st == 1 and now - tile_timestamps[board].get(k, now) >= TILE_STATE_TRANSITION_DELAY:
            tile_states[board][k] = 2
            del tile_timestamps[board][k]
            due.append(k)

    for k in due:
        emit('tile-update', {'key': k, 'state': 2, 'board': board},
             namespace='/game', broadcast=True)

    # re‑broadcast clicked tile
    emit('tile-update', {'key': key, 'state': tile_states[board].get(key, 0), 'board': board},
         namespace='/game', broadcast=True)

@socketio.on('reset', namespace='/game')
def handle_reset():
    sid = request.sid
    player = players.get(sid)
    if not player:
        return

    current_board = player.get('board_level', 1)
    if current_board < 3:
        # move player to next board
        players[sid]['board_level'] = current_board + 1

        # reposition player back to a random location
        spawn_x, spawn_y = find_random_white_tile(board_level=current_board + 1)
        players[sid]['x'] = spawn_x
        players[sid]['y'] = spawn_y

        # tell client maybe (optional: pop-up "Level 2!")
        emit('chat', {'text': f"{player['username']} fell to Board {current_board+1}!"}, namespace='/game', broadcast=True)

    else:
        # eliminate player
        emit('chat', {'text': f"{player['username']} was eliminated!"}, namespace='/game', broadcast=True)

        # notify *only* the eliminated player to redirect
        emit('eliminated', {'redirect': '/'}, namespace='/game', to=sid)

        players.pop(sid, None)
        emit('players', {'players': players}, namespace='/game', broadcast=True)
    if len(players) == 1:
        winner_sid = next(iter(players))  # Get the last player standing
        winner = players[winner_sid]
        emit('chat', {'text': f"{winner['username']} is the last player standing and has won the game!"},
             namespace='/game', broadcast=True)
        reset_game()
        return
def reset_game():
    global game_in_progress, lobby, players
    game_in_progress = False  # Game is no longer in progress
    players = {}  # Clear players data
    lobby = []  # Clear the lobby

    emit('chat', {'text': "The game has ended! Waiting for players to join the next round."}, namespace='/game',
         broadcast=True)


@socketio.on('disconnect', namespace='/game')
def ws_disconnect():
    global game_in_progress
    sid = request.sid

    if game_in_progress:
        if sid in players:
            players.pop(sid, None)

        if len(players) == 1:
            winner_sid = next(iter(players))
            winner = players[winner_sid]
            emit('chat', {'text': f"{winner['username']} is the last player standing and has won the game!"},
                 namespace='/game', broadcast=True)
            reset_game()
            return
    else:
        for player in lobby:
            if player['sid'] == sid:
                lobby.remove(player)
                emit('chat', {'text': f"{player['username']} has left the lobby."}, namespace='/game', broadcast=True)
                break

    emit('players', {'players': players}, namespace='/game', broadcast=True)

@app.before_request
def log_request_info():
    user = session.get("username", "guest")
    ip = request.remote_addr
    method = request.method
    path = request.path
    status = "N/A"
    g.log_prefix = f"{user}@{ip} - {method} {path}"

@app.after_request
def log_response_info(response):
    status = response.status_code
    app.logger.info(f"{g.log_prefix} -> {status}")
    return response


@app.errorhandler(Exception)
def handle_exception(e):
    with open("/app/~error.log", "a") as f:
        f.write(f"\n--- ERROR ---\n")
        f.write(traceback.format_exc())
    return "Internal Server Error", 500

@app.route("/force-error")
def force_error():
    raise RuntimeError("This is a test error!")

@app.before_request
def log_raw_request():
    method = request.method
    path = request.full_path
    headers = dict(request.headers)
    ip = request.remote_addr

    headers.pop("Authorization", None)
    if "Cookie" in headers:
        # Remove auth token from cookies
        headers["Cookie"] = re.sub(r"auth_token=[^;]+", "auth_token=***", headers["Cookie"])

    body = request.get_data()
    try:
        body_text = body.decode("utf-8")
        if "password" in path or "login" in path or "register" in path:
            body_text = "[BODY REDACTED]"
    except UnicodeDecodeError:
        body_text = "[BINARY DATA OMITTED]"

    body_text = body_text[:2048]

    complete_logger.info(
        f"--- Incoming Request from {ip} ---\n"
        f"{method} {path}\n"
        f"Headers:\n{headers}\n"
        f"Body:\n{body_text}\n"
        f"--- End Request ---\n"
    )

@app.after_request
def log_raw_response(response):
    headers = dict(response.headers)

    if not response.direct_passthrough:
        try:
            body = response.get_data()
            body_text = body.decode("utf-8")[:2048]
        except UnicodeDecodeError:
            body_text = "[BINARY DATA OMITTED]"
    else:
        body_text = "[RESPONSE IN DIRECT PASSTHROUGH MODE]"

    complete_logger.info(
        f"--- Outgoing Response ---\n"
        f"Status: {response.status}\n"
        f"Headers:\n{headers}\n"
        f"Body:\n{body_text}\n"
        f"--- End Response ---\n"
    )
    return response

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=8080, allow_unsafe_werkzeug=True)
