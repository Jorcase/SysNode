import React, { useState, useRef, useEffect } from 'react';
import { View, Text, TouchableOpacity, KeyboardAvoidingView, Platform, Alert, TextInput, FlatList, Modal, DeviceEventEmitter } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useNavigation, useRoute } from '@react-navigation/native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import ChatBubble from '../components/ChatBubble';
import * as DocumentPicker from 'expo-document-picker';
import * as ImagePicker from 'expo-image-picker';
import * as Clipboard from 'expo-clipboard';
import { TcpClient } from '../network/TcpClient';
import { useMyIdentity } from '../network/MyIdentity';
import { MessageStorage } from '../network/MessageStorage';
import { CommandStorage } from '../network/CommandStorage';

import React, { useState, useRef, useEffect, useCallback } from 'react';
import { View, Text, TouchableOpacity, KeyboardAvoidingView, Platform, Alert, TextInput, FlatList, Modal, DeviceEventEmitter, BackHandler } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useNavigation, useRoute } from '@react-navigation/native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import ChatBubble from '../components/ChatBubble';
import * as DocumentPicker from 'expo-document-picker';
import * as ImagePicker from 'expo-image-picker';
import * as Clipboard from 'expo-clipboard';
import { TcpClient } from '../network/TcpClient';
import { useMyIdentity } from '../network/MyIdentity';
import { MessageStorage } from '../network/MessageStorage';
import { CommandStorage } from '../network/CommandStorage';

