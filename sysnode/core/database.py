import sqlite3
import os
import datetime
import logging

logger = logging.getLogger("SysNode.Database")

class SysNodeDatabase:
    def __init__(self, db_path):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        try:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Tabla global de usuarios (perfil local)
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS local_user (
                        id INTEGER PRIMARY KEY CHECK (id = 1),
                        username TEXT NOT NULL
                    )
                ''')
                
                # Tabla de dispositivos conocidos
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS devices (
                        node_id TEXT PRIMARY KEY,
                        hostname TEXT NOT NULL,
                        os_type TEXT NOT NULL
                    )
                ''')
                
                # Tabla de mensajes asociados a un dispositivo
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        node_id TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        text TEXT NOT NULL,
                        direction TEXT NOT NULL,
                        FOREIGN KEY (node_id) REFERENCES devices (node_id)
                    )
                ''')
                conn.commit()
            logger.info(f"[DB] Base de datos normalizada inicializada en {self.db_path}")
        except Exception as e:
            logger.error(f"[DB] Error inicializando DB: {e}")

    def get_local_username(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT username FROM local_user WHERE id = 1")
            row = cursor.fetchone()
            return row[0] if row else None

    def set_local_username(self, username: str):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO local_user (id, username) VALUES (1, ?)
                ON CONFLICT(id) DO UPDATE SET username = excluded.username
            ''', (username,))
            conn.commit()

    def register_device(self, node_id: str, hostname: str, os_type: str = "Unknown"):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO devices (node_id, hostname, os_type) VALUES (?, ?, ?)
                ON CONFLICT(node_id) DO UPDATE SET 
                    hostname = excluded.hostname,
                    os_type = excluded.os_type
            ''', (node_id, hostname, os_type))
            conn.commit()

    def save_message(self, node_id: str, text: str, direction: str):
        try:
            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO messages (node_id, timestamp, text, direction) VALUES (?, ?, ?, ?)",
                    (node_id, now_str, text, direction)
                )
                conn.commit()
        except Exception as e:
            logger.error(f"[DB] Error guardando mensaje: {e}")

    def get_chat_history(self, node_id: str, limit: int = 50):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT timestamp, text, direction FROM messages 
                    WHERE node_id = ? ORDER BY id DESC LIMIT ?
                ''', (node_id, limit))
                rows = cursor.fetchall()
                return rows[::-1]
        except Exception as e:
            logger.error(f"[DB] Error obteniendo historial para {node_id}: {e}")
            return []
