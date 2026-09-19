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
    this.isStopping = false;
  }

  start() {
    if (this.socket) return;
    this.isStopping = false;

    this.socket = dgram.createSocket({ type: 'udp4', reusePort: true });

    this.socket.bind(UDP_PORT, () => {
      if (this.isStopping || !this.socket) return;
      try {
        this.socket.setBroadcast(true);
        console.log(`[UDP] Listening and Broadcasting on port ${UDP_PORT}`);
        this._startBeacon();
      } catch (e) {
        console.warn('[UDP] Could not set broadcast on bound socket:', e.message);
      }
    });

    this.socket.on('message', (msg, rinfo) => {
      if (this.isStopping) return;
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
      if (this.isStopping) return;
      console.error('[UDP] Error:', err);
    });
  }

  _startBeacon() {
    if (this.beaconInterval) clearInterval(this.beaconInterval);
    this.beaconInterval = setInterval(() => {
      if (this.isStopping || !this.socket) return;

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
      
      try {
        this.socket.send(buf, 0, buf.length, UDP_PORT, BROADCAST_IP, (err) => {
          if (err && !this.isStopping) console.error('[UDP] Beacon Send Error:', err);
        });
      } catch (e) {
        // Socket en proceso de cierre
      }
    }, 3000); // 3 segundos, igual que en Python
  }

  stop() {
    this.isStopping = true;
    if (this.beaconInterval) {
      clearInterval(this.beaconInterval);
      this.beaconInterval = null;
    }
    if (this.socket) {
      try {
        this.socket.close();
      } catch (e) {
        // Socket ya cerrado
      }
      this.socket = null;
      console.log('[UDP] Discovery Stopped');
    }
  }
}
