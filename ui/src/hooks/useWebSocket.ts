import { useEffect, useRef } from 'react';

export function useWebSocket(onMessage: (data: unknown) => void): void {
  // Store callback in a ref so callers don't need to memoize it
  const onMessageRef = useRef(onMessage);
  useEffect(() => {
    onMessageRef.current = onMessage;
  }, [onMessage]);

  useEffect(() => {
    let ws: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let destroyed = false;

    function connect() {
      if (destroyed) return;

      const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
      const host = window.location.host;
      ws = new WebSocket(`${protocol}://${host}/ws/graph`);

      ws.onmessage = (event) => {
        try {
          const data: unknown = JSON.parse(event.data as string);
          onMessageRef.current(data);
        } catch {
          onMessageRef.current(event.data);
        }
      };

      ws.onclose = () => {
        if (!destroyed) {
          reconnectTimer = setTimeout(connect, 3000);
        }
      };

      ws.onerror = () => {
        ws?.close();
      };
    }

    connect();

    return () => {
      destroyed = true;
      if (reconnectTimer !== null) {
        clearTimeout(reconnectTimer);
      }
      ws?.close();
    };
  }, []);
}
