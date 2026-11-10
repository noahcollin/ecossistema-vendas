import type {
  ControleAtendimento,
  DesfechoLead,
  EtapaFunil,
  TemperaturaLead,
} from '../types/telemetry';

const brlFormatter = new Intl.NumberFormat('pt-BR', {
  style: 'currency',
  currency: 'BRL',
  minimumFractionDigits: 0,
  maximumFractionDigits: 0,
});

const brlExactFormatter = new Intl.NumberFormat('pt-BR', {
  style: 'currency',
  currency: 'BRL',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

export function formatCurrencyBRL(value: number | null | undefined, exact = false): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return 'A definir';
  }
  return exact ? brlExactFormatter.format(value) : brlFormatter.format(value);
}

export function formatDateTimeBR(isoDate: string | null | undefined): string {
  if (!isoDate) return '—';
  const parsed = new Date(isoDate);
  if (Number.isNaN(parsed.getTime())) return '—';
  return parsed.toLocaleString('pt-BR', {
    day: '2-digit',
    month: '2-digit',
    year: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function formatTimeBR(isoDate: string | null | undefined): string {
  if (!isoDate) return '';
  const parsed = new Date(isoDate);
  if (Number.isNaN(parsed.getTime())) return '';
  return parsed.toLocaleTimeString('pt-BR', {
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function getEtapaLabel(etapa: EtapaFunil): string {
  switch (etapa) {
    case 'NOVO_CONTATO':
      return 'Novo Contato';
    case 'QUALIFICACAO':
      return 'Qualificação';
    case 'NEGOCIACAO':
      return 'Negociação';
    case 'FECHAMENTO':
      return 'Fechamento';
  }
}

export function getDesfechoLabel(desfecho: DesfechoLead): string {
  switch (desfecho) {
    case 'EM_ANDAMENTO':
      return 'Em Andamento';
    case 'GANHO':
      return 'Negócio Ganho';
    case 'PERDIDO':
      return 'Perdido';
    case 'CONGELADO_CADENCIA':
      return 'Cadência Congelada';
  }
}

export function getControleLabel(controle: ControleAtendimento): string {
  switch (controle) {
    case 'PILOTO_IA':
      return 'Piloto IA';
    case 'TRANSBORDO_SOLICITADO':
      return 'Aguardando Closer';
    case 'HUMANO_ASSUMIU':
      return 'Closer Ativo';
  }
}

export function getTemperaturaLabel(temp: TemperaturaLead): string {
  switch (temp) {
    case 'QUENTE':
      return 'Quente';
    case 'MORNO':
      return 'Morno';
    case 'FRIO':
      return 'Frio';
  }
}

export function getCanalLabel(canal: string | null | undefined): string {
  if (!canal) return 'WhatsApp Direto';
  return canal
    .replace(/_/g, ' ')
    .toLowerCase()
    .replace(/\b\w/g, (l) => l.toUpperCase());
}

