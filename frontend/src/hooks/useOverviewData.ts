import { useCallback, useEffect, useMemo, useState } from 'react';
import { fetchAnalyticsOverview, fetchLeads } from '../services/api';
import type { DashboardOverviewResponse, TimeRange, TractionPoint } from '../types/analytics';
import type { Lead } from '../types/telemetry';

function getWindowCutoffMs(range: TimeRange): number {
  const now = Date.now();
  if (range === '24h') return now - 24 * 60 * 60 * 1000;
  if (range === '7d') return now - 7 * 24 * 60 * 60 * 1000;
  return now - 30 * 24 * 60 * 60 * 1000;
}

function buildTractionSeries(leads: Lead[], range: TimeRange): TractionPoint[] {
  const now = new Date();
  const bucketsCount = range === '24h' ? 6 : range === '7d' ? 7 : 6;
  const bucketMap = new Map<string, TractionPoint>();
  const orderedKeys: string[] = [];

  for (let i = bucketsCount - 1; i >= 0; i -= 1) {
    let label = '';
    if (range === '24h') {
      const d = new Date(now.getTime() - i * 4 * 60 * 60 * 1000);
      label = `${String(d.getHours()).padStart(2, '0')}h`;
    } else if (range === '7d') {
      const d = new Date(now.getTime() - i * 24 * 60 * 60 * 1000);
      label = d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' });
    } else {
      const d = new Date(now.getTime() - i * 5 * 24 * 60 * 60 * 1000);
      label = d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' });
    }
    orderedKeys.push(label);
    bucketMap.set(label, { label, entradas: 0, fechamentos: 0, capital: 0 });
  }

  const cutoffMs = getWindowCutoffMs(range);
  for (const lead of leads) {
    const createdMs = new Date(lead.criado_em).getTime();
    if (Number.isNaN(createdMs) || createdMs < cutoffMs) continue;

    let targetKey = orderedKeys[orderedKeys.length - 1];
    if (range === '24h') {
      const diffHours = Math.max(0, (now.getTime() - createdMs) / (1000 * 60 * 60));
      const idxFromEnd = Math.min(bucketsCount - 1, Math.floor(diffHours / 4));
      targetKey = orderedKeys[bucketsCount - 1 - idxFromEnd];
    } else if (range === '7d') {
      const d = new Date(createdMs);
      const candidate = d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' });
      if (bucketMap.has(candidate)) targetKey = candidate;
    } else {
      const diffDays = Math.max(0, (now.getTime() - createdMs) / (1000 * 60 * 60 * 24));
      const idxFromEnd = Math.min(bucketsCount - 1, Math.floor(diffDays / 5));
      targetKey = orderedKeys[bucketsCount - 1 - idxFromEnd];
    }

    const bucket = bucketMap.get(targetKey);
    if (bucket) {
      bucket.entradas += 1;
      if (lead.desfecho === 'GANHO' || lead.etapa_funil === 'FECHAMENTO') {
        bucket.fechamentos += 1;
      }
      bucket.capital += lead.valor_estimado ?? 0;
    }
  }

  return orderedKeys.map((k) => bucketMap.get(k)!);
}

export function useOverviewData() {
  const [overview, setOverview] = useState<DashboardOverviewResponse | null>(null);
  const [leads, setLeads] = useState<Lead[]>([]);
  const [timeRange, setTimeRange] = useState<TimeRange>('7d');
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async (signal?: AbortSignal) => {
    setIsLoading(true);
    setError(null);
    try {
      const [overviewRes, leadsRes] = await Promise.all([
        fetchAnalyticsOverview(signal),
        fetchLeads(250, 0, signal),
      ]);
      setOverview(overviewRes);
      setLeads(leadsRes);
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        return;
      }
      setError(
        err instanceof Error
          ? err.message
          : 'Não foi possível carregar os indicadores analíticos do servidor.'
      );
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      fetchAnalyticsOverview(controller.signal),
      fetchLeads(250, 0, controller.signal),
    ])
      .then(([overviewRes, leadsRes]) => {
        setOverview(overviewRes);
        setLeads(leadsRes);
        setError(null);
      })
      .catch((err) => {
        if (err instanceof DOMException && err.name === 'AbortError') return;
        setError(
          err instanceof Error
            ? err.message
            : 'Não foi possível carregar os indicadores analíticos do servidor.'
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setIsLoading(false);
        }
      });
    return () => controller.abort();
  }, []);

  const tractionData = useMemo(
    () => buildTractionSeries(leads, timeRange),
    [leads, timeRange]
  );

  const priorityDeals = useMemo(() => {
    const cutoff = getWindowCutoffMs(timeRange);
    const inWindow = leads.filter((l) => {
      const ts = new Date(l.criado_em).getTime();
      return Number.isNaN(ts) || ts >= cutoff;
    });

    const source = inWindow.length > 0 ? inWindow : leads;
    const tempWeight = { QUENTE: 3, MORNO: 2, FRIO: 1 } as const;
    const controlWeight = {
      TRANSBORDO_SOLICITADO: 3,
      HUMANO_ASSUMIU: 2,
      PILOTO_IA: 1,
    } as const;

    return [...source]
      .filter((l) => l.desfecho === 'EM_ANDAMENTO' || l.desfecho === 'GANHO')
      .sort((a, b) => {
        const ctrlDiff = controlWeight[b.controle] - controlWeight[a.controle];
        if (ctrlDiff !== 0) return ctrlDiff;
        const tempDiff = tempWeight[b.temperatura] - tempWeight[a.temperatura];
        if (tempDiff !== 0) return tempDiff;
        return (b.valor_estimado ?? 0) - (a.valor_estimado ?? 0);
      })
      .slice(0, 8);
  }, [leads, timeRange]);

  const pendingHandoverCount = useMemo(
    () => leads.filter((l) => l.controle === 'TRANSBORDO_SOLICITADO').length,
    [leads]
  );

  return {
    overview,
    leads,
    tractionData,
    priorityDeals,
    pendingHandoverCount,
    timeRange,
    setTimeRange,
    isLoading,
    error,
    reload,
  };
}
