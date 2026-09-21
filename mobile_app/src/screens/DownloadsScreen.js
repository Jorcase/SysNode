import React, { useState, useEffect } from 'react';
import { View, Text, TouchableOpacity, FlatList, Alert, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import * as FileSystem from 'expo-file-system/legacy';
import * as Sharing from 'expo-sharing';
import * as IntentLauncher from 'expo-intent-launcher';
import { Platform } from 'react-native';

export default function DownloadsScreen({ navigation }) {
  const insets = useSafeAreaInsets();
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(true);
  
  const downloadPath = FileSystem.documentDirectory + 'SysNode_Received/';

  useEffect(() => {
    loadFiles();
  }, []);

  const loadFiles = async () => {
    setLoading(true);
    try {
      const info = await FileSystem.getInfoAsync(downloadPath);
      if (!info.exists) {
        await FileSystem.makeDirectoryAsync(downloadPath, { intermediates: true });
      }
      
      const fileNames = await FileSystem.readDirectoryAsync(downloadPath);
      
      const fileInfos = await Promise.all(
        fileNames.map(async (name) => {
          const fileUri = downloadPath + name;
          const fileInfo = await FileSystem.getInfoAsync(fileUri);
          return {
            id: name,
            name: name,
            uri: fileUri,
            size: fileInfo.size,
            time: fileInfo.modificationTime
          };
        })
      );
      
      // Sort by newest first
      fileInfos.sort((a, b) => b.time - a.time);
      setFiles(fileInfos);
    } catch (error) {
      console.log("Error loading files:", error);
      Alert.alert("Error", "No se pudieron cargar los archivos.");
    } finally {
      setLoading(false);
    }
  };

  const formatSize = (bytes) => {
    if (!bytes) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const handleOpenFile = async (file) => {
    try {
      if (Platform.OS === 'android') {
        const cUri = await FileSystem.getContentUriAsync(file.uri);
        await IntentLauncher.startActivityAsync('android.intent.action.VIEW', {
          data: cUri,
          flags: 1, // FLAG_GRANT_READ_URI_PERMISSION
        });
      } else {
        const isAvailable = await Sharing.isAvailableAsync();
        if (isAvailable) {
          await Sharing.shareAsync(file.uri);
        } else {
          Alert.alert("Error", "No se puede abrir el archivo en este dispositivo.");
        }
      }
    } catch (error) {
      // Fallback to sharing if direct opening fails (very common on Android)
      try {
        const isAvailable = await Sharing.isAvailableAsync();
        if (isAvailable) {
          await Sharing.shareAsync(file.uri);
        }
      } catch (e) {
        Alert.alert("Error", "No se pudo abrir el archivo.");
      }
    }
  };

  const handleDeleteFile = (file) => {
    Alert.alert(
      "Eliminar Archivo",
      `¿Deseas eliminar "${file.name}" permanentemente?`,
      [
        { text: "Cancelar", style: "cancel" },
        {
          text: "Eliminar",
          style: "destructive",
          onPress: async () => {
            try {
              await FileSystem.deleteAsync(file.uri);
              loadFiles();
            } catch (error) {
              Alert.alert("Error", "No se pudo eliminar el archivo.");
            }
          }
        }
      ]
    );
  };

  const renderItem = ({ item }) => (
    <View className="flex-row items-center px-4 py-3 border-b border-gray-100 dark:border-gray-800 bg-white dark:bg-[#1e2128]">
      <TouchableOpacity 
        className="flex-1 flex-row items-center"
        onPress={() => handleOpenFile(item)}
      >
        <View className="w-10 h-10 rounded-md bg-blue-100 dark:bg-blue-900/30 items-center justify-center mr-3">
          <Ionicons name="document-text-outline" size={20} color="#3b82f6" />
        </View>
        <View className="flex-1">
          <Text className="text-sm font-medium text-black dark:text-white" numberOfLines={1}>
            {item.name}
          </Text>
          <Text className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
            {formatSize(item.size)} • {new Date(item.time * 1000).toLocaleString()}
          </Text>
        </View>
      </TouchableOpacity>
      
      <TouchableOpacity 
        className="p-2 ml-2 rounded-full"
        onPress={() => handleDeleteFile(item)}
      >
        <Ionicons name="trash-outline" size={20} color="#ef4444" />
      </TouchableOpacity>
    </View>
  );

  return (
    <View className="flex-1 bg-gray-50 dark:bg-[#0b0c10]">
      {/* Header */}
      <View 
        className="px-4 pb-3 bg-white dark:bg-[#1e2128] border-b border-gray-200 dark:border-gray-800 flex-row items-center"
        style={{ paddingTop: insets.top > 0 ? insets.top + 12 : 16 }}
      >
        <TouchableOpacity onPress={() => navigation.goBack()} className="mr-3 p-1">
          <Ionicons name="arrow-back" size={24} color="#3b82f6" />
        </TouchableOpacity>
        <Text className="text-lg font-bold text-black dark:text-white">Archivos Recibidos</Text>
      </View>

      {loading ? (
        <View className="flex-1 items-center justify-center">
          <ActivityIndicator size="large" color="#3b82f6" />
        </View>
      ) : files.length === 0 ? (
        <View className="flex-1 items-center justify-center p-6">
          <Ionicons name="folder-open-outline" size={64} color="#9ca3af" className="mb-4" />
          <Text className="text-base text-gray-500 dark:text-gray-400 text-center">
            No hay archivos descargados.
          </Text>
        </View>
      ) : (
        <FlatList
          data={files}
          keyExtractor={item => item.id}
          renderItem={renderItem}
          contentContainerStyle={{ paddingBottom: 20 }}
        />
      )}
    </View>
  );
}
