/**
 * VK Dub Studio — Native Messaging Bridge Client
 * Manages communication with the native messaging host (com.vkdub.bridge).
 */

import { NativeHostName, Actions, ProtocolVersion } from "./protocol.js";

export class NativeMessagingBridge {
  constructor({ onMessage, onConnect, onDisconnect, logger = console } = {}) {
    this.onMessage = onMessage || (() => {});
    this.onConnect = onConnect || (() => {});
    this.onDisconnect = onDisconnect || (() => {});
    this.logger = logger;

    this.port = null;
    this.isConnected = false;
    this.reconnectTimer = null;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 10;
    this.baseReconnectDelayMs = 2000;
  }

  connect() {
    if (this.port) {
      try {
        this.port.disconnect();
      } catch (e) {
        // ignore
      }
      this.port = null;
    }

    this.logger.info(`[NativeBridge] Connecting to ${NativeHostName}...`);

    try {
      this.port = chrome.runtime.connectNative(NativeHostName);
    } catch (err) {
      this.logger.error("[NativeBridge] Failed to initiate connectNative:", err);
      this._handleDisconnect(err);
      return;
    }

    this.port.onMessage.addListener((message) => {
      this._handleMessage(message);
    });

    this.port.onDisconnect.addListener(() => {
      const lastError = chrome.runtime.lastError;
      const errorMsg = lastError ? lastError.message : "Port closed";
      this.logger.warn(`[NativeBridge] Disconnected: ${errorMsg}`);
      this._handleDisconnect(new Error(errorMsg));
    });

    this.isConnected = true;
    this.reconnectAttempts = 0;
    this.onConnect();

    // Send initial handshake
    this.send({
      action: Actions.HELLO,
      version: ProtocolVersion,
      client: "VK Dub Browser Extension",
      timestamp: Date.now(),
    });
  }

  send(message) {
    if (!this.port || !this.isConnected) {
      this.logger.warn("[NativeBridge] Cannot send, port not connected:", message);
      return false;
    }
    try {
      this.port.postMessage(message);
      return true;
    } catch (err) {
      this.logger.error("[NativeBridge] Error sending message:", err);
      return false;
    }
  }

  _handleMessage(message) {
    if (message && message.action === Actions.PING) {
      this.send({ action: Actions.PONG, timestamp: Date.now() });
      return;
    }
    this.onMessage(message);
  }

  _handleDisconnect(error) {
    this.isConnected = false;
    this.port = null;
    this.onDisconnect(error);
    this._scheduleReconnect();
  }

  _scheduleReconnect() {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
    }

    const delay = Math.min(
      this.baseReconnectDelayMs * Math.pow(1.5, this.reconnectAttempts),
      30000
    );
    this.reconnectAttempts++;

    this.logger.info(`[NativeBridge] Scheduling reconnect in ${Math.round(delay / 1000)}s (attempt ${this.reconnectAttempts})...`);
    this.reconnectTimer = setTimeout(() => {
      this.connect();
    }, delay);
  }

  disconnect() {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.port) {
      try {
        this.port.disconnect();
      } catch (e) {
        // ignore
      }
      this.port = null;
    }
    this.isConnected = false;
  }
}