export default function ChatDetailScreen() {
  const navigation = useNavigation();
  const route = useRoute();
  const insets = useSafeAreaInsets();
  
  const node = route.params?.node || { name: 'Desconocido', isActive: false, ip: '0.0.0.0' };
  
  // Modals & Input state
  const [showAttachMenu, setShowAttachMenu] = useState(false);
  const [showCommandsModal, setShowCommandsModal] = useState(false);
  const [showDeviceInfoModal, setShowDeviceInfoModal] = useState(false);
  const [showOptionsMenu, setShowOptionsMenu] = useState(false);
  const [showMediaViewerModal, setShowMediaViewerModal] = useState(false);
  const [selectedMediaUri, setSelectedMediaUri] = useState(null);
  
  // Message edit state
  const [editingMsgId, setEditingMsgId] = useState(null);

  const [availableCmds, setAvailableCmds] = useState([]);
  const [messageText, setMessageText] = useState('');
  const [messages, setMessages] = useState([]);
  const clientRef = useRef(null);
  const flatListRef = useRef(null);
  const { identity } = useMyIdentity();

  // Android Back Gesture Handler
  useEffect(() => {
    const backAction = () => {
      navigation.goBack();
      return true;
    };
    const backHandler = BackHandler.addEventListener('hardwareBackPress', backAction);
    return () => backHandler.remove();
  }, [navigation]);

  const scrollToBottom = useCallback(() => {
    setTimeout(() => {
      if (flatListRef.current) {
        flatListRef.current.scrollToEnd({ animated: true });
      }
    }, 100);
  }, []);

  useEffect(() => {
    const targetNodeId = node.id || 'pc_desktop_node';

    // 1. Cargar historial guardado
    MessageStorage.getMessages(targetNodeId).then(history => {
      setMessages(history);
      scrollToBottom();
    });

    // 2. Escuchar mensajes entrantes y eventos de edición
    const subMsg = DeviceEventEmitter.addListener('onChatMessageReceived', (payload) => {
      if (payload.action === 'SHARE_TEXT' || payload.type === 'TEXT') {
        const incomingSenderId = payload.senderId || payload.sender_id || targetNodeId;
        const text = payload.payload || payload.text;
        const msgId = payload.msg_uuid || Date.now().toString();
        
        const newMsg = payload.message || {
          id: msgId,
          text: text,
          time: new Date().toLocaleTimeString().slice(0, 5),
          timestamp: Date.now(),
          isMe: false,
          status: 'read'
        };

        MessageStorage.saveMessage(incomingSenderId, newMsg);

        if (incomingSenderId === targetNodeId || targetNodeId === 'pc_desktop_node') {
          setMessages(prev => {
            if (prev.some(m => m.id === newMsg.id)) return prev;
            return [...prev, newMsg];
          });
          scrollToBottom();
        }
      }
    });

    const subEdit = DeviceEventEmitter.addListener('MSG_EDITED', (evt) => {
      setMessages(prev => prev.map(m => m.id === evt.msg_uuid ? { ...m, text: evt.new_text, isEdited: true } : m));
    });

    return () => {
      subMsg.remove();
      subEdit.remove();
    };
  }, [node.id, scrollToBottom]);

  const handleSend = () => {
    if (!messageText.trim()) return;
    const targetNodeId = node.id || 'pc_desktop_node';

    // Si estamos editando un mensaje existente
    if (editingMsgId) {
      const updatedText = messageText;
      const targetMsgId = editingMsgId;
      setEditingMsgId(null);
      setMessageText('');

      setMessages(prev => prev.map(m => m.id === targetMsgId ? { ...m, text: updatedText, isEdited: true } : m));

      if (!clientRef.current) {
        clientRef.current = new TcpClient(node.ip, node.tcp_port);
      }

      clientRef.current.connect(
        () => {
          clientRef.current.sendMessage({
            action: "EDIT_MSG",
            sender_id: identity?.node_id || "mobile-id",
            msg_uuid: targetMsgId,
            new_text: updatedText
          }).catch(err => console.error("Error al enviar edición:", err));
        },
        (err) => console.error("Error al conectar para edición:", err)
      );
      return;
    }

    const msgId = Date.now().toString();
    const newMsg = {
      id: msgId,
      text: messageText,
      time: new Date().toLocaleTimeString().slice(0, 5),
      timestamp: Date.now(),
      isMe: true,
      status: 'sending'
    };
    
    setMessages(prev => [...prev, newMsg]);
    MessageStorage.saveMessage(targetNodeId, newMsg);
    scrollToBottom();
    
    const textToSend = messageText;
    setMessageText('');

    if (!clientRef.current) {
      clientRef.current = new TcpClient(node.ip, node.tcp_port);
    }

    clientRef.current.connect(
      () => {
        clientRef.current.sendMessage({
          action: "SHARE_TEXT",
          sender_id: identity?.node_id || "mobile-fallback-id",
          sender_name: identity?.node_name || "Desconocido",
          payload: textToSend,
          msg_uuid: msgId
        }).then(() => {
          setMessages(prev => prev.map(m => m.id === msgId ? {...m, status: 'sent'} : m));
          MessageStorage.updateMessageStatus(targetNodeId, msgId, 'sent');
        }).catch(err => {
          console.error("Error enviando:", err);
          setMessages(prev => prev.map(m => m.id === msgId ? {...m, status: 'error'} : m));
          MessageStorage.updateMessageStatus(targetNodeId, msgId, 'error');
        });
      },
      (err) => {
        console.error("Error conectando:", err);
        setMessages(prev => prev.map(m => m.id === msgId ? {...m, status: 'error'} : m));
        MessageStorage.updateMessageStatus(targetNodeId, msgId, 'error');
      }
    );
  };

  const sendFileMessage = async (fileUri, filename, typeName) => {
    const targetNodeId = node.id || 'pc_desktop_node';
    const msgId = Date.now().toString();

    const ext = filename.split('.').pop().toLowerCase();
    const isImage = ['jpg', 'jpeg', 'png', 'webp', 'gif', 'bmp'].includes(ext);

    const newMsg = {
      id: msgId,
      text: isImage ? `📸 Foto enviada (${filename})` : `📄 Archivo enviado (${filename})`,
      imageUri: isImage ? fileUri : null,
      fileUri: !isImage ? fileUri : null,
      time: new Date().toLocaleTimeString().slice(0, 5),
      timestamp: Date.now(),
      isMe: true,
      status: 'sending'
    };

    setMessages(prev => [...prev, newMsg]);
    MessageStorage.saveMessage(targetNodeId, newMsg);
    scrollToBottom();

    if (!clientRef.current) {
      clientRef.current = new TcpClient(node.ip, node.tcp_port);
    }

    try {
      await clientRef.current.sendFile(fileUri, filename, identity?.node_id || "mobile-id", identity?.node_name || "Celular");
      setMessages(prev => prev.map(m => m.id === msgId ? {...m, status: 'sent'} : m));
      MessageStorage.updateMessageStatus(targetNodeId, msgId, 'sent');
    } catch (e) {
      console.error("Error enviando archivo:", e);
      setMessages(prev => prev.map(m => m.id === msgId ? {...m, status: 'error'} : m));
      MessageStorage.updateMessageStatus(targetNodeId, msgId, 'error');
    }
  };

  const handleMessageLongPress = (msg) => {
    const targetNodeId = node.id || 'pc_desktop_node';
    const isWithin15Min = msg.timestamp && (Date.now() - msg.timestamp <= 15 * 60 * 1000);

    const options = [
      { text: "Cancelar", style: "cancel" },
      { 
        text: "Copiar Texto", 
        onPress: async () => {
          await Clipboard.setStringAsync(msg.text);
          Alert.alert("Copiado", "Texto copiado al portapapeles.");
        } 
      }
    ];

    if (msg.isMe && isWithin15Min && !msg.imageUri && !msg.fileUri) {
      options.push({
        text: "Editar Mensaje",
        onPress: () => {
          setEditingMsgId(msg.id);
          setMessageText(msg.text);
        }
      });
    }

    if (isWithin15Min) {
      options.push({
        text: "Eliminar Mensaje",
        style: "destructive",
        onPress: async () => {
          setMessages(prev => {
            const updated = prev.filter(m => m.id !== msg.id);
            MessageStorage.clearMessages(targetNodeId).then(() => {
              updated.forEach(m => MessageStorage.saveMessage(targetNodeId, m));
            });
            return updated;
          });
        }
      });
    } else {
      options.push({
        text: "El plazo de 15 min para editar/borrar ha expirado",
        style: "cancel"
      });
    }

    Alert.alert(
      "Opciones de Mensaje",
      msg.text ? (msg.text.length > 40 ? msg.text.substring(0, 40) + "..." : msg.text) : "Mensaje adjunto",
      options
    );
  };

  const handleOptionsPress = () => {
    setShowOptionsMenu(true);
  };

  const handleTakePhoto = async () => {
    setShowAttachMenu(false);
    const { status } = await ImagePicker.requestCameraPermissionsAsync();
    if (status !== 'granted') {
      Alert.alert('Permiso Denegado', 'Necesitamos acceso a la cámara para tomar fotos.');
      return;
    }
    const result = await ImagePicker.launchCameraAsync({ quality: 0.7 });
    if (!result.canceled && result.assets && result.assets.length > 0) {
      const asset = result.assets[0];
      const filename = asset.fileName || `foto_${Date.now()}.jpg`;
      sendFileMessage(asset.uri, filename, "Cámara");
    }
  };

  const handlePickGallery = async () => {
    setShowAttachMenu(false);
    const result = await ImagePicker.launchImageLibraryAsync({ quality: 0.7 });
    if (!result.canceled && result.assets && result.assets.length > 0) {
      const asset = result.assets[0];
      const filename = asset.fileName || `imagen_${Date.now()}.jpg`;
      sendFileMessage(asset.uri, filename, "Galería");
    }
  };

  const handlePickDocument = async () => {
    setShowAttachMenu(false);
    const result = await DocumentPicker.getDocumentAsync({});
    if (!result.canceled && result.assets && result.assets.length > 0) {
      const asset = result.assets[0];
      const filename = asset.name || `doc_${Date.now()}`;
      sendFileMessage(asset.uri, filename, "Documento");
    }
  };

  const handleOpenCommands = async () => {
    setShowAttachMenu(false);
    const cmds = await CommandStorage.getCommands();
    setAvailableCmds(cmds);
    setShowCommandsModal(true);
  };

  const handleExecuteCommand = (cmd) => {
    setShowCommandsModal(false);
    const targetNodeId = node.id || 'pc_desktop_node';

    const reqMsgId = Date.now().toString();
    const reqMsg = {
      id: reqMsgId,
      text: `[SysAdmin] Comando enviado: ${cmd.name} ($ ${cmd.command})`,
      time: new Date().toLocaleTimeString().slice(0, 5),
      timestamp: Date.now(),
      isMe: true,
      status: 'sending'
    };

    setMessages(prev => [...prev, reqMsg]);
    MessageStorage.saveMessage(targetNodeId, reqMsg);

    if (!clientRef.current) {
      clientRef.current = new TcpClient(node.ip, node.tcp_port);
    }

    clientRef.current.connect(
      () => {
        clientRef.current.sendMessageWithResponse({
          action: "REMOTE_BASH_CMD",
          sender_id: identity?.node_id || "mobile-id",
          sender_name: identity?.node_name || "Celular",
          bash_command: cmd.command
        }).then((res) => {
          setMessages(prev => prev.map(m => m.id === reqMsgId ? {...m, status: 'sent'} : m));
          MessageStorage.updateMessageStatus(targetNodeId, reqMsgId, 'sent');

          // Mensaje con resultado devuelto por la PC
          const resResult = res?.result || res?.msg || "Comando ejecutado exitosamente en PC.";
          const resMsg = {
            id: (Date.now() + 1).toString(),
            text: `[SysAdmin - Resultado de ${node.name}]:\n${resResult}`,
            time: new Date().toLocaleTimeString().slice(0, 5),
            timestamp: Date.now(),
            isMe: false,
            status: 'read'
          };
          setMessages(prev => [...prev, resMsg]);
          MessageStorage.saveMessage(targetNodeId, resMsg);
        }).catch(err => {
          console.error("Error ejecutando comando:", err);
          setMessages(prev => prev.map(m => m.id === reqMsgId ? {...m, status: 'error'} : m));
          MessageStorage.updateMessageStatus(targetNodeId, reqMsgId, 'error');
        });
      },
      (err) => {
        console.error("Error de conexión:", err);
        setMessages(prev => prev.map(m => m.id === reqMsgId ? {...m, status: 'error'} : m));
        MessageStorage.updateMessageStatus(targetNodeId, reqMsgId, 'error');
      }
    );
  };

  return (
    <View className="flex-1 bg-white dark:bg-[#0f1115]" style={{ paddingTop: insets.top, paddingBottom: insets.bottom }}>
      <KeyboardAvoidingView 
        style={{ flex: 1 }} 
        behavior={Platform.OS === "ios" ? "padding" : "padding"}
      >
        {/* Custom Header */}
        <View className="flex-row items-center px-4 py-2 border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-[#1e2128]">
          <TouchableOpacity onPress={() => navigation.goBack()} className="mr-3 p-1">
            <Ionicons name="arrow-back" size={22} color="#3b82f6" />
          </TouchableOpacity>

          <TouchableOpacity 
            className="flex-1 flex-row items-center" 
            activeOpacity={0.7}
            onPress={() => setShowDeviceInfoModal(true)}
          >
            <View className="relative">
              <View className="w-9 h-9 rounded-md bg-blue-100 dark:bg-blue-900/30 items-center justify-center">
                <Ionicons 
                  name={
                    node.os?.toLowerCase().includes('android') || node.os?.toLowerCase().includes('ios') 
                      ? 'phone-portrait-outline' 
                      : 'desktop-outline'
                  } 
                  size={18} 
                  color="#3b82f6" 
                />
              </View>
              <View className={`absolute bottom-0 right-0 w-2.5 h-2.5 rounded-full border border-white dark:border-[#1e2128] ${node.isActive ? 'bg-green-500' : 'bg-gray-400'}`} />
            </View>

            <View className="ml-2.5 flex-1 justify-center">
              <Text className="text-sm font-bold text-black dark:text-white" numberOfLines={1}>
                {node.name}
              </Text>
              <Text className="text-[11px] text-gray-500 dark:text-gray-400">
                {node.isActive ? 'En línea' : 'Desconectado'}
              </Text>
            </View>
          </TouchableOpacity>

          {/* Botón de Terminal SSH Remota */}
          <TouchableOpacity 
            onPress={() => navigation.navigate('Terminal', { node })} 
            className="ml-2 p-1.5 bg-blue-500/10 rounded-md flex-row items-center"
          >
            <Ionicons name="terminal-outline" size={18} color="#3b82f6" />
          </TouchableOpacity>

          {/* Botón de 3 Puntos */}
          <TouchableOpacity onPress={handleOptionsPress} className="ml-2 p-1.5">
            <Ionicons name="ellipsis-vertical" size={18} color="#6b7280" />
          </TouchableOpacity>
        </View>

        {/* Banner de modo edición */}
        {editingMsgId && (
          <View className="bg-blue-50 dark:bg-blue-950/40 px-4 py-2 flex-row justify-between items-center border-b border-blue-200 dark:border-blue-800">
            <Text className="text-xs text-blue-600 dark:text-blue-300 font-medium">Editando mensaje...</Text>
            <TouchableOpacity onPress={() => { setEditingMsgId(null); setMessageText(''); }}>
              <Ionicons name="close" size={16} color="#3b82f6" />
            </TouchableOpacity>
          </View>
        )}

        {/* Área de Mensajes */}
        <FlatList 
          ref={flatListRef}
          data={messages}
          keyExtractor={item => item.id}
          className="flex-1 bg-gray-50 dark:bg-[#0b0c10]"
          contentContainerStyle={{ paddingTop: 12, paddingBottom: 12 }}
          onContentSizeChange={() => scrollToBottom()}
          renderItem={({ item }) => (
            <ChatBubble 
              message={item} 
              onLongPress={handleMessageLongPress} 
              onOpenMedia={(uri) => {
                setSelectedMediaUri(uri);
                setShowMediaViewerModal(true);
              }}
            />
          )}
        />

        {/* Cajón de Input */}
        <View className="p-2 border-t border-gray-200 dark:border-gray-800 bg-white dark:bg-[#1e2128] flex-row items-center">
          <TouchableOpacity className="p-2" onPress={() => setShowAttachMenu(true)}>
            <Ionicons name="add" size={24} color="#3b82f6" />
          </TouchableOpacity>
          
          <TextInput 
            className="flex-1 bg-gray-100 dark:bg-[#2a2d36] text-black dark:text-white rounded-md mx-2 px-3 py-1.5 max-h-28 min-h-[36px] text-sm"
            placeholder="Escribí un mensaje..."
            placeholderTextColor="#9ca3af"
            multiline
            value={messageText}
            onChangeText={setMessageText}
          />
          
          <TouchableOpacity 
            className={`w-9 h-9 rounded-md items-center justify-center ${messageText.trim().length > 0 ? 'bg-blue-600' : 'bg-gray-300 dark:bg-gray-700'}`}
            onPress={handleSend}
          >
            <Ionicons name="send" size={16} color="white" style={{ marginLeft: 2 }} />
          </TouchableOpacity>
        </View>
      </KeyboardAvoidingView>

      {/* Menú de Adjuntos (Botón +) */}
      <Modal visible={showAttachMenu} transparent animationType="fade">
        <TouchableOpacity 
          className="flex-1 justify-end bg-black/40" 
          activeOpacity={1} 
          onPress={() => setShowAttachMenu(false)}
        >
          <View className="bg-white dark:bg-[#1e2128] rounded-t-xl p-6 pb-8 border-t border-gray-200 dark:border-gray-800">
            <Text className="text-base font-bold text-black dark:text-white mb-4">Adjuntar al chat</Text>
            
            <View className="flex-row justify-between mb-2">
              <TouchableOpacity className="items-center w-1/4" onPress={handleTakePhoto}>
                <View className="w-12 h-12 bg-pink-100 dark:bg-pink-900/30 rounded-md items-center justify-center mb-1.5">
                  <Ionicons name="camera" size={24} color="#ec4899" />
                </View>
                <Text className="text-xs text-black dark:text-white text-center">Cámara</Text>
              </TouchableOpacity>

              <TouchableOpacity className="items-center w-1/4" onPress={handlePickGallery}>
                <View className="w-12 h-12 bg-purple-100 dark:bg-purple-900/30 rounded-md items-center justify-center mb-1.5">
                  <Ionicons name="images" size={24} color="#a855f7" />
                </View>
                <Text className="text-xs text-black dark:text-white text-center">Galería</Text>
              </TouchableOpacity>

              <TouchableOpacity className="items-center w-1/4" onPress={handlePickDocument}>
                <View className="w-12 h-12 bg-orange-100 dark:bg-orange-900/30 rounded-md items-center justify-center mb-1.5">
                  <Ionicons name="document" size={24} color="#f97316" />
                </View>
                <Text className="text-xs text-black dark:text-white text-center">Documento</Text>
              </TouchableOpacity>

              <TouchableOpacity className="items-center w-1/4" onPress={handleOpenCommands}>
                <View className="w-12 h-12 bg-blue-100 dark:bg-blue-900/30 rounded-md items-center justify-center mb-1.5">
                  <Ionicons name="terminal" size={24} color="#3b82f6" />
                </View>
                <Text className="text-xs text-black dark:text-white text-center">Comando</Text>
              </TouchableOpacity>
            </View>
          </View>
        </TouchableOpacity>
      </Modal>

      {/* Modal 3 Puntos: Opciones de Chat */}
      <Modal visible={showOptionsMenu} transparent animationType="fade">
        <TouchableOpacity 
          className="flex-1 bg-black/40 justify-end" 
          activeOpacity={1} 
          onPress={() => setShowOptionsMenu(false)}
        >
          <View className="bg-white dark:bg-[#1e2128] rounded-t-xl p-4 border-t border-gray-200 dark:border-gray-800">
            <TouchableOpacity 
              className="py-3 border-b border-gray-100 dark:border-gray-800 flex-row items-center px-2"
              onPress={() => {
                setShowOptionsMenu(false);
                Alert.alert("Seleccionar Mensajes", "Función activada.");
              }}
            >
              <Ionicons name="checkbox-outline" size={18} color="#3b82f6" className="mr-3" />
              <Text className="text-sm text-black dark:text-white font-medium ml-2">Seleccionar mensajes</Text>
            </TouchableOpacity>

            <TouchableOpacity 
              className="py-3 border-b border-gray-100 dark:border-gray-800 flex-row items-center px-2"
              onPress={() => {
                setShowOptionsMenu(false);
                Alert.alert("Buscar", "Buscador en conversación activado.");
              }}
            >
              <Ionicons name="search-outline" size={18} color="#3b82f6" className="mr-3" />
              <Text className="text-sm text-black dark:text-white font-medium ml-2">Buscar en la conversación</Text>
            </TouchableOpacity>

            <TouchableOpacity 
              className="py-3 border-b border-gray-100 dark:border-gray-800 flex-row items-center px-2"
              onPress={() => {
                setShowOptionsMenu(false);
                setShowDeviceInfoModal(true);
              }}
            >
              <Ionicons name="person-outline" size={18} color="#3b82f6" className="mr-3" />
              <Text className="text-sm text-black dark:text-white font-medium ml-2">Ver perfil</Text>
            </TouchableOpacity>

            <TouchableOpacity 
              className="py-3 flex-row items-center px-2"
              onPress={async () => {
                setShowOptionsMenu(false);
                const targetNodeId = node.id || 'pc_desktop_node';
                await MessageStorage.clearMessages(targetNodeId);
                setMessages([]);
              }}
            >
              <Ionicons name="trash-outline" size={18} color="#ef4444" className="mr-3" />
              <Text className="text-sm text-red-500 font-medium ml-2">Vaciar chat</Text>
            </TouchableOpacity>
          </View>
        </TouchableOpacity>
      </Modal>

      {/* Modal: Visor de Imagen a Pantalla Completa */}
      <Modal visible={showMediaViewerModal} transparent animationType="fade">
        <View className="flex-1 bg-black justify-center items-center">
          <TouchableOpacity 
            onPress={() => setShowMediaViewerModal(false)}
            className="absolute top-12 right-6 z-30 p-2 bg-black/60 rounded-md"
          >
            <Ionicons name="close" size={24} color="white" />
          </TouchableOpacity>
          {selectedMediaUri && (
            <Image 
              source={{ uri: selectedMediaUri }}
              style={{ width: '100%', height: '80%' }}
              resizeMode="contain"
            />
          )}
        </View>
      </Modal>

      {/* Modal: Seleccionar Comando para Ejecutar */}
      <Modal visible={showCommandsModal} transparent animationType="slide">
        <View className="flex-1 justify-end bg-black/50">
          <View className="bg-white dark:bg-[#1e2128] rounded-t-xl p-6 max-h-[70%] border-t border-gray-200 dark:border-gray-800">
            <View className="flex-row justify-between items-center mb-4 border-b border-gray-200 dark:border-gray-800 pb-3">
              <Text className="text-base font-bold text-black dark:text-white">Ejecutar Comando en {node.name}</Text>
              <TouchableOpacity onPress={() => setShowCommandsModal(false)}>
                <Ionicons name="close" size={22} color="#9ca3af" />
              </TouchableOpacity>
            </View>

            <FlatList
              data={availableCmds}
              keyExtractor={item => item.id}
              renderItem={({ item }) => (
                <TouchableOpacity
                  className="p-3 mb-2 bg-gray-100 dark:bg-[#0f1115] rounded-md border border-gray-200 dark:border-gray-800 flex-row items-center justify-between"
                  onPress={() => handleExecuteCommand(item)}
                >
                  <View className="flex-1 pr-3">
                    <Text className="text-sm font-bold text-black dark:text-white">{item.name}</Text>
                    <Text className="text-xs font-mono text-gray-500 dark:text-gray-400 mt-0.5">$ {item.command}</Text>
                  </View>
                  <Ionicons name="play-circle" size={24} color="#3b82f6" />
                </TouchableOpacity>
              )}
            />
          </View>
        </View>
      </Modal>

      {/* Modal: Información del Dispositivo Remoto */}
      <Modal visible={showDeviceInfoModal} transparent animationType="fade">
        <View className="flex-1 bg-black/60 justify-center items-center px-6">
          <View className="w-full bg-white dark:bg-[#1e2128] rounded-md p-6 border border-gray-200 dark:border-gray-800">
            <View className="flex-row items-center mb-4">
              <View className="w-10 h-10 rounded-md bg-blue-100 dark:bg-blue-900/30 items-center justify-center mr-3">
                <Ionicons 
                  name={node.os?.toLowerCase().includes('android') || node.os?.toLowerCase().includes('ios') ? 'phone-portrait-outline' : 'desktop-outline'} 
                  size={22} 
                  color="#3b82f6" 
                />
              </View>
              <View className="flex-1">
                <Text className="text-base font-bold text-black dark:text-white" numberOfLines={1}>{node.name}</Text>
                <Text className="text-xs text-gray-500">{node.isActive ? 'Activo' : 'Inactivo'}</Text>
              </View>
            </View>

            <View className="bg-gray-50 dark:bg-[#0f1115] rounded-md p-3 mb-4">
              <Text className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-2">Detalles Técnicos</Text>
              <Text className="text-xs text-gray-600 dark:text-gray-300 mb-1">IP Local: <Text className="font-bold">{node.ip || '192.168.0.x'}</Text></Text>
              <Text className="text-xs text-gray-600 dark:text-gray-300 mb-1">Puerto TCP: <Text className="font-bold">{node.tcp_port || 50001}</Text></Text>
              <Text className="text-xs text-gray-600 dark:text-gray-300 mb-1">Sistema Operativo: <Text className="font-bold">{node.os || 'Linux/Windows'}</Text></Text>
              <Text className="text-xs text-gray-600 dark:text-gray-300" numberOfLines={1}>ID del Nodo: <Text className="font-mono">{node.id}</Text></Text>
            </View>

            <TouchableOpacity 
              onPress={() => {
                setShowDeviceInfoModal(false);
                navigation.navigate('Settings');
              }}
              className="py-2.5 bg-blue-600 rounded-md items-center mb-2"
            >
              <Text className="text-xs text-white font-bold">Archivos compartidos</Text>
            </TouchableOpacity>

            <TouchableOpacity 
              onPress={() => setShowDeviceInfoModal(false)}
              className="py-2.5 bg-gray-200 dark:bg-gray-800 rounded-md items-center"
            >
              <Text className="text-xs text-gray-700 dark:text-gray-300 font-semibold">Cerrar</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>
    </View>
  );
}
