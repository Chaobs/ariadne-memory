/**
 * SSE Client for real-time observation updates
 *
 * Connects to /api/sse endpoint and handles events for:
 * - new_observation: New observation recorded
 * - new_summary: Session summary generated
 * - session_ended: Session completed
 * - heartbeat: Keep-alive ping
 */

export type SSEEventType = 'connected' | 'new_observation' | 'new_summary' | 'session_ended' | 'heartbeat' | 'error';

export interface SSEEvent {
  type: SSEEventType;
  client_id?: string;
  session_id?: string;
  data?: Record<string, unknown>;
  timestamp?: string;
}

export interface ObservationData {
  id: string;
  session_id: string;
  obs_type: string;
  summary: string;
  detail?: string;
  files?: string[];
  created_at: string;
}

export interface SummaryData {
  session_id: string;
  narrative: string;
  key_decisions?: string[];
}

type EventHandler = (event: SSEEvent) => void;

export class SSEClient {
  private eventSource: EventSource | null = null;
  private sessionId: string | null;
  private eventHandlers: Map<SSEEventType, EventHandler[]> = new Map();
  private reconnectDelay: number = 1000;
  private maxReconnectDelay: number = 30000;
  private shouldReconnect: boolean = true;
  private isConnected: boolean = false;
  private reconnectTimeout: ReturnType<typeof setTimeout> | null = null;

  constructor(sessionId: string | null = null) {
    this.sessionId = sessionId;
  }

  /**
   * Connect to SSE endpoint
   */
  connect(): void {
    if (this.eventSource) {
      this.disconnect();
    }

    const url = this.sessionId
      ? `/api/sse?session_id=${encodeURIComponent(this.sessionId)}`
      : '/api/sse';

    try {
      this.eventSource = new EventSource(url);
      this.setupEventHandlers();
    } catch (error) {
      console.error('SSE connection error:', error);
      this.scheduleReconnect();
    }
  }

  private setupEventHandlers(): void {
    if (!this.eventSource) return;

    this.eventSource.onopen = () => {
      console.log('[SSE] Connected');
      this.isConnected = true;
      this.reconnectDelay = 1000; // Reset delay on successful connection
      this.dispatch('connected', { type: 'connected' });
    };

    this.eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        this.dispatch(data.type, data);
      } catch (e) {
        console.error('[SSE] Parse error:', e);
      }
    };

    this.eventSource.onerror = (error) => {
      console.error('[SSE] Error:', error);
      this.isConnected = false;

      // Dispatch error event
      this.dispatch('error', { type: 'error' });

      // Schedule reconnect
      this.scheduleReconnect();
    };
  }

  private scheduleReconnect(): void {
    if (!this.shouldReconnect || this.reconnectTimeout) return;

    console.log(`[SSE] Reconnecting in ${this.reconnectDelay}ms...`);

    this.reconnectTimeout = setTimeout(() => {
      this.reconnectTimeout = null;
      this.connect();
    }, this.reconnectDelay);

    // Exponential backoff
    this.reconnectDelay = Math.min(this.reconnectDelay * 2, this.maxReconnectDelay);
  }

  /**
   * Disconnect from SSE endpoint
   */
  disconnect(): void {
    this.shouldReconnect = false;

    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }

    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }

    this.isConnected = false;
    console.log('[SSE] Disconnected');
  }

  /**
   * Register event handler
   */
  on(eventType: SSEEventType, handler: EventHandler): () => void {
    if (!this.eventHandlers.has(eventType)) {
      this.eventHandlers.set(eventType, []);
    }
    this.eventHandlers.get(eventType)!.push(handler);

    // Return unsubscribe function
    return () => this.off(eventType, handler);
  }

  /**
   * Unregister event handler
   */
  off(eventType: SSEEventType, handler: EventHandler): void {
    const handlers = this.eventHandlers.get(eventType);
    if (handlers) {
      const index = handlers.indexOf(handler);
      if (index > -1) {
        handlers.splice(index, 1);
      }
    }
  }

  /**
   * Dispatch event to handlers
   */
  private dispatch(eventType: SSEEventType, data: SSEEvent): void {
    const handlers = this.eventHandlers.get(eventType);
    if (handlers) {
      handlers.forEach((handler) => {
        try {
          handler(data);
        } catch (e) {
          console.error(`[SSE] Handler error (${eventType}):`, e);
        }
      });
    }
  }

  /**
   * Check if connected
   */
  get connected(): boolean {
    return this.isConnected;
  }
}

// Singleton instance for session events
let globalSSEClient: SSEClient | null = null;

export function getSSEClient(sessionId?: string): SSEClient {
  if (!globalSSEClient) {
    globalSSEClient = new SSEClient(sessionId || null);
  } else if (sessionId && globalSSEClient.sessionId !== sessionId) {
    // Session changed, need new connection
    globalSSEClient.disconnect();
    globalSSEClient = new SSEClient(sessionId);
  }
  return globalSSEClient;
}

export function closeSSEClient(): void {
  if (globalSSEClient) {
    globalSSEClient.disconnect();
    globalSSEClient = null;
  }
}
