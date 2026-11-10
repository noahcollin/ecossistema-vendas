import React from 'react';
import { FunnelConduitSection } from '../components/overview/FunnelConduitSection';
import { HeroThesisSection } from '../components/overview/HeroThesisSection';
import { PriorityDealsLedger } from '../components/overview/PriorityDealsLedger';
import { TractionAndObjectionsSection } from '../components/overview/TractionAndObjectionsSection';
import { useOverviewData } from '../hooks/useOverviewData';

interface OverviewViewProps {
  onOpenLead: (leadId: number) => void;
  onOpenLeadsTab: () => void;
}

export const OverviewView: React.FC<OverviewViewProps> = ({
  onOpenLead,
  onOpenLeadsTab,
}) => {
  const {
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
  } = useOverviewData();

  if (isLoading && !overview) {
    return (
      <div className="surface-panel panel-body" style={{ textAlign: 'center', padding: '56px' }}>
        <div className="eyebrow eyebrow-ai">SINCRONIZANDO TELEMETRIA</div>
        <p style={{ color: 'var(--text-muted)', marginTop: '8px' }}>
          Carregando indicadores financeiros, funil 4D e histórico analítico...
        </p>
      </div>
    );
  }

  if (error && !overview) {
    return (
      <div className="alert-banner is-error">
        <span>{error}</span>
        <button type="button" className="btn btn-sm" onClick={() => void reload()}>
          Tentar Novamente
        </button>
      </div>
    );
  }

  if (!overview) return null;

  return (
    <div className="overview-stack">
      {error && (
        <div className="alert-banner is-warning">
          <span>Aviso de sincronização: {error}</span>
          <button type="button" className="btn btn-sm" onClick={() => void reload()}>
            Atualizar
          </button>
        </div>
      )}

      <HeroThesisSection
        overview={overview}
        leads={leads}
        pendingHandoverCount={pendingHandoverCount}
        onNavigateToHandover={onOpenLeadsTab}
      />

      <FunnelConduitSection funil={overview.funil} />

      <TractionAndObjectionsSection
        tractionData={tractionData}
        timeRange={timeRange}
        onChangeTimeRange={setTimeRange}
        funil={overview.funil}
        aquisicao={overview.aquisicao}
        perdas={overview.perdas}
      />

      <PriorityDealsLedger
        deals={priorityDeals}
        onOpenLead={onOpenLead}
        onOpenAllLeads={onOpenLeadsTab}
      />
    </div>
  );
};
