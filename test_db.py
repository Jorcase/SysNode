import sqlite3
import os

db_path = os.path.abspath("SysNode_Received/history.db")
with sqlite3.connect(db_path) as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT node_id, hostname, os_type FROM devices")
    print(cursor.fetchall())
