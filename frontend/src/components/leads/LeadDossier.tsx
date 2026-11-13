import React, { useState } from 'react';
import { mapLeadToQualificationViewModel } from '../../mappers/leadMapper';
import type { FollowupAgendado, Interacao, Lead } from '../../types/telemetry';
import {
  getControleLabel,
  getDesfechoLabel,
  getEtapaLabel,
  getTemperaturaLabel,
} from '../../utils/formatters';
import { DossierFinancialTab } from './DossierFinancialTab';
import { DossierStrategyTab } from './DossierStrategyTab';
import { DossierTechnicalTab } from './DossierTechnicalTab';
import { DossierWhatsAppTab } from './DossierWhatsAppTab';

type DossierTabId = 'strategy' | 'whatsapp' | 'financial' | 'technical';

interface LeadDossierProps {
  lead: Lead | null;
  interactions: Interacao[];
  followups: FollowupAgendado[];
  isLoadingThread: boolean;
  isMutating: boolean;
  onRunAudit: () => Promise<void>;
  onOpenHandoverModal: (mode: 'assume' | 'return') => void;
  onRequestManualHandover: () => Promise<void>;
  onOpenSingleBriefing: () => void;
  onSendHumanMessage: (texto: string) => Promise<void>;
  onRequestResetMemory: () => void;
  onRequestDeleteLead: () => void;
}

