import React from 'react';
import type { OperacaoSettings } from '../../types/settings';

interface CadenceAndHoursSectionProps {
  settings: OperacaoSettings;
  onPatch: (updater: (prev: OperacaoSettings) => OperacaoSettings) => void;
}

const WEEKDAYS = [
  { day: 0, label: 'Seg' },
  { day: 1, label: 'Ter' },
  { day: 2, label: 'Qua' },
  { day: 3, label: 'Qui' },
  { day: 4, label: 'Sex' },
  { day: 5, label: 'Sáb' },
  { day: 6, label: 'Dom' },
];

export const CadenceAndHoursSection: React.FC<CadenceAndHoursSectionProps> = ({
  settings,
  onPatch,
}) => {
  const { cadencia, horario_comercial } = settings;
  const toques = cadencia.intervalos_toques?.length >= 3 ? cadencia.intervalos_toques : [2, 24, 72];

  const updateTouchHour = (idx: number, val: number) => {
    const next = [...toques];
    next[idx] = Math.max(0.5, val);
    onPatch((prev) => ({
      ...prev,
      cadencia: {
        ...prev.cadencia,
        intervalos_toques: next,
        intervalo_horas: Math.round(next[1] ?? 24),
      },
    }));
  };

  const toggleDay = (day: number) => {
    const exists = horario_comercial.dias_semana.includes(day);
    const updatedDays = exists
      ? horario_comercial.dias_semana.filter((d) => d !== day)
      : [...horario_comercial.dias_semana, day].sort((a, b) => a - b);

    onPatch((prev) => ({
      ...prev,
      horario_comercial: {
        ...prev.horario_comercial,
        dias_semana: updatedDays,
      },
    }));
  };

  return (
    <section className="surface-panel">
      <div className="panel-header">
        <div>
          <div className="eyebrow">MOTOR DE CADÊNCIA &amp; BLINDAGEM ANTI-BAN</div>
          <h2 className="section-title" style={{ marginTop: '2px' }}>
            Intervalos de Resgate &amp; Janela Comercial (Brasília)
          </h2>
        </div>
      </div>

      <div className="panel-body" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '10px' }}>
          <div>
            <label className="eyebrow" style={{ display: 'block', marginBottom: '6px' }}>
              MÁX. TOQUES
            </label>
            <input
              type="number"
              min="1"
              max="7"
              className="field-input mono-metric"
              value={cadencia.max_tentativas}
              onChange={(e) =>
                onPatch((prev) => ({
                  ...prev,
                  cadencia: {
                    ...prev.cadencia,
                    max_tentativas: Math.min(7, Math.max(1, Number.parseInt(e.target.value, 10) || 3)),
                  },
                }))
              }
            />
          </div>

          <div>
            <label className="eyebrow" style={{ display: 'block', marginBottom: '6px' }}>
              1º TOQUE (H)
            </label>
            <input
              type="number"
              min="0.5"
              step="0.5"
              className="field-input mono-metric"
              value={toques[0]}
              onChange={(e) => updateTouchHour(0, Number.parseFloat(e.target.value) || 2)}
            />
          </div>

          <div>
            <label className="eyebrow" style={{ display: 'block', marginBottom: '6px' }}>
              2º TOQUE (H)
            </label>
            <input
              type="number"
              min="1"
              step="1"
              className="field-input mono-metric"
              value={toques[1]}
              onChange={(e) => updateTouchHour(1, Number.parseFloat(e.target.value) || 24)}
            />
          </div>

          <div>
            <label className="eyebrow" style={{ display: 'block', marginBottom: '6px' }}>
              3º TOQUE (H)
            </label>
            <input
              type="number"
              min="1"
              step="1"
              className="field-input mono-metric"
              value={toques[2]}
              onChange={(e) => updateTouchHour(2, Number.parseFloat(e.target.value) || 72)}
            />
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
          <div>
            <label className="eyebrow" style={{ display: 'block', marginBottom: '6px' }}>
              ABERTURA DO EXPEDIENTE (HORA 0-23)
            </label>
            <input
              type="number"
              min="0"
              max="23"
              className="field-input mono-metric"
              value={horario_comercial.inicio_hora}
              onChange={(e) =>
                onPatch((prev) => ({
                  ...prev,
                  horario_comercial: {
                    ...prev.horario_comercial,
                    inicio_hora: Math.min(23, Math.max(0, Number.parseInt(e.target.value, 10) || 8)),
                  },
                }))
              }
            />
          </div>

          <div>
            <label className="eyebrow" style={{ display: 'block', marginBottom: '6px' }}>
              FECHAMENTO DO EXPEDIENTE (HORA 0-23)
            </label>
            <input
              type="number"
              min="0"
              max="23"
              className="field-input mono-metric"
              value={horario_comercial.fim_hora}
              onChange={(e) =>
                onPatch((prev) => ({
                  ...prev,
                  horario_comercial: {
                    ...prev.horario_comercial,
                    fim_hora: Math.min(23, Math.max(0, Number.parseInt(e.target.value, 10) || 18)),
                  },
                }))
              }
            />
          </div>
        </div>

        <div>
          <label className="eyebrow" style={{ display: 'block', marginBottom: '8px' }}>
            DIAS ATIVOS PARA DISPARO DE CADÊNCIA
          </label>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
            {WEEKDAYS.map((w) => {
              const active = horario_comercial.dias_semana.includes(w.day);
              return (
                <button
                  key={w.day}
                  type="button"
                  className={`btn btn-sm ${active ? 'btn-ai' : ''}`}
                  onClick={() => toggleDay(w.day)}
                >
                  {w.label}
                </button>
              );
            })}
          </div>
        </div>

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '18px' }}>
          <label style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={cadencia.respeitar_horario_comercial}
              onChange={(e) =>
                onPatch((prev) => ({
                  ...prev,
                  cadencia: { ...prev.cadencia, respeitar_horario_comercial: e.target.checked },
                }))
              }
            />
            <span style={{ fontSize: '13px' }}>Postergar follow-ups noturnos para o próximo dia útil</span>
          </label>
        </div>
      </div>
    </section>
  );
};

