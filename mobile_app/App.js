import React from 'react';
import { SafeAreaView, StatusBar, Text, View } from 'react-native';
import HomeScreen from './src/screens/HomeScreen';
import { withExpoSnack } from 'nativewind';

export default function App() {
  return (
    <SafeAreaView className="flex-1 bg-[#1a1a1a]">
      <StatusBar barStyle="light-content" backgroundColor="#1a1a1a" />
      <HomeScreen />
    </SafeAreaView>
  );
}
