import React, { useState } from 'react';
import { View, Text, SafeAreaView, TextInput, TouchableOpacity, Switch } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useMyIdentity } from '../network/MyIdentity';

export default function ProfileScreen() {
  const insets = useSafeAreaInsets();
  
  const { identity, updateIdentity } = useMyIdentity();
  const [name, setName] = useState(identity?.node_name || 'Desconocido');
  const [isEditingName, setIsEditingName] = useState(false);

  // Update local state if global changes
  React.useEffect(() => {
    if (identity?.node_name) setName(identity.node_name);
  }, [identity?.node_name]);

  const toggleStealth = () => {
    if (identity) updateIdentity({ is_stealth: !identity.is_stealth });
  };

  const handleSaveName = () => {
    setIsEditingName(false);
    updateIdentity({ node_name: name });
  };

  return (
    <View className="flex-1 bg-gray-50 dark:bg-[#0b0c10]" style={{ paddingTop: insets.top }}>
      {/* Header */}
      <View className="px-6 py-4 bg-white dark:bg-[#1e2128] border-b border-gray-200 dark:border-gray-800">
        <Text className="text-2xl font-bold text-black dark:text-white">Tu Perfil</Text>
      </View>

      <View className="p-6">
        {/* Avatar */}
        <View className="items-center mb-6">
          <View className="w-24 h-24 rounded-full bg-blue-100 dark:bg-blue-900/30 items-center justify-center mb-2 border-4 border-white dark:border-[#1e2128] shadow-sm">
            <Ionicons name="phone-portrait-outline" size={48} color="#3b82f6" />
          </View>
        </View>

        {/* Nombre Público Editable */}
        <View className="bg-white dark:bg-[#1e2128] rounded-2xl p-4 shadow-sm mb-4">
          <Text className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-2">Nombre Público</Text>
          <View className="flex-row items-center bg-gray-50 dark:bg-[#0f1115] rounded-xl px-4 py-1">
            <Ionicons name="person-outline" size={20} color="#9ca3af" />
            <TextInput 
              className="flex-1 text-black dark:text-white text-base ml-3 py-3"
              value={name}
              onChangeText={setName}
              placeholder="Tu nombre en la red"
              placeholderTextColor="#9ca3af"
              editable={isEditingName}
              style={{ opacity: isEditingName ? 1 : 0.6 }}
            />
            <TouchableOpacity 
              onPress={() => {
                if (isEditingName) {
                  handleSaveName();
                } else {
                  setIsEditingName(true);
                }
              }}
              className="p-2"
            >
              <Ionicons 
                name={isEditingName ? "checkmark-circle" : "pencil"} 
                size={22} 
                color={isEditingName ? "#10b981" : "#3b82f6"} 
              />
            </TouchableOpacity>
          </View>
        </View>

        {/* Información del Dispositivo */}
        <View className="bg-white dark:bg-[#1e2128] rounded-2xl p-4 shadow-sm mb-4">
          <Text className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-3">Información del Dispositivo</Text>
          
          <View className="flex-row justify-between mb-2">
            <Text className="text-sm font-medium text-gray-500 dark:text-gray-400">Sistema Operativo</Text>
            <Text className="text-sm font-bold text-black dark:text-white">Android</Text>
          </View>
          <View className="flex-row justify-between mb-2">
            <Text className="text-sm font-medium text-gray-500 dark:text-gray-400">IP Local</Text>
            <Text className="text-sm font-bold text-black dark:text-white">192.168.0.49</Text>
          </View>
          <View className="flex-row justify-between mb-2">
            <Text className="text-sm font-medium text-gray-500 dark:text-gray-400">Puerto TCP</Text>
            <Text className="text-sm font-bold text-black dark:text-white">46623</Text>
          </View>
          <View className="flex-row justify-between">
            <Text className="text-sm font-medium text-gray-500 dark:text-gray-400">ID Único</Text>
            <Text className="text-sm font-bold text-black dark:text-white">a8f9-3c21-mock</Text>
          </View>
        </View>

        {/* Modo Oculto */}
        <View className="bg-white dark:bg-[#1e2128] rounded-2xl p-4 shadow-sm flex-row items-center justify-between">
          <View className="flex-1 pr-4">
            <View className="flex-row items-center mb-1">
              <Ionicons name={identity?.is_stealth ? "eye-off" : "eye"} size={20} color={identity?.is_stealth ? "#f43f5e" : "#3b82f6"} />
              <Text className="text-base font-bold text-black dark:text-white ml-2">
                Modo Oculto
              </Text>
            </View>
            <Text className="text-xs text-gray-500 dark:text-gray-400 leading-tight">
              Si está activo, tu dispositivo no será visible en la red. Solo podrán agregarte escaneando tu QR.
            </Text>
          </View>
          <Switch 
            value={identity?.is_stealth || false} 
            onValueChange={toggleStealth} 
            trackColor={{ false: '#d1d5db', true: '#fca5a5' }}
            thumbColor={identity?.is_stealth ? '#f43f5e' : '#f3f4f6'}
          />
        </View>

        {/* QR Code Button (Futuro) */}
        <TouchableOpacity className="mt-8 flex-row items-center justify-center bg-blue-500 rounded-xl py-4 shadow-sm">
          <Ionicons name="qr-code" size={20} color="white" />
          <Text className="text-white font-bold text-base ml-2">Mostrar mi Código QR</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}
