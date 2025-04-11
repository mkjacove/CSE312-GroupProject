from datetime import timedelta

from flask import Flask, request, render_template, jsonify, session
from utils.auth import auth_bp


app = Flask(__name__)
app.register_blueprint(auth_bp)
app.secret_key = "very_secret_key"
app.permanent_session_lifetime = timedelta(days=1)
app.config.update(SESSION_COOKIE_HTTPONLY=True)


@app.route("/")
def home():
    return render_template("home.html")
@app.route("/change-avatar")
def avatar():
    return render_template("change-avatar.html")
@app.route("/play")
def play():
    return render_template("play.html")
@app.route("/leaderboard")
def leaderboard():
    return render_template("leaderboard.html")
@app.route("/player-statistics")
def stats():
    return render_template("player-statistics.html")
@app.route("/achievements")
def achievements():
    return render_template("achievements.html")
@app.route("/direct-messaging")
def messaging():
    return render_template("direct-messaging.html")  #Apparently, doing this just returns a 200 OK response

@app.route("/api/users/@me")
def get_current_user():
    if "username" in session:
        return jsonify({"id": True, "username": session["username"]})
    return jsonify({"id": None})

# @app.route("/login", methods=['GET'])
# def login():
#     # if request.method == 'GET':
#     print("this is a test")
#     return render_template("login.html")
#     # elif request.method == 'POST':
#     #     print("this is also a test")
#     #     print(request.form)  # needed to import request with flask to access form content
#     #     return "message received!"
#
# @app.route("/handle_login", methods=['POST'])
# def handle_login():
#     print("this is also a test")
#     print(request.form)  # needed to import request with flask to access form content
#     return "message received!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
