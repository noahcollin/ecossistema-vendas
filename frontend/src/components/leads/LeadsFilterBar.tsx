import React from 'react';
import type { LeadsFilters } from '../../hooks/useLeadsWorkspace';
import type {
  ControleAtendimento,
  EtapaFunil,
  TemperaturaLead,
} from '../../types/telemetry';

interface LeadsFilterBarProps {
  filters: LeadsFilters;
  onChangeFilters: React.Dispatch<React.SetStateAction<LeadsFilters>>;
  totalCount: number;
  filteredCount: number;
  isLoading: boolean;
  onRefresh: () => void;
  onOpenBatchBriefing: () => void;
}

export const LeadsFilterBar: React.FC<LeadsFilterBarProps> = ({
  filters,
  onChangeFilters,
  totalCount,
  filteredCount,
  isLoading,
  onRefresh,
  onOpenBatchBriefing,
}) => {
  return (
    <section
      className="surface-panel"
      style={{
        padding: '14px 18px',
        marginBottom: '18px',
        display: 'flex',
        flexWrap: 'wrap',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: '12px',
      }}
    >
      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '10px', flex: 1 }}>
        <input
          type="search"
          className="field-input"
          style={{ maxWidth: '280px' }}
          placeholder="Buscar nome, telefone, segmento ou tag..."
          value={filters.search}
          onChange={(e) => onChangeFilters((prev) => ({ ...prev, search: e.target.value }))}
        />

        <select
          className="field-select"
          style={{ width: 'auto', minWidth: '155px' }}
          aria-label="Filtrar por etapa do funil"
          value={filters.etapa}
          onChange={(e) =>
            onChangeFilters((prev) => ({
              ...prev,
              etapa: e.target.value as 'TODAS' | EtapaFunil,
            }))
          }
        >
          <option value="TODAS">Todas as Etapas</option>
          <option value="NOVO_CONTATO">01 · Novo Contato</option>
          <option value="QUALIFICACAO">02 · Qualificação</option>
          <option value="NEGOCIACAO">03 · Negociação</option>
          <option value="FECHAMENTO">04 · Fechamento</option>
        </select>

        <select
          className="field-select"
          style={{ width: 'auto', minWidth: '150px' }}
          aria-label="Filtrar por temperatura"
          value={filters.temperatura}
          onChange={(e) =>
            onChangeFilters((prev) => ({
              ...prev,
              temperatura: e.target.value as 'TODAS' | TemperaturaLead,
            }))
          }
        >
          <option value="TODAS">Todas Temperaturas</option>
          <option value="QUENTE">Quentes</option>
          <option value="MORNO">Mornos</option>
          <option value="FRIO">Frios</option>
        </select>

        <select
          className="field-select"
          style={{ width: 'auto', minWidth: '175px' }}
          aria-label="Filtrar por condução"
          value={filters.controle}
          onChange={(e) =>
            onChangeFilters((prev) => ({
              ...prev,
              controle: e.target.value as 'TODOS' | ControleAtendimento,
            }))
          }
        >
          <option value="TODOS">Toda Condução</option>
          <option value="TRANSBORDO_SOLICITADO">Aguardando Closer</option>
          <option value="HUMANO_ASSUMIU">Closer Ativo</option>
          <option value="PILOTO_IA">Piloto IA</option>
        </select>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
        <span className="mono-metric" style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
          {filteredCount}/{totalCount} leads
        </span>

        <button
          type="button"
          className="btn btn-sm"
          onClick={onOpenBatchBriefing}
          disabled={totalCount === 0}
        >
          Briefing de Carteira
        </button>

        <button type="button" className="btn btn-sm" onClick={onRefresh} disabled={isLoading}>
          {isLoading ? 'Atualizando...' : 'Sincronizar'}
        </button>
      </div>
    </section>
  );
};
