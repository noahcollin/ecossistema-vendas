import React, { useState, useEffect } from 'react'

export type ActiveTab = 'overview' | 'leads' | 'settings'

interface HeaderProps {
  activeTab: ActiveTab
  setActiveTab: (tab: ActiveTab) => void
}

export const Header: React.FC<HeaderProps> = ({ activeTab, setActiveTab }) => {
  const [time, setTime] = useState<string>('')

  useEffect(() => {
    const updateTime = () => {
      const now = new Date()
      setTime(
        now.toLocaleTimeString('pt-BR', {
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
          hour12: false,
        })
      )
    }
    updateTime()
    const timer = setInterval(updateTime, 1000)
    return () => clearInterval(timer)
  }, [])

  return (
    <header
      style={{
        backgroundColor: 'rgba(8, 8, 10, 0.75)',
        backdropFilter: 'blur(12px)',
        borderBottom: '1.5px solid var(--border-rule)',
        padding: '24px 48px',
        position: 'sticky',
        top: 0,
        zIndex: 100,
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        {/* Logomarca Executiva com Título Bem Grosso */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
          <div>
            <div
              style={{
                fontFamily: 'var(--font-title)',
                fontSize: '28px',
                fontWeight: 900,
                letterSpacing: '-0.03em',
                color: 'var(--text-headline)',
                lineHeight: 1,
              }}
            >
              ECOSSISTEMA DE VENDAS
            </div>
            <div
              style={{
                fontSize: '12px',
                fontWeight: 700,
                color: 'var(--text-muted)',
                marginTop: '6px',
                letterSpacing: '0.06em',
                textTransform: 'uppercase',
              }}
            >
              VISUALIZADOR OPERACIONAL & CENTRO DE CONTROLE
            </div>
          </div>
        </div>

        {/* Navegação Business Robusta */}
        <nav style={{ display: 'flex', gap: '12px' }}>
          <button
            onClick={() => setActiveTab('overview')}
            className={`btn-business ${activeTab === 'overview' ? 'btn-business-blue' : ''}`}
          >
            VISÃO GERAL
          </button>

          <button
            onClick={() => setActiveTab('leads')}
            className={`btn-business ${activeTab === 'leads' ? 'btn-business-blue' : ''}`}
          >
            DOSSIÊS DOS LEADS
          </button>

          <button
            onClick={() => setActiveTab('settings')}
            className={`btn-business ${activeTab === 'settings' ? 'btn-business-blue' : ''}`}
          >
            CONFIGURAÇÕES DA OPERAÇÃO
          </button>
        </nav>

        {/* Relógio e Status */}
        <div
          style={{
            fontSize: '14px',
            fontWeight: 700,
            color: 'var(--text-muted)',
            fontFamily: 'var(--font-mono)',
          }}
        >
          {time} BRT
        </div>
      </div>
    </header>
  )
}
