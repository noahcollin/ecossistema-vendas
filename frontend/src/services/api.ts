import type { OperacaoSettings } from '../types/settings'

const API_BASE = '' // O proxy do Vite redireciona para http://localhost:8000

export async function fetchOperacaoSettings(): Promise<OperacaoSettings> {
  const res = await fetch(`${API_BASE}/settings/operacao`)
  if (!res.ok) {
    throw new Error(`Erro ao buscar configurações: ${res.statusText}`)
  }
  return res.json()
}

export async function updateOperacaoSettings(
  payload: Partial<OperacaoSettings>,
  apiKey: string = 'master-secret-key-123'
): Promise<OperacaoSettings> {
  const res = await fetch(`${API_BASE}/settings/operacao`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': apiKey,
    },
    body: JSON.stringify(payload),
  })

  if (!res.ok) {
    const errData = await res.json().catch(() => ({}))
    throw new Error(errData.detail || `Erro ao atualizar configurações: ${res.statusText}`)
  }
  return res.json()
}

export async function fetchLeads(apiKey: string = 'master-secret-key-123') {
  const res = await fetch(`${API_BASE}/leads/`, {
    headers: {
      'X-API-Key': apiKey,
    },
  })
  if (!res.ok) {
    throw new Error(`Erro ao buscar leads: ${res.statusText}`)
  }
  return res.json()
}

export async function fetchLeadInteracoes(
  leadId: number,
  apiKey: string = 'master-secret-key-123'
) {
  const res = await fetch(`${API_BASE}/leads/${leadId}/interacoes`, {
    headers: {
      'X-API-Key': apiKey,
    },
  })
  if (!res.ok) {
    throw new Error(`Erro ao buscar histórico de conversas: ${res.statusText}`)
  }
  return res.json()
}

export async function auditarLead(
  leadId: number,
  apiKey: string = 'master-secret-key-123'
) {
  const res = await fetch(`${API_BASE}/leads/${leadId}/auditar`, {
    method: 'POST',
    headers: {
      'X-API-Key': apiKey,
    },
  })
  if (!res.ok) {
    throw new Error(`Erro ao gerar auditoria do lead: ${res.statusText}`)
  }
  return res.json()
}

export async function assumirTransbordo(
  leadId: number,
  atendente: string = 'Consultor Humano',
  apiKey: string = 'master-secret-key-123'
) {
  const res = await fetch(`${API_BASE}/leads/${leadId}/transbordo/assumir`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': apiKey,
    },
    body: JSON.stringify({ atendente }),
  })
  if (!res.ok) {
    throw new Error(`Erro ao assumir transbordo: ${res.statusText}`)
  }
  return res.json()
}

export async function devolverTransbordo(
  leadId: number,
  diretriz_ia?: string,
  apiKey: string = 'master-secret-key-123'
) {
  const res = await fetch(`${API_BASE}/leads/${leadId}/transbordo/devolver`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': apiKey,
    },
    body: JSON.stringify({ diretriz_ia }),
  })
  if (!res.ok) {
    throw new Error(`Erro ao devolver atendimento para IA: ${res.statusText}`)
  }
  return res.json()
}

export async function enviarMensagemHumana(
  leadId: number,
  texto: string,
  atendente: string = 'Consultor Humano',
  apiKey: string = 'master-secret-key-123'
) {
  const res = await fetch(`${API_BASE}/leads/${leadId}/transbordo/mensagem`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': apiKey,
    },
    body: JSON.stringify({ texto, atendente }),
  })
  if (!res.ok) {
    throw new Error(`Erro ao enviar mensagem humana: ${res.statusText}`)
  }
  return res.json()
}

