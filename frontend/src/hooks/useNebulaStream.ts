import { useEffect, useRef } from 'react';
import { apiClient } from '../api/client';
import { useNebulaStore } from '../store/nebulaStore';

export function useNebulaStream() {
  const addEvent = useNebulaStore((s) => s.addEvent);
  const esRef = useRef<EventSource | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const delayRef = useRef<number>(1000);

  useEffect(() => {
    function connect() {
      const es = new EventSource(apiClient.sseUrl('/api/v1/nebula/stream'));
      esRef.current = es;
      es.onmessage = (e) => {
        delayRef.current = 1000;
        try { addEvent(JSON.parse(e.data)); } catch {}
      };
      es.onerror = () => {
        es.close();
        const delay = delayRef.current;
        delayRef.current = Math.min(delay * 2, 30000);
        timerRef.current = setTimeout(connect, delay);
      };
    }
    connect();
    return () => {
      esRef.current?.close();
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [addEvent]);
}
