from flask import Blueprint, render_template, request, redirect, url_for

auth_bp = Blueprint("auth", __name__, url_prefix="")

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        # TODO: Add MongoDB login logic here
        print(f"Logging in user: {username}")
        print(f"User password: {password}")
        return redirect(url_for("home"))
    return render_template("login.html")

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        # TODO: Add MongoDB registration logic here
        print(f"Registering user: {username}")
        print(f"User password: {password}")
        return redirect(url_for("home"))
    return render_template("register.html")