export const LeadDossier: React.FC<LeadDossierProps> = ({
  lead,
  interactions,
  followups,
  isLoadingThread,
  isMutating,
  onRunAudit,
  onOpenHandoverModal,
  onRequestManualHandover,
  onOpenSingleBriefing,
  onSendHumanMessage,
  onRequestResetMemory,
  onRequestDeleteLead,
}) => {
  const [activeSubTab, setActiveSubTab] = useState<DossierTabId>('strategy');

  if (!lead) {
    return (
      <section className="dossier-panel" style={{ padding: '48px 24px', textAlign: 'center' }}>
        <div className="eyebrow">NENHUM LEAD SELECIONADO</div>
        <p style={{ color: 'var(--text-muted)', marginTop: '8px' }}>
          Selecione uma negociação na coluna à esquerda para inspecionar o Dossiê Executivo e operar o atendimento.
        </p>
      </section>
    );
  }

  const vm = mapLeadToQualificationViewModel(lead);

  const desfechoClass =
    lead.desfecho === 'GANHO'
      ? 'badge-won'
      : lead.desfecho === 'PERDIDO' || lead.desfecho === 'CONGELADO_CADENCIA'
        ? 'badge-closer'
        : 'badge-ai';

  return (
    <section className="dossier-panel" aria-label="Dossiê Comercial do Lead">
      {/* Cabeçalho Institucional do Dossiê */}
      <div
        className="panel-header"
        style={{
          flexWrap: 'wrap',
          alignItems: 'flex-start',
          padding: '20px 24px',
        }}
      >
        <div>
          <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px' }}>
            <span className={`badge ${desfechoClass}`}>{getDesfechoLabel(lead.desfecho)}</span>
            <span className="badge">{getEtapaLabel(lead.etapa_funil)}</span>
            <span
              className={`badge ${
                lead.temperatura === 'QUENTE'
                  ? 'badge-closer'
                  : lead.temperatura === 'MORNO'
                    ? 'badge-warm'
                    : 'badge-muted'
              }`}
            >
              {getTemperaturaLabel(lead.temperatura)}
            </span>
            <span
              className={`badge ${
                lead.controle === 'PILOTO_IA' ? 'badge-ai' : 'badge-closer'
              }`}
            >
              {getControleLabel(lead.controle)}
            </span>
          </div>

          <h2 className="headline-display" style={{ fontSize: '24px', marginTop: '10px' }}>
            {vm.displayName}
          </h2>
          <div className="mono-metric" style={{ color: 'var(--text-muted)', fontSize: '13px', marginTop: '2px' }}>
            {lead.telefone} · Valor estimado: <strong style={{ color: 'var(--text-primary)' }}>{vm.valorEstimadoFormatado}</strong>
          </div>
        </div>

        {/* Barra de Ações Reais */}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
          <button
            type="button"
            className="btn btn-sm"
            onClick={() => void onRunAudit()}
            disabled={isMutating}
            title="Acionar Agente Auditor (GPT-4o-mini) para gerar/atualizar Dossiê Executivo"
          >
            {isMutating ? 'Processando...' : 'Auditar Dossiê IA'}
          </button>

          {lead.controle === 'PILOTO_IA' && (
            <button
              type="button"
              className="btn btn-sm btn-outline-closer"
              onClick={() => void onRequestManualHandover()}
              disabled={isMutating}
            >
              Solicitar Transbordo
            </button>
          )}

          {lead.controle !== 'HUMANO_ASSUMIU' && (
            <button
              type="button"
              className="btn btn-sm btn-closer"
              onClick={() => onOpenHandoverModal('assume')}
              disabled={isMutating}
            >
              Assumir Atendimento
            </button>
          )}

          <button
            type="button"
            className="btn btn-sm btn-ai"
            onClick={() => onOpenHandoverModal('return')}
            disabled={isMutating}
            title="Devolver condução para o Piloto Automático de IA (ou enviar diretriz tática / atualizar etapa)"
          >
            Devolver para IA
          </button>

          <button type="button" className="btn btn-sm" onClick={onOpenSingleBriefing}>
            Exportar PDF
          </button>
        </div>
      </div>

      {/* Sub-Abas do Dossiê */}
      <div className="dossier-subtabs" role="tablist">
        <button
          type="button"
          role="tab"
          aria-selected={activeSubTab === 'strategy'}
          className={`dossier-subtab-btn ${activeSubTab === 'strategy' ? 'is-active' : ''}`}
          onClick={() => setActiveSubTab('strategy')}
        >
          Estratégia &amp; Qualificação
        </button>

        <button
          type="button"
          role="tab"
          aria-selected={activeSubTab === 'whatsapp'}
          className={`dossier-subtab-btn ${activeSubTab === 'whatsapp' ? 'is-active' : ''}`}
          onClick={() => setActiveSubTab('whatsapp')}
        >
          WhatsApp &amp; Resposta ({interactions.length})
        </button>

        <button
          type="button"
          role="tab"
          aria-selected={activeSubTab === 'financial'}
          className={`dossier-subtab-btn ${activeSubTab === 'financial' ? 'is-active' : ''}`}
          onClick={() => setActiveSubTab('financial')}
        >
          Financeiro &amp; Cadência ({followups.length})
        </button>

        <button
          type="button"
          role="tab"
          aria-selected={activeSubTab === 'technical'}
          className={`dossier-subtab-btn ${activeSubTab === 'technical' ? 'is-active' : ''}`}
          onClick={() => setActiveSubTab('technical')}
        >
          Governança &amp; Registro
        </button>
      </div>

      {/* Corpo da Aba Ativa */}
      <div className="panel-body">
        {activeSubTab === 'strategy' && <DossierStrategyTab lead={lead} vm={vm} />}

        {activeSubTab === 'whatsapp' && (
          <DossierWhatsAppTab
            lead={lead}
            interactions={interactions}
            isLoading={isLoadingThread}
            isSending={isMutating}
            onSendHumanMessage={onSendHumanMessage}
          />
        )}

        {activeSubTab === 'financial' && (
          <DossierFinancialTab lead={lead} vm={vm} followups={followups} />
        )}

        {activeSubTab === 'technical' && (
          <DossierTechnicalTab
            lead={lead}
            isBusy={isMutating}
            onRequestResetMemory={onRequestResetMemory}
            onRequestDeleteLead={onRequestDeleteLead}
          />
        )}
      </div>
    </section>
  );
};
