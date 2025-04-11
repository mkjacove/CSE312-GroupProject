from flask import Blueprint, render_template, request, redirect, url_for, abort
from werkzeug.security import generate_password_hash, check_password_hash
from utils.db import users_collection
from flask import session
import json

auth_bp = Blueprint("auth", __name__, url_prefix="")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        user = users_collection.find_one({"username": username})
        if user and check_password_hash(user["password"], password):
            print(f"✅ Logged in as {username}")
            session["username"] = user["username"]
            return "logged in"
        else:
            print("❌ Invalid login")
            abort(401)

    return render_template("login.html")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":

        username = request.form.get("username")
        password = request.form.get("password")

        if users_collection.find_one({"username": username}):
            print("❌ Username already exists")
            abort(401)  # abort 401 quite literally just sets the code to 401 unauthorized, I think.

        hashed_password = generate_password_hash(password)
        users_collection.insert_one({"username": username, "password": hashed_password})

        print(f"✅ Registered user: {username}")
        return "User is registered now!"  # This should return a 200 ok response for the frontend to handle.
    return render_template("register.html")


@auth_bp.route("/logout")
def logout():
    print(f"✅ User logged out: {session["username"]}")
    session.clear()
    return redirect(url_for("home"))


