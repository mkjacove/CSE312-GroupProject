import os
from datetime import timedelta

import uuid
from flask import Flask, request, render_template, jsonify, session, redirect, url_for, send_from_directory
from utils.auth import auth_bp
from utils.db import users_collection

#testaccount, theone, pass = T1h2e3%%One

app = Flask(__name__)
app.register_blueprint(auth_bp)
app.secret_key = "very_secret_key"
app.permanent_session_lifetime = timedelta(days=1)
app.config.update(SESSION_COOKIE_HTTPONLY=True)


@app.route("/")
def home():
    return render_template("home.html")
@app.route("/change-avatar", methods=["POST"])
def upload_avatar():
    if "username" not in session:
        return redirect(url_for("home", error="not_signed_in"))

    if "avatar" not in request.files:
        return "No file uploaded", 400

    file = request.files["avatar"]
    if file.filename == "":
        return "No selected file", 400

    ext = os.path.splitext(file.filename)[1].lower()
    unique_name = f"{uuid.uuid4()}{ext}"
    file_path = os.path.join("images/", unique_name)
    file.save(file_path)
    session["avatar"] = unique_name

    users_collection.update_one({"username": session.get("username")}, {"$set": {"avatar":unique_name}})
    return redirect(url_for("avatar"))
@app.route("/change-avatar")
def avatar():
    if "username" not in session:
        return redirect(url_for("home", error="not_signed_in"))
    return render_template("change-avatar.html")
@app.route('/images/<filename>')
def serve_image(filename):

    return send_from_directory('images/', filename)
@app.route("/play")
def play():
    if "username" not in session:
        return redirect(url_for("home", error="not_signed_in"))
    return render_template("play.html")
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
    return render_template("direct-messaging.html")  #Apparently, doing this just returns a 200 OK response
@app.route("/api/users/@me")
def get_current_user():
    if "username" in session and users_collection.find_one({"username": session["username"]}):
        return jsonify({"id": True, "username": session["username"], "avatar": session.get("avatar",
                                                                                     "user.webp")})
    return jsonify({"id": None})

@app.route("/canvas")
def canvas():
    return render_template("canvas.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)

