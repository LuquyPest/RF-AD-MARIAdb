import threading  # Permet d'exécuter des fonctions en parallèle (thread)
from datetime import datetime  # Pour générer des horodatages
import ldap  # Module pour interagir avec un annuaire LDAP (Active Directory, OpenLDAP…)
import schedule  # Pour planifier des exécutions régulières
from env import DOOR_ACCESS_GROUPS_DN, LDAP_SERVER, LDAPPASS, LDAPUSER, USERS_DN  # Variables d’environnement
from database import get_connection  # Fonction pour se connecter à la base MariaDB

# Initialise une connexion LDAP
def initialize_ldap_connection():
    try:
        connect = ldap.initialize(LDAP_SERVER)  # Initialise le client LDAP
        connect.set_option(ldap.OPT_REFERRALS, 0)  # Désactive les redirections LDAP (utile avec AD)
        connect.simple_bind_s(LDAPUSER, LDAPPASS)  # Authentifie l’utilisateur LDAP
        print(f"[{datetime.now()}] LDAP connection successful.")
        return connect
    except ldap.LDAPError as e:
        print(f"[{datetime.now()}] LDAP Error: {e}")
        return None

# Récupère tous les utilisateurs de l'annuaire LDAP
def retrieve_users_from_ldap(ldap_connection):
    try:
        result = ldap_connection.search_s(
            USERS_DN,
            ldap.SCOPE_SUBTREE,
            "(objectClass=user)",  # Filtre LDAP pour les utilisateurs
        )
        return result
    except ldap.LDAPError as e:
        print(f"[{datetime.now()}] LDAP Error: {e}")
        return []

# Récupère tous les groupes de l'annuaire LDAP
def retrieve_groups_from_ldap(ldap_connection):
    try:
        result = ldap_connection.search_s(
            DOOR_ACCESS_GROUPS_DN,
            ldap.SCOPE_SUBTREE,
            "(objectClass=group)",  # Filtre LDAP pour les groupes
        )
        return result
    except ldap.LDAPError as e:
        print(f"[{datetime.now()}]LDAP Error: {e}")
        return []

# Ajoute ou met à jour un utilisateur dans la base
def add_user_to_database(cursor, upn, rfid_uid, member_of):
    try:
        cursor.execute("SELECT * FROM Users WHERE upn=%s", (upn,))
        existing_user = cursor.fetchone()
        if existing_user:
            # Si l'utilisateur existe mais a des données différentes, on le met à jour
            if existing_user[1] != rfid_uid or existing_user[2] != member_of:
                cursor.execute(
                    "UPDATE Users SET rFIDUID=%s, MemberOf=%s WHERE upn=%s",
                    (rfid_uid, member_of, upn),
                )
                print(f"[{datetime.now()}] User '{upn}' updated in the database.")
            else:
                print(f"[{datetime.now()}] User '{upn}' already up to date.")
        else:
            # Sinon, on l'ajoute
            cursor.execute(
                "INSERT INTO Users (upn, rFIDUID, MemberOf) VALUES (%s, %s, %s)",
                (upn, rfid_uid, member_of),
            )
            print(f"[{datetime.now()}] User '{upn}' added to the database.")
    except Exception as e:
        print(f"MariaDB Error: {e}")

# Ajoute un groupe s’il n’existe pas déjà
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

# Supprime un groupe de l'annuaire LDAP
def delete_group_from_ldap(group_cn):
    group_dn = f"CN={group_cn},{GROUPS_DN}"
    conn = initialize_ldap_connection()
    if not conn:
        print("[LDAP] Connexion échouée pour suppression du groupe.")
        return False
    try:
        conn.delete_s(group_dn)
        print(f"[LDAP] Groupe supprimé : {group_dn}")
        conn.unbind()
        return True
    except ldap.NO_SUCH_OBJECT:
        print(f"[LDAP] Le groupe {group_dn} n'existe pas.")
        return False
    except ldap.LDAPError as e:
        print(f"[LDAP] Erreur lors de la suppression du groupe : {e}")
        return False

