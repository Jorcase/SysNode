import * as FileSystem from 'expo-file-system/legacy';

const STORAGE_FILE = (FileSystem.documentDirectory || '') + 'sysnode_custom_commands.json';

const DEFAULT_COMMANDS = [
  { id: 'def_1', name: 'Bloquear Sesión', command: 'loginctl lock-session || gnome-screensaver-command -l', isDefault: true },
  { id: 'def_2', name: 'Espacio en Disco', command: 'df -h', isDefault: true },
  { id: 'def_3', name: 'Uptime del Sistema', command: 'uptime', isDefault: true },
  { id: 'def_4', name: 'Top 10 Procesos por Memoria', command: 'ps aux --sort=-%mem | head -n 10', isDefault: true },
];

let memoryCache = null;

async function loadFromDisk() {
  if (memoryCache !== null) return memoryCache;
  try {
    const info = await FileSystem.getInfoAsync(STORAGE_FILE);
    if (info.exists) {
      const content = await FileSystem.readAsStringAsync(STORAGE_FILE);
      memoryCache = JSON.parse(content);
    } else {
      memoryCache = DEFAULT_COMMANDS;
      await saveToDisk();
    }
  } catch (e) {
    console.error("[CommandStorage] Error cargando comandos:", e);
    memoryCache = DEFAULT_COMMANDS;
  }
  return memoryCache;
}

async function saveToDisk() {
  if (!memoryCache) return;
  try {
    await FileSystem.writeAsStringAsync(STORAGE_FILE, JSON.stringify(memoryCache));
  } catch (e) {
    console.error("[CommandStorage] Error guardando comandos:", e);
  }
}

export const CommandStorage = {
  async getCommands() {
    return await loadFromDisk();
  },

  async saveCommand(cmdObj) {
    const cache = await loadFromDisk();
    if (!cmdObj.id) {
      cmdObj.id = 'cmd_' + Date.now().toString();
    }
    const index = cache.findIndex(c => c.id === cmdObj.id);
    if (index >= 0) {
      cache[index] = { ...cache[index], ...cmdObj };
    } else {
      cache.push(cmdObj);
    }
    await saveToDisk();
    return cache;
  },

  async deleteCommand(cmdId) {
    let cache = await loadFromDisk();
    memoryCache = cache.filter(c => c.id !== cmdId);
    await saveToDisk();
    return memoryCache;
  }
};
