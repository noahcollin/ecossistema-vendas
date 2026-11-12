import React, { useCallback, useEffect, useState } from 'react';
import { GrainyGradient } from './components/GrainyGradient';
import { Header } from './components/Header';
import { LoginScreen } from './components/LoginScreen';
import { AuthKeyModal } from './components/modals/AuthKeyModal';
import { useHashNavigation } from './hooks/useHashNavigation';
import { useSystemHealth } from './hooks/useSystemHealth';
import {
  clearStoredApiKey,
  fetchPendingHandoverLeads,
  getStoredApiKey,
  getStoredUserEmail,
} from './services/api';
import { LeadsView } from './views/LeadsView';
import { OverviewView } from './views/OverviewView';
import { SettingsView } from './views/SettingsView';

export const App: React.FC = () => {
  const { activeTab, selectedLeadId, navigateToTab, navigateToLead } = useHashNavigation();
  const { health, refreshHealth } = useSystemHealth();

  const [pendingHandoverCount, setPendingHandoverCount] = useState<number>(0);
  const [isAuthModalOpen, setIsAuthModalOpen] = useState<boolean>(false);
  const [wasUnauthorized, setWasUnauthorized] = useState<boolean>(false);
  const [authRevision, setAuthRevision] = useState<number>(0);
  const [userEmail, setUserEmail] = useState<string>(() => getStoredUserEmail());
  const [hasAuthToken, setHasAuthToken] = useState<boolean>(() => Boolean(getStoredApiKey()));

  const handleLogout = useCallback(() => {
    clearStoredApiKey();
    setUserEmail('');
    setHasAuthToken(false);
    setAuthRevision((r) => r + 1);
  }, []);

  const handleLoginSuccess = useCallback(() => {
    setUserEmail(getStoredUserEmail());
    setHasAuthToken(true);
    setWasUnauthorized(false);
    setAuthRevision((r) => r + 1);
    void refreshHealth();
  }, [refreshHealth]);

  const syncPendingHandovers = useCallback(async () => {
    try {
      const pending = await fetchPendingHandoverLeads();
      setPendingHandoverCount(pending.filter((l) => l.controle === 'TRANSBORDO_SOLICITADO').length);
    } catch {
      // Silencioso caso backend esteja offline ou aguardando chave
    }
  }, []);

  useEffect(() => {
    let active = true;
    const poll = () => {
      fetchPendingHandoverLeads()
        .then((pending) => {
          if (active) {
            setPendingHandoverCount(
              pending.filter((l) => l.controle === 'TRANSBORDO_SOLICITADO').length
            );
          }
        })
        .catch(() => {
          // Silencioso caso backend esteja offline ou aguardando chave
        });
    };

    poll();
    const interval = window.setInterval(poll, 30000);
    return () => {
      active = false;
      window.clearInterval(interval);
    };
  }, [authRevision, activeTab]);

  useEffect(() => {
    const handleUnauthorized = () => {
      setWasUnauthorized(true);
      // Se a sessão expirou, redireciona para a tela de login corporativo
      setHasAuthToken(false);
    };
    window.addEventListener('ev:unauthorized', handleUnauthorized);
    return () => window.removeEventListener('ev:unauthorized', handleUnauthorized);
  }, []);

  // Se o usuário ainda não estiver logado, exibe a tela de login oficial Locaweb
  if (!hasAuthToken) {
    return (
      <>
        <GrainyGradient />
        <LoginScreen onLoginSuccess={handleLoginSuccess} />
      </>
    );
  }

  return (
    <>
      <GrainyGradient />

      <div className="app-shell">
        <Header
          activeTab={activeTab}
          onSelectTab={navigateToTab}
          pendingHandoverCount={pendingHandoverCount}
          health={health}
          hasSessionKey={Boolean(getStoredApiKey())}
          userEmail={userEmail}
          onLogout={handleLogout}
          onOpenAuthModal={() => {
            setWasUnauthorized(false);
            setIsAuthModalOpen(true);
          }}
        />

        <main className="main-container" key={authRevision}>
          {activeTab === 'overview' && (
            <OverviewView
              onOpenLead={(leadId) => navigateToLead(leadId)}
              onOpenLeadsTab={() => navigateToTab('leads')}
            />
          )}

          {activeTab === 'leads' && (
            <LeadsView
              selectedLeadId={selectedLeadId}
              onSelectLeadId={(leadId) => navigateToLead(leadId)}
            />
          )}

          {activeTab === 'settings' && (
            <SettingsView
              health={health}
              onRefreshHealth={() => {
                void refreshHealth();
                void syncPendingHandovers();
              }}
            />
          )}
        </main>
      </div>

      <AuthKeyModal
        isOpen={isAuthModalOpen}
        wasUnauthorized={wasUnauthorized}
        onClose={() => setIsAuthModalOpen(false)}
        onSaved={() => {
          setWasUnauthorized(false);
          setAuthRevision((r) => r + 1);
          void refreshHealth();
        }}
      />
    </>
  );
};

export default App;
