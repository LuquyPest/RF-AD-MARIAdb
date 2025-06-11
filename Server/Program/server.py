import schedule
from database import setup_database
from env import DBFILE
from ldapSync import schedule_sync_ldap_to_database
from Webserver import run_webServer_thread

setup_database()
run_webServer_thread()
schedule_sync_ldap_to_database()


while True:
    schedule.run_pending()
