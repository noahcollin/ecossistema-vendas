import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  assumirAtendimentoHumano,
  clearLeadInteractions,
  deleteLead,
  devolverAtendimentoIA,
  enviarMensagemHumana,
  fetchLeadFollowups,
  fetchLeadInteractions,
  fetchLeads,
  solicitarTransbordoManual,
  triggerLeadAudit,
  type DevolverIaPayload,
} from '../services/api';
import type {
  ControleAtendimento,
  EtapaFunil,
  FollowupAgendado,
  Interacao,
  Lead,
  TemperaturaLead,
} from '../types/telemetry';

export interface LeadsFilters {
  search: string;
  etapa: 'TODAS' | EtapaFunil;
  temperatura: 'TODAS' | TemperaturaLead;
  controle: 'TODOS' | ControleAtendimento;
}

export interface ActionBanner {
  kind: 'info' | 'success' | 'warning' | 'error';
  message: string;
}

export function useLeadsWorkspace(
  selectedLeadIdFromUrl: number | null,
  onSelectLeadId: (leadId: number | null) => void
) {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [interactions, setInteractions] = useState<Interacao[]>([]);
  const [followups, setFollowups] = useState<FollowupAgendado[]>([]);

  const [filters, setFilters] = useState<LeadsFilters>({
    search: '',
    etapa: 'TODAS',
    temperatura: 'TODAS',
    controle: 'TODOS',
  });

  const [isLoadingLeads, setIsLoadingLeads] = useState<boolean>(true);
  const [isMutating, setIsMutating] = useState<boolean>(false);
  const [banner, setBanner] = useState<ActionBanner | null>(null);

  const loadLeads = useCallback(async (signal?: AbortSignal) => {
    setIsLoadingLeads(true);
    try {
      const list = await fetchLeads(250, 0, signal);
      setLeads(list);
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') return;
      setBanner({
        kind: 'error',
        message:
          err instanceof Error
            ? `Falha ao sincronizar carteira de leads: ${err.message}`
            : 'Falha ao sincronizar carteira de leads com o servidor.',
      });
    } finally {
      setIsLoadingLeads(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    fetchLeads(250, 0, controller.signal)
      .then((list) => {
        setLeads(list);
      })
      .catch((err) => {
        if (err instanceof DOMException && err.name === 'AbortError') return;
        setBanner({
          kind: 'error',
          message:
            err instanceof Error
              ? `Falha ao sincronizar carteira de leads: ${err.message}`
              : 'Falha ao sincronizar carteira de leads com o servidor.',
        });
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setIsLoadingLeads(false);
        }
      });
    return () => controller.abort();
  }, []);

  const filteredLeads = useMemo(() => {
    const q = filters.search.trim().toLowerCase();
    return leads.filter((lead) => {
      if (filters.etapa !== 'TODAS' && lead.etapa_funil !== filters.etapa) return false;
      if (filters.temperatura !== 'TODAS' && lead.temperatura !== filters.temperatura) return false;
      if (filters.controle !== 'TODOS' && lead.controle !== filters.controle) return false;

      if (!q) return true;
      const nomeMatch = (lead.nome ?? '').toLowerCase().includes(q);
      const phoneMatch = lead.telefone.toLowerCase().includes(q);
      const segMatch = (lead.dados_qualificacao?.segmento ?? '').toLowerCase().includes(q);
      const tagMatch = lead.tags.some((t) => t.toLowerCase().includes(q));
      return nomeMatch || phoneMatch || segMatch || tagMatch;
    });
  }, [filters, leads]);

  const activeLead = useMemo(() => {
    if (selectedLeadIdFromUrl !== null) {
      const found = leads.find((l) => l.id === selectedLeadIdFromUrl);
      if (found) return found;
    }
    return filteredLeads[0] ?? null;
  }, [filteredLeads, leads, selectedLeadIdFromUrl]);

  const activeLeadId = activeLead?.id ?? null;
  const [loadedThreadLeadId, setLoadedThreadLeadId] = useState<number | null>(null);

  // Carrega interações e follow-ups com AbortController (elimina race condition ao trocar rápido de lead)
  useEffect(() => {
    if (activeLeadId === null) {
      return;
    }

    const controller = new AbortController();

    Promise.all([
      fetchLeadInteractions(activeLeadId, controller.signal),
      fetchLeadFollowups(activeLeadId, controller.signal),
    ])
      .then(([msgs, fups]) => {
        setInteractions(msgs);
        setFollowups(fups);
        setLoadedThreadLeadId(activeLeadId);
      })
      .catch((err) => {
        if (err instanceof DOMException && err.name === 'AbortError') return;
        setLoadedThreadLeadId(activeLeadId);
        setBanner({
          kind: 'error',
          message:
            err instanceof Error
              ? `Erro ao carregar histórico do lead: ${err.message}`
              : 'Erro ao carregar histórico da conversa.',
        });
      });

    return () => controller.abort();
  }, [activeLeadId]);

  const effectiveIsLoadingThread =
    activeLeadId !== null && loadedThreadLeadId !== activeLeadId;
  const visibleInteractions = activeLeadId !== null ? interactions : [];
  const visibleFollowups = activeLeadId !== null ? followups : [];

  const replaceLeadInState = useCallback((updated: Lead) => {
    setLeads((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
  }, []);

  const refreshActiveThread = useCallback(async (leadId: number) => {
    const [msgs, fups] = await Promise.all([
      fetchLeadInteractions(leadId),
      fetchLeadFollowups(leadId),
    ]);
    setInteractions(msgs);
    setFollowups(fups);
  }, []);

  const runLeadAudit = useCallback(async () => {
    if (!activeLead) return;
    setIsMutating(true);
    setBanner({
      kind: 'info',
      message: 'Executando auditoria retrospectiva via Agente Auditor (GPT-4o-mini)...',
    });
    try {
      const audited = await triggerLeadAudit(activeLead.id);
      replaceLeadInState(audited);
      setBanner({
        kind: 'success',
        message: 'Dossiê Comercial Executivo auditado e persistido com sucesso.',
      });
    } catch (err) {
      setBanner({
        kind: 'error',
        message:
          err instanceof Error
            ? `Não foi possível auditar o dossiê: ${err.message}`
            : 'Falha ao acionar o Agente Auditor no backend.',
      });
    } finally {
      setIsMutating(false);
    }
  }, [activeLead, replaceLeadInState]);

  const assumeHumanControl = useCallback(
    async (atendente = 'Consultor Comercial') => {
      if (!activeLead) return;
      setIsMutating(true);
      try {
        const updated = await assumirAtendimentoHumano(activeLead.id, atendente);
        replaceLeadInState(updated);
        await refreshActiveThread(activeLead.id);
        setBanner({
          kind: 'success',
          message: `Atendimento assumido por ${atendente}. IA silenciada e follow-ups cancelados.`,
        });
      } catch (err) {
        setBanner({
          kind: 'error',
          message:
            err instanceof Error
              ? `Erro ao assumir atendimento: ${err.message}`
              : 'Falha na transição para atendimento humano.',
        });
        throw err;
      } finally {
        setIsMutating(false);
      }
    },
    [activeLead, refreshActiveThread, replaceLeadInState]
  );

  const returnToAiPilot = useCallback(
    async (payload: DevolverIaPayload = {}) => {
      if (!activeLead) return;
      setIsMutating(true);
      try {
        const updated = await devolverAtendimentoIA(activeLead.id, payload);
        replaceLeadInState(updated);
        await refreshActiveThread(activeLead.id);
        setBanner({
          kind: 'success',
          message: 'Controle devolvido ao Piloto Automático de IA com diretrizes registradas.',
        });
      } catch (err) {
        setBanner({
          kind: 'error',
          message:
            err instanceof Error
              ? `Erro ao devolver controle para a IA: ${err.message}`
              : 'Falha ao reativar o Piloto IA.',
        });
        throw err;
      } finally {
        setIsMutating(false);
      }
    },
    [activeLead, refreshActiveThread, replaceLeadInState]
  );

  const requestManualHandover = useCallback(
    async (motivo = 'Escalonamento manual via Dossiê') => {
      if (!activeLead) return;
      setIsMutating(true);
      try {
        const updated = await solicitarTransbordoManual(activeLead.id, motivo);
        replaceLeadInState(updated);
        await refreshActiveThread(activeLead.id);
        setBanner({
          kind: 'warning',
          message: 'Transbordo solicitado! Equipe humana alertada e IA silenciada.',
        });
      } catch (err) {
        setBanner({
          kind: 'error',
          message:
            err instanceof Error
              ? `Erro ao solicitar transbordo: ${err.message}`
              : 'Falha ao escalar atendimento.',
        });
      } finally {
        setIsMutating(false);
      }
    },
    [activeLead, refreshActiveThread, replaceLeadInState]
  );

  const sendHumanWhatsAppMessage = useCallback(
    async (texto: string, atendente = 'Closer Comercial') => {
      if (!activeLead || !texto.trim()) return;
      setIsMutating(true);
      try {
        const sent = await enviarMensagemHumana(activeLead.id, texto.trim(), atendente);
        setInteractions((prev) => [
          ...prev,
          {
            id: sent.interacao_id,
            origem: 'humano',
            texto: sent.texto,
            data: sent.data,
          },
        ]);
        // Enviar mensagem humana automaticamente assume controle no backend
        setLeads((prev) =>
          prev.map((l) =>
            l.id === activeLead.id ? { ...l, controle: 'HUMANO_ASSUMIU' } : l
          )
        );
        setBanner({
          kind: 'success',
          message: 'Mensagem enviada ao WhatsApp do cliente via Uazapi.',
        });
      } catch (err) {
        setBanner({
          kind: 'error',
          message:
            err instanceof Error
              ? `Falha no envio WhatsApp: ${err.message}`
              : 'Não foi possível enviar a mensagem humana.',
        });
        throw err;
      } finally {
        setIsMutating(false);
      }
    },
    [activeLead]
  );

  const resetActiveLeadMemory = useCallback(async () => {
    if (!activeLead) return;
    setIsMutating(true);
    try {
      await clearLeadInteractions(activeLead.id);
      await loadLeads();
      setInteractions([]);
      setFollowups([]);
      setBanner({
        kind: 'info',
        message: 'Histórico e memória de longo prazo reiniciados para NOVO_CONTATO.',
      });
    } catch (err) {
      setBanner({
        kind: 'error',
        message:
          err instanceof Error
            ? `Erro ao limpar histórico: ${err.message}`
            : 'Falha ao resetar memória do lead.',
      });
    } finally {
      setIsMutating(false);
    }
  }, [activeLead, loadLeads]);

  const removeActiveLead = useCallback(async () => {
    if (!activeLead) return;
    setIsMutating(true);
    const removedId = activeLead.id;
    try {
      await deleteLead(removedId);
      setLeads((prev) => prev.filter((l) => l.id !== removedId));
      onSelectLeadId(null);
      setBanner({
        kind: 'info',
        message: 'Cadastro do lead e histórico removidos permanentemente.',
      });
    } catch (err) {
      setBanner({
        kind: 'error',
        message:
          err instanceof Error
            ? `Erro ao excluir lead: ${err.message}`
            : 'Falha ao excluir lead.',
      });
    } finally {
      setIsMutating(false);
    }
  }, [activeLead, onSelectLeadId]);

  return {
    leads,
    filteredLeads,
    activeLead,
    interactions: visibleInteractions,
    followups: visibleFollowups,
    filters,
    setFilters,
    isLoadingLeads,
    isLoadingThread: effectiveIsLoadingThread,
    isMutating,
    banner,
    clearBanner: () => setBanner(null),
    selectLead: (lead: Lead) => onSelectLeadId(lead.id),
    reloadLeads: loadLeads,
    runLeadAudit,
    assumeHumanControl,
    returnToAiPilot,
    requestManualHandover,
    sendHumanWhatsAppMessage,
    resetActiveLeadMemory,
    removeActiveLead,
  };
}
