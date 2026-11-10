import React, { useEffect, useRef, useState } from 'react';
import type { Interacao, Lead } from '../../types/telemetry';
import { formatTimeBR } from '../../utils/formatters';

interface DossierWhatsAppTabProps {
  lead: Lead;
  interactions: Interacao[];
  isLoading: boolean;
  isSending: boolean;
  onSendHumanMessage: (texto: string) => Promise<void>;
}

export const DossierWhatsAppTab: React.FC<DossierWhatsAppTabProps> = ({
  lead,
  interactions,
  isLoading,
  isSending,
  onSendHumanMessage,
}) => {
  const [draft, setDraft] = useState('');
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [interactions.length]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const cleaned = draft.trim();
    if (!cleaned || isSending) return;
    try {
      await onSendHumanMessage(cleaned);
      setDraft('');
    } catch {
      // Mantém rascunho em caso de falha de envio
    }
  };

  return (
    <div className="surface-panel" style={{ overflow: 'hidden' }}>
      <div className="panel-header" style={{ padding: '12px 16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span className="eyebrow">TRANSCRIÇÃO CRONOLÓGICA WHATSAPP (UAZAPI)</span>
          <span className="mono-metric" style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
            {interactions.length} evento(s)
          </span>
        </div>

        <span
          className={`badge ${
            lead.controle === 'PILOTO_IA' ? 'badge-ai' : 'badge-closer'
          }`}
        >
          {lead.controle === 'PILOTO_IA'
            ? 'ENVIAR MENSAGEM ASSUME CONTROLE HUMANO'
            : 'CLOSER CONECTADO'}
        </span>
      </div>

      <div className="chat-stream">
        {isLoading ? (
          <div style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '32px' }}>
            Carregando histórico da conversa...
          </div>
        ) : interactions.length === 0 ? (
          <div style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '32px' }}>
            Nenhuma interação registrada para este lead.
          </div>
        ) : (
          interactions.map((msg) => {
            if (msg.origem === 'sistema') {
              return (
                <div key={msg.id} className="chat-system-note">
                  <span>{msg.texto}</span>
                  {msg.data && (
                    <span style={{ marginLeft: '8px', color: 'var(--text-dim)' }}>
                      {formatTimeBR(msg.data)}
                    </span>
                  )}
                </div>
              );
            }

            const roleClass =
              msg.origem === 'ia'
                ? 'is-ai'
                : msg.origem === 'humano'
                  ? 'is-human'
                  : 'is-client';

            const senderLabel =
              msg.origem === 'ia'
                ? 'Seu Zé · Piloto IA'
                : msg.origem === 'humano'
                  ? 'Closer Humano'
                  : lead.nome || 'Cliente';

            const senderColor =
              msg.origem === 'ia'
                ? 'var(--blue-ai-bright)'
                : msg.origem === 'humano'
                  ? 'var(--red-closer)'
                  : 'var(--text-muted)';

            return (
              <div key={msg.id} className={`chat-bubble ${roleClass}`}>
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    gap: '12px',
                    marginBottom: '4px',
                    fontSize: '11px',
                  }}
                >
                  <span style={{ fontWeight: 700, color: senderColor }}>{senderLabel}</span>
                  <span className="mono-metric" style={{ color: 'var(--text-dim)' }}>
                    {formatTimeBR(msg.data)}
                  </span>
                </div>
                <div>{msg.texto}</div>
              </div>
            );
          })
        )}
        <div ref={bottomRef} />
      </div>

      <form onSubmit={handleSubmit} className="chat-composer">
        <input
          type="text"
          className="field-input"
          placeholder={
            lead.opt_out
              ? 'Cliente solicitou Opt-Out LGPD (envio bloqueado)'
              : `Enviar mensagem humana para ${lead.nome || lead.telefone}...`
          }
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          disabled={lead.opt_out || isSending}
        />
        <button
          type="submit"
          className="btn btn-closer"
          disabled={lead.opt_out || isSending || !draft.trim()}
        >
          {isSending ? 'Enviando...' : 'Enviar no WhatsApp'}
        </button>
      </form>
    </div>
  );
};

