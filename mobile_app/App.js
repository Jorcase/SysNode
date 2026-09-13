import React from 'react';
import { StatusBar } from 'react-native';
import { NavigationContainer, DefaultTheme, DarkTheme } from '@react-navigation/native';
import { useColorScheme } from 'nativewind';
import AppNavigator from './src/navigation/AppNavigator';

export default function App() {
  const { colorScheme } = useColorScheme();
  const isDark = colorScheme === 'dark';

  return (
    <NavigationContainer theme={isDark ? DarkTheme : DefaultTheme}>
      <StatusBar 
        barStyle={colorScheme === 'dark' ? 'light-content' : 'dark-content'} 
        backgroundColor={colorScheme === 'dark' ? '#0f1115' : '#ffffff'} 
      />
      <AppNavigator />
    </NavigationContainer>
  );
}
