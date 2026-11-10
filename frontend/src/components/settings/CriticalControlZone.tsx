import React from 'react';

interface CriticalControlZoneProps {
  iaSilenciadaGlobal: boolean;
  isBusy: boolean;
  onRequestToggleKillSwitch: () => void;
  onRequestPurgeRedis: () => void;
}

export const CriticalControlZone: React.FC<CriticalControlZoneProps> = ({
  iaSilenciadaGlobal,
  isBusy,
  onRequestToggleKillSwitch,
  onRequestPurgeRedis,
}) => {
  return (
    <section
      className="surface-panel"
      style={{
        borderColor: 'var(--red-closer-border)',
        background: 'rgba(255, 30, 70, 0.03)',
      }}
    >
      <div className="panel-header" style={{ borderBottomColor: 'var(--red-closer-border)' }}>
        <div>
          <div className="eyebrow eyebrow-closer">ZONA CRÍTICA DE GOVERNANÇA OPERACIONAL</div>
          <h2 className="section-title" style={{ marginTop: '2px' }}>
            Kill-Switch Global &amp; Expurgo de Filas Voláteis
          </h2>
        </div>

        <span className={`badge ${iaSilenciadaGlobal ? 'badge-closer' : 'badge-won'}`}>
          {iaSilenciadaGlobal ? 'IA GLOBALMENTE PAUSADA' : 'IA AUTÔNOMA ATIVA'}
        </span>
      </div>

      <div
        className="panel-body"
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
          gap: '16px',
        }}
      >
        <div
          className="surface-elevated"
          style={{
            padding: '16px',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
            gap: '14px',
          }}
        >
          <div>
            <div style={{ fontWeight: 700, fontSize: '14px' }}>
              {iaSilenciadaGlobal
                ? 'Retomar Operação Autônoma da IA'
                : 'Acionar Kill-Switch Global (Pausar IA)'}
            </div>
            <p style={{ color: 'var(--text-muted)', fontSize: '12.5px', marginTop: '6px' }}>
              {iaSilenciadaGlobal
                ? 'Reativa imediatamente o Agente Closer e o Motor de Cadência para responder leads em PILOTO_IA.'
                : 'Suspende imediatamente respostas autônomas e disparos de follow-up. Todas as mensagens de clientes continuam sendo gravadas no PostgreSQL.'}
            </p>
          </div>

          <button
            type="button"
            className={`btn ${iaSilenciadaGlobal ? 'btn-ai' : 'btn-closer'}`}
            onClick={onRequestToggleKillSwitch}
            disabled={isBusy}
          >
            {iaSilenciadaGlobal ? 'Reativar Piloto IA Global' : 'Pausar Toda a IA Agora'}
          </button>
        </div>

        <div
          className="surface-elevated"
          style={{
            padding: '16px',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
            gap: '14px',
          }}
        >
          <div>
            <div style={{ fontWeight: 700, fontSize: '14px' }}>
              Expurgar Filas Voláteis do Redis (SCAN)
            </div>
            <p style={{ color: 'var(--text-muted)', fontSize: '12.5px', marginTop: '6px' }}>
              Limpa de forma não-bloqueante buffers de debounce retidos (`buffer:*`) e locks órfãos (`lock:inbound:*`) sem apagar leads ou histórico no PostgreSQL.
            </p>
          </div>

          <button
            type="button"
            className="btn btn-outline-closer"
            onClick={onRequestPurgeRedis}
            disabled={isBusy}
          >
            Expurgar Buffers Voláteis Redis
          </button>
        </div>
      </div>
    </section>
  );
};

