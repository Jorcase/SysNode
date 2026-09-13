import CryptoJS from 'crypto-js';
import { Buffer } from 'buffer';

const AUTH_TOKEN = "sysnode_secret_123";

// Create framed message for TCP: [4-byte length] [64-byte HMAC] [JSON payload]
export function createFramedMessage(payloadObj) {
  const jsonStr = JSON.stringify(payloadObj);
  
  // Create HMAC (returns 64-character hex string for SHA-256)
  const hmacHex = CryptoJS.HmacSHA256(jsonStr, AUTH_TOKEN).toString(CryptoJS.enc.Hex);
  
  const hmacBuf = Buffer.from(hmacHex, 'utf-8');
  const jsonBuf = Buffer.from(jsonStr, 'utf-8');
  
  const totalLen = hmacBuf.length + jsonBuf.length;
  
  // 4-byte header (Big Endian unsigned int)
  const headerBuf = Buffer.alloc(4);
  headerBuf.writeUInt32BE(totalLen, 0);
  
  return Buffer.concat([headerBuf, hmacBuf, jsonBuf]);
}

// Extract framed message from buffer
// Returns { message: object, remainingBuffer: Buffer } or { error: string } or null (need more data)
export function parseFramedMessage(buffer) {
  if (buffer.length < 4) return null;
  
  const payloadLen = buffer.readUInt32BE(0);
  
  if (buffer.length < 4 + payloadLen) return null;
  
  if (payloadLen < 64) {
    return { error: 'Size too small for HMAC' };
  }
  
  const payloadBuf = buffer.slice(4, 4 + payloadLen);
  const remainingBuffer = buffer.slice(4 + payloadLen);
  
  const receivedHmac = payloadBuf.slice(0, 64).toString('utf-8');
  const jsonStr = payloadBuf.slice(64).toString('utf-8');
  
  const expectedHmac = CryptoJS.HmacSHA256(jsonStr, AUTH_TOKEN).toString(CryptoJS.enc.Hex);
  
  if (receivedHmac !== expectedHmac) {
    return { error: 'Invalid HMAC signature. Access Denied.' };
  }
  
  try {
    const message = JSON.parse(jsonStr);
    return { message, remainingBuffer };
  } catch (e) {
    return { error: 'JSON parse error' };
  }
}