# Synchronise LDAP vers MariaDB
def sync_ldap_to_database():
    ldap_conn = initialize_ldap_connection()
    if ldap_conn:
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Traitement des utilisateurs LDAP
            users = retrieve_users_from_ldap(ldap_conn)
            for dn, user_info in users:
                upn = user_info.get("userPrincipalName", [b""])[0].decode("utf-8")
                rfid_uid = user_info.get("rFIDUID", [b""])[0].decode("utf-8")
                member_of = [
                    group.decode("utf-8").split(",")[0].split("=")[1]
                    for group in user_info.get("memberOf", [])
                ]

                # Si le compte est désactivé (UAC 514 ou 66050), on le supprime
                user_account_control = user_info.get("userAccountControl", [b"0"])[0]
                if user_account_control in [b"514", b"66050"]:
                    cursor.execute("SELECT * FROM Users WHERE upn=%s", (upn,))
                    if cursor.fetchone():
                        cursor.execute("DELETE FROM Users WHERE upn=%s", (upn,))
                        print(f"[{datetime.now()}] Disabled user '{upn}' removed.")
                    else:
                        print(f"[{datetime.now()}] Disabled user '{upn}' not in DB.")
                    continue

                # Ajout ou mise à jour de l’utilisateur
                add_user_to_database(cursor, upn, rfid_uid, ", ".join(member_of))

            # Traitement des groupes LDAP
            groups = retrieve_groups_from_ldap(ldap_conn)
            for dn, group_info in groups:
                cn = group_info.get("cn", [b""])[0].decode("utf-8")
                add_group_to_database(cursor, cn)

            conn.commit()
            conn.close()
            ldap_conn.unbind()
        except Exception as e:
            print(f"MariaDB Error during sync: {e}")

# Lance la synchronisation LDAP dans un thread
def run_sync_ldap_to_database_thread():
    print(f"[{datetime.now()}] Running LDAP sync")
    threading.Thread(target=sync_ldap_to_database, daemon=True).start()

# Planifie la synchronisation LDAP toutes les 5 minutes
def schedule_sync_ldap_to_database():
    run_sync_ldap_to_database_thread()
    schedule.every(5).minutes.do(run_sync_ldap_to_database_thread)

import time  # Pour temporiser certaines étapes (attente de réplication)

# Crée un utilisateur dans LDAP (en 4 étapes)
def create_user_in_ldap(upn, password, rfid_uid, groups_dn):
    username = upn.split('@')[0]
    dn = f"CN={username},{USERS_DN}"

    # Étape 1 : création de l’utilisateur
    conn = initialize_ldap_connection()
    if not conn:
        return False, "LDAP connection failed"
    try:
        attrs = {
            'objectClass': [b'top', b'person', b'organizationalPerson', b'user'],
            'cn': [username.encode()],
            'sAMAccountName': [username.encode()],
            'userPrincipalName': [upn.encode()],
            'rFIDUID': [rfid_uid.encode()],
        }
        conn.add_s(dn, list(attrs.items()))
        print(f"[LDAP] User {dn} created.")
        conn.unbind()
    except ldap.LDAPError as e:
        return False, f"LDAP Error during creation: {e}"

    # Étape 2 : définir le mot de passe
    time.sleep(1)
    conn = initialize_ldap_connection()
    if not conn:
        return False, "LDAP reconnection failed"
    try:
        pwd = f'"{password}"'.encode('utf-16-le')  # Encodage spécial requis
        conn.modify_s(dn, [(ldap.MOD_REPLACE, 'unicodePwd', [pwd])])
        print(f"[LDAP] Password set for {dn}.")
        conn.unbind()
    except ldap.LDAPError as e:
        return False, f"LDAP Error during password set: {e}"

    # Étape 3 : activer le compte
    time.sleep(1)
    conn = initialize_ldap_connection()
    if not conn:
        return False, "LDAP reconnection failed (for activation)"
    try:
        conn.modify_s(dn, [(ldap.MOD_REPLACE, 'userAccountControl', [b'512'])])
        print(f"[LDAP] userAccountControl set to 512 for {dn}.")
    except ldap.LDAPError as e:
        return False, f"LDAP Error during activation: {e}"

    # Étape 4 : ajouter aux groupes
    for group_dn in groups_dn:
        try:
            conn.modify_s(group_dn, [(ldap.MOD_ADD, 'member', [dn.encode()])])
            print(f"[LDAP] User {dn} added to group {group_dn}.")
        except ldap.LDAPError as group_error:
            print(f"[LDAP] Failed to add {dn} to group {group_dn}: {group_error}")

# Supprime un utilisateur LDAP par son CN
def delete_user_from_ldap(user_cn):
    from env import USERS_DN
    conn = initialize_ldap_connection()
    if not conn:
        print("[LDAP] Connexion échouée pour suppression utilisateur.")
        return False

    user_dn = f"CN={user_cn},{USERS_DN}"
    try:
        conn.delete_s(user_dn)
        print(f"[LDAP] Utilisateur supprimé : {user_dn}")
        conn.unbind()
        return True
    except ldap.NO_SUCH_OBJECT:
        print(f"[LDAP] L'utilisateur {user_dn} n'existe pas.")
        return False
    except ldap.LDAPError as e:
        print(f"[LDAP] Erreur LDAP lors de la suppression : {e}")
        return False
