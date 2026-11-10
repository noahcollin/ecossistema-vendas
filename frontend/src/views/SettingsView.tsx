import React, { useState } from 'react';
import { TypedConfirmModal } from '../components/modals/TypedConfirmModal';
import { CadenceAndHoursSection } from '../components/settings/CadenceAndHoursSection';
import { ConversationalPacingSection } from '../components/settings/ConversationalPacingSection';
import { CriticalControlZone } from '../components/settings/CriticalControlZone';
import { InfrastructureHealthSection } from '../components/settings/InfrastructureHealthSection';
import { ProductCatalogSection } from '../components/settings/ProductCatalogSection';
import { useOperacaoSettings } from '../hooks/useOperacaoSettings';
import type { SystemHealthResponse } from '../types/telemetry';
import { formatDateTimeBR } from '../utils/formatters';

interface SettingsViewProps {
  health: SystemHealthResponse | null;
  onRefreshHealth: () => void;
}

export const SettingsView: React.FC<SettingsViewProps> = ({
  health,
  onRefreshHealth,
}) => {
  const {
    settings,
    isLoading,
    isSaving,
    isDirty,
    banner,
    clearBanner,
    patchLocal,
    updateProduct,
    addProduct,
    removeProduct,
    saveAllSettings,
    executeKillSwitch,
    executeRedisPurge,
  } = useOperacaoSettings(onRefreshHealth);

  const [pendingGovernanceModal, setPendingGovernanceModal] = useState<
    'kill-switch' | 'purge-redis' | null
  >(null);

  if (isLoading && settings.produtos.length === 0) {
    return (
      <div className="surface-panel panel-body" style={{ textAlign: 'center', padding: '56px' }}>
        <div className="eyebrow eyebrow-ai">CARREGANDO SALA DE MÁQUINAS</div>
        <p style={{ color: 'var(--text-muted)', marginTop: '8px' }}>
          Sincronizando catálogo de produtos, regras de cadência e governança...
        </p>
      </div>
    );
  }

  const nextKillState = !settings.ia_silenciada_global;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {banner && (
        <div className={`alert-banner is-${banner.kind}`} style={{ marginBottom: 0 }}>
          <span>{banner.message}</span>
          <button type="button" className="btn btn-sm btn-ghost" onClick={clearBanner}>
            Fechar
          </button>
        </div>
      )}

      {/* Barra Superior de Sincronização */}
      <section
        className="surface-panel"
        style={{
          padding: '16px 22px',
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '14px',
        }}
      >
        <div>
          <div className="eyebrow eyebrow-ai">SALA DE MÁQUINAS // PARÂMETROS VIVOS EM RUNTIME</div>
          <div style={{ fontSize: '13px', color: 'var(--text-muted)', marginTop: '2px' }}>
            Última sincronização:{' '}
            <span className="mono-metric">{formatDateTimeBR(settings.atualizado_em)}</span>
            {isDirty && (
              <span className="badge badge-warm" style={{ marginLeft: '10px' }}>
                ALTERAÇÕES NÃO SALVAS
              </span>
            )}
          </div>
        </div>

        <button
          type="button"
          className="btn btn-ai"
          onClick={() => void saveAllSettings()}
          disabled={isSaving}
        >
          {isSaving ? 'Sincronizando...' : 'Salvar e Aplicar em Tempo Real'}
        </button>
      </section>

      <InfrastructureHealthSection health={health} onRefreshHealth={onRefreshHealth} />

      <ProductCatalogSection
        produtos={settings.produtos}
        onUpdateProduct={updateProduct}
        onAddProduct={addProduct}
        onRemoveProduct={removeProduct}
      />

      <div className="settings-grid-2">
        <ConversationalPacingSection settings={settings} onPatch={patchLocal} />
        <CadenceAndHoursSection settings={settings} onPatch={patchLocal} />
      </div>

      <CriticalControlZone
        iaSilenciadaGlobal={settings.ia_silenciada_global}
        isBusy={isSaving}
        onRequestToggleKillSwitch={() => setPendingGovernanceModal('kill-switch')}
        onRequestPurgeRedis={() => setPendingGovernanceModal('purge-redis')}
      />

      <TypedConfirmModal
        isOpen={pendingGovernanceModal === 'kill-switch'}
        title={
          nextKillState
            ? 'Pausar Globalmente a Operação Autônoma de IA'
            : 'Retomar Operação Autônoma de IA'
        }
        description={
          nextKillState
            ? 'Ao confirmar, nenhuma resposta automática do Agente Closer nem toques de follow-up serão enviados até a reativação. As mensagens recebidas continuarão sendo salvas.'
            : 'Ao confirmar, o Agente Closer e o Motor de Cadência voltarão a operar normalmente nos leads em PILOTO_IA.'
        }
        confirmWord={nextKillState ? 'PAUSAR' : 'RETOMAR'}
        confirmButtonLabel={nextKillState ? 'Ativar Kill-Switch' : 'Desativar Kill-Switch'}
        variant={nextKillState ? 'closer' : 'ai'}
        isBusy={isSaving}
        onCancel={() => setPendingGovernanceModal(null)}
        onConfirm={async () => {
          await executeKillSwitch(nextKillState);
          setPendingGovernanceModal(null);
        }}
      />

      <TypedConfirmModal
        isOpen={pendingGovernanceModal === 'purge-redis'}
        title="Expurgar Filas Voláteis de Debounce no Redis"
        description="Esta ação removerá buffers temporários de agrupamento e locks órfãos no Redis via varredura SCAN não-bloqueante. Nenhum dado do PostgreSQL será afetado."
        confirmWord="EXPURGAR"
        confirmButtonLabel="Expurgar Filas Voláteis"
        variant="closer"
        isBusy={isSaving}
        onCancel={() => setPendingGovernanceModal(null)}
        onConfirm={async () => {
          await executeRedisPurge();
          setPendingGovernanceModal(null);
        }}
      />
    </div>
  );
};
