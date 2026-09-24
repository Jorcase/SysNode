import { useState, useEffect } from 'react';
import * as FileSystem from 'expo-file-system/legacy';
import { DeviceEventEmitter } from 'react-native';

const IDENTITY_FILE = FileSystem.documentDirectory + 'sysnode_identity.json';

// Genera un UUID simple (v4 mock)
function generateUUID() {
  let d = new Date().getTime();
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
    let r = (d + Math.random() * 16) % 16 | 0;
    d = Math.floor(d / 16);
    return (c == 'x' ? r : (r & 0x3 | 0x8)).toString(16);
  });
}

// Singleton state
let globalIdentity = {
  node_id: null,
  node_name: 'SysNode Mobile',
  is_stealth: false
};

let isLoaded = false;

export const loadIdentity = async () => {
  if (isLoaded) return globalIdentity;
  try {
    const fileInfo = await FileSystem.getInfoAsync(IDENTITY_FILE);
    if (fileInfo.exists) {
      const content = await FileSystem.readAsStringAsync(IDENTITY_FILE);
      globalIdentity = JSON.parse(content);
    } else {
      // First time launch
      globalIdentity = {
        node_id: generateUUID(),
        node_name: 'Android (' + Math.floor(Math.random() * 1000) + ')',
        is_stealth: false
      };
      await FileSystem.writeAsStringAsync(IDENTITY_FILE, JSON.stringify(globalIdentity));
    }
  } catch (e) {
    console.error("Error loading identity:", e);
  }
  isLoaded = true;
  DeviceEventEmitter.emit('onIdentityUpdated', globalIdentity);
  return globalIdentity;
};

export const saveIdentity = async (updates) => {
  globalIdentity = { ...globalIdentity, ...updates };
  try {
    await FileSystem.writeAsStringAsync(IDENTITY_FILE, JSON.stringify(globalIdentity));
    DeviceEventEmitter.emit('onIdentityUpdated', globalIdentity);
  } catch (e) {
    console.error("Error saving identity:", e);
  }
};

export const getIdentity = () => globalIdentity;

export function useMyIdentity() {
  const [identity, setIdentity] = useState(globalIdentity);

  useEffect(() => {
    loadIdentity().then(setIdentity);
    const sub = DeviceEventEmitter.addListener('onIdentityUpdated', setIdentity);
    return () => sub.remove();
  }, []);

  const updateIdentity = async (updates) => {
    await saveIdentity(updates);
  };

  return { identity, updateIdentity };
}
