import threading
from datetime import datetime
import ldap
import schedule
from env import DOOR_ACCESS_GROUPS_DN, LDAP_SERVER, LDAPPASS, LDAPUSER, USERS_DN
from database import get_connection


def initialize_ldap_connection():
    try:
        connect = ldap.initialize(LDAP_SERVER)
        connect.set_option(ldap.OPT_REFERRALS, 0)
        connect.simple_bind_s(LDAPUSER, LDAPPASS)
        print(f"[{datetime.now()}] LDAP connection successful.")
        return connect
    except ldap.LDAPError as e:
        print(f"[{datetime.now()}] LDAP Error: {e}")
        return None


def retrieve_users_from_ldap(ldap_connection):
    try:
        result = ldap_connection.search_s(
            USERS_DN,
            ldap.SCOPE_SUBTREE,
            "(objectClass=user)",
        )
        return result
    except ldap.LDAPError as e:
        print(f"[{datetime.now()}] LDAP Error: {e}")
        return []


def retrieve_groups_from_ldap(ldap_connection):
    try:
        result = ldap_connection.search_s(
            DOOR_ACCESS_GROUPS_DN,
            ldap.SCOPE_SUBTREE,
            "(objectClass=group)",
        )
        return result
    except ldap.LDAPError as e:
        print(f"[{datetime.now()}]LDAP Error: {e}")
        return []


def add_user_to_database(cursor, upn, rfid_uid, member_of):
    try:
        cursor.execute("SELECT * FROM Users WHERE upn=%s", (upn,))
        existing_user = cursor.fetchone()
        if existing_user:
            if existing_user[1] != rfid_uid or existing_user[2] != member_of:
                cursor.execute(
                    "UPDATE Users SET rFIDUID=%s, MemberOf=%s WHERE upn=%s",
                    (rfid_uid, member_of, upn),
                )
                print(f"[{datetime.now()}] User '{upn}' updated in the database.")
            else:
                print(f"[{datetime.now()}] User '{upn}' already up to date.")
        else:
            cursor.execute(
                "INSERT INTO Users (upn, rFIDUID, MemberOf) VALUES (%s, %s, %s)",
                (upn, rfid_uid, member_of),
            )
            print(f"[{datetime.now()}] User '{upn}' added to the database.")
    except Exception as e:
        print(f"MariaDB Error: {e}")


def add_group_to_database(cursor, cn):
    try:
        cursor.execute("SELECT * FROM Groups WHERE cn=%s", (cn,))
        existing_group = cursor.fetchone()
        if existing_group:
            print(f"[{datetime.now()}] Group '{cn}' already exists.")
        else:
            cursor.execute("INSERT INTO Groups (cn) VALUES (%s)", (cn,))
            print(f"[{datetime.now()}] Group '{cn}' added to the database.")
    except Exception as e:
        print(f"MariaDB Error: {e}")


def sync_ldap_to_database():
    ldap_conn = initialize_ldap_connection()
    if ldap_conn:
        try:
            conn = get_connection()
            cursor = conn.cursor()

            users = retrieve_users_from_ldap(ldap_conn)
            for dn, user_info in users:
                upn = user_info.get("userPrincipalName", [b""])[0].decode("utf-8")
                rfid_uid = user_info.get("rFIDUID", [b""])[0].decode("utf-8")
                member_of = [
                    group.decode("utf-8").split(",")[0].split("=")[1]
                    for group in user_info.get("memberOf", [])
                ]

                user_account_control = user_info.get("userAccountControl", [b"0"])[0]
                if user_account_control in [b"514", b"66050"]:
                    cursor.execute("SELECT * FROM Users WHERE upn=%s", (upn,))
                    if cursor.fetchone():
                        cursor.execute("DELETE FROM Users WHERE upn=%s", (upn,))
                        print(f"[{datetime.now()}] Disabled user '{upn}' removed.")
                    else:
                        print(f"[{datetime.now()}] Disabled user '{upn}' not in DB.")
                    continue

                add_user_to_database(cursor, upn, rfid_uid, ", ".join(member_of))

            groups = retrieve_groups_from_ldap(ldap_conn)
            for dn, group_info in groups:
                cn = group_info.get("cn", [b""])[0].decode("utf-8")
                add_group_to_database(cursor, cn)

            conn.commit()
            conn.close()
            ldap_conn.unbind()
        except Exception as e:
            print(f"MariaDB Error during sync: {e}")


def run_sync_ldap_to_database_thread():
    print(f"[{datetime.now()}] Running LDAP sync")
    threading.Thread(target=sync_ldap_to_database, daemon=True).start()


def schedule_sync_ldap_to_database():
    run_sync_ldap_to_database_thread()
    schedule.every(5).minutes.do(run_sync_ldap_to_database_thread)