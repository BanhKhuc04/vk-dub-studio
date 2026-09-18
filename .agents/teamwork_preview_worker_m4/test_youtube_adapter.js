/**
 * VK Dub Studio — Test Runner for apps/browser-extension/content/youtubeAdapter.js
 */

const assert = require("assert");
const path = require("path");

// Mock global browser environment for Node.js
global.window = {
  location: { pathname: "/watch", search: "?v=dQw4w9WgXcQ", href: "https://www.youtube.com/watch?v=dQw4w9WgXcQ" },
  addEventListener: () => {},
  removeEventListener: () => {},
};
global.document = {
  title: "Rick Astley - Never Gonna Give You Up - YouTube",
  readyState: "complete",
  addEventListener: () => {},
  removeEventListener: () => {},
  querySelector: () => null,
  querySelectorAll: () => [],
  getElementById: () => null,
  createElement: (tag) => {
    const el = {
      tagName: tag.toUpperCase(),
      style: {},
      classList: { add: () => {}, remove: () => {}, contains: () => false, toggle: () => {} },
      appendChild: () => {},
      removeChild: () => {},
      attachShadow: () => ({
        appendChild: () => {},
        getElementById: () => null,
        addEventListener: () => {},
      }),
      addEventListener: () => {},
      removeEventListener: () => {},
    };
    return el;
  },
  head: { appendChild: () => {} },
  documentElement: { appendChild: () => {} },
  activeElement: null,
};
global.chrome = {
  runtime: {
    sendMessage: () => Promise.resolve(),
    onMessage: { addListener: () => {} },
  },
  storage: {
    local: {
      get: (keys, cb) => cb({}),
      set: () => Promise.resolve(),
    },
  },
};
global.Node = { ELEMENT_NODE: 1 };
global.requestAnimationFrame = (fn) => setTimeout(fn, 16);
global.cancelAnimationFrame = (id) => clearTimeout(id);

const adapterModule = require(path.resolve(__dirname, "../../apps/browser-extension/content/youtubeAdapter.js"));

console.log("Testing YouTube Adapter exports...");
assert(adapterModule.YouTubeAdapter, "YouTubeAdapter class should be exported");
assert(adapterModule.Actions, "Actions object should be exported");
assert(typeof adapterModule.roundMs === "function", "roundMs should be exported");
assert(typeof adapterModule.formatTimecode === "function", "formatTimecode should be exported");
assert(typeof adapterModule.parseTimecode === "function", "parseTimecode should be exported");
assert(typeof adapterModule.validateClipBounds === "function", "validateClipBounds should be exported");
assert(typeof adapterModule.isDuplicateClip === "function", "isDuplicateClip should be exported");
assert(typeof adapterModule.isUserTyping === "function", "isUserTyping should be exported");

console.log("1. Testing Actions Constants...");
assert.strictEqual(adapterModule.Actions.YOUTUBE_CONTEXT_SYNC, "YOUTUBE_CONTEXT_SYNC");
assert.strictEqual(adapterModule.Actions.YOUTUBE_SEEK_TO, "YOUTUBE_SEEK_TO");
assert.strictEqual(adapterModule.Actions.YOUTUBE_PREVIEW_CLIP, "YOUTUBE_PREVIEW_CLIP");
assert.strictEqual(adapterModule.Actions.YOUTUBE_CLIP_ADDED, "YOUTUBE_CLIP_ADDED");

console.log("2. Testing roundMs...");
assert.strictEqual(adapterModule.roundMs(0), 0);
assert.strictEqual(adapterModule.roundMs(12.3456), 12.346);
assert.strictEqual(adapterModule.roundMs(0.1 + 0.2), 0.3);
assert.strictEqual(adapterModule.roundMs("45.6789"), 45.679);
assert.strictEqual(adapterModule.roundMs(NaN), 0);

console.log("3. Testing formatTimecode...");
assert.strictEqual(adapterModule.formatTimecode(0), "00:00.000");
assert.strictEqual(adapterModule.formatTimecode(0, true), "00:00:00.000");
assert.strictEqual(adapterModule.formatTimecode(65.5), "01:05.500");
assert.strictEqual(adapterModule.formatTimecode(3665.123), "01:01:05.123");
assert.strictEqual(adapterModule.formatTimecode(null), "--:--.---");
assert.strictEqual(adapterModule.formatTimecode(null, true), "--:--:--.---");
assert.strictEqual(adapterModule.formatTimecode(-5), "--:--.---");

