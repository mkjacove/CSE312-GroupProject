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
from utils.auth import auth_bp
import imageio.v3 as iio
import random
import logging
import traceback
import re

from threading import Event

COUNTDOWN_START = 10
countdown_abort_event: Event | None = None

# testaccount, theone, pass = T1h2e3%%One
app = Flask(__name__)
# app.secret_key = "very_secret_key"
app.secret_key = os.environ.get("SECRET_KEY", os.urandom(24))
app.permanent_session_lifetime = timedelta(days=1)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=True
)


def redact_tokens(message: str) -> str:
    return re.sub(r"(Cookie:\s*Bearer\s+|access_token=|auth_token=|session=)([^\s&\"']+)", r"\1<REDACTED>", message,
                  flags=re.IGNORECASE)


class RedactingFilter(logging.Filter):
    def filter(self, record):
        record.msg = redact_tokens(str(record.msg))
        return True


log_path = "/app/~log.log"
if not os.path.exists(log_path):
    open(log_path, "a").close()

log_handler = logging.FileHandler(log_path)
log_handler.setLevel(logging.INFO)
log_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
log_handler.addFilter(RedactingFilter())
app.logger.addHandler(log_handler)
app.logger.setLevel(logging.INFO)

complete_log_path = "/app/~complete.log"
if not os.path.exists(complete_log_path):
    open(complete_log_path, "w").close()

complete_log_handler = logging.FileHandler(complete_log_path)
complete_log_handler.setLevel(logging.INFO)
complete_log_handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))
complete_log_handler.addFilter(RedactingFilter())
complete_logger = logging.getLogger("complete_logger")
complete_logger.addHandler(complete_log_handler)
complete_logger.setLevel(logging.INFO)

app.register_blueprint(auth_bp)

lobby = []
game_in_progress = False
first_death_recorded = False
MIN_PLAYERS = 2  # Minimum number of players to start the game


# Serve images
@app.route("/images/<filename>")
def serve_image(filename):
    return send_from_directory(
        os.path.join(app.root_path, "images/"), filename)


@app.route("/")
def home():
    return render_template("home.html")


