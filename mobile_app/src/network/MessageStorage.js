import * as SQLite from 'expo-sqlite';

let dbPromise = null;

async function getDb() {
  if (!dbPromise) {
    dbPromise = (async () => {
      const db = await SQLite.openDatabaseAsync('sysnode_chats.db');
      await db.execAsync(`
        CREATE TABLE IF NOT EXISTS messages (
          id TEXT PRIMARY KEY,
          msg_uuid TEXT,
          node_id TEXT NOT NULL,
          text TEXT,
          imageUri TEXT,
          fileUri TEXT,
          time TEXT,
          timestamp INTEGER,
          isMe INTEGER,
          status TEXT,
          sender_name TEXT,
          ip TEXT,
          tcp_port INTEGER,
          isEdited INTEGER DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_node_id ON messages (node_id);
        CREATE INDEX IF NOT EXISTS idx_timestamp ON messages (timestamp);
        
        CREATE TABLE IF NOT EXISTS devices (
          node_id TEXT PRIMARY KEY,
          is_paired INTEGER DEFAULT 0,
          trust_token TEXT
        );
      `);
      return db;
    })();
  }
  return dbPromise;
}

export const MessageStorage = {
  async getMessages(nodeId) {
    if (!nodeId) return [];
    const db = await getDb();
    const rows = await db.getAllAsync('SELECT * FROM messages WHERE node_id = ? ORDER BY timestamp ASC', [nodeId]);
    return rows.map(r => ({
      ...r,
      isMe: r.isMe === 1,
      isEdited: r.isEdited === 1
    }));
  },

  async getMessagesPaged(nodeId, limit = 30, offsetFromEnd = 0) {
    if (!nodeId) return { messages: [], totalCount: 0, hasMore: false, loadedOffset: 0 };
    const db = await getDb();
    const totalCountRow = await db.getFirstAsync('SELECT COUNT(*) as c FROM messages WHERE node_id = ?', [nodeId]);
    const totalCount = totalCountRow ? totalCountRow.c : 0;
    
    if (totalCount === 0) return { messages: [], totalCount: 0, hasMore: false, loadedOffset: 0 };

    // Since we'll invert FlatList later, we should probably fetch the most recent ones first and order DESC, 
    // but the UI currently expects them in chronological order if not inverted, or we just rely on FlatList inverted.
    // If we use inverted FlatList, we return the newest first. But wait, we haven't modified ChatDetailScreen yet.
    // We will return them sorted by timestamp DESC so the FlatList inverted works natively!
    const rows = await db.getAllAsync('SELECT * FROM messages WHERE node_id = ? ORDER BY timestamp DESC LIMIT ? OFFSET ?', [nodeId, limit, offsetFromEnd]);
    
    const hasMore = (offsetFromEnd + rows.length) < totalCount;
    
    return {
      messages: rows.map(r => ({
        ...r,
        isMe: r.isMe === 1,
        isEdited: r.isEdited === 1
      })),
      totalCount: totalCount,
      hasMore: hasMore,
      loadedOffset: offsetFromEnd + rows.length
    };
  },

  async saveMessage(nodeId, message) {
    if (!nodeId) return [];
    const db = await getDb();
    await db.runAsync(`
      INSERT OR REPLACE INTO messages (
        id, msg_uuid, node_id, text, imageUri, fileUri, time, timestamp, isMe, status, sender_name, ip, tcp_port, isEdited
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `, [
      message.id,
      message.msg_uuid || message.id,
      nodeId,
      message.text || null,
      message.imageUri || null,
      message.fileUri || null,
      message.time || null,
      message.timestamp || Date.now(),
      message.isMe ? 1 : 0,
      message.status || 'read',
      message.sender_name || null,
      message.ip || null,
      message.tcp_port || null,
      message.isEdited ? 1 : 0
    ]);
    return []; // Para compatibilidad
  },

  async updateMessageStatus(nodeId, messageId, status) {
    if (!nodeId) return;
    const db = await getDb();
    await db.runAsync('UPDATE messages SET status = ? WHERE id = ?', [status, messageId]);
  },

  async markAllAsRead(nodeId) {
    if (!nodeId) return;
    const db = await getDb();
    await db.runAsync('UPDATE messages SET status = ? WHERE node_id = ? AND isMe = 0 AND status = ?', ['read', nodeId, 'unread']);
  },

  async updateMessageText(nodeId, msgUuid, newText) {
    if (!nodeId || !msgUuid) return;
    const db = await getDb();
    await db.runAsync('UPDATE messages SET text = ?, isEdited = 1 WHERE id = ? OR msg_uuid = ?', [newText, msgUuid, msgUuid]);
  },

  async getLatestMessages() {
    const db = await getDb();
    const rows = await db.getAllAsync(`
      SELECT m.* FROM messages m 
      INNER JOIN (SELECT node_id, MAX(timestamp) as max_ts FROM messages GROUP BY node_id) grouped 
      ON m.node_id = grouped.node_id AND m.timestamp = grouped.max_ts
    `);
    const latest = {};
    for (const r of rows) {
      latest[r.node_id] = { ...r, isMe: r.isMe === 1, isEdited: r.isEdited === 1 };
      
      // Intentar buscar los IPs y puertos más recientes si el mensaje actual no los tiene (como en el JSON original)
      if (!latest[r.node_id].ip || !latest[r.node_id].tcp_port) {
        const infoRow = await db.getFirstAsync('SELECT ip, tcp_port, sender_name FROM messages WHERE node_id = ? AND ip IS NOT NULL ORDER BY timestamp DESC LIMIT 1', [r.node_id]);
        if (infoRow) {
          latest[r.node_id].ip = latest[r.node_id].ip || infoRow.ip;
          latest[r.node_id].tcp_port = latest[r.node_id].tcp_port || infoRow.tcp_port;
          latest[r.node_id].sender_name = latest[r.node_id].sender_name || infoRow.sender_name;
        }
      }
    }
    
    // Buscar conteo de no leídos
    const unreadRows = await db.getAllAsync('SELECT node_id, COUNT(*) as count FROM messages WHERE status = ? AND isMe = 0 GROUP BY node_id', ['unread']);
    for (const r of unreadRows) {
      if (latest[r.node_id]) {
        latest[r.node_id].unreadCount = r.count;
      }
    }
    
    return latest;
  },

  async clearMessages(nodeId) {
    if (!nodeId) return;
    const db = await getDb();
    await db.runAsync('DELETE FROM messages WHERE node_id = ?', [nodeId]);
  },

  async deleteMessage(nodeId, messageId) {
    if (!nodeId || !messageId) return;
    const db = await getDb();
    await db.runAsync('DELETE FROM messages WHERE id = ? OR msg_uuid = ?', [messageId, messageId]);
  },

  async getDeviceTrustToken(nodeId) {
    if (!nodeId) return null;
    const db = await getDb();
    const row = await db.getFirstAsync('SELECT trust_token FROM devices WHERE node_id = ?', [nodeId]);
    return row ? row.trust_token : null;
  },

  async isDevicePaired(nodeId) {
    if (!nodeId) return false;
    const db = await getDb();
    const row = await db.getFirstAsync('SELECT is_paired FROM devices WHERE node_id = ?', [nodeId]);
    return row ? row.is_paired === 1 : false;
  },

  async verifyDeviceTrust(nodeId, token) {
    if (!token) return false;
    const savedToken = await this.getDeviceTrustToken(nodeId);
    const isPaired = await this.isDevicePaired(nodeId);
    return savedToken === token && isPaired;
  },

  async setDevicePaired(nodeId, isPaired, trustToken) {
    if (!nodeId) return;
    const db = await getDb();
    await db.runAsync(`
      INSERT OR REPLACE INTO devices (node_id, is_paired, trust_token)
      VALUES (?, ?, ?)
    `, [nodeId, isPaired ? 1 : 0, trustToken || null]);
  }
};
