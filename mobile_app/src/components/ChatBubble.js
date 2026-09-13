import React from 'react';
import { View, Text, TouchableOpacity, Image } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import * as Clipboard from 'expo-clipboard';
import * as Sharing from 'expo-sharing';

export default function ChatBubble({ message, onLongPress, onOpenMedia }) {
  const isMe = message.isMe;

  const handleCopy = async () => {
    if (message.text) {
      await Clipboard.setStringAsync(message.text);
    }
  };

  const handleOpenFile = async () => {
    if (message.imageUri) {
      if (onOpenMedia) onOpenMedia(message.imageUri);
      return;
    }
    if (message.fileUri) {
      try {
        const isAvailable = await Sharing.isAvailableAsync();
        if (isAvailable) {
          await Sharing.shareAsync(message.fileUri);
        }
      } catch (e) {
        console.error("Error abriendo archivo:", e);
      }
    }
  };

  // Determinar si el mensaje contiene sólo foto/archivo sin comentario del usuario
  const isPurePhoto = message.imageUri || (message.text && message.text.startsWith('📸 Foto enviada'));
  const isPureFile = message.fileUri || (message.text && message.text.startsWith('📄 Archivo enviado'));

  // Extraer nombre del archivo si es foto/archivo generado
  let displayFileName = '';
  if (isPureFile && message.text) {
    const match = message.text.match(/\((.*?)\)/);
    displayFileName = match ? match[1] : 'Archivo adjunto';
  }

  return (
    <View className={`flex-row w-full mb-2 px-4 ${isMe ? 'justify-end' : 'justify-start'}`}>
      <TouchableOpacity 
        activeOpacity={0.85}
        onLongPress={() => onLongPress(message)}
        onPress={handleOpenFile}
        className={`max-w-[80%] rounded-md p-2.5 ${
          isMe 
            ? 'bg-blue-600 rounded-tr-none' 
            : 'bg-white dark:bg-[#1e2128] border border-gray-200 dark:border-gray-800 rounded-tl-none'
        }`}
      >
        {/* Renderizado de Imagen */}
        {message.imageUri && (
          <TouchableOpacity onPress={() => onOpenMedia && onOpenMedia(message.imageUri)}>
            <Image 
              source={{ uri: message.imageUri }} 
              style={{ width: 220, height: 220, borderRadius: 4, marginBottom: message.text && !isPurePhoto ? 6 : 2 }}
              resizeMode="cover"
            />
          </TouchableOpacity>
        )}

        {/* Renderizado de Tarjeta de Archivo Minimalista */}
        {isPureFile && (
          <View className="flex-row items-center p-2 rounded bg-black/10 dark:bg-white/10 mb-1">
            <Ionicons name="document-text-outline" size={24} color={isMe ? 'white' : '#3b82f6'} className="mr-2" />
            <View className="flex-1 ml-2">
              <Text className={`text-xs font-semibold ${isMe ? 'text-white' : 'text-black dark:text-white'}`} numberOfLines={1}>
                {displayFileName || 'Documento'}
              </Text>
              <Text className={`text-[10px] ${isMe ? 'text-blue-100' : 'text-gray-400'}`}>
                Toca para abrir
              </Text>
            </View>
          </View>
        )}

        {/* Renderizado de Texto (Si no es una etiqueta redundante) */}
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
        
        <View className="flex-row justify-end items-center mt-1 space-x-1.5">
          <TouchableOpacity onPress={handleCopy} className="p-0.5">
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
