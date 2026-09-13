import React from 'react';
import { View, Text } from 'react-native';

export default function ConfigScreen() {
  return (
    <View className="flex-1 items-center justify-center bg-white dark:bg-[#0f1115]">
      <Text className="text-lg font-bold text-black dark:text-white">Configuración</Text>
      <Text className="text-gray-500 dark:text-gray-400 mt-2">Menú de Rutas y Comandos</Text>
    </View>
  );
}
