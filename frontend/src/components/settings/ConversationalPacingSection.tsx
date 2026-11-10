import React from 'react';
import type { OperacaoSettings } from '../../types/settings';

interface ConversationalPacingSectionProps {
  settings: OperacaoSettings;
  onPatch: (updater: (prev: OperacaoSettings) => OperacaoSettings) => void;
}

export const ConversationalPacingSection: React.FC<ConversationalPacingSectionProps> = ({
  settings,
  onPatch,
}) => {
  const { pacing } = settings;

  return (
    <section className="surface-panel">
      <div className="panel-header">
        <div>
          <div className="eyebrow eyebrow-ai">HUMANIZAÇÃO &amp; FINOPS ANTI-LOOP</div>
          <h2 className="section-title" style={{ marginTop: '2px' }}>
            Debounce, Pacing de Digitação &amp; Limiares Conversacionais
          </h2>
        </div>
      </div>

      <div className="panel-body" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
          <div>
            <label className="eyebrow" style={{ display: 'block', marginBottom: '6px' }}>
              JANELA DE DEBOUNCE (SEGUNDOS)
            </label>
            <input
              type="number"
              min="1"
              max="15"
              step="0.5"
              className="field-input mono-metric"
              value={settings.debounce_segundos}
              onChange={(e) =>
                onPatch((prev) => ({
                  ...prev,
                  debounce_segundos: Math.min(15, Math.max(1, Number.parseFloat(e.target.value) || 4.5)),
                }))
              }
            />
          </div>

          <div>
            <label className="eyebrow" style={{ display: 'block', marginBottom: '6px' }}>
              DELAY BASE DE DIGITAÇÃO (MS)
            </label>
            <input
              type="number"
              min="250"
              max="10000"
              step="250"
              className="field-input mono-metric"
              value={pacing.delay_base_ms}
              onChange={(e) =>
                onPatch((prev) => ({
                  ...prev,
                  pacing: {
                    ...prev.pacing,
                    delay_base_ms: Math.max(250, Number.parseInt(e.target.value, 10) || 1500),
                  },
                }))
              }
            />
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px' }}>
          <div>
            <label className="eyebrow" style={{ display: 'block', marginBottom: '6px' }}>
              LIMIAR PROATIVO (MSGS)
            </label>
            <input
              type="number"
              min="4"
              max="40"
              className="field-input mono-metric"
              value={pacing.limiar_proativo}
              onChange={(e) =>
                onPatch((prev) => ({
                  ...prev,
                  pacing: {
                    ...prev.pacing,
                    limiar_proativo: Number.parseInt(e.target.value, 10) || 10,
                  },
                }))
              }
            />
          </div>

          <div>
            <label className="eyebrow" style={{ display: 'block', marginBottom: '6px' }}>
              LIMIAR DECISIVO (MSGS)
            </label>
            <input
              type="number"
              min="8"
              max="60"
              className="field-input mono-metric"
              value={pacing.limiar_decisivo}
              onChange={(e) =>
                onPatch((prev) => ({
                  ...prev,
                  pacing: {
                    ...prev.pacing,
                    limiar_decisivo: Number.parseInt(e.target.value, 10) || 20,
                  },
                }))
              }
            />
          </div>

          <div>
            <label className="eyebrow" style={{ display: 'block', marginBottom: '6px' }}>
              TETO FINOPS (MSGS)
            </label>
            <input
              type="number"
              min="12"
              max="100"
              className="field-input mono-metric"
              value={pacing.limiar_max_finops}
              onChange={(e) =>
                onPatch((prev) => ({
                  ...prev,
                  pacing: {
                    ...prev.pacing,
                    limiar_max_finops: Number.parseInt(e.target.value, 10) || 30,
                  },
                }))
              }
            />
          </div>
        </div>

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '18px' }}>
          <label style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={settings.modo_24h_inbound}
              onChange={(e) =>
                onPatch((prev) => ({ ...prev, modo_24h_inbound: e.target.checked }))
              }
            />
            <span style={{ fontSize: '13px' }}>Atendimento Inbound 24/7 (inclusive madrugada/domingo)</span>
          </label>

          <label style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={pacing.simular_digitacao}
              onChange={(e) =>
                onPatch((prev) => ({
                  ...prev,
                  pacing: { ...prev.pacing, simular_digitacao: e.target.checked },
                }))
              }
            />
            <span style={{ fontSize: '13px' }}>Simular presença &ldquo;digitando...&rdquo; no WhatsApp</span>
          </label>
        </div>

        <div>
          <label className="eyebrow" style={{ display: 'block', marginBottom: '6px' }}>
            MENSAGEM DE ENCERRAMENTO CORDIAL POR ESTAGNAÇÃO
          </label>
          <textarea
            rows={2}
            className="field-textarea"
            value={settings.mensagem_inatividade ?? ''}
            onChange={(e) =>
              onPatch((prev) => ({ ...prev, mensagem_inatividade: e.target.value }))
            }
          />
        </div>
      </div>
    </section>
  );
};

