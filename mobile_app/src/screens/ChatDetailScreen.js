import React, { useState, useRef, useEffect, useCallback } from 'react';
import { View, Text, Image, TouchableOpacity, KeyboardAvoidingView, Platform, Alert, TextInput, FlatList, Modal, DeviceEventEmitter, BackHandler } from 'react-native';
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
  const [selectedMsgForOptions, setSelectedMsgForOptions] = useState(null);
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

  const [isPaired, setIsPaired] = useState(false);
  const [trustToken, setTrustToken] = useState("");
  const [hasLoadedPairing, setHasLoadedPairing] = useState(false);
  const [isPairingRequested, setIsPairingRequested] = useState(false);

  const checkPairingState = useCallback(async () => {
    const targetNodeId = node.id || 'pc_desktop_node';
    const paired = await MessageStorage.isDevicePaired(targetNodeId);
    const token = await MessageStorage.getDeviceTrustToken(targetNodeId);
    setIsPaired(paired);
    setTrustToken(token || "");
    setHasLoadedPairing(true);
    if (paired) {
      setIsPairingRequested(false);
    }
  }, [node.id]);

  useEffect(() => {
    checkPairingState();
  }, [checkPairingState]);

  // Android Back Gesture Handler
  useEffect(() => {
    const backAction = () => {
      navigation.goBack();
      return true;
    };
    const backHandler = BackHandler.addEventListener('hardwareBackPress', backAction);
    return () => backHandler.remove();
  }, [navigation]);

  const userHasScrolledRef = useRef(false);
  const PAGE_SIZE = 30;
  const [hasMoreHistory, setHasMoreHistory] = useState(false);
  const [loadedOffset, setLoadedOffset] = useState(0);
  const isLoadingMoreRef = useRef(false);

  // Se elimina scrollToBottom por uso de FlatList invertido

  useEffect(() => {
    userHasScrolledRef.current = false;
    isLoadingMoreRef.current = false;
    const targetNodeId = node.id || 'pc_desktop_node';

    // 1. Cargar únicamente los últimos 30 mensajes para evitar saturación
    MessageStorage.getMessagesPaged(targetNodeId, PAGE_SIZE, 0).then(res => {
      setMessages(res.messages);
      setHasMoreHistory(res.hasMore);
      setLoadedOffset(res.loadedOffset);
    });

    // 2. Escuchar mensajes entrantes (Texto, Archivos/Imágenes y Ediciones)
    const subMsg = DeviceEventEmitter.addListener('onChatMessageReceived', (payload) => {
      if (payload.action === 'EDIT_MSG' || payload.type === 'MSG_EDITED') {
        const msgUuid = payload.msg_uuid;
        const newText = payload.new_text || payload.payload;
        if (msgUuid && newText) {
          setMessages(prev => prev.map(m => m.id === msgUuid ? { ...m, text: newText, isEdited: true } : m));
          MessageStorage.updateMessageText(targetNodeId, msgUuid, newText);
        }
        return;
      }

      if (payload.action === 'SHARE_TEXT' || payload.type === 'TEXT' || payload.type === 'FILE' || payload.uri || payload.imageUri || payload.fileUri) {
        const incomingSenderId = payload.senderId || payload.sender_id || targetNodeId;
        const text = payload.payload || payload.text || '';
        const msgId = payload.msg_uuid || payload.id || Date.now().toString();
        
        const uri = payload.uri || payload.imageUri || payload.fileUri;
        const isImage = uri ? ['jpg', 'jpeg', 'png', 'webp', 'gif', 'bmp'].some(ext => uri.toLowerCase().endsWith('.' + ext)) : false;

        const newMsg = payload.message || {
          id: msgId,
          text: text,
          imageUri: isImage ? uri : (payload.imageUri || null),
          fileUri: (!isImage && uri) ? uri : (payload.fileUri || null),
          time: new Date().toLocaleTimeString().slice(0, 5),
          timestamp: Date.now(),
          isMe: false,
          status: 'read'
        };

        MessageStorage.saveMessage(incomingSenderId, newMsg);

        if (incomingSenderId === targetNodeId || targetNodeId === 'pc_desktop_node') {
          setMessages(prev => {
            if (prev.some(m => m.id === newMsg.id)) return prev;
            return [newMsg, ...prev]; // Invertido: nuevo va al inicio
          });
        }
      }
    });

    const subEdit = DeviceEventEmitter.addListener('MSG_EDITED', (evt) => {
      setMessages(prev => prev.map(m => m.id === evt.msg_uuid ? { ...m, text: evt.new_text, isEdited: true } : m));
      MessageStorage.updateMessageText(targetNodeId, evt.msg_uuid, evt.new_text);
    });

    const subPairingResp = DeviceEventEmitter.addListener('onPairingResponse', () => {
      checkPairingState();
    });

    const subUnpair = DeviceEventEmitter.addListener('onUnpairRequest', () => {
      checkPairingState();
    });

    return () => {
      subMsg.remove();
      subEdit.remove();
      subPairingResp.remove();
      subUnpair.remove();
    };
  }, [node.id]);

  const loadMoreHistory = useCallback(() => {
    if (!hasMoreHistory || isLoadingMoreRef.current) return;
    isLoadingMoreRef.current = true;
    const targetNodeId = node.id || 'pc_desktop_node';

    MessageStorage.getMessagesPaged(targetNodeId, PAGE_SIZE, loadedOffset).then(res => {
      if (res.messages && res.messages.length > 0) {
        setMessages(prev => [...prev, ...res.messages]); // Los viejos van al final
        setHasMoreHistory(res.hasMore);
        setLoadedOffset(res.loadedOffset);
      } else {
        setHasMoreHistory(false);
      }
      isLoadingMoreRef.current = false;
    }).catch(() => {
      isLoadingMoreRef.current = false;
    });
  }, [hasMoreHistory, loadedOffset, node.id]);

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
      MessageStorage.updateMessageText(targetNodeId, targetMsgId, updatedText);

      if (!clientRef.current) {
        clientRef.current = new TcpClient(node.ip, node.tcp_port, trustToken);
      } else {
        clientRef.current.trustToken = trustToken;
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
    
    setMessages(prev => [newMsg, ...prev]); // Invertido: nuevo va al inicio
    MessageStorage.saveMessage(targetNodeId, newMsg);
    
    const textToSend = messageText;
    setMessageText('');

    if (!clientRef.current) {
      clientRef.current = new TcpClient(node.ip, node.tcp_port, trustToken);
    } else {
      clientRef.current.trustToken = trustToken;
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

    setMessages(prev => [newMsg, ...prev]); // Invertido
    MessageStorage.saveMessage(targetNodeId, newMsg);

    if (!clientRef.current) {
      clientRef.current = new TcpClient(node.ip, node.tcp_port, trustToken);
    } else {
      clientRef.current.trustToken = trustToken;
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
    setSelectedMsgForOptions(msg);
  };

  const handleOptionsPress = () => {
    setShowOptionsMenu(true);
  };

  const handleTakePhoto = async () => {
    setShowAttachMenu(false);
    setTimeout(async () => {
      try {
        const { status } = await ImagePicker.requestCameraPermissionsAsync();
        if (status !== 'granted') {
          Alert.alert('Permiso Denegado', 'Necesitamos acceso a la cámara para tomar fotos.');
          return;
        }
        const result = await ImagePicker.launchCameraAsync({
          mediaTypes: ImagePicker.MediaTypeOptions.Images,
          quality: 0.7,
        });
        if (!result.canceled && result.assets && result.assets.length > 0) {
          const asset = result.assets[0];
          const filename = asset.fileName || `foto_${Date.now()}.jpg`;
          sendFileMessage(asset.uri, filename, "Cámara");
        }
      } catch (err) {
        console.error('Error al tomar foto:', err);
        Alert.alert('Error Cámara', 'No se pudo abrir la cámara: ' + (err.message || ''));
      }
    }, 150);
  };

  const handlePickGallery = async () => {
    setShowAttachMenu(false);
    setTimeout(async () => {
      try {
        const result = await ImagePicker.launchImageLibraryAsync({
          mediaTypes: ImagePicker.MediaTypeOptions.All,
          quality: 0.7,
        });
        if (!result.canceled && result.assets && result.assets.length > 0) {
          const asset = result.assets[0];
          const isVideo = asset.type === 'video';
          const ext = isVideo ? 'mp4' : 'jpg';
          const filename = asset.fileName || `media_${Date.now()}.${ext}`;
          sendFileMessage(asset.uri, filename, "Galería");
        }
      } catch (err) {
        console.error('Error al seleccionar de galería:', err);
      }
    }, 150);
  };

  const handlePickDocument = async () => {
    setShowAttachMenu(false);
    setTimeout(async () => {
      try {
        const result = await DocumentPicker.getDocumentAsync({});
        if (!result.canceled && result.assets && result.assets.length > 0) {
          const asset = result.assets[0];
          const filename = asset.name || `doc_${Date.now()}`;
          sendFileMessage(asset.uri, filename, "Documento");
        }
      } catch (err) {
        console.error('Error al seleccionar documento:', err);
      }
    }, 150);
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

    setMessages(prev => [reqMsg, ...prev]);
    MessageStorage.saveMessage(targetNodeId, reqMsg);

    if (!clientRef.current) {
      clientRef.current = new TcpClient(node.ip, node.tcp_port, trustToken);
    } else {
      clientRef.current.trustToken = trustToken;
    }

    clientRef.current.connect(
      () => {
        clientRef.current.sendMessageWithResponse({
          action: "REMOTE_BASH_CMD",
          sender_id: identity?.node_id || "mobile-id",
          sender_name: identity?.node_name || "Celular",
          bash_command: cmd.command,
          is_background: cmd.isBackground || false
        }).then((res) => {
          setMessages(prev => prev.map(m => m.id === reqMsgId ? {...m, status: 'sent'} : m));
          MessageStorage.updateMessageStatus(targetNodeId, reqMsgId, 'sent');

          const resResult = res?.result || res?.msg || "Comando ejecutado exitosamente en PC.";
          const statusIcon = res?.status === 'OK' ? '[ÉXITO]' : '[ERROR]';
          
          const resMsg = {
            id: (Date.now() + 1).toString(),
            text: `${statusIcon} Resultado del Remoto\n------------------------------\n${resResult}`,
            time: new Date().toLocaleTimeString().slice(0, 5),
            timestamp: Date.now(),
            isMe: false,
            status: 'read'
          };
          setMessages(prev => [resMsg, ...prev]);
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

        {/* Área Principal (Chat o Vinculación) */}
        {!hasLoadedPairing ? (
          <View className="flex-1 justify-center items-center bg-gray-50 dark:bg-[#0b0c10]">
            <Text className="text-gray-500 dark:text-gray-400">Cargando estado...</Text>
          </View>
        ) : !isPaired ? (
          <View className="flex-1 justify-center items-center bg-gray-50 dark:bg-[#0b0c10] px-6">
            <View className="bg-white dark:bg-[#1e2128] p-6 rounded-2xl w-full max-w-sm items-center shadow-sm">
              <View className="w-16 h-16 bg-blue-100 dark:bg-blue-900/30 rounded-full items-center justify-center mb-4">
                <Ionicons name="lock-closed" size={32} color="#3b82f6" />
              </View>
              <Text className="text-lg font-bold text-black dark:text-white mb-2 text-center">Dispositivo No Vinculado</Text>
              <Text className="text-sm text-gray-500 dark:text-gray-400 text-center mb-6">
                {isPairingRequested 
                  ? "Esperando a que el otro dispositivo acepte la solicitud de vinculación..." 
                  : "Por seguridad, debes vincular este dispositivo antes de poder chatear o enviar comandos."}
              </Text>
              
              <TouchableOpacity 
                className={`w-full py-3 rounded-xl flex-row justify-center items-center ${isPairingRequested ? 'bg-gray-400 dark:bg-gray-600' : 'bg-blue-600 active:bg-blue-700'}`}
                disabled={isPairingRequested}
                onPress={async () => {
                  setIsPairingRequested(true);
                  try {
                    await TcpClient.sendPairingRequest(
                      node.ip, 
                      node.tcp_port, 
                      identity?.node_id || "mobile-id", 
                      identity?.node_name || "Celular",
                      global.myTcpPort || 50001,
                      ""
                    );
                    // The wait is handled by listening to DeviceEventEmitter
                  } catch (e) {
                    console.log("Error solicitando vinculación:", e);
                    Alert.alert("Error", "No se pudo enviar la solicitud de vinculación.");
                    setIsPairingRequested(false);
                  }
                }}
              >
                {isPairingRequested ? (
                  <Text className="text-white font-bold">Esperando...</Text>
                ) : (
                  <>
                    <Ionicons name="link" size={18} color="white" className="mr-2" />
                    <Text className="text-white font-bold ml-2">Vincular Dispositivo</Text>
                  </>
                )}
              </TouchableOpacity>
            </View>
          </View>
        ) : (
          <>
            {/* Área de Mensajes */}
            <FlatList 
              ref={flatListRef}
              data={messages}
              inverted={true}
              keyExtractor={item => item.id}
              className="flex-1 bg-gray-50 dark:bg-[#0b0c10]"
              contentContainerStyle={{ paddingTop: 12, paddingBottom: 12 }}
              onEndReached={loadMoreHistory}
              onEndReachedThreshold={0.5}
              ListFooterComponent={hasMoreHistory ? (
                <View className="py-4">
                  <Text className="text-xs text-blue-500 font-semibold text-center">
                    Cargando...
                  </Text>
                </View>
              ) : null}
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
          </>
        )}
      </KeyboardAvoidingView>

      {/* Modal Opciones de Mensaje (Reemplazo de Alert.alert para evitar límite de Android) */}
      <Modal visible={!!selectedMsgForOptions} transparent animationType="fade">
        <TouchableOpacity 
          className="flex-1 bg-black/40 justify-center items-center" 
          activeOpacity={1} 
          onPress={() => setSelectedMsgForOptions(null)}
        >
          <View className="bg-white dark:bg-[#1e2128] rounded-xl w-4/5 overflow-hidden">
            <View className="p-4 border-b border-gray-100 dark:border-gray-800">
              <Text className="text-center font-bold text-gray-800 dark:text-gray-200" numberOfLines={1}>
                {selectedMsgForOptions?.text ? selectedMsgForOptions.text : "Mensaje adjunto"}
              </Text>
            </View>
            
            {selectedMsgForOptions?.text && (
              <TouchableOpacity 
                className="py-4 border-b border-gray-100 dark:border-gray-800 flex-row items-center justify-center"
                onPress={async () => {
                  await Clipboard.setStringAsync(selectedMsgForOptions.text);
                  Alert.alert("Copiado", "Texto copiado al portapapeles.");
                  setSelectedMsgForOptions(null);
                }}
              >
                <Ionicons name="copy-outline" size={20} color="#3b82f6" />
                <Text className="ml-3 font-semibold text-blue-500">Copiar Texto</Text>
              </TouchableOpacity>
            )}

            {selectedMsgForOptions?.isMe && 
             (!selectedMsgForOptions.timestamp || Date.now() - selectedMsgForOptions.timestamp <= 30 * 60 * 1000) && 
             !selectedMsgForOptions.imageUri && 
             !selectedMsgForOptions.fileUri && (
              <TouchableOpacity 
                className="py-4 border-b border-gray-100 dark:border-gray-800 flex-row items-center justify-center"
                onPress={() => {
                  setEditingMsgId(selectedMsgForOptions.id);
                  setMessageText(selectedMsgForOptions.text);
                  setSelectedMsgForOptions(null);
                }}
              >
                <Ionicons name="pencil-outline" size={20} color="#3b82f6" />
                <Text className="ml-3 font-semibold text-blue-500">Editar Mensaje</Text>
              </TouchableOpacity>
            )}

            <TouchableOpacity 
              className="py-4 border-b border-gray-100 dark:border-gray-800 flex-row items-center justify-center"
              onPress={async () => {
                const targetNodeId = node.id || 'pc_desktop_node';
                const msgId = selectedMsgForOptions.id;
                setMessages(prev => prev.filter(m => m.id !== msgId));
                await MessageStorage.deleteMessage(targetNodeId, msgId);
                setSelectedMsgForOptions(null);
              }}
            >
              <Ionicons name="trash-outline" size={20} color="#ef4444" />
              <Text className="ml-3 font-semibold text-red-500">Eliminar Mensaje</Text>
            </TouchableOpacity>

            <TouchableOpacity 
              className="py-4 bg-gray-50 dark:bg-[#1a1d24] flex-row items-center justify-center"
              onPress={() => setSelectedMsgForOptions(null)}
            >
              <Text className="font-semibold text-gray-500 dark:text-gray-400">Cancelar</Text>
            </TouchableOpacity>
          </View>
        </TouchableOpacity>
      </Modal>

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
              className="py-3 border-b border-gray-100 dark:border-gray-800 flex-row items-center px-2"
              onPress={() => {
                setShowOptionsMenu(false);
                Alert.alert(
                  "Desvincular",
                  "¿Seguro que quieres desvincular este dispositivo?",
                  [
                    { text: "Cancelar", style: "cancel" },
                    { text: "Desvincular", style: "destructive", onPress: async () => {
                        const targetNodeId = node.id || 'pc_desktop_node';
                        
                        await MessageStorage.setDevicePaired(targetNodeId, false, null);
                        checkPairingState();
                        setIsPairingRequested(false);
                        
                        try {
                          await TcpClient.sendUnpairRequest(
                            node.ip, 
                            node.tcp_port, 
                            identity?.node_id || "mobile-id", 
                            identity?.node_name || "Celular",
                            global.myTcpPort || 50001
                          );
                        } catch (e) {
                          console.log("Error al enviar UNPAIR_REQ al remoto:", e);
                        }
                    }}
                  ]
                );
              }}
            >
              <Ionicons name="link-outline" size={18} color="#ef4444" className="mr-3" />
              <Text className="text-sm text-red-500 font-medium ml-2">Desvincular dispositivo</Text>
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
                navigation.navigate('MainTabs', { screen: 'Settings' });
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
