import React, { useState, useEffect, useRef } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  ScrollView,
  Alert,
  Modal,
  KeyboardAvoidingView,
  Platform
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { TcpClient } from '../network/TcpClient';

export default function TerminalScreen({ route, navigation }) {
  const { node } = route.params || {};
  const insets = useSafeAreaInsets();

  const [sessionId, setSessionId] = useState(null);
  const [pinModalVisible, setPinModalVisible] = useState(false);
  const [pinInput, setPinInput] = useState('');
  const [terminalOutput, setTerminalOutput] = useState("");
  const cursorRef = useRef(0);
  const [commandInput, setCommandInput] = useState('');
  const [connected, setConnected] = useState(false);

  const tcpClientRef = useRef(null);
  const scrollViewRef = useRef(null);

  useEffect(() => {
    if (node && node.ip && node.tcp_port) {
      initTerminalSession();
    }

    return () => {
      if (tcpClientRef.current) {
        if (sessionId) {
          tcpClientRef.current.sendMessage({
            action: 'TERM_CLOSE',
            session_id: sessionId
          }).catch(() => {});
        }
        tcpClientRef.current.disconnect();
      }
    };
  }, []);

  // Función para inicializar la sesión terminal e iniciar el flujo de PIN
  const initTerminalSession = async () => {
    try {
      appendOutput(`[SYSNODE] Conectando a Terminal Remota en ${node.hostname || node.ip} (${node.ip}:${node.tcp_port})...\n`);

      const { MessageStorage } = require('../network/MessageStorage');
      const trustToken = await MessageStorage.getDeviceTrustToken(node.id || 'pc_desktop_node');

      const client = new TcpClient(node.ip, node.tcp_port, trustToken || "");
      tcpClientRef.current = client;

      client.connect(
        async () => {
          appendOutput(`[SYSNODE] Solicitando sesión PTY...\n`);
          try {
            const { getIdentity } = require('../network/MyIdentity');
            const myId = getIdentity();

            const response = await client.sendMessageWithResponse({
              action: 'TERM_INIT',
              sender_id: myId.node_id,
              sender_name: myId.node_name,
              cols: 80,
              rows: 24
            });

            if (response && response.status === 'OK') {
              setSessionId(response.session_id);
              setConnected(true);
              setTerminalOutput("");
              cursorRef.current = 0;
              listenToStdout();
            } else {
              appendOutput(`[ERROR] El nodo remoto rechazó la sesión terminal: ${response?.msg || 'Error desconocido'}\n`);
            }
          } catch (e) {
            appendOutput(`[ERROR] Fallo al negociar la sesión terminal: ${e.message}\n`);
          }
        },
        (err) => {
          appendOutput(`[ERROR] Error de conexión TCP: ${err.message}\n`);
        },
        () => {
          setConnected(false);
          appendOutput(`\n[SYSNODE] Conexión terminal cerrada.\n`);
        }
      );
    } catch (e) {
      appendOutput(`[ERROR] Excepción: ${e.message}\n`);
    }
  };

  // Hilo receptor de datos STDOUT devueltos por la shell PTY
  const listenToStdout = () => {
    if (!tcpClientRef.current || !tcpClientRef.current.client) return;

    const { parseFramedMessage } = require('../network/Protocol');
    const { Buffer } = require('buffer');
    let buffer = Buffer.alloc(0);

    tcpClientRef.current.client.on('data', (data) => {
      buffer = Buffer.concat([buffer, data]);
      let parsed;
      while ((parsed = parseFramedMessage(buffer)) !== null) {
        if (parsed.error) break;
        buffer = parsed.remainingBuffer;
        
        const payload = parsed.message;
        if (payload.action === 'TERM_STDOUT' && payload.data) {
          appendOutput(payload.data);
        } else if (payload.action === 'TERM_CLOSE') {
          appendOutput(`\n[SYSNODE] La sesión PTY fue terminada por el servidor.\n`);
          setConnected(false);
        }
      }
    });
  };

  const appendOutput = (text) => {
    // Sanitizar códigos ANSI pero mantener \x1b[K para limpiar la línea
    let cleanText = text
      .replace(/\x1b\[K/g, '\x0E').replace(/\x1b\[0K/g, '\x0E')
      .replace(/\x1b\[2K/g, '\x0F')
      .replace(/\x1b\[[0-9;?]*[a-zA-Z]/g, '')     // CSI
      .replace(/\x1b\][\s\S]*?(?:\x07|\x1b\\)/g, '') // OSC
      .replace(/\x1b[=>]/g, '')                   // Modos
      .replace(/\x1b[()][A-B0-2]/g, '');          // Designadores

    setTerminalOutput(prev => {
      let chars = prev.split('');
      let c = cursorRef.current;
      if (c > chars.length) c = chars.length;

      for (let i = 0; i < cleanText.length; i++) {
        const char = cleanText[i];
        if (char === '\x0E') {
          let end = c;
          while (end < chars.length && chars[end] !== '\n') end++;
          chars.splice(c, end - c);
        } else if (char === '\x0F') {
          let start = c;
          while (start > 0 && chars[start - 1] !== '\n') start--;
          let end = c;
          while (end < chars.length && chars[end] !== '\n') end++;
          chars.splice(start, end - start);
          c = start;
        } else if (char === '\r') {
          while (c > 0 && chars[c - 1] !== '\n') c--;
        } else if (char === '\b' || char === '\x08' || char === '\x7f') {
          if (c > 0 && chars[c - 1] !== '\n') {
            c--;
            chars.splice(c, 1);
          }
        } else if (char === '\n') {
          while (c < chars.length && chars[c] !== '\n') c++;
          chars.splice(c, 0, '\n');
          c++;
        } else {
          if (c < chars.length && chars[c] !== '\n') {
            chars[c] = char;
            c++;
          } else {
            chars.splice(c, 0, char);
            c++;
          }
        }
      }

      if (chars.length > 15000) {
        let trim = chars.length - 15000;
        chars = chars.slice(trim);
        c = Math.max(0, c - trim);
      }
      
      cursorRef.current = c;
      return chars.join('');
    });

    setTimeout(() => {
      if (scrollViewRef.current) {
        scrollViewRef.current.scrollToEnd({ animated: true });
      }
    }, 50);
  };

  // Enviar comando o teclas desde la barra de entrada del celular
  const sendStdinData = (dataStr) => {
    if (!connected || !tcpClientRef.current || !sessionId) {
      Alert.alert('Sin Conexión', 'No hay una sesión de terminal activa autenticada.');
      return;
    }

    tcpClientRef.current.sendMessage({
      action: 'TERM_STDIN',
      session_id: sessionId,
      data: dataStr
    }).catch(err => {
      appendOutput(`[ERROR] Error al transmitir a la terminal: ${err.message}\n`);
    });
  };

  const handleSubmitCommand = () => {
    if (commandInput) {
      sendStdinData(commandInput + '\n');
      setCommandInput('');
    } else {
      sendStdinData('\n');
    }
  };

  return (
    <View style={{ flex: 1, backgroundColor: '#0f1115' }}>
      {/* Header */}
      <View 
        style={{ paddingTop: insets.top + 10 }}
        className="px-4 pb-3 bg-[#1e2128] border-b border-gray-800 flex-row items-center justify-between"
      >
        <View className="flex-row items-center">
          <TouchableOpacity onPress={() => navigation.goBack()} className="mr-3 p-1">
            <Ionicons name="arrow-back" size={24} color="white" />
          </TouchableOpacity>
          <View>
            <Text className="text-white font-bold text-base">Terminal SSH Remota</Text>
            <Text className="text-gray-400 text-xs">{node?.hostname || node?.ip} ({node?.ip})</Text>
          </View>
        </View>
        <View className="flex-row items-center">
          <View className={`w-3 h-3 rounded-full mr-2 ${connected ? 'bg-green-500' : 'bg-red-500'}`} />
          <Text className="text-xs text-gray-300">{connected ? 'Online' : 'Offline'}</Text>
        </View>
      </View>

      {/* Consola de Texto Terminal */}
      <KeyboardAvoidingView 
        style={{ flex: 1 }} 
        behavior={Platform.OS === 'ios' ? 'padding' : 'padding'}
      >
        <ScrollView 
          ref={scrollViewRef} 
          className="flex-1 p-4 bg-black"
          contentContainerStyle={{ paddingBottom: 20 }}
        >
          <Text className="font-mono text-green-400 text-sm leading-5">
            {terminalOutput}
          </Text>
        </ScrollView>

        {/* Toolbar con teclas rápidas SSH */}
        <View className="bg-[#1e2128] px-2 py-1 flex-row justify-around border-t border-gray-800">
          <TouchableOpacity onPress={() => sendStdinData('\t')} className="bg-gray-800 px-3 py-1.5 rounded">
            <Text className="text-gray-200 font-bold text-xs">Tab</Text>
          </TouchableOpacity>
          <TouchableOpacity onPress={() => sendStdinData('\x1b')} className="bg-gray-800 px-3 py-1.5 rounded">
            <Text className="text-gray-200 font-bold text-xs">Esc</Text>
          </TouchableOpacity>
          <TouchableOpacity onPress={() => sendStdinData('\x03')} className="bg-red-900/60 px-3 py-1.5 rounded">
            <Text className="text-red-300 font-bold text-xs">Ctrl+C</Text>
          </TouchableOpacity>
          <TouchableOpacity onPress={() => sendStdinData('\x1b[A')} className="bg-gray-800 px-3 py-1.5 rounded">
            <Ionicons name="arrow-up" size={16} color="#d1d5db" />
          </TouchableOpacity>
          <TouchableOpacity onPress={() => sendStdinData('\x1b[B')} className="bg-gray-800 px-3 py-1.5 rounded">
            <Ionicons name="arrow-down" size={16} color="#d1d5db" />
          </TouchableOpacity>
          <TouchableOpacity onPress={() => sendStdinData('\x1b[D')} className="bg-gray-800 px-3 py-1.5 rounded">
            <Ionicons name="arrow-back" size={16} color="#d1d5db" />
          </TouchableOpacity>
          <TouchableOpacity onPress={() => sendStdinData('\x1b[C')} className="bg-gray-800 px-3 py-1.5 rounded">
            <Ionicons name="arrow-forward" size={16} color="#d1d5db" />
          </TouchableOpacity>
        </View>

        {/* Campo de Entrada de Comando */}
        <View className="p-3 bg-[#181a20] border-t border-gray-800 flex-row items-center">
          <Text className="text-green-500 font-mono font-bold mr-2">$</Text>
          <TextInput
            className="flex-1 text-white font-mono text-base py-1"
            value={commandInput}
            onChangeText={setCommandInput}
            onSubmitEditing={handleSubmitCommand}
            placeholder="Escribí un comando..."
            placeholderTextColor="#6b7280"
            autoCapitalize="none"
            autoCorrect={false}
          />
          <TouchableOpacity onPress={handleSubmitCommand} className="bg-blue-600 p-2 rounded-lg ml-2">
            <Ionicons name="send" size={18} color="white" />
          </TouchableOpacity>
        </View>
      </KeyboardAvoidingView>
    </View>
  );
}
