import React, { useState, useEffect } from 'react';
import { View, Text, TouchableOpacity, ScrollView, Modal, TextInput, Alert, FlatList, Switch } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import * as FileSystem from 'expo-file-system/legacy';
import * as Sharing from 'expo-sharing';
import { CommandStorage } from '../network/CommandStorage';
import { useMyIdentity } from '../network/MyIdentity';

export default function SettingsScreen({ navigation }) {
  const insets = useSafeAreaInsets();
  const { identity, updateIdentity } = useMyIdentity();

  // Downloads / Storage State
  const [downloadPath, setDownloadPath] = useState('');
  const [fileCount, setFileCount] = useState(0);
  const [totalSize, setTotalSize] = useState('0 MB');
  const [customPathInput, setCustomPathInput] = useState('');
  const [showChangePathModal, setShowChangePathModal] = useState(false);

  // Command Management State
  const [commands, setCommands] = useState([]);
  const [showCommandsModal, setShowCommandsModal] = useState(false);
  const [showEditCmdModal, setShowEditCmdModal] = useState(false);
  const [editingCmd, setEditingCmd] = useState(null);
  const [cmdNameInput, setCmdNameInput] = useState('');
  const [cmdScriptInput, setCmdScriptInput] = useState('');
  const [cmdBgInput, setCmdBgInput] = useState(false);

  useEffect(() => {
    loadStorageStats();
    loadCommands();
  }, []);

  const loadStorageStats = async () => {
    try {
      const dir = (FileSystem.documentDirectory || '') + 'SysNode_Received/';
      setDownloadPath(dir);
      setCustomPathInput(dir);
      const info = await FileSystem.getInfoAsync(dir);
      if (info.exists) {
        const files = await FileSystem.readDirectoryAsync(dir);
        setFileCount(files.length);
        
        let bytes = 0;
        for (const file of files) {
          const fileStats = await FileSystem.getInfoAsync(dir + file);
          if (fileStats.exists && fileStats.size) {
            bytes += fileStats.size;
          }
        }
        const mb = (bytes / (1024 * 1024)).toFixed(2);
        setTotalSize(`${mb} MB`);
      } else {
        setFileCount(0);
        setTotalSize('0 MB');
      }
    } catch (e) {
      console.error("[SettingsScreen] Error cargando stats de descargas:", e);
    }
  };

  const loadCommands = async () => {
    const cmds = await CommandStorage.getCommands();
    setCommands(cmds);
  };

  const handleOpenFolder = () => {
    navigation.navigate('Downloads');
  };

  const handleOpenAddCommand = () => {
    setEditingCmd(null);
    setCmdNameInput('');
    setCmdScriptInput('');
    setCmdBgInput(false);
    setShowEditCmdModal(true);
  };

  const handleOpenEditCommand = (cmd) => {
    setEditingCmd(cmd);
    setCmdNameInput(cmd.name);
    setCmdScriptInput(cmd.command);
    setCmdBgInput(cmd.isBackground || false);
    setShowEditCmdModal(true);
  };

  const handleSaveCommand = async () => {
    if (!cmdNameInput.trim() || !cmdScriptInput.trim()) {
      Alert.alert("Atención", "Por favor completa el nombre y el comando.");
      return;
    }

    const cmdObj = {
      id: editingCmd ? editingCmd.id : null,
      name: cmdNameInput.trim(),
      command: cmdScriptInput.trim(),
      isBackground: cmdBgInput,
      isDefault: editingCmd ? editingCmd.isDefault : false
    };

    await CommandStorage.saveCommand(cmdObj);
    await loadCommands();
    setShowEditCmdModal(false);
  };

  const handleDeleteCommand = async (cmdId) => {
    Alert.alert(
      "Eliminar Comando",
      "¿Deseas eliminar este comando?",
      [
        { text: "Cancelar", style: "cancel" },
        {
          text: "Eliminar",
          style: "destructive",
          onPress: async () => {
            await CommandStorage.deleteCommand(cmdId);
            await loadCommands();
          }
        }
      ]
    );
  };

  return (
    <View className="flex-1 bg-gray-50 dark:bg-[#0b0c10]" style={{ paddingTop: insets.top }}>
      {/* Header */}
      <View className="px-6 py-4 bg-white dark:bg-[#1e2128] border-b border-gray-200 dark:border-gray-800">
        <Text className="text-xl font-bold text-black dark:text-white">Configuración</Text>
      </View>

      <ScrollView className="flex-1 pt-4">
        {/* Sección: Modo de Visibilidad */}
        <Text className="px-6 mb-2 text-xs font-bold text-gray-400 uppercase tracking-wider">Modo de Visibilidad en Red</Text>
        <View className="bg-white dark:bg-[#1e2128] border-y border-gray-200 dark:border-gray-800 mb-6 p-4">
          <View className="flex-row justify-between">
            <TouchableOpacity
              onPress={() => updateIdentity({ is_stealth: false })}
              className={`flex-1 p-3 rounded-md border mr-2 items-center ${
                !identity?.is_stealth 
                  ? 'bg-blue-500/10 border-blue-500' 
                  : 'bg-gray-100 dark:bg-[#0f1115] border-gray-200 dark:border-gray-800'
              }`}
            >
              <Text className={`font-bold text-sm ${!identity?.is_stealth ? 'text-blue-600 dark:text-blue-400' : 'text-gray-400'}`}>Público</Text>
              <Text className="text-[10px] text-gray-400 text-center mt-1">Visible por UDP Broadcast</Text>
            </TouchableOpacity>

            <TouchableOpacity
              onPress={() => updateIdentity({ is_stealth: true })}
              className={`flex-1 p-3 rounded-md border ml-2 items-center ${
                identity?.is_stealth 
                  ? 'bg-purple-500/10 border-purple-500' 
                  : 'bg-gray-100 dark:bg-[#0f1115] border-gray-200 dark:border-gray-800'
              }`}
            >
              <Text className={`font-bold text-sm ${identity?.is_stealth ? 'text-purple-600 dark:text-purple-300' : 'text-gray-400'}`}>Oculto</Text>
              <Text className="text-[10px] text-gray-400 text-center mt-1">Conexión directa por TCP / QR</Text>
            </TouchableOpacity>
          </View>
        </View>

        {/* Sección: Almacenamiento y Descargas */}
        <Text className="px-6 mb-2 text-xs font-bold text-gray-400 uppercase tracking-wider">Almacenamiento y Descargas</Text>
        <View className="bg-white dark:bg-[#1e2128] border-y border-gray-200 dark:border-gray-800 mb-6 p-4">
          <View className="flex-row items-center mb-3">
            <View className="w-8 h-8 rounded-md bg-blue-100 dark:bg-blue-900/30 items-center justify-center mr-3">
              <Ionicons name="folder-outline" size={18} color="#3b82f6" />
            </View>
            <View className="flex-1">
              <Text className="text-sm font-medium text-black dark:text-white">Carpeta de Descargas</Text>
              <Text className="text-xs text-gray-500 dark:text-gray-400 mt-0.5" numberOfLines={1}>
                {downloadPath || 'SysNode_Received/'}
              </Text>
              <Text className="text-[11px] text-blue-500 font-semibold mt-0.5">
                {fileCount} archivos ({totalSize})
              </Text>
            </View>
          </View>

          <View className="flex-row space-x-2 mt-2">
            <TouchableOpacity 
              className="flex-1 flex-row items-center justify-center py-2.5 px-3 bg-blue-600 rounded-md"
              onPress={handleOpenFolder}
            >
              <Ionicons name="folder-open-outline" size={16} color="white" className="mr-1.5" />
              <Text className="text-xs font-bold text-white ml-1">Ver Archivos</Text>
            </TouchableOpacity>
          </View>
        </View>

        {/* Sección: Avanzado */}
        <Text className="px-6 mb-2 text-xs font-bold text-gray-400 uppercase tracking-wider">Avanzado y Comandos</Text>
        <View className="bg-white dark:bg-[#1e2128] border-y border-gray-200 dark:border-gray-800 mb-6">
          <TouchableOpacity 
            className="flex-row items-center px-6 py-4"
            onPress={() => setShowCommandsModal(true)}
          >
            <View className="w-8 h-8 rounded-md bg-purple-100 dark:bg-purple-900/30 items-center justify-center mr-4">
              <Ionicons name="terminal-outline" size={18} color="#a855f7" />
            </View>
            <View className="flex-1">
              <Text className="text-sm font-medium text-black dark:text-white">Comandos Rápidos</Text>
              <Text className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                {commands.length} comandos configurados
              </Text>
            </View>
            <Ionicons name="chevron-forward" size={18} color="#9ca3af" />
          </TouchableOpacity>
        </View>

        {/* Info de la app */}
        <View className="items-center mt-2 mb-10">
          <Text className="text-xs font-bold text-gray-400">SysNode Mobile v1.0.0</Text>
          <Text className="text-[10px] text-gray-500 mt-0.5">Conexión P2P Local LAN</Text>
        </View>
      </ScrollView>

      {/* Modal: Lista de Comandos Rápidos */}
      <Modal visible={showCommandsModal} animationType="slide" transparent={false}>
        <View className="flex-1 bg-gray-50 dark:bg-[#0b0c10]" style={{ paddingTop: insets.top }}>
          {/* Header Modal */}
          <View className="flex-row items-center justify-between px-6 py-4 bg-white dark:bg-[#1e2128] border-b border-gray-200 dark:border-gray-800">
            <TouchableOpacity onPress={() => setShowCommandsModal(false)} className="p-1">
              <Ionicons name="close" size={24} color="#3b82f6" />
            </TouchableOpacity>
            <Text className="text-base font-bold text-black dark:text-white">Comandos Rápidos</Text>
            <TouchableOpacity onPress={handleOpenAddCommand} className="p-1">
              <Ionicons name="add-circle-outline" size={26} color="#3b82f6" />
            </TouchableOpacity>
          </View>

          {/* List Commands */}
          <FlatList
            data={commands}
            keyExtractor={item => item.id}
            contentContainerStyle={{ paddingVertical: 10 }}
            renderItem={({ item }) => (
              <View className="mx-4 my-1.5 p-3.5 bg-white dark:bg-[#1e2128] rounded-md border border-gray-200 dark:border-gray-800 flex-row items-center justify-between">
                <View className="flex-1 pr-3">
                  <Text className="text-sm font-bold text-black dark:text-white">{item.name}</Text>
                  <Text className="text-xs font-mono text-gray-500 dark:text-gray-400 mt-1 bg-gray-100 dark:bg-[#0f1115] p-1.5 rounded-md" numberOfLines={2}>
                    $ {item.command}
                  </Text>
                </View>

                <View className="flex-row items-center">
                  <TouchableOpacity onPress={() => handleOpenEditCommand(item)} className="p-2 mr-1">
                    <Ionicons name="pencil-outline" size={18} color="#3b82f6" />
                  </TouchableOpacity>
                  <TouchableOpacity onPress={() => handleDeleteCommand(item.id)} className="p-2">
                    <Ionicons name="trash-outline" size={18} color="#ef4444" />
                  </TouchableOpacity>
                </View>
              </View>
            )}
          />
        </View>
      </Modal>

      {/* Modal: Crear / Editar Comando */}
      <Modal visible={showEditCmdModal} animationType="fade" transparent={true}>
        <View className="flex-1 bg-black/60 justify-center items-center px-6">
          <View className="w-full bg-white dark:bg-[#1e2128] rounded-md p-6 border border-gray-200 dark:border-gray-800">
            <Text className="text-base font-bold text-black dark:text-white mb-4">
              {editingCmd ? 'Editar Comando' : 'Nuevo Comando'}
            </Text>

            <Text className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-1">Nombre</Text>
            <TextInput
              className="bg-gray-100 dark:bg-[#0f1115] text-black dark:text-white p-2.5 rounded-md mb-4 text-sm border border-gray-200 dark:border-gray-800"
              placeholder="ej. Bloquear Sesión"
              placeholderTextColor="#9ca3af"
              value={cmdNameInput}
              onChangeText={setCmdNameInput}
            />

            <Text className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-1">Comando o Script (Opcional: Multi-OS con etiquetas [windows], [linux])</Text>
            <TextInput
              className="bg-gray-100 dark:bg-[#0f1115] text-black dark:text-white p-2.5 rounded-md mb-4 text-sm font-mono border border-gray-200 dark:border-gray-800"
              placeholder="[windows]\nwinget upgrade\n[ubuntu]\napt update"
              placeholderTextColor="#9ca3af"
              value={cmdScriptInput}
              onChangeText={setCmdScriptInput}
              multiline
              numberOfLines={4}
              textAlignVertical="top"
              autoCapitalize="none"
              autoCorrect={false}
            />

            <View className="flex-row items-center justify-between mb-6">
              <View>
                <Text className="text-sm font-bold text-black dark:text-white">Fondo / Background</Text>
                <Text className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">Ideal para abrir apps (no espera logs)</Text>
              </View>
              <Switch
                value={cmdBgInput}
                onValueChange={setCmdBgInput}
                trackColor={{ false: "#374151", true: "#3b82f6" }}
                thumbColor={"#ffffff"}
              />
            </View>

            <View className="flex-row justify-end space-x-2">
              <TouchableOpacity 
                onPress={() => setShowEditCmdModal(false)}
                className="px-4 py-2 rounded-md bg-gray-200 dark:bg-gray-800 mr-2"
              >
                <Text className="text-xs text-gray-700 dark:text-gray-300 font-semibold">Cancelar</Text>
              </TouchableOpacity>

              <TouchableOpacity 
                onPress={handleSaveCommand}
                className="px-4 py-2 rounded-md bg-blue-600"
              >
                <Text className="text-xs text-white font-bold">Guardar</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </View>
  );
}
