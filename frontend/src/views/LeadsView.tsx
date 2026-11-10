import React, { useState } from 'react';
import { LeadDossier } from '../components/leads/LeadDossier';
import { LeadsFilterBar } from '../components/leads/LeadsFilterBar';
import { LeadsListColumn } from '../components/leads/LeadsListColumn';
import { BriefingModal } from '../components/modals/BriefingModal';
import { TransbordoModal } from '../components/modals/TransbordoModal';
import { TypedConfirmModal } from '../components/modals/TypedConfirmModal';
import { useLeadsWorkspace } from '../hooks/useLeadsWorkspace';

interface LeadsViewProps {
  selectedLeadId: number | null;
  onSelectLeadId: (leadId: number | null) => void;
}

export const LeadsView: React.FC<LeadsViewProps> = ({
  selectedLeadId,
  onSelectLeadId,
}) => {
  const {
    leads,
    filteredLeads,
    activeLead,
    interactions,
    followups,
    filters,
    setFilters,
    isLoadingLeads,
    isLoadingThread,
    isMutating,
    banner,
    clearBanner,
    selectLead,
    reloadLeads,
    runLeadAudit,
    assumeHumanControl,
    returnToAiPilot,
    requestManualHandover,
    sendHumanWhatsAppMessage,
    resetActiveLeadMemory,
    removeActiveLead,
  } = useLeadsWorkspace(selectedLeadId, onSelectLeadId);

  const [isHandoverOpen, setIsHandoverOpen] = useState(false);
  const [briefingMode, setBriefingMode] = useState<'single' | 'batch' | null>(null);
  const [confirmAction, setConfirmAction] = useState<'reset' | 'delete' | null>(null);

  return (
    <div>
      {banner && (
        <div className={`alert-banner is-${banner.kind}`}>
          <span>{banner.message}</span>
          <button type="button" className="btn btn-sm btn-ghost" onClick={clearBanner}>
            Fechar
          </button>
        </div>
      )}

      <LeadsFilterBar
        filters={filters}
        onChangeFilters={setFilters}
        totalCount={leads.length}
        filteredCount={filteredLeads.length}
        isLoading={isLoadingLeads}
        onRefresh={() => void reloadLeads()}
        onOpenBatchBriefing={() => setBriefingMode('batch')}
      />

      <div className="leads-workspace">
        <LeadsListColumn
          leads={filteredLeads}
          activeLeadId={activeLead?.id ?? null}
          isLoading={isLoadingLeads}
          onSelectLead={selectLead}
        />

        <LeadDossier
          lead={activeLead}
          interactions={interactions}
          followups={followups}
          isLoadingThread={isLoadingThread}
          isMutating={isMutating}
          onRunAudit={runLeadAudit}
          onOpenHandoverModal={() => setIsHandoverOpen(true)}
          onRequestManualHandover={() => requestManualHandover()}
          onOpenSingleBriefing={() => setBriefingMode('single')}
          onSendHumanMessage={(texto) => sendHumanWhatsAppMessage(texto)}
          onRequestResetMemory={() => setConfirmAction('reset')}
          onRequestDeleteLead={() => setConfirmAction('delete')}
        />
      </div>

      <TransbordoModal
        isOpen={isHandoverOpen}
        lead={activeLead}
        isBusy={isMutating}
        onClose={() => setIsHandoverOpen(false)}
        onAssumeHuman={assumeHumanControl}
        onReturnToAi={returnToAiPilot}
      />

      <BriefingModal
        isOpen={briefingMode !== null}
        mode={briefingMode ?? 'single'}
        lead={activeLead}
        leads={filteredLeads.length > 0 ? filteredLeads : leads}
        onClose={() => setBriefingMode(null)}
      />

      <TypedConfirmModal
        isOpen={confirmAction === 'reset'}
        title="Reiniciar Memória e Conversa do Lead"
        description={`Esta ação apagará as mensagens trocadas com ${activeLead?.nome || activeLead?.telefone || 'o lead'}, cancelará follow-ups pendentes e retornará o estágio para NOVO_CONTATO.`}
        confirmWord="RESETAR"
        confirmButtonLabel="Reiniciar Conversa"
        variant="ai"
        isBusy={isMutating}
        onCancel={() => setConfirmAction(null)}
        onConfirm={async () => {
          await resetActiveLeadMemory();
          setConfirmAction(null);
        }}
      />

      <TypedConfirmModal
        isOpen={confirmAction === 'delete'}
        title="Excluir Lead Permanentemente"
        description={`Esta ação removerá definitivamente o cadastro de ${activeLead?.nome || activeLead?.telefone || 'o lead'} e todo o seu histórico do PostgreSQL e Redis.`}
        confirmWord="EXCLUIR"
        confirmButtonLabel="Excluir Permanentemente"
        variant="closer"
        isBusy={isMutating}
        onCancel={() => setConfirmAction(null)}
        onConfirm={async () => {
          await removeActiveLead();
          setConfirmAction(null);
        }}
      />
    </div>
  );
};
