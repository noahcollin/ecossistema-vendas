import { useCallback, useEffect, useState } from 'react';

export type AppTab = 'overview' | 'leads' | 'settings';

interface HashRouteState {
  activeTab: AppTab;
  selectedLeadId: number | null;
}

function parseWindowHash(hash: string): HashRouteState {
  const cleaned = hash.replace(/^#\/?/, '').trim();
  if (!cleaned || cleaned === 'overview') {
    return { activeTab: 'overview', selectedLeadId: null };
  }

  if (cleaned === 'settings') {
    return { activeTab: 'settings', selectedLeadId: null };
  }

  if (cleaned.startsWith('leads')) {
    const parts = cleaned.split('/');
    const maybeId = parts[1] ? Number.parseInt(parts[1], 10) : Number.NaN;
    return {
      activeTab: 'leads',
      selectedLeadId: Number.isFinite(maybeId) && maybeId > 0 ? maybeId : null,
    };
  }

  return { activeTab: 'overview', selectedLeadId: null };
}

function buildHash(tab: AppTab, leadId: number | null): string {
  if (tab === 'leads' && leadId !== null) {
    return `#leads/${leadId}`;
  }
  return `#${tab}`;
}

export function useHashNavigation() {
  const [route, setRoute] = useState<HashRouteState>(() =>
    parseWindowHash(window.location.hash)
  );

  useEffect(() => {
    const handleHashChange = () => {
      setRoute(parseWindowHash(window.location.hash));
    };

    window.addEventListener('hashchange', handleHashChange);
    return () => window.removeEventListener('hashchange', handleHashChange);
  }, []);

  const navigateToTab = useCallback((tab: AppTab) => {
    const targetHash = buildHash(tab, null);
    if (window.location.hash !== targetHash) {
      window.location.hash = targetHash;
    } else {
      setRoute({ activeTab: tab, selectedLeadId: null });
    }
  }, []);

  const navigateToLead = useCallback((leadId: number | null) => {
    const targetHash = buildHash('leads', leadId);
    if (window.location.hash !== targetHash) {
      window.location.hash = targetHash;
    } else {
      setRoute({ activeTab: 'leads', selectedLeadId: leadId });
    }
  }, []);

  return {
    activeTab: route.activeTab,
    selectedLeadId: route.selectedLeadId,
    navigateToTab,
    navigateToLead,
  };
}

