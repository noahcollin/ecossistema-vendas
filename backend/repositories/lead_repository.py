from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError
import models

class LeadRepository:
    """
    Camada de persistência para as entidades Lead e Interacao.
    Isola consultas e transações SQLAlchemy do restante da aplicação.
    """

    @staticmethod
    async def get_by_id(db: AsyncSession, lead_id: int) -> Optional[models.Lead]:
        """Obtém um Lead pelo ID primário utilizando o Identity Map da sessão quando disponível."""
        return await db.get(models.Lead, lead_id)

    @staticmethod
    async def get_by_phone(db: AsyncSession, telefone: str) -> Optional[models.Lead]:
        """Obtém um Lead pelo número de telefone (compara exato ou com/sem prefixo +)."""
        digitos = "".join(filter(str.isdigit, telefone))
        if digitos:
            query = select(models.Lead).where(
                (models.Lead.telefone == telefone) |
                (models.Lead.telefone == f"+{digitos}") |
                (models.Lead.telefone == digitos)
            )
        else:
            query = select(models.Lead).where(models.Lead.telefone == telefone)
        resultado = await db.execute(query)
        return resultado.scalars().first()

    @staticmethod
    async def find_by_phone_digits(db: AsyncSession, telefone: str, digitos: str) -> Optional[models.Lead]:
        """
        Busca um Lead pelo telefone exato ou por terminação segura (endswith) de dígitos.
        """
        query = select(models.Lead).where(
            (models.Lead.telefone == telefone) | (models.Lead.telefone.endswith(digitos))
        )
        resultado = await db.execute(query)
        return resultado.scalars().first()

    @staticmethod
    async def list_all(
        db: AsyncSession,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[models.Lead]:
        """Retorna todos os leads cadastrados ordenados por criação descendente com suporte opcional a paginação."""
        query = select(models.Lead).order_by(models.Lead.criado_em.desc())
        if limit is not None:
            query = query.limit(limit).offset(offset)
        resultado = await db.execute(query)
        return list(resultado.scalars().all())

    @staticmethod
    async def create(
        db: AsyncSession,
        telefone: str,
        nome: Optional[str] = None,
        tipo_entrada: Optional[models.TipoEntradaLead] = models.TipoEntradaLead.INBOUND,
        origem_canal: Optional[str] = "WHATSAPP_DIRETO",
        etapa_funil: Optional[models.EtapaFunil] = models.EtapaFunil.NOVO_CONTATO,
        desfecho: Optional[models.DesfechoLead] = models.DesfechoLead.EM_ANDAMENTO,
        controle: Optional[models.ControleAtendimento] = models.ControleAtendimento.PILOTO_IA,
        temperatura: Optional[models.TemperaturaLead] = models.TemperaturaLead.FRIO,
        valor_estimado: Optional[float] = None,
        tags: Optional[List[str]] = None
    ) -> models.Lead:
        """Cria e persiste um novo Lead com as 4 dimensões de vendas e canal de aquisição."""
        novo_lead = models.Lead(
            nome=nome,
            telefone=telefone,
            tipo_entrada=tipo_entrada or models.TipoEntradaLead.INBOUND,
            origem_canal=origem_canal or "WHATSAPP_DIRETO",
            etapa_funil=etapa_funil or models.EtapaFunil.NOVO_CONTATO,
            desfecho=desfecho or models.DesfechoLead.EM_ANDAMENTO,
            controle=controle or models.ControleAtendimento.PILOTO_IA,
            temperatura=temperatura or models.TemperaturaLead.FRIO,
            valor_estimado=valor_estimado,
            tags=tags or [],
            opt_out=False
        )
        try:
            db.add(novo_lead)
            await db.commit()
            await db.refresh(novo_lead)
            return novo_lead
        except IntegrityError:
            await db.rollback()
            existente = await LeadRepository.get_by_phone(db, telefone)
            if existente:
                return existente
            raise

    @staticmethod
    async def update_multidimensional(
        db: AsyncSession,
        lead: models.Lead,
        nome: Optional[str] = None,
        tipo_entrada: Optional[models.TipoEntradaLead] = None,
        origem_canal: Optional[str] = None,
        etapa_funil: Optional[models.EtapaFunil] = None,
        desfecho: Optional[models.DesfechoLead] = None,
        controle: Optional[models.ControleAtendimento] = None,
        temperatura: Optional[models.TemperaturaLead] = None,
        motivo_perda: Optional[str] = None,
        valor_estimado: Optional[float] = None,
        tags: Optional[List[str]] = None,
        opt_out: Optional[bool] = None,
        resumo_perfil: Optional[str] = None,
        dados_qualificacao: Optional[dict] = None
    ) -> models.Lead:
        """Atualiza as dimensões, dados cadastrais e inteligência do lead de forma atômica."""
        if nome is not None:
            lead.nome = nome
        if tipo_entrada is not None:
            lead.tipo_entrada = tipo_entrada
        if origem_canal is not None:
            lead.origem_canal = origem_canal
        if etapa_funil is not None:
            lead.etapa_funil = etapa_funil
        if desfecho is not None:
            lead.desfecho = desfecho
        if controle is not None:
            lead.controle = controle
        if temperatura is not None:
            lead.temperatura = temperatura
        if motivo_perda is not None:
            lead.motivo_perda = motivo_perda
        if valor_estimado is not None:
            lead.valor_estimado = valor_estimado
        if tags is not None:
            lead.tags = tags
        if opt_out is not None:
            lead.opt_out = opt_out
        if resumo_perfil is not None:
            lead.resumo_perfil = resumo_perfil
        if dados_qualificacao is not None:
            lead.dados_qualificacao = dados_qualificacao
        await db.commit()
        await db.refresh(lead)
        return lead

    @staticmethod
    def sincronizar_tags(
        lead: models.Lead,
        adicionar: Optional[List[str]] = None,
        remover: Optional[List[str]] = None
    ) -> List[str]:
        """Adiciona e remove tags de forma idempotente, higienizada e normalizada no Lead."""
        tags_set = set(t.strip().upper() for t in (lead.tags or []) if t and t.strip())
        if remover:
            for r in remover:
                if r and r.strip():
                    tags_set.discard(r.strip().upper())
        if adicionar:
            for a in adicionar:
                if a and a.strip():
                    tags_set.add(a.strip().upper())
        lead.tags = sorted(list(tags_set))
        return lead.tags

    @staticmethod
    async def delete_interactions_by_lead_id(db: AsyncSession, lead_id: int) -> int:
        """Deleta todas as interações vinculadas a um Lead."""
        result = await db.execute(delete(models.Interacao).where(models.Interacao.lead_id == lead_id))
        return result.rowcount

    @staticmethod
    async def delete_lead(db: AsyncSession, lead: models.Lead) -> None:
        """Remove o registro do Lead."""
        await db.delete(lead)
        await db.commit()

    @staticmethod
    async def get_interactions(db: AsyncSession, lead_id: int) -> List[models.Interacao]:
        """Retorna histórico cronológico de interações de um Lead."""
        query = (
            select(models.Interacao)
            .where(models.Interacao.lead_id == lead_id)
            .order_by(models.Interacao.criado_em.asc())
        )
        resultado = await db.execute(query)
        return list(resultado.scalars().all())

    @staticmethod
    async def get_recent_interactions(db: AsyncSession, lead_id: int, limit: int) -> List[models.Interacao]:
        """
        Retorna as últimas N interações de um Lead em ordem cronológica (mais antiga -> mais recente).
        """
        query = (
            select(models.Interacao)
            .where(models.Interacao.lead_id == lead_id)
            .order_by(models.Interacao.criado_em.desc())
            .limit(limit)
        )
        resultado = await db.execute(query)
        return list(reversed(resultado.scalars().all()))

    @staticmethod
    async def get_latest_interaction_by_origins(
        db: AsyncSession,
        lead_id: int,
        origens: List[models.InteracaoOrigem]
    ) -> Optional[models.Interacao]:
        """Retorna a interação mais recente de um lead filtrada por uma lista de origens."""
        query = (
            select(models.Interacao)
            .where(
                models.Interacao.lead_id == lead_id,
                models.Interacao.origem.in_(origens)
            )
            .order_by(models.Interacao.criado_em.desc())
            .limit(1)
        )
        resultado = await db.execute(query)
        return resultado.scalars().first()

    @staticmethod
    async def add_interaction(
        db: AsyncSession,
        lead_id: int,
        origem: models.InteracaoOrigem,
        texto: str
    ) -> models.Interacao:
        """Registra uma nova interação vinculada ao Lead (higieniza bytes nulos para Postgres)."""
        texto_limpo = str(texto or "").replace("\x00", "")
        nova_interacao = models.Interacao(
            lead_id=lead_id,
            origem=origem,
            texto=texto_limpo
        )
        db.add(nova_interacao)
        await db.commit()
        await db.refresh(nova_interacao)
        return nova_interacao

    @staticmethod
    async def salvar_dossie(
        db: AsyncSession,
        lead: models.Lead,
        dossie_dict: dict
    ) -> models.Lead:
        """Persiste o Dossiê Executivo Comercial no cadastro do Lead."""
        lead.dossie_comercial = dossie_dict
        await db.commit()
        return lead

    @staticmethod
    async def recarregar_lead(
        db: AsyncSession,
        lead_id: int
    ) -> Optional[models.Lead]:
        """
        Recarrega o estado mais recente do Lead diretamente do banco (populate_existing=True),
        isolando completamente a semântica da sessão SQLAlchemy do Application Service.
        """
        return await db.get(models.Lead, lead_id, populate_existing=True)

