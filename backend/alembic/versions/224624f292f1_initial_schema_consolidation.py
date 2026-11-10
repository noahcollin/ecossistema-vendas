"""initial_schema_consolidation

Revision ID: 224624f292f1
Revises: 
Create Date: 2026-09-28 19:46:15.576800

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '224624f292f1'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Consolidação idempotente do schema inicial.
    Suporta tanto provisionamento do zero (banco PostgreSQL vazio em produção/CI)
    quanto migração de bases legadas que possuíam colunas VARCHAR em `leads`.
    """
    # 1. Criação idempotente de todos os tipos Enum do domínio no PostgreSQL
    op.execute(
        "DO $$ BEGIN CREATE TYPE tipoentradalead AS ENUM ('INBOUND', 'OUTBOUND'); "
        "EXCEPTION WHEN duplicate_object THEN null; END $$;"
    )
    op.execute(
        "DO $$ BEGIN CREATE TYPE etapafunil AS ENUM ('NOVO_CONTATO', 'QUALIFICACAO', 'NEGOCIACAO', 'FECHAMENTO'); "
        "EXCEPTION WHEN duplicate_object THEN null; END $$;"
    )
    op.execute(
        "DO $$ BEGIN CREATE TYPE desfecholead AS ENUM ('EM_ANDAMENTO', 'GANHO', 'PERDIDO', 'CONGELADO_CADENCIA'); "
        "EXCEPTION WHEN duplicate_object THEN null; END $$;"
    )
    op.execute(
        "DO $$ BEGIN CREATE TYPE controleatendimento AS ENUM ('PILOTO_IA', 'TRANSBORDO_SOLICITADO', 'HUMANO_ASSUMIU'); "
        "EXCEPTION WHEN duplicate_object THEN null; END $$;"
    )
    op.execute(
        "DO $$ BEGIN CREATE TYPE temperaturalead AS ENUM ('FRIO', 'MORNO', 'QUENTE'); "
        "EXCEPTION WHEN duplicate_object THEN null; END $$;"
    )
    op.execute(
        "DO $$ BEGIN CREATE TYPE interacaoorigem AS ENUM ('CLIENTE', 'IA', 'HUMANO', 'SISTEMA'); "
        "EXCEPTION WHEN duplicate_object THEN null; END $$;"
    )
    op.execute(
        "DO $$ BEGIN CREATE TYPE statusfollowup AS ENUM "
        "('PENDENTE', 'DISPARADO', 'CANCELADO_POR_RESPOSTA', 'EXPIRADO', 'ABORTADO'); "
        "EXCEPTION WHEN duplicate_object THEN null; END $$;"
    )

    # 2. Criação idempotente das 4 tabelas base (caso o banco esteja vazio)
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS configuracoes_operacionais (
            id SERIAL PRIMARY KEY,
            chave VARCHAR(50) NOT NULL DEFAULT 'geral',
            dados JSON NOT NULL DEFAULT '{}'::json,
            atualizado_em TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
        );
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS leads (
            id SERIAL PRIMARY KEY,
            nome VARCHAR,
            telefone VARCHAR NOT NULL,
            tipo_entrada tipoentradalead DEFAULT 'INBOUND'::tipoentradalead,
            origem_canal VARCHAR DEFAULT 'WHATSAPP_DIRETO',
            etapa_funil etapafunil DEFAULT 'NOVO_CONTATO'::etapafunil,
            desfecho desfecholead DEFAULT 'EM_ANDAMENTO'::desfecholead,
            controle controleatendimento DEFAULT 'PILOTO_IA'::controleatendimento,
            temperatura temperaturalead DEFAULT 'FRIO'::temperaturalead,
            motivo_perda VARCHAR,
            valor_estimado DOUBLE PRECISION,
            tags JSONB DEFAULT '[]'::jsonb,
            opt_out BOOLEAN DEFAULT FALSE,
            resumo_perfil VARCHAR,
            dados_qualificacao JSONB,
            dossie_comercial JSONB,
            criado_em TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
        );
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS interacoes (
            id SERIAL PRIMARY KEY,
            lead_id INTEGER NOT NULL REFERENCES leads (id) ON DELETE CASCADE,
            origem interacaoorigem NOT NULL,
            texto VARCHAR NOT NULL,
            criado_em TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
        );
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS followups_agendados (
            id SERIAL PRIMARY KEY,
            lead_id INTEGER NOT NULL REFERENCES leads (id) ON DELETE CASCADE,
            etapa_funil etapafunil NOT NULL,
            tentativa INTEGER NOT NULL DEFAULT 1,
            agendado_para TIMESTAMP WITHOUT TIME ZONE NOT NULL,
            status statusfollowup DEFAULT 'PENDENTE'::statusfollowup,
            mensagem_disparada VARCHAR,
            criado_em TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
            atualizado_em TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
        );
        """
    )

    # 3. Normalização retrocompatível de colunas em bases pré-existentes
    op.execute("ALTER TABLE leads ALTER COLUMN tipo_entrada DROP DEFAULT;")
    op.execute("ALTER TABLE leads ALTER COLUMN etapa_funil DROP DEFAULT;")
    op.execute("ALTER TABLE leads ALTER COLUMN desfecho DROP DEFAULT;")
    op.execute("ALTER TABLE leads ALTER COLUMN controle DROP DEFAULT;")
    op.execute("ALTER TABLE leads ALTER COLUMN temperatura DROP DEFAULT;")

    op.alter_column(
        'leads',
        'tipo_entrada',
        existing_type=sa.VARCHAR(length=50),
        type_=sa.Enum('INBOUND', 'OUTBOUND', name='tipoentradalead'),
        existing_nullable=True,
        postgresql_using="tipo_entrada::text::tipoentradalead",
    )
    op.alter_column(
        'leads',
        'etapa_funil',
        existing_type=sa.VARCHAR(length=50),
        type_=sa.Enum('NOVO_CONTATO', 'QUALIFICACAO', 'NEGOCIACAO', 'FECHAMENTO', name='etapafunil'),
        existing_nullable=True,
        postgresql_using="etapa_funil::text::etapafunil",
    )
    op.alter_column(
        'leads',
        'desfecho',
        existing_type=sa.VARCHAR(length=50),
        type_=sa.Enum('EM_ANDAMENTO', 'GANHO', 'PERDIDO', 'CONGELADO_CADENCIA', name='desfecholead'),
        existing_nullable=True,
        postgresql_using="desfecho::text::desfecholead",
    )
    op.alter_column(
        'leads',
        'controle',
        existing_type=sa.VARCHAR(length=50),
        type_=sa.Enum('PILOTO_IA', 'TRANSBORDO_SOLICITADO', 'HUMANO_ASSUMIU', name='controleatendimento'),
        existing_nullable=True,
        postgresql_using="controle::text::controleatendimento",
    )
    op.alter_column(
        'leads',
        'temperatura',
        existing_type=sa.VARCHAR(length=20),
        type_=sa.Enum('FRIO', 'MORNO', 'QUENTE', name='temperaturalead'),
        existing_nullable=True,
        postgresql_using="temperatura::text::temperaturalead",
    )

    op.execute("ALTER TABLE leads ALTER COLUMN tipo_entrada SET DEFAULT 'INBOUND'::tipoentradalead;")
    op.execute("ALTER TABLE leads ALTER COLUMN etapa_funil SET DEFAULT 'NOVO_CONTATO'::etapafunil;")
    op.execute("ALTER TABLE leads ALTER COLUMN desfecho SET DEFAULT 'EM_ANDAMENTO'::desfecholead;")
    op.execute("ALTER TABLE leads ALTER COLUMN controle SET DEFAULT 'PILOTO_IA'::controleatendimento;")
    op.execute("ALTER TABLE leads ALTER COLUMN temperatura SET DEFAULT 'FRIO'::temperaturalead;")

    op.alter_column(
        'leads',
        'resumo_perfil',
        existing_type=sa.TEXT(),
        type_=sa.String(),
        existing_nullable=True,
    )

    # 4. Criação idempotente de todos os índices únicos e analíticos
    op.execute("CREATE INDEX IF NOT EXISTS ix_configuracoes_operacionais_id ON configuracoes_operacionais (id);")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_configuracoes_operacionais_chave ON configuracoes_operacionais (chave);")

    op.execute("CREATE INDEX IF NOT EXISTS ix_leads_id ON leads (id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_leads_nome ON leads (nome);")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_leads_telefone ON leads (telefone);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_leads_controle ON leads (controle);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_leads_desfecho ON leads (desfecho);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_leads_etapa_funil ON leads (etapa_funil);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_leads_motivo_perda ON leads (motivo_perda);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_leads_opt_out ON leads (opt_out);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_leads_origem_canal ON leads (origem_canal);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_leads_temperatura ON leads (temperatura);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_leads_tipo_entrada ON leads (tipo_entrada);")

    op.execute("CREATE INDEX IF NOT EXISTS ix_interacoes_id ON interacoes (id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_interacoes_lead_criado ON interacoes (lead_id, criado_em);")

    op.execute("CREATE INDEX IF NOT EXISTS ix_followups_agendados_id ON followups_agendados (id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_followups_agendados_lead_id ON followups_agendados (lead_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_followups_agendados_agendado_para ON followups_agendados (agendado_para);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_followups_agendados_status ON followups_agendados (status);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_followup_status_agendado ON followups_agendados (status, agendado_para);")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP TABLE IF EXISTS followups_agendados CASCADE;")
    op.execute("DROP TABLE IF EXISTS interacoes CASCADE;")
    op.execute("DROP TABLE IF EXISTS configuracoes_operacionais CASCADE;")
    op.execute("DROP TABLE IF EXISTS leads CASCADE;")

    op.execute("DROP TYPE IF EXISTS statusfollowup;")
    op.execute("DROP TYPE IF EXISTS interacaoorigem;")
    op.execute("DROP TYPE IF EXISTS temperaturalead;")
    op.execute("DROP TYPE IF EXISTS controleatendimento;")
    op.execute("DROP TYPE IF EXISTS desfecholead;")
    op.execute("DROP TYPE IF EXISTS etapafunil;")
    op.execute("DROP TYPE IF EXISTS tipoentradalead;")
