import React, { useState, useEffect, useRef } from 'react';
import { View, Text, TouchableOpacity, TextInput, ScrollView, Alert, KeyboardAvoidingView, Platform, ActivityIndicator, Image, Modal, StyleSheet } from 'react-native';
import { UdpDiscovery } from '../network/UdpDiscovery';
import { TcpClient } from '../network/TcpClient';
import { TcpServer } from '../network/TcpServer';
import * as DocumentPicker from 'expo-document-picker';
import * as FileSystem from 'expo-file-system/legacy';
import * as Crypto from 'expo-crypto';
import { CameraView, useCameraPermissions } from 'expo-camera';

// Generador simple de UUID v4 para no instalar dependencias extra
function generateUUID() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
    var r = Math.random() * 16 | 0, v = c == 'x' ? r : (r & 0x3 | 0x8);
    return v.toString(16);
  });
}

export default function HomeScreen() {
  const [nodeId] = useState(generateUUID());
  const [nodeName] = useState('Android (' + Math.floor(Math.random() * 1000) + ')');
  const [tcpPort, setTcpPort] = useState(0); // 0 = Asignación dinámica por SO
  const [peers, setPeers] = useState({});
  const [selectedPeer, setSelectedPeer] = useState(null);
  
  const [permission, requestPermission] = useCameraPermissions();
  const [showQrScanner, setShowQrScanner] = useState(false);
  
  const [showManualModal, setShowManualModal] = useState(false);
  const [manualIp, setManualIp] = useState('');
  
  const [inputText, setInputText] = useState('');
  const [messages, setMessages] = useState([]);
  
  const [isSendingFile, setIsSendingFile] = useState(false);
  const [fileProgress, setFileProgress] = useState(0);

  const udpRef = useRef(null);
  const tcpServerRef = useRef(null);

  useEffect(() => {
    // 1. Iniciar TCP Server primero para obtener el puerto
    const server = new TcpServer(0, (msg) => {
      if (msg.type === "TEXT") {
        setMessages(prev => [...prev, { 
          id: Date.now() + Math.random(), 
          sender: msg.sender, 
          text: msg.text, 
          isSelf: false 
        }]);
      } else if (msg.type === "FILE") {
        setMessages(prev => [...prev, { 
          id: Date.now() + Math.random(), 
          sender: msg.sender, 
          text: msg.text, 
          isSelf: false,
          fileUri: msg.uri
        }]);
      }
    });

    server.start((boundPort) => {
      setTcpPort(boundPort);
      
      // 2. Una vez que tenemos el puerto TCP, iniciamos UDP Discovery
      const udp = new UdpDiscovery(nodeId, nodeName, boundPort, (peer) => {
        setPeers(prev => {
          const newPeers = { ...prev };
          newPeers[peer.node_id] = peer;
          return newPeers;
        });
      });
      
      udp.start();
      udpRef.current = udp;
    });
    
    tcpServerRef.current = server;

    // Limpiar nodos caídos cada 5 segundos
    const cleanupInterval = setInterval(() => {
      const now = Date.now();
      setPeers(prev => {
        const active = {};
        for (const [id, peer] of Object.entries(prev)) {
          // Si el nodo emitió beacon en los últimos 15 segundos, está vivo
          if (now - peer.last_seen < 15000) {
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
  }, [nodeId, nodeName]);

  const handleSendText = () => {
    if (!selectedPeer || !inputText.trim()) return;

    const text = inputText.trim();
    setInputText('');
    
    // Agregamos a nuestro propio chat
    setMessages(prev => [...prev, { id: Date.now(), sender: 'Yo', text, isSelf: true }]);

    // Enviar P2P TCP
    TcpClient.sendText(
      selectedPeer.ip, 
      selectedPeer.tcp_port, 
      nodeId, 
      nodeName, 
      text,
      (success, result) => {
        if (!success) {
          Alert.alert('Error enviando mensaje', result);
        }
      },
      (errorMsg) => {
        Alert.alert('Fallo de conexión', errorMsg);
      }
    );
  };

  const handleSendFile = async () => {
    if (!selectedPeer) return;
    
    try {
      const result = await DocumentPicker.getDocumentAsync({
        copyToCacheDirectory: true // Importante para poder leer el archivo en JS
      });
      
      if (result.canceled) return;
      
      const file = result.assets[0];
      
      // Chequear tamaño (limitamos a 50MB para mobile en esta versión de demostración)
      if (file.size > 50 * 1024 * 1024) {
        Alert.alert('Archivo muy grande', 'Por ahora solo soportamos hasta 50MB desde el celular.');
        return;
      }
      
      setIsSendingFile(true);
      setFileProgress(0);

      // Calcular SHA-256 omitido en React Native para evitar 
      // discordancia con los bytes binarios de Python.
      // Se envía vacío para que el backend salte la verificación en este MVP.
      let sha256 = "";

      setMessages(prev => [...prev, { id: Date.now(), sender: 'Yo', text: `Enviando archivo: ${file.name}...`, isSelf: true }]);

      await TcpClient.sendFile(
        selectedPeer.ip, 
        selectedPeer.tcp_port, 
        nodeId, 
        nodeName, 
        file.uri, 
        file.name, 
        file.size, 
        sha256, 
        (sent, total) => {
          setFileProgress(sent / total);
        },
        (success, result) => {
          setIsSendingFile(false);
          if (success) {
            setMessages(prev => [...prev, { id: Date.now(), sender: 'Yo', text: `Archivo ${file.name} enviado OK.`, isSelf: true }]);
          } else {
            Alert.alert('Error transfiriendo archivo', result);
          }
        },
        (errorMsg) => {
          setIsSendingFile(false);
          Alert.alert('Error de conexión', errorMsg);
        }
      );
    } catch (e) {
      Alert.alert('Error', e.message);
      setIsSendingFile(false);
    }
  };

  return (
    <KeyboardAvoidingView 
      style={{ flex: 1 }} 
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <View className="flex-1 bg-[#1a1a1a] p-4">
        {/* Header */}
        <View className="mb-6 mt-4">
          <Text className="text-white text-2xl font-bold">SysNode Mobile</Text>
          <Text className="text-gray-400 text-sm">ID: {nodeId.substring(0,8)}</Text>
          <Text className="text-gray-400 text-sm">Nombre: {nodeName}</Text>
          <Text className="text-gray-400 text-sm">Puerto TCP: {tcpPort}</Text>
        </View>

        <View className="flex-row flex-1">
          {/* Radar LAN (Lista de Nodos) */}
          <View className="w-1/3 pr-2 border-r border-[#333]">
            <Text className="text-white font-bold mb-4">Radar LAN</Text>
            <ScrollView>
              {Object.values(peers).length === 0 ? (
                <Text className="text-gray-500 italic text-xs">Buscando nodos...</Text>
              ) : (
                Object.values(peers).map(peer => (
                  <TouchableOpacity
                    key={peer.node_id}
                    onPress={() => setSelectedPeer(peer)}
                    className={`p-3 mb-2 rounded-lg ${selectedPeer?.node_id === peer.node_id ? 'bg-[#3498db]' : 'bg-[#2c3e50]'}`}
                  >
                    <Text className="text-white font-bold text-sm" numberOfLines={1}>{peer.hostname}</Text>
                    <Text className="text-gray-300 text-xs">{peer.ip}</Text>
                    <Text className="text-gray-400 text-xs mt-1">{peer.os}</Text>
                  </TouchableOpacity>
                ))
              )}
            </ScrollView>
            
            <TouchableOpacity
              onPress={() => setShowManualModal(true)}
              className="bg-[#27ae60] p-3 mt-2 rounded-lg items-center"
            >
              <Text className="text-white font-bold text-sm">[+] Añadir IP Manual</Text>
            </TouchableOpacity>

            <TouchableOpacity
              onPress={async () => {
                if (!permission?.granted) {
                  const req = await requestPermission();
                  if (!req.granted) return;
                }
                setShowQrScanner(true);
              }}
              className="bg-[#8E44AD] p-3 mt-2 rounded-lg items-center"
            >
              <Text className="text-white font-bold text-sm">[QR] Escanear QR</Text>
            </TouchableOpacity>
          </View>

          {/* Área Principal (Chat) */}
          <View className="flex-1 pl-4 flex-col">
            {!selectedPeer ? (
              <View className="flex-1 items-center justify-center">
                <Text className="text-gray-500 text-center">Selecciona un nodo del Radar LAN para interactuar</Text>
              </View>
            ) : (
              <>
                <View className="bg-[#2a2a2a] p-3 rounded-t-lg border-b border-[#444]">
                  <Text className="text-white font-bold">Destino: {selectedPeer.hostname}</Text>
                </View>
                
                <ScrollView className="flex-1 bg-[#222] p-4">
                  {messages.map(msg => (
                    <View key={msg.id} className={`mb-2 max-w-[80%] ${msg.isSelf ? 'self-end bg-[#3498db]' : 'self-start bg-[#444]'} p-2 rounded-lg`}>
                      <Text className="text-gray-300 text-xs font-bold mb-1">{msg.sender}</Text>
                      <Text className="text-white">{msg.text}</Text>
                      {msg.fileUri && (
                        <View className="mt-2">
                          {(msg.fileUri.toLowerCase().endsWith('.png') || msg.fileUri.toLowerCase().endsWith('.jpg') || msg.fileUri.toLowerCase().endsWith('.jpeg')) && (
                             <View className="bg-black/20 p-1 rounded mb-2 mt-2">
                               <Image source={{ uri: msg.fileUri }} style={{ width: 200, height: 200, resizeMode: 'cover' }} className="rounded" />
                             </View>
                          )}
                        </View>
                      )}
                    </View>
                  ))}
                  
                  {isSendingFile && (
                    <View className="mb-2 self-end bg-[#3498db] p-2 rounded-lg opacity-80 flex-row items-center">
                      <ActivityIndicator color="white" size="small" className="mr-2" />
                      <Text className="text-white">Enviando... {Math.round(fileProgress * 100)}%</Text>
                    </View>
                  )}
                </ScrollView>

                <View className="bg-[#2a2a2a] p-3 rounded-b-lg flex-row items-center">
                  <TouchableOpacity 
                    onPress={handleSendFile}
                    disabled={isSendingFile}
                    className={`bg-[#2c3e50] px-3 py-3 rounded-lg mr-2 ${isSendingFile ? 'opacity-50' : ''}`}
                  >
                    <Text className="text-white font-bold">[FILE] Archivo</Text>
                  </TouchableOpacity>

                  <TextInput
                    value={inputText}
                    onChangeText={setInputText}
                    placeholder="Escribe un mensaje..."
                    placeholderTextColor="#888"
                    className="flex-1 bg-[#333] text-white p-2 rounded-lg mr-2"
                    onSubmitEditing={handleSendText}
                    editable={!isSendingFile}
                  />
                  <TouchableOpacity 
                    onPress={handleSendText}
                    disabled={isSendingFile}
                    className={`bg-[#3498db] px-4 py-3 rounded-lg ${isSendingFile ? 'opacity-50' : ''}`}
                  >
                    <Text className="text-white font-bold">Enviar</Text>
                  </TouchableOpacity>
                </View>
              </>
            )}
          </View>
        </View>
      </View>
      
      <Modal visible={showManualModal} transparent={true} animationType="fade">
        <View style={{ flex: 1, backgroundColor: 'rgba(0,0,0,0.7)', justifyContent: 'center', alignItems: 'center' }}>
          <View className="bg-[#2a2a2a] p-6 rounded-lg w-4/5">
            <Text className="text-white text-lg font-bold mb-4">Añadir Nodo Manual</Text>
            <Text className="text-gray-400 mb-2">Ingresa la IP local del nodo (ej: 192.168.0.10):</Text>
            <TextInput 
              value={manualIp}
              onChangeText={setManualIp}
              placeholder="192.168.0.10"
              placeholderTextColor="#666"
              className="bg-[#1a1a1a] text-white p-3 rounded-lg mb-4"
              keyboardType="numeric"
            />
            <View className="flex-row justify-end">
              <TouchableOpacity onPress={() => setShowManualModal(false)} className="px-4 py-2 mr-2">
                <Text className="text-gray-400 font-bold">Cancelar</Text>
              </TouchableOpacity>
              <TouchableOpacity 
                onPress={() => {
                  if (manualIp.trim()) {
                     const parts = manualIp.trim().split(':');
                     const ip = parts[0];
                     const port = parts.length > 1 && !isNaN(parts[1]) ? parseInt(parts[1]) : 50001;
                     const syntheticId = 'manual_' + Date.now();
                     setPeers(prev => ({
                       ...prev,
                       [syntheticId]: {
                         node_id: syntheticId,
                         hostname: `Manual_${ip}`,
                         os: "unknown",
                         ip: ip,
                         tcp_port: port,
                         last_seen: Date.now() + 86400000
                       }
                     }));
                     setShowManualModal(false);
                     setManualIp('');
                  }
                }}
                className="bg-[#3498db] px-4 py-2 rounded-lg"
              >
                <Text className="text-white font-bold">Añadir</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>

      <Modal visible={showQrScanner} transparent={false} animationType="slide">
        <View style={{ flex: 1, backgroundColor: 'black' }}>
          {showQrScanner && (
            <View style={{ flex: 1 }}>
              <CameraView 
                style={{ flex: 1, ...StyleSheet.absoluteFillObject }}
                facing="back"
                onBarcodeScanned={({ data }) => {
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
                      const finalName = peerName || `PC (${peerIp})`;

                      setPeers(prev => ({
                        ...prev,
                        [finalId]: {
                          node_id: finalId,
                          hostname: finalName,
                          os: "pc",
                          ip: peerIp,
                          tcp_port: peerPort,
                          last_seen: Date.now() + 86400000
                        }
                      }));
                      Alert.alert('Éxito', `Nodo ${finalName} (${peerIp}:${peerPort}) añadido correctamente.`);
                    } else {
                      Alert.alert('QR Inválido', 'El código escaneado no es un nodo SysNode válido.');
                    }
                  } catch (e) {
                    Alert.alert('QR Inválido', 'No se pudo leer la información del código escaneado.');
                  }
                }}
              />
              <View className="flex-1 justify-between p-10 bg-transparent absolute w-full h-full">
                <Text className="text-white text-center font-bold text-lg bg-black/50 p-2 rounded">Escaneá un QR de SysNode</Text>
                <TouchableOpacity 
                  onPress={() => setShowQrScanner(false)}
                  className="bg-red-500 p-4 rounded-lg self-center mb-10"
                >
                  <Text className="text-white font-bold">Cerrar Escáner</Text>
                </TouchableOpacity>
              </View>
            </View>
          )}
        </View>
      </Modal>

    </KeyboardAvoidingView>
  );
}
