from dataclasses import dataclass
from enum import Enum
from typing import Optional
from core.config import settings
from core.logger import logger
from integrations.redis.buffer import redis_client
import models


class PacingLevel(str, Enum):
    """Níveis de velocidade conversacional do lead na etapa atual."""
    EXPLORACAO = "EXPLORACAO"            # 1 a 9 msgs: diagnóstico e rapport consultivo
    CONDUCAO_ATIVA = "CONDUCAO_ATIVA"    # 10 a 19 msgs: postura assertiva de vendas (toma as rédeas)
    DECISAO_FINAL = "DECISAO_FINAL"      # 20 a 29 msgs: chamada conclusiva amigável de fechamento
    ESTAGNADO_LIMITE = "ESTAGNADO_LIMITE"# 30+ msgs: desqualificação graciosa 100% humana (trava FinOps)


@dataclass(frozen=True)
class PacingEvaluation:
    """Resultado imutável da avaliação de cadência e postura comercial."""
    mensagens_na_etapa: int
    nivel: PacingLevel
    deve_encerrar_por_estagnacao: bool
    diretriz_proatividade: Optional[str] = None
    mensagem_despedida_humana: Optional[str] = None


class ConversationPacingService:
    """
    Guardião de Velocidade Conversacional & FinOps Anti-Loop (Autonomous Closer Drive).
    Atende aos princípios SOLID (SRP, OCP) e POO.
    
    Substitui a trava binária por uma evolução natural de postura comercial:
    - O agente é nosso funcionário humano de vendas ('Seu Zé').
    - Em conversas longas na mesma etapa, a IA aumenta a assertividade para fechar ou desqualificar.
    - Elimina transbordo desnecessário para humanos, preservando a autonomia Zero-Touch.
    """

    TTL_PACING_SEGUNDOS = 86400  # 24 horas de retenção de contagem no Redis

    @staticmethod
    def _gerar_chave_redis(lead_id: int) -> str:
        return f"pacing:etapa:{lead_id}"

    @classmethod
    async def obter_contagem_atual(cls, lead_id: int) -> int:
        """Recupera o número de mensagens acumuladas na etapa corrente."""
        try:
            chave = cls._gerar_chave_redis(lead_id)
            val = await redis_client.get(chave)
            return int(val) if val else 0
        except Exception as e:
            logger.warning(f"[PACING GUARD] Falha ao ler contagem no Redis para lead {lead_id}: {e}")
            return 0

    @classmethod
    async def resetar_etapa(cls, lead_id: int) -> None:
        """
        Zera o contador de mensagens na etapa quando o lead avança no funil.
        Chamado na transição de EtapaFunil pelo Agente Analista.
        """
        try:
            chave = cls._gerar_chave_redis(lead_id)
            await redis_client.delete(chave)
            logger.info(f"[PACING GUARD] 🔄 Contador de etapa resetado para Lead ID {lead_id} (avanço de funil).")
        except Exception as e:
            logger.warning(f"[PACING GUARD] Falha ao resetar contador no Redis para lead {lead_id}: {e}")

    @classmethod
    def avaliar_contagem(
        cls,
        contagem: int,
        etapa: models.EtapaFunil,
        nome_cliente: str = ""
    ) -> PacingEvaluation:
        """
        Avalia puramente as métricas de contagem contra os limites Twelve-Factor.
        Método determinístico sem efeitos colaterais de I/O (fácil testabilidade).
        """
        primeiro_nome = nome_cliente.strip().split()[0] if nome_cliente and nome_cliente.strip() else "amigo"
        th_proactive = settings.PACING_THRESHOLD_PROACTIVE
        th_decisive = settings.PACING_THRESHOLD_DECISIVE
        th_max = settings.PACING_THRESHOLD_MAX

        # 1. ZONA VERDE: Exploração consultiva inicial
        if contagem < th_proactive:
            return PacingEvaluation(
                mensagens_na_etapa=contagem,
                nivel=PacingLevel.EXPLORACAO,
                deve_encerrar_por_estagnacao=False,
                diretriz_proatividade=None
            )

        # 2. ZONA AMARELA: Condução ativa para fechamento (Seu Zé toma as rédeas)
        if contagem < th_decisive:
            diretriz = (
                f"⚠️ [POSTURA ATIVA DE VENDAS]: A conversa já teve {contagem} trocas de mensagens nesta etapa ({etapa.value}). "
                "Não responda apenas como um atendente tirando dúvidas passivamente. "
                "Valide o entendimento, ancore o valor comercial da solução e conduza ativamente para o próximo passo "
                "(ex: solicitar sinal verde para contratação, agendar demonstração prática ou definir o plano ideal)."
            )
            return PacingEvaluation(
                mensagens_na_etapa=contagem,
                nivel=PacingLevel.CONDUCAO_ATIVA,
                deve_encerrar_por_estagnacao=False,
                diretriz_proatividade=diretriz
            )

        # 3. ZONA LARANJA: Chamada decisiva final (não fica em cima do muro)
        if contagem < th_max:
            diretriz = (
                f"🚨 [CHAMADA DECISIVA DE FECHAMENTO]: A conversa está com {contagem} mensagens nesta etapa sem avanço. "
                "Seja extremamente direto, atencioso e transparente: faça uma pergunta clara e decisiva de fechamento. "
                "Pergunte com franqueza se o cliente deseja avançar agora ou se prefere pausar o contato para avaliar com calma em outro momento. "
                "Não estenda a conversa com detalhes secundários."
            )
            return PacingEvaluation(
                mensagens_na_etapa=contagem,
                nivel=PacingLevel.DECISAO_FINAL,
                deve_encerrar_por_estagnacao=False,
                diretriz_proatividade=diretriz
            )

        # 4. ZONA VERMELHA: Trava FinOps atingida (desqualificação graciosa e humanizada)
        despedida = (
            f"Super entendo, {primeiro_nome}! Como vejo que você ainda tem dúvidas ou talvez este não seja o momento ideal "
            "para a sua empresa implementar essa automação, vou deixar você totalmente à vontade para não tomar seu tempo. "
            "Se no futuro fizer sentido destravar essa operação, as portas continuam abertas e você já tem meu contato direto por aqui. "
            "Um grande abraço e muito sucesso nos seus negócios!"
        )
        return PacingEvaluation(
            mensagens_na_etapa=contagem,
            nivel=PacingLevel.ESTAGNADO_LIMITE,
            deve_encerrar_por_estagnacao=True,
            diretriz_proatividade=None,
            mensagem_despedida_humana=despedida
        )

    @classmethod
    async def avaliar_e_incrementar(
        cls,
        lead_id: int,
        etapa: models.EtapaFunil,
        nome_cliente: str = ""
    ) -> PacingEvaluation:
        """
        Incrementa atomicamente o contador no Redis e retorna a avaliação de postura comercial.
        """
        chave = cls._gerar_chave_redis(lead_id)
        try:
            contagem = await redis_client.incr(chave)
            if contagem == 1:
                await redis_client.expire(chave, cls.TTL_PACING_SEGUNDOS)
        except Exception as e:
            logger.warning(f"[PACING GUARD] Falha ao incrementar no Redis para lead {lead_id}: {e}")
            contagem = 1

        avaliacao = cls.avaliar_contagem(contagem, etapa, nome_cliente)
        logger.info(
            f"[PACING GUARD] 📊 Lead ID {lead_id} | Etapa: {etapa.value} | "
            f"Mensagens na etapa: {contagem} | Nível: {avaliacao.nivel.value}"
        )
        return avaliacao
