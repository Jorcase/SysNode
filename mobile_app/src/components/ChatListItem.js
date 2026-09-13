import React from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

export default function ChatListItem({ item, onPress, onLongPress }) {
  return (
    <TouchableOpacity 
      activeOpacity={0.7} 
      onPress={onPress}
      onLongPress={onLongPress}
      className="flex-row items-center p-3 border-b border-gray-200 dark:border-gray-800"
    >
      {/* Avatar */}
      <View className="relative">
        <View className="w-10 h-10 rounded-md bg-blue-100 dark:bg-blue-900/30 items-center justify-center">
          <Ionicons 
            name={
              item.os?.toLowerCase().includes('android') || item.os?.toLowerCase().includes('ios') 
                ? 'phone-portrait-outline' 
                : 'desktop-outline'
            } 
            size={20} 
            color="#3b82f6" 
          />
        </View>
        <View className={`absolute bottom-0 right-0 w-2.5 h-2.5 rounded-full border border-white dark:border-[#0f1115] ${item.isActive ? 'bg-green-500' : 'bg-gray-400'}`} />
      </View>

      {/* Content */}
      <View className="flex-1 ml-3 justify-center">
        <Text className="text-sm font-semibold text-black dark:text-white" numberOfLines={1}>
          {item.name} {item.isMe && <Text className="font-normal text-gray-500">(Tú)</Text>}
        </Text>
        <Text className="text-xs text-gray-500 dark:text-gray-400 mt-0.5" numberOfLines={1}>
          {item.lastMessage || 'Sin mensajes recientes'}
        </Text>
      </View>

      {/* Meta (Date & Active Indicator) */}
      <View className="items-end ml-2">
        {item.isActive ? (
          <View className="flex-row items-center bg-green-100 dark:bg-green-900/30 px-2 py-0.5 rounded-md">
            <View className="w-1.5 h-1.5 rounded-full bg-green-500 mr-1" />
            <Text className="text-[10px] font-bold text-green-600 dark:text-green-400">Activo</Text>
          </View>
        ) : (
          <View className="flex-row items-center bg-gray-100 dark:bg-gray-800 px-2 py-0.5 rounded-md">
            <View className="w-1.5 h-1.5 rounded-full bg-gray-400 mr-1" />
            <Text className="text-[10px] font-bold text-gray-500 dark:text-gray-400">Inactivo</Text>
          </View>
        )}
      </View>
    </TouchableOpacity>
  );
}