console.log("4. Testing parseTimecode...");
assert.strictEqual(adapterModule.parseTimecode("85.4"), 85.4);
assert.strictEqual(adapterModule.parseTimecode("01:25"), 85);
assert.strictEqual(adapterModule.parseTimecode("01:25.400"), 85.4);
assert.strictEqual(adapterModule.parseTimecode("01:05:22.100"), 3922.1);
assert.strictEqual(adapterModule.parseTimecode(120.5), 120.5);
assert.strictEqual(adapterModule.parseTimecode("invalid:text"), null);
assert.strictEqual(adapterModule.parseTimecode(""), null);

console.log("5. Testing validateClipBounds...");
// Valid clip
assert.strictEqual(adapterModule.validateClipBounds(10, 15, 100).valid, true);
// Start >= End
assert.strictEqual(adapterModule.validateClipBounds(15, 10, 100).valid, false);
assert.strictEqual(adapterModule.validateClipBounds(10, 10, 100).valid, false);
// Negative start
assert.strictEqual(adapterModule.validateClipBounds(-1, 10, 100).valid, false);
// Less than 0.5s duration
assert.strictEqual(adapterModule.validateClipBounds(10, 10.4, 100).valid, false);
assert.strictEqual(adapterModule.validateClipBounds(10, 10.5, 100).valid, true);
// Exceeds video duration
assert.strictEqual(adapterModule.validateClipBounds(10, 102, 100).valid, false);
assert.strictEqual(adapterModule.validateClipBounds(10, 100.4, 100).valid, true);

console.log("6. Testing isDuplicateClip...");
const clip1 = { start: 10.0, end: 20.0 };
const clip2 = { start: 10.05, end: 20.04 };
const clip3 = { start: 10.2, end: 20.0 };
assert.strictEqual(adapterModule.isDuplicateClip(clip1, clip2), true);
assert.strictEqual(adapterModule.isDuplicateClip(clip1, clip3), false);

console.log("7. Testing isUserTyping...");
const mockEventInput = {
  composedPath: () => [{ nodeType: 1, tagName: "INPUT" }],
};
const mockEventDiv = {
  composedPath: () => [{ nodeType: 1, tagName: "DIV" }],
};
const mockEventTextarea = {
  composedPath: () => [{ nodeType: 1, tagName: "TEXTAREA" }],
};
const mockEventContentEditable = {
  composedPath: () => [{ nodeType: 1, tagName: "DIV", isContentEditable: true }],
};
const mockEventRoleTextbox = {
  composedPath: () => [{ nodeType: 1, tagName: "DIV", getAttribute: (attr) => (attr === "role" ? "textbox" : null) }],
};

assert.strictEqual(adapterModule.isUserTyping(mockEventInput), true);
assert.strictEqual(adapterModule.isUserTyping(mockEventTextarea), true);
assert.strictEqual(adapterModule.isUserTyping(mockEventContentEditable), true);
assert.strictEqual(adapterModule.isUserTyping(mockEventRoleTextbox), true);
assert.strictEqual(adapterModule.isUserTyping(mockEventDiv), false);

console.log("8. Testing YouTubeAdapter instance and methods...");
const adapter = new adapterModule.YouTubeAdapter();
assert.strictEqual(adapter.version, "2.2.0");
assert.strictEqual(adapter.initialized, false);
assert.strictEqual(adapter.clipStart, null);
assert.strictEqual(adapter.clipEnd, null);

// In-Point & Out-Point Setting
adapter.setInPoint(10.5);
assert.strictEqual(adapter.clipStart, 10.5);
assert.strictEqual(adapter.clipEnd, null);

adapter.setOutPoint(25.75);
assert.strictEqual(adapter.clipStart, 10.5);
assert.strictEqual(adapter.clipEnd, 25.75);

// If new In-point >= Out-point, Out-point should reset
adapter.setInPoint(30.0);
assert.strictEqual(adapter.clipStart, 30.0);
assert.strictEqual(adapter.clipEnd, null);

// Clear selection
adapter.setOutPoint(40.0);
adapter.clearSelection();
assert.strictEqual(adapter.clipStart, null);
assert.strictEqual(adapter.clipEnd, null);

