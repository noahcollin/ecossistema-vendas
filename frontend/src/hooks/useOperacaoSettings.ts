import { useCallback, useEffect, useState } from 'react';
import {
  fetchOperacaoSettings,
  purgeRedisQueues,
  toggleKillSwitch,
  updateOperacaoSettings,
} from '../services/api';
import type { OperacaoSettings, ProdutoItem } from '../types/settings';
import type { ActionBanner } from './useLeadsWorkspace';

const FALLBACK_SETTINGS: OperacaoSettings = {
  produtos: [],
  cadencia: {
    max_tentativas: 3,
    intervalo_horas: 24,
    intervalos_toques: [2, 24, 72],
    apenas_dias_uteis: true,
    respeitar_horario_comercial: true,
  },
  horario_comercial: {
    inicio_hora: 8,
    fim_hora: 18,
    dias_semana: [0, 1, 2, 3, 4],
    fuso_horario: 'America/Sao_Paulo',
  },
  pacing: {
    delay_base_ms: 1500,
    intervalo_entre_baloes_seg: 1.8,
    simular_digitacao: true,
    limiar_proativo: 10,
    limiar_decisivo: 20,
    limiar_max_finops: 30,
  },
  debounce_segundos: 4.5,
  modo_24h_inbound: true,
  ia_silenciada_global: false,
  mensagem_inatividade:
    'Olá! Notei que não conseguimos avançar no momento. Ficamos à disposição quando fizer sentido para você!',
};

export function useOperacaoSettings(onGovernanceChange?: () => void) {
  const [settings, setSettings] = useState<OperacaoSettings>(FALLBACK_SETTINGS);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [isDirty, setIsDirty] = useState<boolean>(false);
  const [banner, setBanner] = useState<ActionBanner | null>(null);

  const loadSettings = useCallback(async (signal?: AbortSignal) => {
    setIsLoading(true);
    try {
      const data = await fetchOperacaoSettings(signal);
      setSettings(data);
      setIsDirty(false);
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') return;
      setBanner({
        kind: 'error',
        message:
          err instanceof Error
            ? `Não foi possível carregar as configurações do backend: ${err.message}`
            : 'Falha ao carregar configurações operacionais.',
      });
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    fetchOperacaoSettings(controller.signal)
      .then((data) => {
        setSettings(data);
        setIsDirty(false);
      })
      .catch((err) => {
        if (err instanceof DOMException && err.name === 'AbortError') return;
        setBanner({
          kind: 'error',
          message:
            err instanceof Error
              ? `Não foi possível carregar as configurações do backend: ${err.message}`
              : 'Falha ao carregar configurações operacionais.',
        });
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setIsLoading(false);
        }
      });
    return () => controller.abort();
  }, []);

  const patchLocal = useCallback((updater: (prev: OperacaoSettings) => OperacaoSettings) => {
    setSettings((prev) => updater(prev));
    setIsDirty(true);
  }, []);

  const updateProduct = useCallback(
    (index: number, patch: Partial<ProdutoItem>) => {
      patchLocal((prev) => ({
        ...prev,
        produtos: prev.produtos.map((p, idx) => (idx === index ? { ...p, ...patch } : p)),
      }));
    },
    [patchLocal]
  );

  const addProduct = useCallback(() => {
    const newId = `solucao_${Date.now().toString(36)}`;
    patchLocal((prev) => ({
      ...prev,
      produtos: [
        ...prev.produtos,
        {
          id: newId,
          nome: 'Nova Solução Comercial',
          descricao: 'Descreva a proposta de valor desta oferta',
          modelo_comercial: 'MRR + Setup',
          qualificacao_minima: 'Definir perfil ideal de cliente',
          diretriz_venda: 'Ancorar no retorno sobre investimento da operação.',
          preco_base_mensal: 2500,
          taxa_setup: 1000,
          ativo: true,
        },
      ],
    }));
  }, [patchLocal]);

  const removeProduct = useCallback(
    (index: number) => {
      patchLocal((prev) => ({
        ...prev,
        produtos: prev.produtos.filter((_, idx) => idx !== index),
      }));
    },
    [patchLocal]
  );

  const saveAllSettings = useCallback(async () => {
    setIsSaving(true);
    setBanner(null);
    try {
      const saved = await updateOperacaoSettings({
        produtos: settings.produtos,
        cadencia: settings.cadencia,
        horario_comercial: settings.horario_comercial,
        pacing: settings.pacing,
        debounce_segundos: settings.debounce_segundos,
        modo_24h_inbound: settings.modo_24h_inbound,
        ia_silenciada_global: settings.ia_silenciada_global,
        mensagem_inatividade: settings.mensagem_inatividade,
      });
      setSettings(saved);
      setIsDirty(false);
      setBanner({
        kind: 'success',
        message:
          'Parâmetros sincronizados no PostgreSQL, cache Redis e runtime dos Agentes de IA.',
      });
      onGovernanceChange?.();
    } catch (err) {
      setBanner({
        kind: 'error',
        message:
          err instanceof Error
            ? `Falha ao persistir configurações: ${err.message}`
            : 'Erro ao salvar configurações operacionais.',
      });
    } finally {
      setIsSaving(false);
    }
  }, [onGovernanceChange, settings]);

  const executeKillSwitch = useCallback(
    async (silenciar: boolean) => {
      setIsSaving(true);
      try {
        const res = await toggleKillSwitch(silenciar);
        setSettings((prev) => ({
          ...prev,
          ia_silenciada_global: res.ia_silenciada_global,
          atualizado_em: res.atualizado_em ?? prev.atualizado_em,
        }));
        setBanner({
          kind: silenciar ? 'warning' : 'success',
          message: res.mensagem,
        });
        onGovernanceChange?.();
      } catch (err) {
        setBanner({
          kind: 'error',
          message:
            err instanceof Error
              ? `Falha ao acionar Kill-Switch: ${err.message}`
              : 'Erro ao alternar Kill-Switch global.',
        });
      } finally {
        setIsSaving(false);
      }
    },
    [onGovernanceChange]
  );

  const executeRedisPurge = useCallback(async () => {
    setIsSaving(true);
    try {
      const res = await purgeRedisQueues();
      setBanner({
        kind: 'info',
        message: res.mensagem,
      });
      onGovernanceChange?.();
    } catch (err) {
      setBanner({
        kind: 'error',
        message:
          err instanceof Error
            ? `Falha ao expurgar filas Redis: ${err.message}`
            : 'Erro ao limpar filas voláteis no Redis.',
      });
    } finally {
      setIsSaving(false);
    }
  }, [onGovernanceChange]);

  return {
    settings,
    isLoading,
    isSaving,
    isDirty,
    banner,
    clearBanner: () => setBanner(null),
    patchLocal,
    updateProduct,
    addProduct,
    removeProduct,
    saveAllSettings,
    executeKillSwitch,
    executeRedisPurge,
    reloadSettings: loadSettings,
  };
}
