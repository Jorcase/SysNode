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
                        username TEXT NOT NULL,
                        downloads_path TEXT,
                        device_uuid TEXT
                    )
                ''')
                
                # Add downloads_path column if not exists (for backwards compatibility)
                try:
                    cursor.execute("ALTER TABLE local_user ADD COLUMN downloads_path TEXT")
                except sqlite3.OperationalError:
                    pass
                    
                # Add device_uuid column if not exists
                try:
                    cursor.execute("ALTER TABLE local_user ADD COLUMN device_uuid TEXT")
                except sqlite3.OperationalError:
                    pass
                    
                # Add stealth_mode column if not exists
                try:
                    cursor.execute("ALTER TABLE local_user ADD COLUMN stealth_mode INTEGER DEFAULT 1")
                except sqlite3.OperationalError:
                    pass
                
                # Tabla de dispositivos conocidos
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS devices (
                        node_id TEXT PRIMARY KEY,
                        hostname TEXT NOT NULL,
                        os_type TEXT NOT NULL
                    )
                ''')
                
                # Add last_ip and last_port
                try:
                    cursor.execute("ALTER TABLE devices ADD COLUMN last_ip TEXT")
                    cursor.execute("ALTER TABLE devices ADD COLUMN last_port INTEGER")
                except sqlite3.OperationalError:
                    pass

                # Add is_paired and trust_token
                try:
                    cursor.execute("ALTER TABLE devices ADD COLUMN is_paired INTEGER DEFAULT 0")
                    cursor.execute("ALTER TABLE devices ADD COLUMN trust_token TEXT")
                except sqlite3.OperationalError:
                    pass
                
                # Tabla de mensajes asociados a un dispositivo
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        msg_uuid TEXT UNIQUE,
                        node_id TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        text TEXT NOT NULL,
                        direction TEXT NOT NULL,
                        status TEXT DEFAULT 'delivered',
                        FOREIGN KEY (node_id) REFERENCES devices (node_id)
                    )
                ''')
                
                # Migración para bases de datos existentes
                try:
                    cursor.execute("ALTER TABLE messages ADD COLUMN msg_uuid TEXT")
                except sqlite3.OperationalError:
                    pass
                    
                # Tabla de comandos personalizados JSON
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS custom_commands (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        payload_json TEXT NOT NULL
                    )
                ''')
                
                # Tabla de nodos manuales
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS manual_peers (
                        node_id TEXT PRIMARY KEY,
                        ip TEXT NOT NULL,
                        tcp_port INTEGER NOT NULL
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

    def get_downloads_path(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT downloads_path FROM local_user WHERE id = 1")
            row = cursor.fetchone()
            return row[0] if row and row[0] else None

    def set_downloads_path(self, path: str):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO local_user (id, username, downloads_path) VALUES (1, 'User', ?)
                ON CONFLICT(id) DO UPDATE SET downloads_path = excluded.downloads_path
            ''', (path,))
            conn.commit()
            
    def get_or_create_device_uuid(self) -> str:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT device_uuid FROM local_user WHERE id = 1")
            row = cursor.fetchone()
            
            if row and row[0]:
                return row[0]
                
            # If not found or null, generate one
            import uuid
            new_uuid = str(uuid.uuid4())
            
            # Check if row 1 exists at all
            cursor.execute("SELECT id FROM local_user WHERE id = 1")
            if cursor.fetchone():
                cursor.execute("UPDATE local_user SET device_uuid = ? WHERE id = 1", (new_uuid,))
            else:
                cursor.execute("INSERT INTO local_user (id, username, device_uuid) VALUES (1, 'SysNode-Default', ?)", (new_uuid,))
                
            conn.commit()
            return new_uuid

    def get_local_stealth_mode(self) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT stealth_mode FROM local_user WHERE id = 1")
            row = cursor.fetchone()
            if row and row[0] is not None:
                return bool(row[0])
            return True # Default to True (oculto)
            
    def set_local_stealth_mode(self, is_stealth: bool):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO local_user (id, username, stealth_mode) VALUES (1, 'User', ?)
                ON CONFLICT(id) DO UPDATE SET stealth_mode = excluded.stealth_mode
            ''', (1 if is_stealth else 0,))
            conn.commit()

    def save_manual_peer(self, node_id: str, ip: str, tcp_port: int):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO manual_peers (node_id, ip, tcp_port) VALUES (?, ?, ?)
                ON CONFLICT(node_id) DO UPDATE SET ip=excluded.ip, tcp_port=excluded.tcp_port
            ''', (node_id, ip, tcp_port))
            conn.commit()

    def get_manual_peers(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT node_id, ip, tcp_port FROM manual_peers")
            return cursor.fetchall()
            
    def delete_manual_peer(self, node_id: str):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM manual_peers WHERE node_id = ?", (node_id,))
            conn.commit()

    def delete_device(self, node_id: str):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM devices WHERE node_id = ?", (node_id,))
            cursor.execute("DELETE FROM messages WHERE node_id = ?", (node_id,))
            conn.commit()

    def register_device(self, node_id: str, hostname: str, os_type: str = "Unknown", ip: str = None, port: int = None):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT hostname, os_type, last_ip, last_port FROM devices WHERE node_id = ?", (node_id,))
                row = cursor.fetchone()
                
                if row:
                    c_hostname, c_os, c_ip, c_port = row
                    if c_hostname != hostname or c_os != os_type or (ip and c_ip != ip) or (port and c_port != port):
                        new_ip = ip if ip else c_ip
                        new_port = port if port else c_port
                        cursor.execute("UPDATE devices SET hostname = ?, os_type = ?, last_ip = ?, last_port = ? WHERE node_id = ?", 
                                     (hostname, os_type, new_ip, new_port, node_id))
                else:
                    cursor.execute("INSERT INTO devices (node_id, hostname, os_type, last_ip, last_port) VALUES (?, ?, ?, ?, ?)", 
                                 (node_id, hostname, os_type, ip, port))
            except sqlite3.OperationalError:
                # Fallback if columns not added yet
                cursor.execute("SELECT hostname, os_type FROM devices WHERE node_id = ?", (node_id,))
                row = cursor.fetchone()
                if row:
                    if row[0] != hostname or row[1] != os_type:
                        cursor.execute("UPDATE devices SET hostname = ?, os_type = ? WHERE node_id = ?", (hostname, os_type, node_id))
                else:
                    cursor.execute("INSERT INTO devices (node_id, hostname, os_type) VALUES (?, ?, ?)", (node_id, hostname, os_type))
            conn.commit()

    def get_all_devices(self) -> list:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT node_id, hostname, os_type, last_ip, last_port, is_paired FROM devices")
                return cursor.fetchall()
            except sqlite3.OperationalError:
                try:
                    cursor.execute("SELECT node_id, hostname, os_type, last_ip, last_port FROM devices")
                    return [(r[0], r[1], r[2], r[3], r[4], 0) for r in cursor.fetchall()]
                except sqlite3.OperationalError:
                    cursor.execute("SELECT node_id, hostname, os_type FROM devices")
                    return [(r[0], r[1], r[2], None, None, 0) for r in cursor.fetchall()]

    def is_device_paired(self, node_id: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT is_paired FROM devices WHERE node_id = ?", (node_id,))
                row = cursor.fetchone()
                return bool(row[0]) if row else False
            except sqlite3.OperationalError:
                return False

    def get_device_trust_token(self, node_id: str) -> str:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT trust_token FROM devices WHERE node_id = ?", (node_id,))
                row = cursor.fetchone()
                return row[0] if row else None
            except sqlite3.OperationalError:
                return None

    def verify_device_trust(self, node_id: str, token: str) -> bool:
        if not token:
            return False
        saved_token = self.get_device_trust_token(node_id)
        return saved_token == token and self.is_device_paired(node_id)

    def set_device_paired(self, node_id: str, is_paired: bool, trust_token: str = None):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("UPDATE devices SET is_paired = ?, trust_token = ? WHERE node_id = ?", 
                             (1 if is_paired else 0, trust_token, node_id))
                conn.commit()
            except sqlite3.OperationalError as e:
                logger.error(f"[DB] Error setting device paired: {e}")

    def save_message(self, node_id: str, text: str, direction: str, status: str = 'delivered', msg_uuid: str = None):
        if not msg_uuid:
            import uuid
            msg_uuid = str(uuid.uuid4())
            
        try:
            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO messages (msg_uuid, node_id, timestamp, text, direction, status) VALUES (?, ?, ?, ?, ?, ?)",
                    (msg_uuid, node_id, now_str, text, direction, status)
                )
                conn.commit()
            return msg_uuid
        except Exception as e:
            logger.error(f"[DB] Error guardando mensaje: {e}")
            return None

    def get_chat_history(self, node_id: str, limit: int = 15, offset: int = 0):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT msg_uuid, timestamp, text, direction FROM messages 
                    WHERE node_id = ? ORDER BY id DESC LIMIT ? OFFSET ?
                ''', (node_id, limit, offset))
                rows = cursor.fetchall()
                return rows[::-1]
        except Exception as e:
            logger.error(f"[DB] Error obteniendo historial para {node_id}: {e}")
            return []

    def get_chat_history_count(self, node_id: str) -> int:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM messages WHERE node_id = ?", (node_id,))
                row = cursor.fetchone()
                return row[0] if row else 0
        except Exception as e:
            logger.error(f"[DB] Error obteniendo conteo de historial para {node_id}: {e}")
            return 0

    def delete_message(self, msg_uuid: str):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM messages WHERE msg_uuid = ?", (msg_uuid,))
                conn.commit()
        except Exception as e:
            logger.error(f"[DB] Error borrando mensaje {msg_uuid}: {e}")
            
    def clear_chat_history(self, node_id: str):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM messages WHERE node_id = ?", (node_id,))
                conn.commit()
        except Exception as e:
            logger.error(f"[DB] Error limpiando chat de {node_id}: {e}")

    def get_pending_messages(self, node_id: str):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, text, msg_uuid FROM messages 
                    WHERE node_id = ? AND direction = 'OUT' AND status = 'pending' ORDER BY id ASC
                ''', (node_id,))
                return cursor.fetchall()
        except Exception as e:
            logger.error(f"[DB] Error obteniendo mensajes pendientes para {node_id}: {e}")
            return []

    def mark_message_delivered(self, msg_id: int):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE messages SET status = 'delivered' WHERE id = ?", (msg_id,))
                conn.commit()
        except Exception as e:
            logger.error(f"[DB] Error marcando mensaje como entregado: {e}")
            
    def update_message_text(self, msg_uuid: str, new_text: str):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE messages SET text = ? WHERE msg_uuid = ?", (new_text, msg_uuid))
                conn.commit()
        except Exception as e:
            logger.error(f"[DB] Error actualizando texto de mensaje: {e}")

    # --- Custom Commands ---
    def get_custom_commands(self):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, name, payload_json FROM custom_commands ORDER BY id")
                return cursor.fetchall()
        except Exception as e:
            logger.error(f"[DB] Error obteniendo comandos personalizados: {e}")
            return []
            
    def add_custom_command(self, name: str, payload_json: str):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO custom_commands (name, payload_json) VALUES (?, ?)", (name, payload_json))
                conn.commit()
        except Exception as e:
            logger.error(f"[DB] Error añadiendo comando personalizado: {e}")
            
    def update_custom_command(self, cmd_id: int, name: str, payload_json: str):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE custom_commands SET name = ?, payload_json = ? WHERE id = ?", (name, payload_json, cmd_id))
                conn.commit()
        except Exception as e:
            logger.error(f"[DB] Error actualizando comando personalizado: {e}")
            
    def delete_custom_command(self, cmd_id: int):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM custom_commands WHERE id = ?", (cmd_id,))
                conn.commit()
        except Exception as e:
            logger.error(f"[DB] Error eliminando comando personalizado: {e}")
