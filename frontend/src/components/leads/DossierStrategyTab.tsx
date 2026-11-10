import React from 'react';
import type { LeadQualificationViewModel } from '../../mappers/leadMapper';
import type { Lead } from '../../types/telemetry';

interface DossierStrategyTabProps {
  lead: Lead;
  vm: LeadQualificationViewModel;
}

export const DossierStrategyTab: React.FC<DossierStrategyTabProps> = ({ lead, vm }) => {
  const dossie = lead.dossie_comercial;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
      {/* Síntese Cognitiva / História do Lead */}
      <div className="surface-elevated" style={{ padding: '18px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
          <span className="eyebrow eyebrow-ai">MEMÓRIA EXECUTIVA &amp; CONTEXTO DO NEGÓCIO</span>
          {dossie && (
            <span className="badge badge-ai">
              NOTA IA: {dossie.nota_atendimento_ia.toFixed(1)}/10 · REATIVAÇÃO: {dossie.potencial_reativacao}
            </span>
          )}
        </div>
        <p style={{ color: 'var(--text-secondary)', fontSize: '13.5px', lineHeight: 1.6 }}>
          {vm.resumoExecutivo}
        </p>
      </div>

      {/* Recomendação Tática do Agente Auditor (Quando Auditado) */}
      {dossie?.proximo_passo && (
        <div
          className="surface-panel"
          style={{
            padding: '16px 18px',
            borderLeft: '3px solid var(--red-closer)',
            background: 'rgba(255, 30, 70, 0.04)',
          }}
        >
          <div className="eyebrow eyebrow-closer">PRÓXIMO PASSO RECOMENDADO AO CLOSER</div>
          <div style={{ fontWeight: 700, fontSize: '14px', marginTop: '6px' }}>
            {dossie.proximo_passo.acao_sugerida}{' '}
            <span style={{ color: 'var(--text-muted)', fontWeight: 500 }}>
              ({dossie.proximo_passo.quando_retomar})
            </span>
          </div>
          <p style={{ color: 'var(--text-secondary)', fontSize: '13px', marginTop: '6px' }}>
            <strong>Dica de Ouro:</strong> {dossie.proximo_passo.dica_de_ouro}
          </p>
        </div>
      )}

      {/* Matriz de Qualificação Estruturada */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
          gap: '12px',
        }}
      >
        <div className="surface-panel" style={{ padding: '14px 16px' }}>
          <div className="eyebrow">SEGMENTO &amp; CIDADE</div>
          <div style={{ fontWeight: 600, marginTop: '4px' }}>
            {vm.segmento} · {vm.cidade}
          </div>
        </div>

        <div className="surface-panel" style={{ padding: '14px 16px' }}>
          <div className="eyebrow">PAPEL &amp; PODER DE DECISÃO</div>
          <div style={{ fontWeight: 600, marginTop: '4px' }}>
            {vm.cargo} ({vm.decisorLabel})
          </div>
        </div>

        <div className="surface-panel" style={{ padding: '14px 16px' }}>
          <div className="eyebrow">PORTE DA EQUIPE</div>
          <div style={{ fontWeight: 600, marginTop: '4px' }}>{vm.tamanhoEquipe}</div>
        </div>

        <div className="surface-panel" style={{ padding: '14px 16px' }}>
          <div className="eyebrow">SOLUÇÃO DE INTERESSE</div>
          <div style={{ fontWeight: 600, marginTop: '4px' }}>{vm.solucaoInteresse}</div>
        </div>

        <div className="surface-panel" style={{ padding: '14px 16px', gridColumn: '1 / -1' }}>
          <div className="eyebrow">DOR / GARGALO OPERACIONAL MAPEADO</div>
          <div style={{ fontWeight: 600, marginTop: '4px', color: 'var(--text-primary)' }}>
            {vm.dorPrincipal}
          </div>
        </div>
      </div>

      {/* Objeções & Sinais Positivos/Atritos */}
      {(vm.objecoes.length > 0 || (dossie && (dossie.o_que_agradou.length > 0 || dossie.pontos_de_atrito_e_queixas.length > 0))) && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '12px' }}>
          {dossie && dossie.o_que_agradou.length > 0 && (
            <div className="surface-panel" style={{ padding: '14px 16px' }}>
              <div className="eyebrow" style={{ color: 'var(--emerald-won)', marginBottom: '8px' }}>
                PONTOS DE ADERÊNCIA (O QUE AGRADOU)
              </div>
              <ul style={{ paddingLeft: '18px', color: 'var(--text-secondary)', fontSize: '13px' }}>
                {dossie.o_que_agradou.map((item, idx) => (
                  <li key={idx} style={{ marginBottom: '4px' }}>{item}</li>
                ))}
              </ul>
            </div>
          )}

          {(vm.objecoes.length > 0 || (dossie && dossie.pontos_de_atrito_e_queixas.length > 0)) && (
            <div className="surface-panel" style={{ padding: '14px 16px' }}>
              <div className="eyebrow eyebrow-closer" style={{ marginBottom: '8px' }}>
                OBJEÇÕES &amp; PONTOS DE ATRITO
              </div>
              <ul style={{ paddingLeft: '18px', color: 'var(--text-secondary)', fontSize: '13px' }}>
                {[...vm.objecoes, ...(dossie?.pontos_de_atrito_e_queixas ?? [])].map((item, idx) => (
                  <li key={idx} style={{ marginBottom: '4px' }}>{item}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

