import * as FileSystem from 'expo-file-system/legacy';

const STORAGE_FILE = (FileSystem.documentDirectory || '') + 'sysnode_chats_history.json';

let memoryCache = null;

async function loadFromDisk() {
  if (memoryCache !== null) return memoryCache;
  try {
    const info = await FileSystem.getInfoAsync(STORAGE_FILE);
    if (info.exists) {
      const content = await FileSystem.readAsStringAsync(STORAGE_FILE);
      memoryCache = JSON.parse(content);
    } else {
      memoryCache = {};
    }
  } catch (e) {
    console.error("[MessageStorage] Error cargando mensajes del disco:", e);
    memoryCache = {};
  }
  return memoryCache;
}

async function saveToDisk() {
  if (!memoryCache) return;
  try {
    await FileSystem.writeAsStringAsync(STORAGE_FILE, JSON.stringify(memoryCache));
  } catch (e) {
    console.error("[MessageStorage] Error guardando mensajes en disco:", e);
  }
}

export const MessageStorage = {
  async getMessages(nodeId) {
    if (!nodeId) return [];
    const cache = await loadFromDisk();
    return cache[nodeId] || [];
  },

  async saveMessage(nodeId, message) {
    if (!nodeId) return [];
    const cache = await loadFromDisk();
    if (!cache[nodeId]) {
      cache[nodeId] = [];
    }
    
    // Evitar duplicados por id o por msg_uuid
    const existsIndex = cache[nodeId].findIndex(m => m.id === message.id);
    if (existsIndex >= 0) {
      cache[nodeId][existsIndex] = { ...cache[nodeId][existsIndex], ...message };
    } else {
      cache[nodeId].push(message);
    }
    
    await saveToDisk();
    return cache[nodeId];
  },

  async updateMessageStatus(nodeId, messageId, status) {
    if (!nodeId) return;
    const cache = await loadFromDisk();
    if (cache[nodeId]) {
      const msg = cache[nodeId].find(m => m.id === messageId);
      if (msg) {
        msg.status = status;
        await saveToDisk();
      }
    }
  },

  async updateMessageText(nodeId, msgUuid, newText) {
    if (!nodeId || !msgUuid) return;
    const cache = await loadFromDisk();
    if (cache[nodeId]) {
      const msg = cache[nodeId].find(m => m.msg_uuid === msgUuid || m.id === msgUuid);
      if (msg) {
        msg.text = newText;
        msg.edited = true;
        await saveToDisk();
      }
    }
  },

  async getLatestMessages() {
    const cache = await loadFromDisk();
    const latest = {};
    for (const [nodeId, msgs] of Object.entries(cache)) {
      if (msgs && msgs.length > 0) {
        latest[nodeId] = msgs[msgs.length - 1];
      }
    }
    return latest;
  },

  async clearMessages(nodeId) {
    if (!nodeId) return;
    const cache = await loadFromDisk();
    delete cache[nodeId];
    await saveToDisk();
  }
};
