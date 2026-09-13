import React, { useState, useEffect, useRef, useCallback } from 'react';
import { View, FlatList, TouchableOpacity, Text, Alert, Modal, TextInput, StyleSheet, DeviceEventEmitter } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useNavigation, useFocusEffect } from '@react-navigation/native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import ChatListItem from '../components/ChatListItem';
import { UdpDiscovery } from '../network/UdpDiscovery';
import { TcpServer } from '../network/TcpServer';
import { useMyIdentity } from '../network/MyIdentity';
import { MessageStorage } from '../network/MessageStorage';
import { CameraView, useCameraPermissions } from 'expo-camera';

// Generador simple de UUID v4
function generateUUID() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
    var r = Math.random() * 16 | 0, v = c == 'x' ? r : (r & 0x3 | 0x8);
    return v.toString(16);
  });
}

export default function ChatsScreen() {
  const navigation = useNavigation();
  const insets = useSafeAreaInsets();
  
  const { identity, updateIdentity } = useMyIdentity();
  const nodeId = identity?.node_id;
  const nodeName = identity?.node_name;
  
  const [tcpPort, setTcpPort] = useState(0);
  const [peers, setPeers] = useState({});
  const [latestMessages, setLatestMessages] = useState({});
  
  // FAB / Modals state
  const [showFabOptions, setShowFabOptions] = useState(false);
  const [showManualModal, setShowManualModal] = useState(false);
  const [manualIp, setManualIp] = useState('');
  const [manualPort, setManualPort] = useState('50001'); // Puerto por defecto
  
  // Camera & Start Modal state
  const [permission, requestPermission] = useCameraPermissions();
  const [showQrScanner, setShowQrScanner] = useState(false);
  const [showStartModal, setShowStartModal] = useState(true);
  
  const udpRef = useRef(null);
  const tcpServerRef = useRef(null);

  const refreshLatestMessages = useCallback(async () => {
    const latest = await MessageStorage.getLatestMessages();
    setLatestMessages(latest);
  }, []);

  useFocusEffect(
    useCallback(() => {
      refreshLatestMessages();
    }, [refreshLatestMessages])
  );

  useEffect(() => {
    // 1. Iniciar TCP Server primero para obtener el puerto
    const server = new TcpServer(0, async (payload) => {
      console.log("[ChatsScreen] Mensaje TCP recibido:", payload);
      
      if (payload.action === 'SHARE_TEXT' || payload.type === 'TEXT') {
        const senderId = payload.sender_id || 'pc_desktop_node';
        const text = payload.payload || payload.text;
        const msgId = payload.msg_uuid || Date.now().toString();
        const newMsg = {
          id: msgId,
          text: text,
          time: new Date().toLocaleTimeString().slice(0, 5),
          timestamp: Date.now(),
          isMe: false,
          status: 'read'
        };
        await MessageStorage.saveMessage(senderId, newMsg);
        refreshLatestMessages();
        DeviceEventEmitter.emit('onChatMessageReceived', { ...payload, senderId, message: newMsg });
      } else {
        DeviceEventEmitter.emit('onChatMessageReceived', payload);
      }
    });

    server.start((boundPort) => {
      setTcpPort(boundPort);
      
      if (nodeId && !identity?.is_stealth) {
        const udp = new UdpDiscovery(nodeId, nodeName, boundPort, (peer) => {
          setPeers(prev => {
            const newPeers = { ...prev };
            newPeers[peer.node_id] = peer;
            return newPeers;
          });
        });
        
        udp.start();
        udpRef.current = udp;
      }
    });
    
    tcpServerRef.current = server;

    // Limpiar nodos caídos cada 5 segundos
    const cleanupInterval = setInterval(() => {
      const now = Date.now();
      setPeers(prev => {
        const active = {};
        for (const [id, peer] of Object.entries(prev)) {
          // Aumentamos la tolerancia a 45 segundos para dispositivos Android que pierden paquetes UDP
          if (now - peer.last_seen < 45000) {
            active[id] = peer;
          }
        }
        return active;
      });
    }, 5000);

    return () => {
      if (udpRef.current) udpRef.current.stop();
      if (tcpServerRef.current) tcpServerRef.current.stop();
      clearInterval(cleanupInterval);
    };
  }, [nodeId, nodeName, identity?.is_stealth, refreshLatestMessages]);

  // Convert peers object to array and merge with historic chats from MessageStorage
  const activePeerIds = new Set(Object.keys(peers));
  
  const mergedNodeMap = {};
  
  // First, add all active peers
  Object.values(peers).forEach(peer => {
    const lastMsgObj = latestMessages[peer.node_id];
    mergedNodeMap[peer.node_id] = {
      id: peer.node_id,
      name: peer.hostname || peer.ip,
      lastMessage: lastMsgObj ? lastMsgObj.text : 'Disponible para chatear',
      date: lastMsgObj ? lastMsgObj.time : '',
      timestamp: lastMsgObj ? lastMsgObj.timestamp : Date.now(),
      isActive: true,
      unreadCount: 0,
      ip: peer.ip,
      tcp_port: peer.tcp_port,
      os: peer.os
    };
  });
  
  // Second, add historic nodes from MessageStorage that are currently inactive
  Object.keys(latestMessages).forEach(nodeId => {
    if (!mergedNodeMap[nodeId] && nodeId !== 'me') {
      const lastMsgObj = latestMessages[nodeId];
      mergedNodeMap[nodeId] = {
        id: nodeId,
        name: lastMsgObj.sender_name || nodeId,
        lastMessage: lastMsgObj ? lastMsgObj.text : '',
        date: lastMsgObj ? lastMsgObj.time : '',
        timestamp: lastMsgObj ? lastMsgObj.timestamp : 0,
        isActive: false,
        unreadCount: 0,
        ip: lastMsgObj.ip || '0.0.0.0',
        tcp_port: lastMsgObj.tcp_port || 50001,
        os: 'Desconocido'
      };
    }
  });

  const nodes = Object.values(mergedNodeMap).sort((a, b) => {
    if (a.isActive && !b.isActive) return -1;
    if (!a.isActive && b.isActive) return 1;
    return (b.timestamp || 0) - (a.timestamp || 0);
  });

  // Display array
  const displayNodes = nodes.length > 0 ? nodes : [
    { id: 'me', name: `${nodeName} (Tú)`, lastMessage: 'Esperando nodos en la red...', date: '', isActive: true, unreadCount: 0, isMe: true, os: 'Android' }
  ];

  const handleLongPress = (item) => {
    if (item.isMe) return;
    Alert.alert(
      "Opciones de Chat",
      `¿Qué deseas hacer con ${item.name}?`,
      [
        { text: "Cancelar", style: "cancel" },
        { text: "Vaciar mensajes", onPress: async () => {
            await MessageStorage.clearMessages(item.id);
            refreshLatestMessages();
          } 
        },
        { text: "Eliminar nodo", onPress: async () => {
            await MessageStorage.clearMessages(item.id);
            setPeers(prev => {
              const copy = { ...prev };
              delete copy[item.id];
              return copy;
            });
            refreshLatestMessages();
          }, 
          style: "destructive" 
        }
      ]
    );
  };

  const handleManualAdd = () => {
    if (manualIp.trim().length > 0 && manualPort.trim().length > 0) {
      const port = parseInt(manualPort, 10) || 50001;
      
      setPeers(prev => {
        const newPeers = { ...prev };
        newPeers[`manual-${manualIp}`] = {
          node_id: `manual-${manualIp}`,
          hostname: manualIp,
          ip: manualIp,
          tcp_port: port,
          last_seen: Date.now()
        };
        return newPeers;
      });

      setShowManualModal(false);
      setManualIp('');
      setShowFabOptions(false);
    } else {
      Alert.alert("Error", "Ingresa una IP y un puerto válidos.");
    }
  };

  const openQrScanner = async () => {
    setShowFabOptions(false);
    if (!permission?.granted) {
      const status = await requestPermission();
      if (!status.granted) {
        Alert.alert('Permiso denegado', 'Se requiere acceso a la cámara para escanear el QR.');
        return;
      }
    }
    setShowQrScanner(true);
  };

  const handleBarCodeScanned = ({ type, data }) => {
    setShowQrScanner(false);
    try {
      let peerIp, peerPort, peerNodeId, peerName;

      if (data.startsWith('sysnode://')) {
        const cleanData = data.replace('sysnode://', '');
        const parts = cleanData.split('?');
        const [ip, port] = parts[0].split(':');
        peerIp = ip;
        peerPort = parseInt(port, 10) || 50001;

        if (parts[1]) {
          const params = parts[1].split('&');
          params.forEach(p => {
            const [k, v] = p.split('=');
            if (k === 'node_id') peerNodeId = v;
            if (k === 'name') peerName = decodeURIComponent(v);
          });
        }
      } else {
        const payload = JSON.parse(data);
        peerIp = payload.ip;
        peerPort = payload.tcp_port || payload.port;
        peerNodeId = payload.node_id;
        peerName = payload.hostname || payload.name;
      }

      if (peerIp && peerPort) {
        const finalId = peerNodeId || `manual-${peerIp}`;
        const finalName = peerName || peerIp;

        setPeers(prev => {
          const newPeers = { ...prev };
          newPeers[finalId] = {
            node_id: finalId,
            hostname: finalName,
            ip: peerIp,
            tcp_port: peerPort,
            last_seen: Date.now()
          };
          return newPeers;
        });

        Alert.alert("Nodo Añadido", `Nodo ${finalName} (${peerIp}:${peerPort}) añadido correctamente.`);
      } else {
        Alert.alert("QR Inválido", "El código escaneado no es un nodo SysNode válido.");
      }
    } catch (e) {
      Alert.alert("QR Inválido", "No se pudo leer la información del código.");
    }
  };

  return (
    <View className="flex-1 bg-white dark:bg-[#0f1115]" style={{ paddingTop: insets.top }}>
      {/* Header con Buscador Sutil */}
      <View className="px-4 py-2 bg-white dark:bg-[#1e2128] border-b border-gray-200 dark:border-gray-800 flex-row items-center">
        <View className="flex-1 flex-row items-center bg-gray-100 dark:bg-[#0f1115] rounded-lg px-3 py-1.5">
          <Ionicons name="search" size={18} color="#9ca3af" />
          <TextInput 
            className="flex-1 ml-2 text-sm text-black dark:text-white"
            placeholder="Buscar dispositivos..."
            placeholderTextColor="#9ca3af"
          />
        </View>
      </View>

      <FlatList
        data={displayNodes}
        keyExtractor={item => item.id}
        renderItem={({ item }) => (
          <ChatListItem 
            item={item} 
            onPress={() => {
              if (!item.isMe) {
                navigation.navigate('ChatDetail', { node: item });
              }
            }} 
            onLongPress={() => handleLongPress(item)} 
          />
        )}
      />

      {/* Floating Action Button (FAB) */}
      <TouchableOpacity 
        activeOpacity={0.8}
        className="absolute bottom-6 right-6 w-12 h-12 bg-blue-600 rounded-md items-center justify-center shadow-lg"
        onPress={() => setShowFabOptions(true)}
      >
        <Ionicons name="add" size={28} color="white" />
      </TouchableOpacity>

      {/* Action Sheet (Opciones FAB) */}
      <Modal visible={showFabOptions} transparent animationType="slide">
        <TouchableOpacity className="flex-1 justify-end bg-black/40" activeOpacity={1} onPress={() => setShowFabOptions(false)}>
          <View className="bg-white dark:bg-[#1e2128] rounded-t-xl p-6 pb-10 border-t border-gray-200 dark:border-gray-800">
            <Text className="text-base font-bold text-black dark:text-white mb-4">Añadir Nuevo Nodo</Text>
            
            <TouchableOpacity className="flex-row items-center mb-5" onPress={openQrScanner}>
              <View className="w-10 h-10 bg-blue-100 dark:bg-blue-900/30 rounded-md items-center justify-center mr-3">
                <Ionicons name="qr-code-outline" size={22} color="#3b82f6" />
              </View>
              <Text className="text-sm font-medium text-black dark:text-white">Escanear Código QR</Text>
            </TouchableOpacity>

            <TouchableOpacity className="flex-row items-center" onPress={() => { setShowFabOptions(false); setShowManualModal(true); }}>
              <View className="w-10 h-10 bg-green-100 dark:bg-green-900/30 rounded-md items-center justify-center mr-3">
                <Ionicons name="wifi-outline" size={22} color="#22c55e" />
              </View>
              <Text className="text-sm font-medium text-black dark:text-white">Añadir IP y Puerto Manual</Text>
            </TouchableOpacity>
          </View>
        </TouchableOpacity>
      </Modal>

      {/* Modal Scanner QR */}
      <Modal visible={showQrScanner} animationType="slide" onRequestClose={() => setShowQrScanner(false)}>
        <View className="flex-1 bg-black">
          <View className="pt-12 z-20 absolute top-0 w-full flex-row items-center justify-center">
            <TouchableOpacity 
              onPress={() => setShowQrScanner(false)} 
              className="absolute left-4 top-12 bg-black/50 p-2 rounded-md z-30"
            >
              <Ionicons name="close" size={24} color="white" />
            </TouchableOpacity>
            <Text className="text-white font-bold text-sm bg-black/50 px-4 py-1.5 rounded-md mt-1">
              Escanea el código QR
            </Text>
          </View>
          
          {showQrScanner && (
            <CameraView 
              style={{ flex: 1 }}
              facing="back"
              onBarcodeScanned={handleBarCodeScanned}
            />
          )}
        </View>
      </Modal>

      {/* Modal Agregar IP Manual */}
      <Modal visible={showManualModal} transparent animationType="fade">
        <View className="flex-1 bg-black/50 justify-center items-center px-6">
          <View className="bg-white dark:bg-[#1e2128] w-full rounded-md p-6 border border-gray-200 dark:border-gray-800">
            <Text className="text-lg font-bold text-black dark:text-white mb-1">Añadir Manualmente</Text>
            <Text className="text-xs text-gray-500 dark:text-gray-400 mb-4">Ingresa la IP local y puerto del dispositivo SysNode.</Text>
            
            <View className="flex-row space-x-2">
              <TextInput
                className="flex-1 bg-gray-100 dark:bg-[#0f1115] text-black dark:text-white rounded-md px-3 py-2 mb-4 text-sm"
                placeholder="Ej: 192.168.0.25"
                placeholderTextColor="#6b7280"
                value={manualIp}
                onChangeText={setManualIp}
                keyboardType="numeric"
              />
              <TextInput
                className="w-20 bg-gray-100 dark:bg-[#0f1115] text-black dark:text-white rounded-md px-3 py-2 mb-4 text-sm text-center"
                placeholder="Puerto"
                placeholderTextColor="#6b7280"
                value={manualPort}
                onChangeText={setManualPort}
                keyboardType="numeric"
              />
            </View>
            
            <View className="flex-row justify-end space-x-2">
              <TouchableOpacity className="px-4 py-2 rounded-md bg-gray-200 dark:bg-gray-800 mr-2" onPress={() => setShowManualModal(false)}>
                <Text className="text-xs text-gray-700 dark:text-gray-300 font-semibold">Cancelar</Text>
              </TouchableOpacity>
              <TouchableOpacity className="px-4 py-2 rounded-md bg-blue-600" onPress={handleManualAdd}>
                <Text className="text-xs text-white font-bold">Conectar</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>

      {/* Modal: Confirmación de Inicio (SysNode) */}
      <Modal visible={showStartModal} transparent animationType="fade">
        <View className="flex-1 bg-black/70 justify-center items-center px-6">
          <View className="w-full bg-white dark:bg-[#1e2128] rounded-md p-6 border border-gray-200 dark:border-gray-800">
            <View className="items-center mb-4">
              <Text className="text-xl font-bold text-black dark:text-white">SysNode</Text>
            </View>

            <Text className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-1">Nombre</Text>
            <TextInput
              className="bg-gray-100 dark:bg-[#0f1115] text-black dark:text-white p-2.5 rounded-md mb-4 text-sm border border-gray-200 dark:border-gray-800"
              value={identity?.node_name || ''}
              onChangeText={(text) => updateIdentity({ node_name: text })}
              placeholder="Tu nombre en la red"
              placeholderTextColor="#9ca3af"
            />

            <Text className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-2">Modo de Visibilidad</Text>
            <View className="flex-row justify-between mb-6">
              <TouchableOpacity
                onPress={() => updateIdentity({ is_stealth: false })}
                className={`flex-1 p-3 rounded-md border mr-2 items-center ${
                  !identity?.is_stealth 
                    ? 'bg-blue-500/10 border-blue-500' 
                    : 'bg-gray-100 dark:bg-[#0f1115] border-gray-200 dark:border-gray-800'
                }`}
              >
                <Text className={`font-bold text-sm ${!identity?.is_stealth ? 'text-blue-600 dark:text-blue-400' : 'text-gray-400'}`}>Público</Text>
                <Text className="text-[10px] text-gray-400 text-center mt-1">Visible por UDP Broadcast</Text>
              </TouchableOpacity>

              <TouchableOpacity
                onPress={() => updateIdentity({ is_stealth: true })}
                className={`flex-1 p-3 rounded-md border ml-2 items-center ${
                  identity?.is_stealth 
                    ? 'bg-purple-500/10 border-purple-500' 
                    : 'bg-gray-100 dark:bg-[#0f1115] border-gray-200 dark:border-gray-800'
                }`}
              >
                <Text className={`font-bold text-sm ${identity?.is_stealth ? 'text-purple-600 dark:text-purple-300' : 'text-gray-400'}`}>Oculto</Text>
                <Text className="text-[10px] text-gray-400 text-center mt-1">Conexión directa por TCP / QR</Text>
              </TouchableOpacity>
            </View>

            <TouchableOpacity
              onPress={() => setShowStartModal(false)}
              className="py-3 bg-blue-600 rounded-md items-center"
            >
              <Text className="text-white font-bold text-sm">Entrar</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>
    </View>
  );
}
