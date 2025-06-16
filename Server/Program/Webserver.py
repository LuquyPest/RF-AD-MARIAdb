import io
from threading import Thread
from ldapSync import create_user_in_ldap
from env import DOOR_ACCESS_GROUPS_DN

from database import (
    add_door_to_database,
    check_access,
    delete_group_from_database,
    get_doors,
    get_existing_groups,
    get_latest_logs,
    get_logs,
    get_users,
    log_access_attempt,
    delete_user_from_database_by_rfid,
)
from env import DBFILE, WebServerPORT
from flask import (
    Flask,
    Response,
    jsonify,
    redirect,
    render_template,
    request,
)
from ldapSync import sync_ldap_to_database
from ldapSync import delete_user_from_ldap


app = Flask(__name__)


# Route to the home
@app.route("/")
def index():
    existing_groups = get_existing_groups()
    logs = get_latest_logs(5)
    # print(logs[0])
    return render_template("./index.html", existing_groups=existing_groups, logs=logs)
if __name__ == "__main__":
    app.run(ssl_context=('cert.pem', 'key.pem'))
    
# Route to display the fuser db
@app.route("/UserDB")
def usersdb():
    users = get_users()
    return render_template("userdb.html", users=users)
if __name__ == "__main__":
    app.run(ssl_context=('cert.pem', 'key.pem'))

@app.route('/delete_user_form')
def delete_user_form():
    users = get_users()
    # print("[DEBUG] Utilisateurs restants :", users)
    return render_template('delete_user.html', users=users)


if __name__ == "__main__":
    app.run(ssl_context=('cert.pem', 'key.pem'))


@app.route('/delete_user', methods=['POST'])
def delete_user():
    user_cn = request.form['user_cn']
    rfid_uid = request.form['rfid_uid']

    ldap_ok = delete_user_from_ldap(user_cn)
    db_ok = delete_user_from_database_by_rfid(rfid_uid)

    if ldap_ok and db_ok:
        print(f"[OK] {user_cn} supprimé de l'AD et de la base.")
    elif ldap_ok:
        print(f"[WARN] {user_cn} supprimé de l'AD, mais pas de la base.")
    elif db_ok:
        print(f"[WARN] {user_cn} supprimé de la base, mais pas de l'AD.")
    else:
        print(f"[ERREUR] {user_cn} n'a pas pu être supprimé.")

    return redirect('/delete_user_form') 




if __name__ == "__main__":
    app.run(ssl_context=('cert.pem', 'key.pem'))

# Route to display the fuser db
@app.route("/LogsDB")
def logsdb():
    logs = get_logs()
    return render_template("logsdb.html", logs=logs)

if __name__ == "__main__":
    app.run(ssl_context=('cert.pem', 'key.pem'))

@app.route("/export_logs")
def export_logs():
    logs = get_logs()

    # Create a file-like string to write logs
    log_output = io.StringIO()
    log_line = "TimeStamp,User,Tag UID,Door ID,Granted,\n"
    log_output.write(log_line)
    for log in logs:
        log_line = f"{log[0]},{log[1]},{log[2]},{log[4]},{'Yes' if log[3] else 'No'},\n"
        log_output.write(log_line)

    # Set the position to the beginning of the stream
    log_output.seek(0)

    # Create a response with the file data
    return Response(
        log_output,
        mimetype="text/plain",
        headers={"Content-disposition": "attachment; filename=logs.csv"},
    )

if __name__ == "__main__":
    app.run(ssl_context=('cert.pem', 'key.pem'))

@app.route("/GroupsDB")
def groupsdb():
    doors = get_doors()
    groups = get_existing_groups()
    return render_template("groupsdb.html", doors=doors, groups=groups)
if __name__ == "__main__":
    app.run(ssl_context=('cert.pem', 'key.pem'))

@app.route("/delete_group/<group_cn>", methods=["POST"])
def delete_group(group_cn):
    delete_group_from_database(group_cn)
    return render_template("./index.html")
if __name__ == "__main__":
    app.run(ssl_context=('cert.pem', 'key.pem'))

# Route to handle form submission and add the door to the database
@app.route("/add_door", methods=["POST"])
def add_door():
    Door_id = request.form["Door_id"]
    group_cn = request.form["group_cn"]

    # Update with your database file path
    if add_door_to_database(group_cn, Door_id):
        return redirect("/")
    return "Failed to add door to the database."

if __name__ == "__main__":
    app.run(ssl_context=('cert.pem', 'key.pem'))

# Route to handle sync button click
@app.route("/sync")
def sync():
    sync_ldap_to_database()
    return render_template("./LDAP.html")
if __name__ == "__main__":
    app.run(ssl_context=('cert.pem', 'key.pem'))

# Route to handle door access requests
@app.route("/access", methods=["POST"])
def door_access():
    data = request.get_json()
    rfid_uid = data.get("rfid_uid")
    door_id = data.get("door_id")

    if rfid_uid is None or door_id is None:
        return jsonify({"error": "RFID UID and door ID are required"}), 400

    access_granted, upn = check_access(rfid_uid, door_id)
    if access_granted:
        log_access_attempt(upn, rfid_uid, True, door_id)
        return jsonify({"access_granted": True, "upn": upn}), 200

    log_access_attempt(upn, rfid_uid, False, door_id)
    return jsonify({"access_granted": False}), 403
if __name__ == "__main__":
    app.run(ssl_context=('cert.pem', 'key.pem'))

@app.route("/create_user", methods=["GET", "POST"])
def create_user():
    if request.method == "GET":
        groups = get_existing_groups()
        return render_template("create_user.html", groups=groups)

    # POST
    upn = request.form["upn"]
    password = request.form["password"]
    rfid_uid = request.form["rfid_uid"]
    selected_groups = request.form.getlist("groups")

    groups_dn = [f"CN={g},{DOOR_ACCESS_GROUPS_DN}" for g in selected_groups]
    success, message = create_user_in_ldap(upn, password, rfid_uid, groups_dn)

    return redirect('/')

if __name__ == "__main__":
    app.run(debug=True)


def run_flask_app():
    """Run the Flask web application.

    This function starts the Flask web application with debugging enabled,
    no reloader, on the specified port and host. It serves as the main entry
    point for running the web server.
    """
    app.run(debug=True, use_reloader=False, port=WebServerPORT, host="0.0.0.0", ssl_context=("cert.pem", "key.pem"))


def run_webServer_thread():
    """Start the Flask web server in a separate thread.

    This function initializes and starts a new thread to run the Flask web
    application. It allows the web server to run concurrently with other
    tasks in the main program, ensuring the web interface remains responsive.
    """
    print(f"STARTING WEB SERVER ON PORT {WebServerPORT}")
    flask_thread = Thread(target=run_flask_app, daemon=True)
    flask_thread.start()
    # flask_thread.join()


if __name__ == "__main__":
    app.run(debug=True)

