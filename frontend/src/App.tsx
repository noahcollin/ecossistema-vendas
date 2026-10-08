import React, { useState } from 'react'
import { Header, type ActiveTab } from './components/Header'
import { GrainOverlay } from './components/GrainOverlay'
import { OverviewView } from './views/OverviewView'
import { LeadsView } from './views/LeadsView'
import { SettingsView } from './views/SettingsView'

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<ActiveTab>('overview')

  const handleTabChange = (tab: ActiveTab) => {
    setActiveTab(tab)
    window.scrollTo({ top: 0, behavior: 'instant' })
  }

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', backgroundColor: 'var(--bg-void)' }}>
      {/* Textura de Grão Analógico Editorial */}
      <GrainOverlay />

      {/* Header Estilo Jornal */}
      <Header activeTab={activeTab} setActiveTab={handleTabChange} />

      {/* Corpo Principal da Página */}
      <main
        style={{
          flex: 1,
          maxWidth: '1440px',
          width: '100%',
          margin: '0 auto',
          padding: '48px 40px 80px 40px',
        }}
      >
        {activeTab === 'overview' && <OverviewView />}
        {activeTab === 'leads' && <LeadsView />}
        {activeTab === 'settings' && <SettingsView />}
      </main>

      {/* Rodapé Clássico de Imprensa */}
      <footer
        style={{
          borderTop: '2px solid var(--border-rule)',
          padding: '32px 40px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'baseline',
          fontSize: '14px',
          color: 'var(--text-muted)',
          backgroundColor: 'var(--bg-void)',
        }}
      >
        <div style={{ fontFamily: 'var(--font-headline)', fontSize: '18px', fontWeight: 800, color: 'var(--text-headline)' }}>
          ECOSSISTEMA DE VENDAS
        </div>

        <div style={{ fontFamily: 'var(--font-body)', fontSize: '13px' }}>
          INTELIGENTTE © 2026 — TODOS OS DIREITOS RESERVADOS
        </div>
      </footer>
    </div>
  )
}

export default App
