/**
 * WebSocket client for chat completions
 * This replaces the HTTP streaming endpoint with a WebSocket connection
 */

// Get the server base URL from environment or use default
const SERVER_BASE_URL = process.env.SERVER_BASE_URL || 'http://localhost:8001';

// Convert HTTP URL to WebSocket URL
const getWebSocketUrl = () => {
  const baseUrl = SERVER_BASE_URL;
  // Replace http:// with ws:// or https:// with wss://
  const wsBaseUrl = baseUrl.replace(/^http/, 'ws');
  return `${wsBaseUrl}/ws/chat`;
};

export interface ChatMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
}

export interface ChatCompletionRequest {
  repo_url: string;
  messages: ChatMessage[];
  filePath?: string;
  token?: string;
  type?: string;
  provider?: string;
  model?: string;
  language?: string;
  excluded_dirs?: string;
  excluded_files?: string;
  included_dirs?: string;
  included_files?: string;
}

export const sendChatCompletionRequest = async (
  request: ChatCompletionRequest,
): Promise<string> => {
  let content = '';

  try {
    const ws = new WebSocket(getWebSocketUrl());

    await new Promise<void>((resolve, reject) => {
      const timeout = setTimeout(() => {
        reject(new Error('WebSocket connection timeout'));
      }, 5000);

      ws.onopen = () => {
        clearTimeout(timeout);
        ws.send(JSON.stringify(request));
        resolve();
      };

      ws.onerror = () => {
        clearTimeout(timeout);
        reject(new Error('WebSocket connection failed'));
      };
    });

    await new Promise<void>((resolve, reject) => {
      ws.onmessage = (event) => {
        content += event.data;
      };
      ws.onclose = () => resolve();
      ws.onerror = () => reject(new Error('WebSocket error during message reception'));
    });

    return content;
  } catch {
    const response = await fetch('/api/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      const errorText = await response.text().catch(() => 'No error details available');
      throw new Error(`Chat request failed: ${response.status} ${response.statusText} ${errorText}`);
    }

    const reader = response.body?.getReader();
    const decoder = new TextDecoder();
    if (!reader) {
      throw new Error('Failed to get response reader');
    }

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      content += decoder.decode(value, { stream: true });
    }
    content += decoder.decode();
    return content;
  }
};

/**
 * Creates a WebSocket connection for chat completions
 * @param request The chat completion request
 * @param onMessage Callback for received messages
 * @param onError Callback for errors
 * @param onClose Callback for when the connection closes
 * @returns The WebSocket connection
 */
export const createChatWebSocket = (
  request: ChatCompletionRequest,
  onMessage: (message: string) => void,
  onError: (error: Event) => void,
  onClose: () => void
): WebSocket => {
  // Create WebSocket connection
  const ws = new WebSocket(getWebSocketUrl());
  
  // Set up event handlers
  ws.onopen = () => {
    console.log('WebSocket connection established');
    // Send the request as JSON
    ws.send(JSON.stringify(request));
  };
  
  ws.onmessage = (event) => {
    // Call the message handler with the received text
    onMessage(event.data);
  };
  
  ws.onerror = (error) => {
    console.error('WebSocket error:', error);
    onError(error);
  };
  
  ws.onclose = () => {
    console.log('WebSocket connection closed');
    onClose();
  };
  
  return ws;
};

/**
 * Closes a WebSocket connection
 * @param ws The WebSocket connection to close
 */
export const closeWebSocket = (ws: WebSocket | null): void => {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.close();
  }
};
