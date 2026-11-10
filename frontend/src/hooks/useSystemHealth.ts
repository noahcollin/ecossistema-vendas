import { useCallback, useEffect, useState } from 'react';
import { fetchSystemHealth } from '../services/api';
import type { SystemHealthResponse } from '../types/telemetry';

export function useSystemHealth(pollIntervalMs = 25000) {
  const [health, setHealth] = useState<SystemHealthResponse | null>(null);
  const [isChecking, setIsChecking] = useState<boolean>(true);

  const refreshHealth = useCallback(async (signal?: AbortSignal) => {
    try {
      const data = await fetchSystemHealth(signal);
      setHealth(data);
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        return;
      }
      setHealth({
        status: 'offline',
        timestamp: new Date().toISOString(),
        componentes: {},
      });
    } finally {
      setIsChecking(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();

    const runCheck = () => {
      fetchSystemHealth(controller.signal)
        .then((data) => {
          setHealth(data);
          setIsChecking(false);
        })
        .catch((err) => {
          if (err instanceof DOMException && err.name === 'AbortError') return;
          setHealth({
            status: 'offline',
            timestamp: new Date().toISOString(),
            componentes: {},
          });
          setIsChecking(false);
        });
    };

    runCheck();
    const timer = window.setInterval(runCheck, pollIntervalMs);

    return () => {
      controller.abort();
      window.clearInterval(timer);
    };
  }, [pollIntervalMs]);

  return {
    health,
    isChecking,
    refreshHealth,
  };
}
