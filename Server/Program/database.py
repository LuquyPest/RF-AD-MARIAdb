import mysql.connector
from datetime import datetime
from env import DBFILE


def get_connection():
    return mysql.connector.connect(
        host=DBFILE['host'],
        user=DBFILE['user'],
        password=DBFILE['password'],
        database=DBFILE['database']
    )


def table_exists(cursor, table_name):
    cursor.execute("""
        SELECT COUNT(*) FROM information_schema.tables
        WHERE table_schema = %s AND table_name = %s
    """, (DBFILE['database'], table_name))
    return cursor.fetchone()[0] > 0


def create_users_table(cursor):
    cursor.execute("""
        CREATE TABLE Users (
            upn VARCHAR(255) PRIMARY KEY,
            rFIDUID VARCHAR(255),
            MemberOf TEXT
        )
    """)


def create_groups_table(cursor):
    cursor.execute("""
        CREATE TABLE Groups (
            cn VARCHAR(255) PRIMARY KEY
        )
    """)


def create_doors_table(cursor):
    cursor.execute("""
        CREATE TABLE Doors (
            id INT PRIMARY KEY AUTO_INCREMENT,
            GroupCn VARCHAR(255),
            FOREIGN KEY (GroupCn) REFERENCES Groups(cn)
        )
    """)


def create_logs_table(cursor):
    cursor.execute("""
        CREATE TABLE log (
            id INT PRIMARY KEY AUTO_INCREMENT,
            timestamp DATETIME,
            user VARCHAR(255),
            rFIDUID VARCHAR(255),
            door_id INT,
            granted BOOLEAN,
            FOREIGN KEY (door_id) REFERENCES Doors(id),
            FOREIGN KEY (user) REFERENCES Users(upn)
        )
    """)


def setup_database():
    conn = get_connection()
    cursor = conn.cursor()


    if not table_exists(cursor, "Groups"):
        create_groups_table(cursor)
    if not table_exists(cursor, "Users"):
        create_users_table(cursor)
    if not table_exists(cursor, "Doors"):
        create_doors_table(cursor)
    if not table_exists(cursor, "log"):
        create_logs_table(cursor)

    conn.commit()
    conn.close()


def log_access_attempt(user, rFIDUID, granted, doorID):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO log (timestamp, user, rFIDUID, granted, door_id)
        VALUES (%s, %s, %s, %s, %s)
    """, (datetime.now(), user, rFIDUID, granted, doorID))

    conn.commit()
    conn.close()


def print_users_table(cursor):
    cursor.execute("SELECT * FROM Users")
    for row in cursor.fetchall():
        print(row)


def print_groups_table(cursor):
    cursor.execute("SELECT * FROM Groups")
    for row in cursor.fetchall():
        print(row)


def print_doors_table(cursor):
    cursor.execute("SELECT * FROM Doors")
    for row in cursor.fetchall():
        print(row)


def print_log_table(cursor):
    cursor.execute("SELECT * FROM log")
    for row in cursor.fetchall():
        print(row)


def print_database_content():
    conn = get_connection()
    cursor = conn.cursor()
    print_users_table(cursor)
    print_groups_table(cursor)
    print_doors_table(cursor)
    # print_log_table(cursor)
    conn.close()


def get_logs():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT timestamp, user, rFIDUID, granted, door_id
        FROM log ORDER BY id DESC
    """)
    logs = cursor.fetchall()
    conn.close()
    return logs


def get_latest_logs(limit=10):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT timestamp, user, rFIDUID, granted, door_id
        FROM log ORDER BY id DESC LIMIT %s
    """, (limit,))
    logs = cursor.fetchall()
    conn.close()
    return logs


def get_existing_groups():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT cn FROM Groups")
        groups = cursor.fetchall()
        conn.close()
        return [g[0] for g in groups]
    except Exception as e:
        print(f"MariaDB Error: {e}")
        return []

from ldapSync import delete_group_from_ldap

def delete_group_from_database(group_cn):
    # Supprimer d'abord dans l'AD
    delete_group_from_ldap(group_cn)

    # Ensuite supprimer en base de données
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM Doors WHERE GroupCn = %s", (group_cn,))
        cursor.execute("DELETE FROM Groups WHERE cn = %s", (group_cn,))
        conn.commit()
    except Exception as e:
        print(f"MariaDB Error during group deletion: {e}")
    finally:
        conn.close()

def delete_user_from_database_by_rfid(rfid_uid):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM Users WHERE rFIDUID = %s", (rfid_uid,))
        conn.commit()
        print(f"[DB] Utilisateur supprimé par RFID : {rfid_uid}")
        return True
    except Exception as e:
        print(f"[DB] Erreur suppression RFID : {e}")
        return False
    finally:
        conn.close()





def get_doors():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Doors")
    doors = cursor.fetchall()
    conn.close()
    return doors


def get_users():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT upn, rFIDUID, MemberOf FROM Users")
    users = cursor.fetchall()
    conn.close()
    return users


def add_door_to_database(group_cn, Door_id):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO Doors (id, GroupCn) VALUES (%s, %s)", (Door_id, group_cn))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"MariaDB Error: {e}")
        return False, e


def check_access(rfid_uid_str, door_id):
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT upn, MemberOf FROM Users WHERE rFIDUID = %s", (rfid_uid_str,))
        user_data = cursor.fetchone()
        if not user_data:
            return False, None

        upn, user_groups = user_data

        cursor.execute("SELECT GroupCn FROM Doors WHERE id = %s", (door_id,))
        door_group = cursor.fetchone()
        if not door_group:
            return False, None

        door_group = door_group[0]

        if door_group in user_groups.split(","):
            return True, upn
        return False, None

    except Exception as e:
        print(f"MariaDB Error: {e}")
        return False, None
