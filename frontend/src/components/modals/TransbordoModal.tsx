import React, { useState } from 'react';
import type { DevolverIaPayload } from '../../services/api';
import type { EtapaFunil, Lead } from '../../types/telemetry';
import { getControleLabel, getEtapaLabel } from '../../utils/formatters';

interface TransbordoModalProps {
  isOpen: boolean;
  mode?: 'assume' | 'return';
  lead: Lead | null;
  isBusy: boolean;
  onClose: () => void;
  onAssumeHuman: (atendente: string) => Promise<void>;
  onReturnToAi: (payload: DevolverIaPayload) => Promise<void>;
}

export const TransbordoModal: React.FC<TransbordoModalProps> = ({
  isOpen,
  mode,
  lead,
  isBusy,
  onClose,
  onAssumeHuman,
  onReturnToAi,
}) => {
  const [atendente, setAtendente] = useState('Closer Sênior');
  const [diretrizIa, setDiretrizIa] = useState('');
  const [etapaOverride, setEtapaOverride] = useState<'' | EtapaFunil>('');
  const [valorOverride, setValorOverride] = useState<string>('');

  if (!isOpen || !lead) return null;

  const isReturnMode = mode ? mode === 'return' : lead.controle === 'HUMANO_ASSUMIU';

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      if (isReturnMode) {
        const parsedVal = valorOverride.trim() ? Number.parseFloat(valorOverride) : undefined;
        await onReturnToAi({
          diretriz_ia: diretrizIa.trim() || undefined,
          etapa_sugerida: etapaOverride || undefined,
          valor_estimado:
            parsedVal !== undefined && Number.isFinite(parsedVal) ? parsedVal : undefined,
        });
      } else {
        await onAssumeHuman(atendente.trim() || 'Consultor Comercial');
      }
      setDiretrizIa('');
      setEtapaOverride('');
      setValorOverride('');
      onClose();
    } catch {
      // Erro já exibido no banner honesto do workspace
    }
  };

  return (
    <div className="modal-overlay" role="dialog" aria-modal="true">
      <div className="modal-card" style={{ maxWidth: '540px' }}>
        <div className="prestige-beam" />
        <div className="panel-header">
          <div>
            <div className={`eyebrow ${isReturnMode ? 'eyebrow-ai' : 'eyebrow-closer'}`}>
              GOVERNANÇA DE HANDOVER · ESTADO ATUAL: {getControleLabel(lead.controle).toUpperCase()}
            </div>
            <h2 className="section-title" style={{ marginTop: '4px' }}>
              {isReturnMode
                ? 'Devolver Condução ao Piloto Automático de IA'
                : 'Assumir Condução Humana Direta (Closer)'}
            </h2>
          </div>
          <button type="button" className="btn btn-sm btn-ghost" onClick={onClose}>
            Fechar
          </button>
        </div>

        <form onSubmit={handleSubmit} className="panel-body" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {isReturnMode ? (
            <>
              <p style={{ color: 'var(--text-secondary)', fontSize: '13.5px' }}>
                A IA (&ldquo;Seu Zé&rdquo;) retomará o atendimento de{' '}
                <strong>{lead.nome || lead.telefone}</strong> e reativará a cadência temporal caso o negócio siga em andamento.
              </p>

              <div>
                <label className="eyebrow" style={{ display: 'block', marginBottom: '6px' }}>
                  DIRETRIZ TÁTICA DA EQUIPE PARA A IA (OPCIONAL)
                </label>
                <textarea
                  className="field-textarea"
                  rows={3}
                  placeholder="Ex: Condição especial aprovada de R$ 3.200/mês sem taxa de setup se fechar até sexta-feira."
                  value={diretrizIa}
                  onChange={(e) => setDiretrizIa(e.target.value)}
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div>
                  <label className="eyebrow" style={{ display: 'block', marginBottom: '6px' }}>
                    ATUALIZAR ETAPA (ATUAL: {getEtapaLabel(lead.etapa_funil)})
                  </label>
                  <select
                    className="field-select"
                    value={etapaOverride}
                    onChange={(e) => setEtapaOverride(e.target.value as '' | EtapaFunil)}
                  >
                    <option value="">Manter etapa atual</option>
                    <option value="NOVO_CONTATO">Novo Contato</option>
                    <option value="QUALIFICACAO">Qualificação</option>
                    <option value="NEGOCIACAO">Negociação</option>
                    <option value="FECHAMENTO">Fechamento</option>
                  </select>
                </div>

                <div>
                  <label className="eyebrow" style={{ display: 'block', marginBottom: '6px' }}>
                    ATUALIZAR VALOR ESTIMADO (R$)
                  </label>
                  <input
                    type="number"
                    min="0"
                    step="100"
                    className="field-input mono-metric"
                    placeholder={lead.valor_estimado ? String(lead.valor_estimado) : 'Ex: 4800'}
                    value={valorOverride}
                    onChange={(e) => setValorOverride(e.target.value)}
                  />
                </div>
              </div>
            </>
          ) : (
            <>
              <p style={{ color: 'var(--text-secondary)', fontSize: '13.5px' }}>
                Ao assumir <strong>{lead.nome || lead.telefone}</strong>, o Piloto de IA será imediatamente silenciado e todos os follow-ups agendados serão cancelados para evitar colisão de mensagens.
              </p>

              <div>
                <label className="eyebrow" style={{ display: 'block', marginBottom: '6px' }}>
                  IDENTIFICAÇÃO DO CONSULTOR RESPONSÁVEL
                </label>
                <input
                  type="text"
                  className="field-input"
                  value={atendente}
                  onChange={(e) => setAtendente(e.target.value)}
                  placeholder="Nome do Closer"
                  required
                />
              </div>
            </>
          )}

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '6px' }}>
            <button type="button" className="btn" onClick={onClose} disabled={isBusy}>
              Cancelar
            </button>
            <button
              type="submit"
              className={`btn ${isReturnMode ? 'btn-ai' : 'btn-closer'}`}
              disabled={isBusy}
            >
              {isBusy
                ? 'Sincronizando...'
                : isReturnMode
                  ? 'Reativar Piloto IA'
                  : 'Assumir Atendimento Humano'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
