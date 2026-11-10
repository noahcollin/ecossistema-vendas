import type { DashboardOverviewResponse } from '../types/analytics';
import type {
  FollowupAgendado,
  Interacao,
  Lead,
  SystemHealthResponse,
  EtapaFunil,
} from '../types/telemetry';
import type {
  KillSwitchResponse,
  OperacaoSettings,
  OperacaoSettingsUpdate,
  RedisPurgeResponse,
} from '../types/settings';

const SESSION_KEY_STORAGE = 'ev_admin_api_key';
const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, '') ?? '';

export class ApiError extends Error {
  public readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

export function getStoredApiKey(): string {
  try {
    return (window.sessionStorage.getItem(SESSION_KEY_STORAGE) || '').trim();
  } catch {
    return '';
  }
}

export function setStoredApiKey(key: string): void {
  try {
    const trimmed = key.trim();
    if (trimmed) {
      window.sessionStorage.setItem(SESSION_KEY_STORAGE, trimmed);
    } else {
      window.sessionStorage.removeItem(SESSION_KEY_STORAGE);
    }
  } catch {
    // Ignora caso sessionStorage esteja indisponível
  }
}

export function clearStoredApiKey(): void {
  try {
    window.sessionStorage.removeItem(SESSION_KEY_STORAGE);
  } catch {
    // Ignora
  }
}

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE';
  body?: unknown;
  signal?: AbortSignal;
}

async function requestJson<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, signal } = options;
  const headers: Record<string, string> = {
    Accept: 'application/json',
  };

  if (body !== undefined) {
    headers['Content-Type'] = 'application/json';
  }

  const apiKey = getStoredApiKey();
  if (apiKey) {
    headers['X-API-Key'] = apiKey;
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
    signal,
  });

  if (response.status === 401 || response.status === 403) {
    window.dispatchEvent(new CustomEvent('ev:unauthorized'));
  }

  if (!response.ok) {
    let detail = `Erro HTTP ${response.status}`;
    try {
      const errJson = (await response.json()) as { detail?: string };
      if (errJson?.detail) {
        detail = errJson.detail;
      }
    } catch {
      // Resposta não-JSON (ex: 502 Bad Gateway do proxy)
    }
    throw new ApiError(response.status, detail);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

/* ==========================================================================
   SISTEMA & SAÚDE (/health)
   ========================================================================== */
export async function fetchSystemHealth(signal?: AbortSignal): Promise<SystemHealthResponse> {
  const start = performance.now();
  const headers: Record<string, string> = { Accept: 'application/json' };
  const response = await fetch(`${API_BASE_URL}/health`, { method: 'GET', headers, signal });
  const latency = Math.round(performance.now() - start);

  // /health pode retornar 200 (healthy) ou 503 (degraded) com payload JSON rico
  const payload = (await response.json()) as SystemHealthResponse;
  return {
    ...payload,
    latency_ms: latency,
  };
}

/* ==========================================================================
   ANALYTICS (/analytics/*)
   ========================================================================== */
export async function fetchAnalyticsOverview(
  signal?: AbortSignal
): Promise<DashboardOverviewResponse> {
  return requestJson<DashboardOverviewResponse>('/analytics/overview', { signal });
}

/* ==========================================================================
   LEADS, DOSSIÊ & TRANSBORDO HUMANO (/leads/*)
   ========================================================================== */
export async function fetchLeads(limit = 250, offset = 0, signal?: AbortSignal): Promise<Lead[]> {
  return requestJson<Lead[]>(`/leads/?limit=${limit}&offset=${offset}`, { signal });
}

export async function fetchPendingHandoverLeads(signal?: AbortSignal): Promise<Lead[]> {
  return requestJson<Lead[]>('/leads/transbordo/pendentes?limit=150', { signal });
}

export async function fetchLeadInteractions(
  leadId: number,
  signal?: AbortSignal
): Promise<Interacao[]> {
  return requestJson<Interacao[]>(`/leads/${leadId}/interacoes`, { signal });
}

export async function fetchLeadFollowups(
  leadId: number,
  signal?: AbortSignal
): Promise<FollowupAgendado[]> {
  return requestJson<FollowupAgendado[]>(`/leads/${leadId}/followups`, { signal });
}

export async function triggerLeadAudit(leadId: number): Promise<Lead> {
  return requestJson<Lead>(`/leads/${leadId}/auditar`, { method: 'POST' });
}

export async function assumirAtendimentoHumano(
  leadId: number,
  atendente = 'Consultor Comercial'
): Promise<Lead> {
  return requestJson<Lead>(`/leads/${leadId}/transbordo/assumir`, {
    method: 'POST',
    body: { atendente },
  });
}

export interface DevolverIaPayload {
  diretriz_ia?: string;
  etapa_sugerida?: EtapaFunil;
  valor_estimado?: number;
}

export async function devolverAtendimentoIA(
  leadId: number,
  payload: DevolverIaPayload = {}
): Promise<Lead> {
  return requestJson<Lead>(`/leads/${leadId}/transbordo/devolver`, {
    method: 'POST',
    body: payload,
  });
}

export async function solicitarTransbordoManual(
  leadId: number,
  motivo = 'Solicitação manual via painel operacional'
): Promise<Lead> {
  return requestJson<Lead>(`/leads/${leadId}/transbordo/solicitar`, {
    method: 'POST',
    body: { motivo },
  });
}

export interface MensagemHumanaSentResponse {
  status: string;
  interacao_id: number;
  origem: 'humano';
  texto: string;
  data: string;
}

export async function enviarMensagemHumana(
  leadId: number,
  texto: string,
  atendente = 'Closer Comercial'
): Promise<MensagemHumanaSentResponse> {
  return requestJson<MensagemHumanaSentResponse>(`/leads/${leadId}/transbordo/mensagem`, {
    method: 'POST',
    body: { texto, atendente },
  });
}

export async function clearLeadInteractions(leadId: number): Promise<void> {
  await requestJson<unknown>(`/leads/${leadId}/interacoes`, { method: 'DELETE' });
}

export async function deleteLead(leadId: number): Promise<void> {
  await requestJson<void>(`/leads/${leadId}`, { method: 'DELETE' });
}

/* ==========================================================================
   SALA DE MÁQUINAS & GOVERNANÇA (/settings/*)
   ========================================================================== */
export async function fetchOperacaoSettings(signal?: AbortSignal): Promise<OperacaoSettings> {
  return requestJson<OperacaoSettings>('/settings/operacao', { signal });
}

export async function updateOperacaoSettings(
  payload: OperacaoSettingsUpdate
): Promise<OperacaoSettings> {
  return requestJson<OperacaoSettings>('/settings/operacao', {
    method: 'PUT',
    body: payload,
  });
}

export async function toggleKillSwitch(silenciar: boolean): Promise<KillSwitchResponse> {
  return requestJson<KillSwitchResponse>('/settings/kill-switch', {
    method: 'POST',
    body: { silenciar },
  });
}

export async function purgeRedisQueues(): Promise<RedisPurgeResponse> {
  return requestJson<RedisPurgeResponse>('/settings/redis/purge', {
    method: 'POST',
  });
}