console.log("9. Testing Hotkey Interception...");
let prevented = false;
let stoppedImmediate = false;
function createMockKeyEvent(key, { ctrl = false, alt = false, meta = false, isTyping = false } = {}) {
  prevented = false;
  stoppedImmediate = false;
  return {
    key,
    ctrlKey: ctrl,
    altKey: alt,
    metaKey: meta,
    preventDefault: () => { prevented = true; },
    stopImmediatePropagation: () => { stoppedImmediate = true; },
    stopPropagation: () => {},
    composedPath: () => (isTyping ? [{ nodeType: 1, tagName: "INPUT" }] : [{ nodeType: 1, tagName: "DIV" }]),
  };
}

// Watch page mock
adapter.isWatchPage = () => true;
adapter.videoElement = { currentTime: 15.2, duration: 120.0, play: () => Promise.resolve(), pause: () => {} };

// Test key 'i' overrides Miniplayer
const eventI = createMockKeyEvent("i");
adapter.handleKeydown(eventI);
assert.strictEqual(prevented, true, "Key 'i' must call preventDefault to override Miniplayer");
assert.strictEqual(stoppedImmediate, true, "Key 'i' must call stopImmediatePropagation");
assert.strictEqual(adapter.clipStart, 15.2);

// Test typing guard ignores hotkey
const eventITyping = createMockKeyEvent("i", { isTyping: true });
prevented = false;
stoppedImmediate = false;
adapter.handleKeydown(eventITyping);
assert.strictEqual(prevented, false, "Typing in input must not trigger hotkey");
assert.strictEqual(stoppedImmediate, false);

// Test key 'o'
adapter.videoElement.currentTime = 35.8;
const eventO = createMockKeyEvent("o");
adapter.handleKeydown(eventO);
assert.strictEqual(prevented, true, "Key 'o' must call preventDefault");
assert.strictEqual(stoppedImmediate, true, "Key 'o' must call stopImmediatePropagation");
assert.strictEqual(adapter.clipEnd, 35.8);

// Test key 'Enter' commits clip
let lastMessageSent = null;
global.chrome.runtime.sendMessage = (msg) => {
  lastMessageSent = msg;
  return Promise.resolve();
};
const eventEnter = createMockKeyEvent("Enter");
adapter.handleKeydown(eventEnter);
assert.strictEqual(prevented, true, "Key 'Enter' must call preventDefault");
assert.strictEqual(stoppedImmediate, true, "Key 'Enter' must call stopImmediatePropagation");
assert(lastMessageSent, "A clip message must have been dispatched");
assert.strictEqual(lastMessageSent.action, "YOUTUBE_CLIP_ADDED");
assert.strictEqual(lastMessageSent.payload.start, 15.2);
assert.strictEqual(lastMessageSent.payload.end, 35.8);
assert.strictEqual(adapter.clipStart, null, "Markers must be reset after clip added");
assert.strictEqual(adapter.clipEnd, null);

// Test Escape when selection active
adapter.setInPoint(5.0);
const eventEsc = createMockKeyEvent("Escape");
adapter.handleKeydown(eventEsc);
assert.strictEqual(prevented, true, "Escape must clear active markers");
assert.strictEqual(stoppedImmediate, true);
assert.strictEqual(adapter.clipStart, null);

// Test Escape when NO selection active (passes through for native fullscreen exit)
prevented = false;
stoppedImmediate = false;
const eventEscIdle = createMockKeyEvent("Escape");
adapter.handleKeydown(eventEscIdle);
assert.strictEqual(prevented, false, "Escape without markers must not call preventDefault");
assert.strictEqual(stoppedImmediate, false);

console.log("10. Testing Seek & Preview methods...");
const seekResult = adapter.seekTo(42.5, false);
assert.strictEqual(seekResult, 42.5);
assert.strictEqual(adapter.videoElement.currentTime, 42.5);

adapter.previewClip(10.0, 20.0, false);
assert.strictEqual(adapter.previewActive, true);
assert.strictEqual(adapter.videoElement.currentTime, 10.0);
adapter.stopPreview();
assert.strictEqual(adapter.previewActive, false);

console.log("ALL TESTS PASSED SUCCESSFULLY!");
