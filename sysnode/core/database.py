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
            # Asegurar que el directorio exista
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                # direction: "IN" o "OUT"
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        sender_name TEXT NOT NULL,
                        text TEXT NOT NULL,
                        direction TEXT NOT NULL
                    )
                ''')
                conn.commit()
            logger.info(f"[DB] Base de datos inicializada en {self.db_path}")
        except Exception as e:
            logger.error(f"[DB] Error inicializando DB: {e}")

    def save_message(self, sender_name: str, text: str, direction: str):
        try:
            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO messages (timestamp, sender_name, text, direction) VALUES (?, ?, ?, ?)",
                    (now_str, sender_name, text, direction)
                )
                conn.commit()
        except Exception as e:
            logger.error(f"[DB] Error guardando mensaje: {e}")

    def get_recent_messages(self, limit: int = 20):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT timestamp, sender_name, text, direction FROM messages ORDER BY id DESC LIMIT ?",
                    (limit,)
                )
                rows = cursor.fetchall()
                # Devolver en orden cronológico (los más antiguos primero dentro del límite)
                return rows[::-1]
        except Exception as e:
            logger.error(f"[DB] Error obteniendo mensajes recientes: {e}")
            return []
