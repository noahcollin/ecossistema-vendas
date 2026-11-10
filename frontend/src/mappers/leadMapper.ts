import type { Lead } from '../types/telemetry';
import { formatCurrencyBRL } from '../utils/formatters';

export interface LeadQualificationViewModel {
  displayName: string;
  segmento: string;
  cargo: string;
  tamanhoEquipe: string;
  cidade: string;
  solucaoInteresse: string;
  dorPrincipal: string;
  gargaloPrincipal: string;
  orcamentoDeclarado: string;
  prazoImplementacao: string;
  ferramentaAtual: string;
  volumeLeadsMes: string;
  decisorLabel: string;
  objecoes: string[];
  resumoExecutivo: string;
  valorEstimadoFormatado: string;
  requiresHumanAttention: boolean;
  isAiPilot: boolean;
}

/**
 * Anti-Corruption Mapper: traduz o payload aninhado `dados_qualificacao` e `dossie_comercial`
 * do Backend para um ViewModel plano, sem jamais inventar valores monetários fictícios.
 */
export function mapLeadToQualificationViewModel(lead: Lead): LeadQualificationViewModel {
  const dq = lead.dados_qualificacao ?? {};
  const dossie = lead.dossie_comercial;

  const decisorLabel =
    dq.decisor === true
      ? 'Sim (Decisor)'
      : dq.decisor === false
        ? 'Influenciador / Equipe'
        : 'Em validação';

  const dorPrincipal =
    dq.dor_ou_necessidade ||
    dq.gargalo_principal ||
    'Ainda não explicitada pelo lead';

  const resumoExecutivo =
    dossie?.historia_do_lead ||
    lead.resumo_perfil ||
    'Aguardando consolidação cognitiva das primeiras interações.';

  return {
    displayName: lead.nome?.trim() || 'Contato sem nome',
    segmento: dq.segmento || 'Não informado',
    cargo: dq.cargo_ou_papel || 'Não informado',
    tamanhoEquipe: dq.tamanho_equipe || 'Não informado',
    cidade: dq.cidade || 'Não informada',
    solucaoInteresse: dq.solucao_interesse || 'Em diagnóstico consultivo',
    dorPrincipal,
    gargaloPrincipal: dq.gargalo_principal || dorPrincipal,
    orcamentoDeclarado: dq.orcamento_estimado || 'Não declarado',
    prazoImplementacao: dq.prazo_implementacao || dq.urgencia || 'A mapear',
    ferramentaAtual: dq.ferramenta_atual || 'Não informada',
    volumeLeadsMes: dq.volume_leads_mes || 'Não informado',
    decisorLabel,
    objecoes: Array.isArray(dq.objecoes_detectadas) ? dq.objecoes_detectadas : [],
    resumoExecutivo,
    valorEstimadoFormatado: formatCurrencyBRL(lead.valor_estimado),
    requiresHumanAttention: lead.controle === 'TRANSBORDO_SOLICITADO',
    isAiPilot: lead.controle === 'PILOTO_IA',
  };
}

