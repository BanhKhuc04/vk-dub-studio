/**
 * VK Dub Studio — Dual Hybrid Bridge Client
 * Connects directly via WebSocket (ws://127.0.0.1:49814/ws) for zero-dependency,
 * instant communication, with automatic fallback to Native Messaging (com.vkdub.bridge).
 */

import { NativeHostName, Actions, ProtocolVersion } from "./protocol.js";

const WS_URL = "ws://127.0.0.1:49814/ws";

export class NativeMessagingBridge {
  constructor({ onMessage, onConnect, onDisconnect, logger = console } = {}) {
    this.onMessage = onMessage || (() => {});
    this.onConnect = onConnect || (() => {});
    this.onDisconnect = onDisconnect || (() => {});
    this.logger = logger;

    this.ws = null;
    this.port = null;
    this.isConnected = false;
    this.activeTransport = null; // 'websocket' | 'native'
    this.reconnectTimer = null;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 20;
    this.baseReconnectDelayMs = 2000;
  }

  connect() {
    this.disconnect();
    this.logger.info(`[Bridge] Connecting to VK Dub Studio (trying WebSocket -> Native Host)...`);

    // 1. Try WebSocket direct connection first
    let wsFailed = false;
    try {
      const ws = new WebSocket(WS_URL);

      const wsTimeout = setTimeout(() => {
        if (!this.isConnected && ws.readyState !== WebSocket.OPEN) {
          this.logger.info("[Bridge] WebSocket connect timeout, trying Native Messaging fallback...");
          try {
            ws.close();
          } catch (e) {}
          if (!wsFailed) {
            wsFailed = true;
            this._connectNative();
          }
        }
      }, 1500);

      ws.onopen = () => {
        clearTimeout(wsTimeout);
        this.logger.info("[Bridge] Connected directly via WebSocket (port 49814)!");
        this.ws = ws;
        this.activeTransport = "websocket";
        this.isConnected = true;
        this.reconnectAttempts = 0;
        this.onConnect();

        // Send initial handshake
        this.send({
          action: Actions.HELLO,
          version: ProtocolVersion,
          client: "VK Dub Browser Extension (WebSocket Direct)",
          timestamp: Date.now(),
        });
      };

      ws.onmessage = (event) => {
        try {
          const message = typeof event.data === "string" ? JSON.parse(event.data) : event.data;
          this._handleMessage(message);
        } catch (err) {
          this.logger.error("[Bridge] Error parsing incoming WS message:", err);
        }
      };

      ws.onerror = (err) => {
        clearTimeout(wsTimeout);
        if (!this.isConnected && !wsFailed) {
          wsFailed = true;
          this.logger.info("[Bridge] WebSocket direct connect failed, attempting Native Host fallback...");
          this._connectNative();
        }
      };

      ws.onclose = (event) => {
        clearTimeout(wsTimeout);
        if (this.ws === ws) {
          this.ws = null;
          this.isConnected = false;
          this.activeTransport = null;
          this.logger.warn("[Bridge] WebSocket disconnected.");
          this.onDisconnect(new Error("WebSocket disconnected"));
          this._scheduleReconnect();
        }
      };
    } catch (err) {
      this.logger.warn("[Bridge] WebSocket init error, falling back to Native Messaging:", err);
      this._connectNative();
    }
  }

  _connectNative() {
    if (this.isConnected) return;
    this.logger.info(`[Bridge] Attempting Native Messaging connection to ${NativeHostName}...`);

    try {
      this.port = chrome.runtime.connectNative(NativeHostName);
    } catch (err) {
      this.logger.error("[Bridge] Failed to initiate connectNative:", err);
      this._handleDisconnect(err);
      return;
    }

    this.port.onMessage.addListener((message) => {
      this._handleMessage(message);
    });

    this.port.onDisconnect.addListener(() => {
      const lastError = chrome.runtime.lastError;
      const errorMsg = lastError ? lastError.message : "Port closed";
      this.logger.warn(`[Bridge] Native Port disconnected: ${errorMsg}`);
      this._handleDisconnect(new Error(errorMsg));
    });

    this.activeTransport = "native";
    this.isConnected = true;
    this.reconnectAttempts = 0;
    this.onConnect();

    // Send initial handshake
    this.send({
      action: Actions.HELLO,
      version: ProtocolVersion,
      client: "VK Dub Browser Extension (Native Host)",
      timestamp: Date.now(),
    });
  }

  send(message) {
    if (!this.isConnected) {
      this.logger.warn("[Bridge] Cannot send, not connected:", message);
      return false;
    }

    if (this.activeTransport === "websocket" && this.ws && this.ws.readyState === WebSocket.OPEN) {
      try {
        this.ws.send(JSON.stringify(message));
        return true;
      } catch (err) {
        this.logger.error("[Bridge] WS send error:", err);
        return false;
      }
    }

    if (this.activeTransport === "native" && this.port) {
      try {
        this.port.postMessage(message);
        return true;
      } catch (err) {
        this.logger.error("[Bridge] Native send error:", err);
        return false;
      }
    }

    this.logger.warn("[Bridge] No active transport ready to send:", message);
    return false;
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
    this.activeTransport = null;
    this.port = null;
    this.ws = null;
    this.onDisconnect(error);
    this._scheduleReconnect();
  }

  _scheduleReconnect() {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
    }

    const delay = Math.min(
      this.baseReconnectDelayMs * Math.pow(1.3, this.reconnectAttempts),
      15000
    );
    this.reconnectAttempts++;

    this.logger.info(`[Bridge] Reconnecting in ${Math.round(delay / 1000)}s (attempt ${this.reconnectAttempts})...`);
    this.reconnectTimer = setTimeout(() => {
      this.connect();
    }, delay);
  }

  disconnect() {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      try {
        this.ws.close();
      } catch (e) {}
      this.ws = null;
    }
    if (this.port) {
      try {
        this.port.disconnect();
      } catch (e) {}
      this.port = null;
    }
    this.isConnected = false;
    this.activeTransport = null;
  }
}
