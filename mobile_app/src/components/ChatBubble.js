import React from 'react';
import { View, Text, TouchableOpacity, Image, Platform, Linking } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import * as Clipboard from 'expo-clipboard';
import * as Sharing from 'expo-sharing';
import * as FileSystem from 'expo-file-system/legacy';
import * as IntentLauncher from 'expo-intent-launcher';

const getMimeType = (filename) => {
  const ext = (filename || '').split('.').pop().toLowerCase();
  switch (ext) {
    case 'pdf': return 'application/pdf';
    case 'doc': case 'docx': return 'application/msword';
    case 'xls': case 'xlsx': return 'application/vnd.ms-excel';
    case 'ppt': case 'pptx': return 'application/vnd.ms-powerpoint';
    case 'txt': return 'text/plain';
    case 'jpg': case 'jpeg': return 'image/jpeg';
    case 'png': return 'image/png';
    case 'gif': return 'image/gif';
    case 'mp4': return 'video/mp4';
    case 'zip': return 'application/zip';
    default: return '*/*';
  }
};

export default function ChatBubble({ message, onLongPress, onOpenMedia }) {
  const isMe = message.isMe;

  const handleCopy = async () => {
    if (message.text) {
      await Clipboard.setStringAsync(message.text);
    }
  };

  // Determinar si el mensaje contiene foto o archivo adjunto
  const isPurePhoto = Boolean(message.imageUri) || (message.text && message.text.includes('Foto enviada'));
  const isPureFile = Boolean(message.fileUri) || (message.text && (message.text.includes('Archivo enviado') || message.text.includes('Archivo recibido')));

  // Extraer nombre real y limpio del archivo
  let displayFileName = '';
  if (message.text) {
    if (message.text.startsWith('📄 Archivo enviado (') && message.text.endsWith(')')) {
      displayFileName = message.text.slice('📄 Archivo enviado ('.length, -1);
    } else if (message.text.startsWith('Archivo recibido: ')) {
      displayFileName = message.text.replace('Archivo recibido: ', '');
    }
  }
  if (!displayFileName && message.fileUri) {
    displayFileName = message.fileUri.split('/').pop();
  }
  if (!displayFileName) {
    displayFileName = 'Documento adjunto';
  }

  const handleOpenFile = async () => {
    if (message.imageUri) {
      if (onOpenMedia) onOpenMedia(message.imageUri);
      return;
    }
    if (message.fileUri) {
      const mime = getMimeType(displayFileName);

      // 1. En Android, intentar abrir contentUri nativo directamente usando IntentLauncher
      if (Platform.OS === 'android') {
        try {
          const contentUri = await FileSystem.getContentUriAsync(message.fileUri);
          await IntentLauncher.startActivityAsync('android.intent.action.VIEW', {
            data: contentUri,
            flags: 1, // FLAG_GRANT_READ_URI_PERMISSION
            type: mime
          });
          return;
        } catch (androidErr) {
          console.log("[ChatBubble] IntentLauncher error:", androidErr);
        }
      }

      // 2. Fallback compatible con Expo Go (Sharing.shareAsync)
      try {
        const isAvailable = await Sharing.isAvailableAsync();
        if (isAvailable) {
          await Sharing.shareAsync(message.fileUri, {
            mimeType: mime,
            dialogTitle: `Abrir ${displayFileName}`,
            UTI: mime
          });
        }
      } catch (err) {
        console.error("[ChatBubble] Error al abrir archivo:", err);
      }
    }
  };

  return (
    <View className={`flex-row w-full mb-2 px-4 ${isMe ? 'justify-end' : 'justify-start'}`}>
      <TouchableOpacity 
        activeOpacity={0.85}
        onLongPress={() => onLongPress(message)}
        onPress={handleOpenFile}
        style={{ minWidth: (isPureFile || message.imageUri) ? 230 : 70 }}
        className={`max-w-[80%] rounded-xl p-2.5 ${
          isMe 
            ? 'bg-blue-600 rounded-tr-none' 
            : 'bg-white dark:bg-[#1e2128] border border-gray-200 dark:border-gray-800 rounded-tl-none'
        }`}
      >
        {/* Renderizado de Imagen */}
        {message.imageUri && (
          <TouchableOpacity 
            activeOpacity={0.9}
            onPress={() => onOpenMedia && onOpenMedia(message.imageUri)}
            onLongPress={() => onLongPress && onLongPress(message)}
          >
            <Image 
              source={{ uri: message.imageUri }} 
              style={{ width: '100%', height: 220, borderRadius: 8, marginBottom: 4 }}
              resizeMode="cover"
            />
          </TouchableOpacity>
        )}

        {/* Renderizado de Tarjeta de Archivo Proporcionada */}
        {isPureFile && (
          <View className={`flex-row items-center p-2.5 rounded-lg mb-1 ${isMe ? 'bg-black/20' : 'bg-gray-100 dark:bg-white/10'}`}>
            <View className={`w-9 h-9 rounded-full justify-center items-center ${isMe ? 'bg-white/20' : 'bg-blue-600/10 dark:bg-blue-500/20'}`}>
              <Ionicons name="document-text" size={20} color={isMe ? 'white' : '#3b82f6'} />
            </View>
            <View className="flex-1 ml-2.5 pr-1">
              <Text 
                className={`text-xs font-semibold ${isMe ? 'text-white' : 'text-black dark:text-white'}`} 
                numberOfLines={1} 
                ellipsizeMode="middle"
              >
                {displayFileName}
              </Text>
              <Text className={`text-[10px] ${isMe ? 'text-blue-100' : 'text-gray-400'} mt-0.5`}>
                Tocar para abrir
              </Text>
            </View>
          </View>
        )}

        {/* Renderizado de Texto Libre (Solo si no es foto o archivo comprimido) */}
        {!isPurePhoto && !isPureFile && message.text && (
          <Text className={`text-sm ${isMe ? 'text-white' : 'text-black dark:text-gray-100'}`}>
            {message.text}
          </Text>
        )}

        {message.isEdited && (
          <Text className={`text-[10px] italic ${isMe ? 'text-blue-200' : 'text-gray-400'} mt-0.5`}>
            (editado)
          </Text>
        )}
        
        {/* Pie de mensaje (Hora y Estado) */}
        <View className="flex-row justify-end items-center mt-1 space-x-1.5">
          <TouchableOpacity onPress={handleCopy} className="p-0.5 mr-1">
            <Ionicons name="copy-outline" size={12} color={isMe ? 'rgba(255,255,255,0.7)' : '#9ca3af'} />
          </TouchableOpacity>
          
          <Text className={`text-[10px] ${isMe ? 'text-blue-100' : 'text-gray-400'}`}>
            {message.time}
          </Text>
          
          {isMe && (
            <Ionicons 
              name="checkmark-done" 
              size={14} 
              color={message.status === 'read' ? '#93c5fd' : 'rgba(255,255,255,0.7)'} 
            />
          )}
        </View>
      </TouchableOpacity>
    </View>
  );
}
