import mysql.connector  # Permet de se connecter à une base de données MySQL/MariaDB
from datetime import datetime  # Utilisé pour générer des horodatages
from env import DBFILE  # Fichier contenant les informations de connexion à la base

# Fonction qui établit une connexion à la base de données en utilisant les infos de env.py
def get_connection():
    return mysql.connector.connect(
        host=DBFILE['host'],
        user=DBFILE['user'],
        password=DBFILE['password'],
        database=DBFILE['database']
    )

# Vérifie si une table existe déjà dans la base de données
def table_exists(cursor, table_name):
    cursor.execute("""
        SELECT COUNT(*) FROM information_schema.tables
        WHERE table_schema = %s AND table_name = %s
    """, (DBFILE['database'], table_name))
    return cursor.fetchone()[0] > 0

# Crée la table "Users" pour stocker les utilisateurs
def create_users_table(cursor):
    cursor.execute("""
        CREATE TABLE Users (
            upn VARCHAR(255) PRIMARY KEY,       -- Identifiant unique (User Principal Name)
            rFIDUID VARCHAR(255),               -- UID de la carte RFID
            MemberOf TEXT                       -- Groupes auxquels l'utilisateur appartient (séparés par virgule)
        )
    """)

# Crée la table "Groups" pour stocker les noms de groupes
def create_groups_table(cursor):
    cursor.execute("""
        CREATE TABLE Groups (
            cn VARCHAR(255) PRIMARY KEY          -- Common Name du groupe
        )
    """)

# Crée la table "Doors" qui lie une porte à un groupe
def create_doors_table(cursor):
    cursor.execute("""
        CREATE TABLE Doors (
            id INT PRIMARY KEY AUTO_INCREMENT,   -- Identifiant unique de la porte
            GroupCn VARCHAR(255),                -- Groupe autorisé à accéder à cette porte
            FOREIGN KEY (GroupCn) REFERENCES Groups(cn) -- Clé étrangère vers Groups
        )
    """)

# Crée la table "log" pour enregistrer les tentatives d'accès
def create_logs_table(cursor):
    cursor.execute("""
        CREATE TABLE log (
            id INT PRIMARY KEY AUTO_INCREMENT,   -- ID du log
            timestamp DATETIME,                  -- Horodatage de la tentative
            user VARCHAR(255),                   -- UPN de l'utilisateur
            rFIDUID VARCHAR(255),                -- UID RFID utilisé
            door_id INT,                         -- Porte concernée
            granted BOOLEAN,                     -- Accès autorisé ou refusé
            FOREIGN KEY (door_id) REFERENCES Doors(id),
            FOREIGN KEY (user) REFERENCES Users(upn)
        )
    """)

# Crée toutes les tables nécessaires si elles n'existent pas
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

# Insère un log dans la base suite à une tentative d'accès
def log_access_attempt(user, rFIDUID, granted, doorID):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO log (timestamp, user, rFIDUID, granted, door_id)
        VALUES (%s, %s, %s, %s, %s)
    """, (datetime.now(), user, rFIDUID, granted, doorID))

    conn.commit()
    conn.close()

# Fonctions pour afficher le contenu des tables
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

# Affiche les tables principales (sauf les logs)
def print_database_content():
    conn = get_connection()
    cursor = conn.cursor()
    print_users_table(cursor)
    print_groups_table(cursor)
    print_doors_table(cursor)
    # print_log_table(cursor)  # Décommenter pour voir les logs
    conn.close()

# Récupère tous les logs
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

# Récupère les X derniers logs (par défaut 10)
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

# Récupère la liste des groupes existants
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

from ldapSync import delete_group_from_ldap  # Fonction externe pour supprimer un groupe dans l'annuaire LDAP

# Supprime un groupe (dans l'AD + la base)
def delete_group_from_database(group_cn):
    delete_group_from_ldap(group_cn)  # Supprimer dans l'AD
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

# Supprime un utilisateur via son UID RFID
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

# Récupère toutes les portes
def get_doors():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Doors")
    doors = cursor.fetchall()
    conn.close()
    return doors

# Récupère tous les utilisateurs
def get_users():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT upn, rFIDUID, MemberOf FROM Users")
    users = cursor.fetchall()
    conn.close()
    return users

# Ajoute une porte liée à un groupe donné
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

# Vérifie si un badge RFID a accès à une porte donnée
def check_access(rfid_uid_str, door_id):
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Récupère les infos utilisateur
        cursor.execute("SELECT upn, MemberOf FROM Users WHERE rFIDUID = %s", (rfid_uid_str,))
        user_data = cursor.fetchone()
        if not user_data:
            return False, None

        upn, user_groups = user_data

        # Récupère le groupe associé à la porte
        cursor.execute("SELECT GroupCn FROM Doors WHERE id = %s", (door_id,))
        door_group = cursor.fetchone()
        if not door_group:
            return False, None

        door_group = door_group[0]

        # Vérifie si l'utilisateur fait partie du groupe autorisé
        if door_group in user_groups.split(","):
            return True, upn
        return False, None

    except Exception as e:
        print(f"MariaDB Error: {e}")
        return False, None
