import { useEffect, useRef } from 'react';
import { apiClient } from '../api/client';
import { useNebulaStore } from '../store/nebulaStore';

export function useNebulaStream() {
  const addEvent = useNebulaStore((s) => s.addEvent);
  const esRef = useRef<EventSource | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    function connect() {
      const es = new EventSource(apiClient.sseUrl('/api/v1/nebula/stream'));
      esRef.current = es;
      es.onmessage = (e) => {
        try { addEvent(JSON.parse(e.data)); } catch {}
      };
      es.onerror = () => {
        es.close();
        timerRef.current = setTimeout(connect, 5000);
      };
    }
    connect();
    return () => {
      esRef.current?.close();
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [addEvent]);
}
