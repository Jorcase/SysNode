import React from 'react';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { useColorScheme } from 'nativewind';
import { Ionicons } from '@expo/vector-icons';

import ChatsScreen from '../screens/ChatsScreen';
import ProfileScreen from '../screens/ProfileScreen';
import SettingsScreen from '../screens/SettingsScreen';

const Tab = createBottomTabNavigator();

export default function BottomTabNavigator() {
  const { colorScheme } = useColorScheme();
  const isDark = colorScheme === 'dark';

  return (
    <Tab.Navigator
      screenOptions={({ route }) => ({
        headerShown: false,
        tabBarActiveTintColor: isDark ? '#3b82f6' : '#2563eb',
        tabBarInactiveTintColor: isDark ? '#6b7280' : '#9ca3af',
        tabBarStyle: {
          backgroundColor: isDark ? '#0f1115' : '#ffffff',
          borderTopColor: isDark ? '#1e2128' : '#e5e7eb',
          paddingBottom: 5,
          paddingTop: 5,
          minHeight: 60,
        },
        tabBarActiveTintColor: '#3b82f6', // sysnode blue
        tabBarInactiveTintColor: isDark ? '#94a3b8' : '#64748b',
        tabBarIcon: ({ focused, color, size }) => {
          let iconName;
          
          if (route.name === 'Chats') {
            iconName = focused ? 'chatbubbles' : 'chatbubbles-outline';
          } else if (route.name === 'Perfil') {
            iconName = focused ? 'person' : 'person-outline';
          } else if (route.name === 'Settings') {
            iconName = focused ? 'settings' : 'settings-outline';
          }

          return <Ionicons name={iconName} size={24} color={color} />;
        },
      })}
    >
      <Tab.Screen name="Chats" component={ChatsScreen} />
      <Tab.Screen 
        name="Settings" 
        component={SettingsScreen} 
        options={{
          tabBarLabel: 'Configuración',
        }}
      />
      <Tab.Screen 
        name="Perfil" 
        component={ProfileScreen} 
        options={{
          tabBarLabel: 'Perfil',
        }}
      />
    </Tab.Navigator>
  );
}
