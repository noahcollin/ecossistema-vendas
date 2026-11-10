import React from 'react';
import type { ProdutoItem } from '../../types/settings';

interface ProductCatalogSectionProps {
  produtos: ProdutoItem[];
  onUpdateProduct: (index: number, patch: Partial<ProdutoItem>) => void;
  onAddProduct: () => void;
  onRemoveProduct: (index: number) => void;
}

export const ProductCatalogSection: React.FC<ProductCatalogSectionProps> = ({
  produtos,
  onUpdateProduct,
  onAddProduct,
  onRemoveProduct,
}) => {
  return (
    <section className="surface-panel">
      <div className="panel-header">
        <div>
          <div className="eyebrow eyebrow-ai">PORTFÓLIO COMERCIAL SINCRONIZADO AO PROMPT</div>
          <h2 className="section-title" style={{ marginTop: '2px' }}>
            Catálogo de Soluções, Preços &amp; Diretrizes do Agente Closer
          </h2>
        </div>

        <button type="button" className="btn btn-sm btn-ai" onClick={onAddProduct}>
          + Adicionar Solução
        </button>
      </div>

      <div className="panel-body">
        {produtos.length === 0 ? (
          <div style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '24px' }}>
            Nenhum produto cadastrado. Adicione soluções para orientar o Agente Closer (&ldquo;Seu Zé&rdquo;).
          </div>
        ) : (
          <div className="products-grid">
            {produtos.map((prod, idx) => (
              <div
                key={prod.id || idx}
                className="surface-elevated"
                style={{
                  padding: '16px',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '12px',
                  opacity: prod.ativo ? 1 : 0.62,
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '8px' }}>
                  <label style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={prod.ativo}
                      onChange={(e) => onUpdateProduct(idx, { ativo: e.target.checked })}
                    />
                    <span className={`badge ${prod.ativo ? 'badge-won' : 'badge-muted'}`}>
                      {prod.ativo ? 'OFERTA ATIVA' : 'PAUSADA'}
                    </span>
                  </label>

                  <button
                    type="button"
                    className="btn btn-sm btn-ghost"
                    onClick={() => onRemoveProduct(idx)}
                    title="Remover solução do catálogo"
                  >
                    Remover
                  </button>
                </div>

                <div>
                  <label className="eyebrow" style={{ display: 'block', marginBottom: '4px' }}>
                    NOME COMERCIAL
                  </label>
                  <input
                    type="text"
                    className="field-input"
                    value={prod.nome}
                    onChange={(e) => onUpdateProduct(idx, { nome: e.target.value })}
                  />
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                  <div>
                    <label className="eyebrow" style={{ display: 'block', marginBottom: '4px' }}>
                      MENSALIDADE (R$)
                    </label>
                    <input
                      type="number"
                      min="0"
                      step="50"
                      className="field-input mono-metric"
                      value={prod.preco_base_mensal}
                      onChange={(e) =>
                        onUpdateProduct(idx, {
                          preco_base_mensal: Number.parseFloat(e.target.value) || 0,
                        })
                      }
                    />
                  </div>

                  <div>
                    <label className="eyebrow" style={{ display: 'block', marginBottom: '4px' }}>
                      SETUP / IMPLANTAÇÃO (R$)
                    </label>
                    <input
                      type="number"
                      min="0"
                      step="50"
                      className="field-input mono-metric"
                      value={prod.taxa_setup}
                      onChange={(e) =>
                        onUpdateProduct(idx, {
                          taxa_setup: Number.parseFloat(e.target.value) || 0,
                        })
                      }
                    />
                  </div>
                </div>

                <div>
                  <label className="eyebrow" style={{ display: 'block', marginBottom: '4px' }}>
                    MODELO COMERCIAL
                  </label>
                  <input
                    type="text"
                    className="field-input"
                    value={prod.modelo_comercial}
                    onChange={(e) => onUpdateProduct(idx, { modelo_comercial: e.target.value })}
                  />
                </div>

                <div>
                  <label className="eyebrow" style={{ display: 'block', marginBottom: '4px' }}>
                    QUALIFICAÇÃO MÍNIMA (ICP)
                  </label>
                  <input
                    type="text"
                    className="field-input"
                    value={prod.qualificacao_minima}
                    onChange={(e) => onUpdateProduct(idx, { qualificacao_minima: e.target.value })}
                  />
                </div>

                <div>
                  <label className="eyebrow" style={{ display: 'block', marginBottom: '4px' }}>
                    DIRETRIZ TÁTICA DE VENDA (INJETADA NO PROMPT)
                  </label>
                  <textarea
                    rows={2}
                    className="field-textarea"
                    value={prod.diretriz_venda || prod.descricao}
                    onChange={(e) =>
                      onUpdateProduct(idx, {
                        diretriz_venda: e.target.value,
                        descricao: prod.descricao || e.target.value,
                      })
                    }
                  />
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
};

