import dgram from 'react-native-udp';
import { Buffer } from 'buffer';

const UDP_PORT = 50000;
const BROADCAST_IP = '255.255.255.255';

export class UdpDiscovery {
  constructor(nodeId, nodeName, tcpPort, onPeerDiscovered) {
    this.nodeId = nodeId;
    this.nodeName = nodeName;
    this.tcpPort = tcpPort;
    this.onPeerDiscovered = onPeerDiscovered;
    
    this.socket = null;
    this.beaconInterval = null;
  }

  start() {
    if (this.socket) return;

    this.socket = dgram.createSocket({ type: 'udp4', reusePort: true });

    this.socket.bind(UDP_PORT, () => {
      this.socket.setBroadcast(true);
      console.log(`[UDP] Listening and Broadcasting on port ${UDP_PORT}`);
      this._startBeacon();
    });

    this.socket.on('message', (msg, rinfo) => {
      try {
        const payload = JSON.parse(msg.toString('utf8'));
        
        // Ignorar nuestros propios paquetes
        if (payload.node_id && payload.node_id !== this.nodeId) {
          if (payload.type === 'SYSNODE_ANNOUNCE') {
            this.onPeerDiscovered({
              node_id: payload.node_id,
              hostname: payload.hostname || 'Unknown',
              ip: rinfo.address,
              tcp_port: payload.tcp_port,
              os: payload.os || 'Unknown',
              last_seen: Date.now()
            });
          }
        }
      } catch (err) {
        // Ignorar paquetes malformados
      }
    });

    this.socket.on('error', (err) => {
      console.error('[UDP] Error:', err);
    });
  }

  _startBeacon() {
    this.beaconInterval = setInterval(() => {
      const payload = JSON.stringify({
        type: 'SYSNODE_ANNOUNCE',
        node_id: this.nodeId,
        hostname: this.nodeName,
        tcp_port: this.tcpPort,
        os: 'Android',
        device_type: 'mobile',
        timestamp: Date.now() / 1000
      });
      
      const buf = Buffer.from(payload);
      
      this.socket.send(buf, 0, buf.length, UDP_PORT, BROADCAST_IP, (err) => {
        if (err) console.error('[UDP] Beacon Send Error:', err);
      });
    }, 3000); // 3 segundos, igual que en Python
  }

  stop() {
    if (this.beaconInterval) {
      clearInterval(this.beaconInterval);
      this.beaconInterval = null;
    }
    if (this.socket) {
      try {
        this.socket.close();
      } catch (e) {
        console.error('[UDP] Error closing socket:', e);
      }
      this.socket = null;
      console.log('[UDP] Discovery Stopped');
    }
  }
}