@app.after_request
def add_header(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response


@app.route("/change-avatar", methods=["GET", "POST"])
def avatar():
    if "username" not in session or not users_collection.find_one({"username": session["username"]}):
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

    return render_template("change-avatar.html", username=session["username"], avatar_url=session["avatar"])


@app.route("/leaderboard")
def leaderboard():
    return render_template("leaderboard.html")


@app.route("/api/users")
def leaderboardusers():
    users = users_collection.find({"games_played": {"$gte": 1}})

    # Convert each user document to a plain dictionary and stringify the ObjectId
    user_list = []
    for user in users:
        user["_id"] = str(user["_id"])  # Optional: convert _id to string
        user_list.append({
            "username": user.get("username", "Unknown"),
            "games_played": user.get("games_played", 0),
            "games_won": user.get("games_won", 0),
        })

    return jsonify(user_list)


@app.route("/player-statistics")
def stats():
    return render_template("player-statistics.html")


@app.route("/achievements")
def achievements():
    if "username" not in session or not users_collection.find_one({"username": session["username"]}):
        return redirect(url_for("home", error="not_signed_in"))
    return render_template("achievements.html")


@app.route("/play")
def play():
    if "username" not in session or not users_collection.find_one({"username": session["username"]}):
        return redirect(url_for("home", error="not_signed_in"))
    return render_template(
        "play.html",
        PLAYER_USERNAME=session["username"],
        PLAYER_AVATAR=session.get("avatar", "user.webp")
    )


@app.route("/api/users/@me")
def get_current_user():
    if "username" in session and (user := users_collection.find_one({"username": session["username"]})):
        achievements = {
            "winner": user.get("games_won", 0) >= 3,
            "consolation": user.get("consolation_prize", False),
            "tile_breaker": user.get("total_tiles", 0) >= 500
        }

        return jsonify({
            "id": True,
            "username": session["username"],
            "avatar": user.get("avatar", "user.webp"),
            "current_tiles": user.get("current_tiles", 0),
            "games_played": user.get("games_played", 0),
            "games_won": user.get("games_won", 0),
            "average_tiles": user.get("average_tiles", 0),
            "total_tiles": user.get("total_tiles", 0),
            "achievements": achievements
        })
    return jsonify({"id": None})


@app.route("/api/users")
def get_all_users():
    users = []
    for user in users_collection.find({}):
        users.append({"username": user.get("username")})
    return jsonify(users)


@app.route("/api/users/<username>/stats")
def get_user_stats(username):
    user = users_collection.find_one({"username": username})
    if user is None:
        return jsonify({"error": "User not found"}), 404
    stats = {
        "games_played": user.get("games_played", 0),
        "games_won": user.get("games_won", 0),
        "average_tiles": user.get("average_tiles", 0),
        "total_tiles": user.get("total_tiles", 0),
    }
    return jsonify(stats)


# ---------- WebSocket setup for /game namespace ----------

socketio = SocketIO(app, cors_allowed_origins="*")

# Game grid settings (must match client!)
TILE_SIZE = 50
GRID_COLS = 150
GRID_ROWS = 150
GRID_WIDTH = TILE_SIZE * GRID_COLS
GRID_HEIGHT = TILE_SIZE * GRID_ROWS

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
players = {}  # sid → { x, y, username, board_level, avatar }


@socketio.on('stepped-on-tile', namespace='/game')
def stepped_on_tile(data):
    user = data['username']
    if user is not None:
        previous_tiles = users_collection.find_one({"username": user}).get('current_tiles')
        users_collection.update_one({"username": user}, {"$set": {"current_tiles": previous_tiles + 1}})
    return


def _me():
    return {
        "username": session.get("username"),
        "avatar": session.get("avatar", "user.webp")
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

    player = {'sid': sid, 'username': session["username"], 'avatar': session.get("avatar", "user.webp")}
    lobby.append(player)

    socketio.emit('lobby', {'players': [p['username'] for p in lobby]}, namespace='/game')
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
    global game_in_progress, players, first_death_recorded
    first_death_recorded = False
    players.clear()

    if len(lobby) < MIN_PLAYERS:
        return

    game_in_progress = True
    socketio.emit('chat', {'text': "The game is starting!"}, namespace='/game')
    socketio.emit('game_start', {}, namespace='/game')

    for player in lobby:
        sid = player['sid']
        spawn_x, spawn_y = find_random_white_tile(1)
        players[sid] = {
            "x": spawn_x,
            "y": spawn_y,
            "board_level": 1,
            'username': player['username'],
            'avatar': player['avatar']
        }
        user = users_collection.find_one({"username": players[sid]["username"]})
        previous_games_played = user.get("games_played")
        users_collection.update_one({"username": players[sid]["username"]},
                                    {"$set": {"games_played": previous_games_played + 1}})
        users_collection.update_one({"username": players[sid]["username"]}, {"$set": {"current_tiles": 0}})

    socketio.emit('tile-init', {'tileStates': tile_states}, namespace='/game')
    socketio.emit('players', {'players': players}, namespace='/game')



@socketio.on('rejoin', namespace='/game')
def handle_rejoin():
    global game_in_progress, lobby

    # If a game is in progress, refuse
    if game_in_progress:
        emit('chat',
             {'text': "The game is already in progress. Please wait for the next round."},
             namespace='/game',
             to=request.sid)
        return

    sid = request.sid

    # Don't double-add
    if any(p['sid'] == sid for p in lobby):
        return

    # Rebuild their player object from session
    player = {
        'sid': sid,
        'username': session.get('username'),
        'avatar': session.get('avatar', 'user.webp')
    }
    lobby.append(player)

    # Announce them joining
    emit('chat',
         {'text': f"{player['username']} has joined the lobby!"},

         namespace='/game',
         broadcast=True)
    socketio.emit('lobby', {'players': [p['username'] for p in lobby]}, namespace='/game')

    # If they've just pushed you over the player count, start a new countdown
    if len(lobby) >= MIN_PLAYERS:
        schedule_countdown()



@socketio.on('move', namespace='/game')
def handle_move(data):
    global players

    sid = request.sid
    if sid not in players:
        return
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
    username = data['username']
    now = datetime.now()

    if tile_states[board].get(key, 0) == 0:
        tile_states[board][key] = 1
        tile_timestamps[board][key] = now
        emit('tile-update', {'key': key, 'state': 1, 'board': board, 'username': username},
             namespace='/game', broadcast=True)

    # 1 ➔ 2 after delay
    due = []
    for k, st in list(tile_states[board].items()):
        if st == 1 and now - tile_timestamps[board].get(k, now) >= TILE_STATE_TRANSITION_DELAY:
            tile_states[board][k] = 2
            del tile_timestamps[board][k]
            due.append(k)

    for k in due:
        emit('tile-update', {'key': k, 'state': 2, 'board': board, 'username': username},
             namespace='/game', broadcast=True)

    # re‑broadcast clicked tile
    emit('tile-update', {'key': key, 'state': tile_states[board].get(key, 0), 'board': board, 'username': username},
         namespace='/game', broadcast=True)


@socketio.on('reset', namespace='/game')
def handle_reset():
    global players

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
        emit('chat', {'text': f"{player['username']} fell to Board {current_board + 1}!"}, namespace='/game',
             broadcast=True)


    else:
        # eliminate player
        emit('chat', {'text': f"{player['username']} was eliminated!"}, namespace='/game', broadcast=True)

        print("before delete players: ", players)
        if sid in players:
            username = players[sid]["username"]

            global first_death_recorded
            if not first_death_recorded:
                first_death_recorded = True
                users_collection.update_one(
                    {"username": username},
                    {"$set": {"consolation_prize": True}}
                )

            del players[sid]
            print(f"[handle_reset]   → deleted sid, players_after={players}")

        # notify *only* the eliminated player to redirect
        emit('eliminated', namespace='/game', to=sid)

        emit('players', {'players': players}, namespace='/game', broadcast=True)

    if len(players) == 1:
        winner_sid = next(iter(players))  # Get the last player standing
        winner = players[winner_sid]
        socketio.emit('chat', {'text': f"{winner['username']} is the last player standing and has won the game!"},
                      namespace='/game')

        user = users_collection.find_one({"username": winner["username"]})
        users_collection.update_one({"username": user["username"]},
                                    {"$set": {"games_won": user["games_won"] + 1}})
        user = users_collection.find_one({"username": winner["username"]})

        if user["games_won"] >= 3:
            users_collection.update_one({"username": user["username"]},
                                        {"$set": {"winner": True}})

        for player in lobby:
            socketio.emit('victory', {'username': winner['username'], 'redirect': '/'}, namespace='/game',
                          to=player["sid"])
        reset_game()
        return


def reset_game():
    global game_in_progress, lobby, players

    global tile_states, tile_timestamps, countdown_abort_event

    # 1) Flip the flag so new connects queue into the lobby
    game_in_progress = False

    # 2) Clear out all player lists
    lobby.clear()
    players.clear()

    # 3) Reset every board’s tiles & timers
    for b in (1, 2, 3):
        tile_states[b].clear()
        tile_timestamps[b].clear()

    # 4) Forget any countdown in flight
    countdown_abort_event = None

    # 5) Announce end-of-game and send clients back to lobby view
    socketio.emit('chat', {'text': "🏁 The game has ended! Waiting for players to join the next round."},
                  namespace='/game')
    socketio.emit('game_reset', {}, namespace='/game')


@socketio.on('disconnect', namespace='/game')
def ws_disconnect(sid, *args):
    global game_in_progress, players
    sid = request.sid

    if game_in_progress:
        if sid in players:
            del players[sid]

        if len(players) == 1:
            winner_sid = next(iter(players))  # Get the last player standing
            winner = players[winner_sid]
            socketio.emit('chat', {'text': f"{winner['username']} is the last player standing and has won the game!"},
                          namespace='/game')
            for player in lobby:
                socketio.emit('victory', {'username': winner['username'], 'redirect': '/'}, namespace='/game',
                              to=player["sid"])
            reset_game()
            return

    else:
        if lobby != []:
            for player in lobby:
                if player['sid'] == sid:
                    lobby.remove(player)
                    emit('chat', {'text': f"{player['username']} has left the lobby."}, namespace='/game', broadcast=True)
                    break

    socketio.emit('lobby', {'players': [p['username'] for p in lobby]}, namespace='/game')
    socketio.emit('players', {'players': players}, namespace='/game')

    user = users_collection.find_one({"username": session["username"]})
    games_played = user.get("games_played", 0)
    previous_games_played = games_played - 1
    previous_average_tiles = user.get("average_tiles", 0)
    previous_total_tiles = user.get("total_tiles", 0)

    users_collection.update_one({"username": session["username"]},{"$set": {"total_tiles": user.get("total_tiles") + user.get("current_tiles", 0)}})
    total_tiles = previous_total_tiles + user.get("current_tiles", 0)
    new_average = total_tiles / user.get("games_played", 1)
    users_collection.update_one({"username": session["username"]},
                                {"$set": {"average_tiles": new_average}})
    session["average_tiles"] = new_average
    session.modified = True
    if user.get("total_tiles") >= 500:
        users_collection.update_one({"username": session["username"]},
                                    {"$set": {"tile_breaker": True}})


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