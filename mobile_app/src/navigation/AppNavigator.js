import React from 'react';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import BottomTabNavigator from './BottomTabNavigator';
import ChatDetailScreen from '../screens/ChatDetailScreen';
import TerminalScreen from '../screens/TerminalScreen';

const Stack = createNativeStackNavigator();

export default function AppNavigator() {
  return (
    <Stack.Navigator screenOptions={{ headerShown: false }}>
      {/* Las pestañas principales (Lista de Chats, Config, Perfil) */}
      <Stack.Screen name="MainTabs" component={BottomTabNavigator} />
      
      {/* La pantalla individual del chat */}
      <Stack.Screen 
        name="ChatDetail" 
        component={ChatDetailScreen} 
      />

      {/* Pantalla de Terminal SSH Remota */}
      <Stack.Screen 
        name="Terminal" 
        component={TerminalScreen} 
      />
    </Stack.Navigator>
  );
}
