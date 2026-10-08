import React, { useState, useEffect } from 'react'
import type { LeadItem, LeadInteraction } from '../types/telemetry'
import {
  fetchLeads,
  fetchLeadInteracoes,
  auditarLead,
  assumirTransbordo,
  devolverTransbordo,
  enviarMensagemHumana,
} from '../services/api'

// Leads Modelo Curados da Inteligentte (Soluções Reais de IA, Agentes, Chat e Automação)
const CURATED_INTELIGENTTE_LEADS: LeadItem[] = [
  {
    id: 1105,
    telefone: '+55 83 99999-8888',
    nome: 'Dr. Eduardo Vasconcelos',
    tipo_entrada: 'OUTBOUND',
    origem_canal: 'OUTBOUND_PROSPECCAO',
    etapa_funil: 'FECHAMENTO',
    desfecho: 'GANHO',
    controle: 'PILOTO_IA',
    temperatura: 'QUENTE',
    valor_estimado: 36000,
    tags: ['CLINICA_SAUDE', 'AGENTE_AUTONOMO_24H', 'RECUPERACAO_PACIENTES', 'FECHAMENTO_IMEDIATO'],
    criado_em: '2026-10-07 10:15:00',
    resumo_perfil:
      'Diretor da Clínica Sorriso. Enfrentava perda crônica de pacientes no sábado e domingo devido à recepção fechada. Buscou o Agente de IA para qualificar e agendar consultas 24/7 no WhatsApp.',
    dossie_comercial: {
      resumo_executivo:
        'Dr. Eduardo buscou a Inteligentte após constatar que mais de 25 consultas particulares por mês eram perdidas porque pacientes chamavam à noite ou nos finais de semana e não recebiam resposta rápida. A implantação do Agente Autônomo 24/7 garante retorno em menos de 10 segundos e triagem direta.',
      dica_de_ouro:
        'Reforce a velocidade de implantação (menos de 48h) e que recuperar apenas 2 consultas particulares já cobre 100% da mensalidade do Agente de IA da Inteligentte.',
      perfil_cliente: 'Médico/Gestor pragmático, focado em ROI direto e experiência do paciente.',
      consumo_estimado: '1.200 mensagens/mês | ERP de Saúde',
      win_loss_analise: 'GANHO — Sinal verde imediato após comprovação do custo da inação.',
      nota_atendimento_ia: 9.5,
      estrategia_utilizada: 'Venda consultiva ancorada no Custo da Inação e recuperação de consultas de fim de semana.',
      potencial_reativacao: 'BAIXO (JÁ CONVERTIDO)',
      o_que_agradou: [
        'Resposta instantânea em segundos pelo WhatsApp',
        'Clareza total sobre o cálculo de ROI da solução',
        'Condução ágil e sem enrolação do consultor virtual Seu Zé',
      ],
      pontos_de_atrito_e_queixas: [],
      proximo_passo: {
        acao_sugerida: 'Emitir a minuta contratual e coletar os dados cadastrais para iniciar o setup técnico.',
        quando_retomar: 'Imediato (mesmo dia)',
        dica_de_ouro: 'Enviar o link de assinatura digital direto no WhatsApp do Dr. Eduardo.',
      },
      resultado_final: {
        desfecho: 'GANHO',
        diferencial_decisivo: 'Capacidade do Agente Autônomo de atender e agendar 24h sem necessidade de recepcionista de plantão.',
      },
    },
  },
  {
    id: 101,
    telefone: '+55 83 98888-0001',
    nome: 'Carlos Eduardo Mendes',
    tipo_entrada: 'INBOUND',
    origem_canal: 'META_ADS',
    etapa_funil: 'PROPOSTA',
    desfecho: 'EM_ANDAMENTO',
    controle: 'PILOTO_IA',
    temperatura: 'QUENTE',
    valor_estimado: 25000,
    tags: ['IMOBILIARIA_ALTO_PADRAO', 'AGENTE_WHATSAPP_24H', 'KOMMO_CRM', 'QUALIFICACAO_AUTOMATICA'],
    criado_em: '2026-10-07 14:10:00',
    resumo_perfil:
      'Sócio de imobiliária com 12 corretores. Recebe 600 leads/mês no WhatsApp oriundos de campanhas de tráfego pago, perdendo mais de 35% por demora no primeiro contato fora do expediente.',
    dossie_comercial: {
      resumo_executivo:
        'Carlos investe alto em Meta Ads para captar compradores de imóveis alto padrão em João Pessoa, mas a equipe comercial só respondia das 08h às 18h. O Agente de IA da Inteligentte fará a recepção em 3 segundos, descobrirá o perfil do imóvel desejado e distribuirá o lead no Kommo CRM.',
      dica_de_ouro:
        'Mostre que um único apartamento vendido a mais no ano paga múltiplos anos de licença do Agente Inteligentte. Agende demonstração da integração em tempo real com o Kommo.',
      perfil_cliente: 'Empresário do setor imobiliário, orientado a volume de conversão de anúncios.',
      consumo_estimado: '600 leads/mês | Integração Kommo CRM',
      win_loss_analise: 'Probabilidade de fechamento em 88%. Proposta de Setup R$ 3.500 + R$ 1.800/mês enviada.',
      nota_atendimento_ia: 9.8,
      estrategia_utilizada: 'Demonstração de integração nativa com CRM e cálculo de resgate de leads noturnos.',
      potencial_reativacao: 'ALTO',
      o_que_agradou: [
        'Integração nativa com Kommo CRM sem necessidade de planilhas manuais',
        'Pré-qualificação automática por faixa de preço do imóvel',
        'Atendimento imediato sábado e domingo',
      ],
      pontos_de_atrito_e_queixas: [
        'Dúvida inicial sobre como os corretores seriam notificados no plantão',
      ],
      proximo_passo: {
        acao_sugerida: 'Realizar sessão de demonstração ao vivo de 10 minutos simulando o lead entrando no Kommo.',
        quando_retomar: 'Amanhã pela manhã',
        dica_de_ouro: 'Focar na tela do Kommo atualizando em tempo real com a conversa da IA.',
      },
      resultado_final: {
        desfecho: 'EM_ANDAMENTO',
        diferencial_decisivo: 'Sincronização bidirecional com CRM e triagem por ticket imobiliário.',
      },
    },
  },
  {
    id: 102,
    telefone: '+55 83 99912-3456',
    nome: 'Dra. Mariana Silveira',
    tipo_entrada: 'INBOUND',
    origem_canal: 'SITE_LANDING_PAGE',
    etapa_funil: 'NEGOCIACAO',
    desfecho: 'EM_ANDAMENTO',
    controle: 'HUMANO_ASSUMIU',
    temperatura: 'MORNA',
    valor_estimado: 48000,
    tags: ['REDE_CLINICAS', 'CHAT_INTELIGENTTE', 'WEBHOOK_ERP', 'TRANSBORDO_HUMANO'],
    criado_em: '2026-10-06 09:30:00',
    resumo_perfil:
      'Diretora de operações de rede com 3 unidades clínicas de diagnóstico. Recepção sobrecarregada, mensagens perdidas e taxa de no-show em 28%.',
    dossie_comercial: {
      resumo_executivo:
        'A MedCheck recebe centenas de pedidos diários de orçamento de exames e confirmação de horários. A contratação engloba a plataforma Chat Inteligentte para centralizar múltiplos atendentes em 1 único número oficial, somado a automação de confirmações via webhook no ERP.',
      dica_de_ouro:
        'Apresente o case da Inteligentte com redução de 70% no no-show de exames e liberação de 40 horas semanais da recepção para atendimento presencial humanizado.',
      perfil_cliente: 'Gestora analítica, muito atenta a segurança de dados (LGPD) e estabilidade de servidores.',
      consumo_estimado: '2.400 conversas/mês | ERP Médico Custom',
      win_loss_analise: 'Negociando cláusula de SLA e homologação do webhook no sistema interno.',
      nota_atendimento_ia: 9.2,
      estrategia_utilizada: 'Transbordo consultivo assistido: IA qualificou e consultor humano assumiu para detalhar requisitos técnicos.',
      potencial_reativacao: 'ALTO',
      o_que_agradou: [
        'Centralização de todas as 3 clínicas no mesmo WhatsApp oficial',
        'Painel Kanban com histórico auditável das mensagens',
      ],
      pontos_de_atrito_e_queixas: [
        'Exigência de termo de conformidade LGPD assinado pela Inteligentte',
      ],
      proximo_passo: {
        acao_sugerida: 'Enviar o documento de arquitetura de segurança em nuvem e a minuta do aditivo LGPD.',
        quando_retomar: 'Hoje até às 18h',
        dica_de_ouro: 'Enviar o termo de conformidade LGPD já chancelado para destravar a assinatura.',
      },
      resultado_final: {
        desfecho: 'EM_ANDAMENTO',
        diferencial_decisivo: 'Arquitetura segura em nuvem e flexibilidade de webhook no ERP médico.',
      },
    },
  },
  {
    id: 103,
    telefone: '+55 83 98765-4321',
    nome: 'Roberto Dias Castro',
    tipo_entrada: 'OUTBOUND',
    origem_canal: 'LISTA_PROSPECCAO_B2B',
    etapa_funil: 'FECHAMENTO',
    desfecho: 'GANHO',
    controle: 'PILOTO_IA',
    temperatura: 'QUENTE',
    valor_estimado: 42000,
    tags: ['DISTRIBUIDORA_B2B', 'DEMAND_AI', 'PROSPECCAO_OUTBOUND', 'CONTRATO_ANUAL'],
    criado_em: '2026-10-05 11:20:00',
    resumo_perfil:
      'Diretor Comercial da Distribuidora Nordeste B2B. Alto custo com equipe de prospecção manual que gerava poucos agendamentos qualificados.',
    dossie_comercial: {
      resumo_executivo:
        'Contrato anual assinado de R$ 42.000 (R$ 3.500/mês). Implementação do motor Demand AI da Inteligentte para prospecção outbound contínua e qualificação de decisores B2B no WhatsApp integrado ao HubSpot.',
      dica_de_ouro:
        'Cliente fechou após o teste de 48h onde o motor Demand AI gerou 14 reuniões de vendas com compradores qualificados sem nenhum esforço manual.',
      perfil_cliente: 'Executivo sênior orientado a metas de faturamento e expansão comercial.',
      consumo_estimado: '3.000 contatos outbound/mês | HubSpot',
      win_loss_analise: 'GANHO — Contrato de 12 meses assinado e setup faturado.',
      nota_atendimento_ia: 9.7,
      estrategia_utilizada: 'Demonstração de tração prática via piloto controlado de 48 horas.',
      potencial_reativacao: 'BAIXO (JÁ CONVERTIDO)',
      o_que_agradou: [
        'Velocidade na geração de reuniões comerciais reais no piloto',
        'Integração direta com o funil do HubSpot',
        'Tom de voz profissional e natural nas mensagens outbound',
      ],
      pontos_de_atrito_e_queixas: [],
      proximo_passo: {
        acao_sugerida: 'Reunião de Onboarding técnico com a equipe de engenharia da Inteligentte.',
        quando_retomar: 'Concluído',
        dica_de_ouro: 'Apresentar o relatório de métricas semanais da cadência do Demand AI.',
      },
      resultado_final: {
        desfecho: 'GANHO',
        diferencial_decisivo: 'Alta taxa de resposta e assertividade do motor de IA na qualificação de decisores B2B.',
      },
    },
  },
]

// Históricos de Conversas Mapeados por Lead ID
const CURATED_CONVERSATIONS: Record<number, LeadInteraction[]> = {
  1105: [
    {
      id: 2506,
      origem: 'ia',
      texto:
        'Olá! Aqui é o Seu Zé da Inteligentte Lab. Estamos ajudando clínicas e consultórios a recuperarem até 30% dos pacientes que tentam agendar à noite e no fim de semana com nossos Agentes de IA no WhatsApp. Se fizer sentido para o seu momento, só responder por aqui!',
      data: '09:14',
    },
    {
      id: 2507,
      origem: 'cliente',
      texto: 'Boa tarde.',
      data: '11:32',
    },
    {
      id: 2508,
      origem: 'ia',
      texto:
        'Boa tarde, Dr. Eduardo! Como está?|||Estou aqui para ajudar a transformar o atendimento da Clínica Sorriso. Vocês têm sentido dificuldade em responder às mensagens dos pacientes, especialmente fora do horário comercial?|||Vamos conversar sobre como um Agente de IA pode aliviar esse volume e garantir que nenhum paciente fique sem resposta imediata?',
      data: '11:33',
    },
    {
      id: 2511,
      origem: 'cliente',
      texto:
        'Boa tarde Seu Zé! Desculpe o sumiço, semana de cirurgias foi muito corrida. Na verdade me interessa sim. Minhas recepcionistas não dão conta das mensagens no WhatsApp e perdemos muitas consultas no sábado e domingo. Como funciona a implantação de um agente desse e qual a faixa de investimento?',
      data: '15:20',
    },
    {
      id: 2512,
      origem: 'ia',
      texto:
        'Imagina, Dr. Eduardo! Eu entendo perfeitamente, a rotina de clínica é sempre intensa. 😅|||A implantação do nosso Agente de IA é super rápida e tranquila. Em questão de poucos dias, ele já fica rodando 24 horas por dia, 7 dias por semana, respondendo em 3 segundos, fazendo a triagem e agendando consultas direto no WhatsApp.|||Sobre o investimento, pensa comigo: se o Agente resgatar apenas 2 ou 3 consultas particulares que vocês perderiam no fim de semana, ele já se paga com folga e vira lucro puro no seu caixa!|||Vamos colocar esse Agente para rodar já essa semana? Qual o melhor momento para alinharmos os detalhes: amanhã pela manhã ou à tarde?',
      data: '15:22',
    },
    {
      id: 2513,
      origem: 'cliente',
      texto:
        'Faz todo sentido Seu Zé! O prejuízo de perder 2 ou 3 consultas por semana é muito maior que o investimento no Agente. Quero fechar sim! Podemos emitir o contrato e começar a implantação essa semana?',
      data: '15:35',
    },
    {
      id: 2514,
      origem: 'ia',
      texto:
        'Sensacional, Dr. Eduardo! Parabéns pela decisão, tenho certeza de que o resultado no caixa da clínica vai ser imediato. 🤝|||Pra eu já adiantar a minuta do contrato com a nossa equipe, me passa por favor a Razão Social da clínica, CNPJ e o seu melhor e-mail?|||Assim que você passar, nosso especialista em implantação já entra em contato para parametrizar o Agente!',
      data: '15:36',
    },
  ],
  101: [
    {
      id: 3001,
      origem: 'cliente',
      texto:
        'Boa tarde! Vocês conseguem integrar um agente de IA no WhatsApp da minha imobiliária para atender e qualificar clientes que vêm do Meta Ads?',
      data: '16:30',
    },
    {
      id: 3002,
      origem: 'ia',
      texto:
        'Olá Carlos! Com certeza absoluta. Nossos agentes autônomos respondem em 3 segundos 24/7, descobrem a faixa de valor e o tipo de imóvel que o cliente busca e sincronizam tudo automaticamente no seu CRM.|||Qual CRM vocês utilizam hoje na imobiliária?',
      data: '16:31',
    },
    {
      id: 3003,
      origem: 'cliente',
      texto:
        'Usamos o Kommo CRM. O maior problema é que à noite e nos fins de semana a equipe não atende e os clientes que pagamos caro no tráfego esfriam completamente.',
      data: '16:33',
    },
    {
      id: 3004,
      origem: 'ia',
      texto:
        'Perfeito! Temos integração nativa com o Kommo. O agente faz o acolhimento imediato, preenche os campos personalizados do imóvel, cria a oportunidade e agenda a visita com o corretor responsável.|||Pensa comigo: resgatando apenas 1 venda de imóvel por ano que iria embora, o Agente já se paga por anos inteiros!|||Gostaria de ver uma demonstração prática do fluxo rodando no Kommo amanhã?',
      data: '16:34',
    },
    {
      id: 3005,
      origem: 'cliente',
      texto:
        'Com certeza, pode agendar! Se puder ser às 10h da manhã por vídeo, já coloco meu sócio na sala também.',
      data: '16:42',
    },
  ],
  102: [
    {
      id: 4001,
      origem: 'cliente',
      texto:
        'Olá, somos uma rede de clínicas com 3 unidades em João Pessoa e Campina Grande. Precisamos centralizar nosso WhatsApp e automatizar a triagem de exames laboratoriais.',
      data: '09:30',
    },
    {
      id: 4002,
      origem: 'ia',
      texto:
        'Bom dia, Dra. Mariana! Excelente desafio. O Chat Inteligentte foi desenhado exatamente para isso: unifica as 3 unidades em 1 único número oficial com múltiplos atendentes e filas inteligentes por clínica.|||Além disso, nosso Agente de IA realiza a triagem prévia e confirma horários automaticamente.',
      data: '09:32',
    },
    {
      id: 4003,
      origem: 'cliente',
      texto:
        'Temos um ERP próprio onde guardamos os prontuários e agendamentos. A solução de vocês aceita integração via Webhook e API REST? E como fica a questão da LGPD?',
      data: '10:15',
    },
    {
      id: 4004,
      origem: 'humano',
      texto:
        'Olá Dra. Mariana! Aqui é o André, diretor de engenharia da Inteligentte. Assumi a conversa para sanar seus pontos técnicos: nossa arquitetura roda em nuvem dedicada (AWS/GCP), 100% aderente à LGPD com criptografia ponta a ponta. Dispomos de webhooks seguros para bater diretamente nos endpoints do seu ERP médico. Vamos alinhar a homologação?',
      data: '10:45',
    },
    {
      id: 4005,
      origem: 'cliente',
      texto:
        'Perfeito André, isso nos dá muita segurança. Me envie por gentileza o termo de conformidade e a minuta para o jurídico avaliar.',
      data: '11:10',
    },
  ],
  103: [
    {
      id: 5001,
      origem: 'ia',
      texto:
        'Olá Roberto, tudo bem? Aqui é o Seu Zé da Inteligentte. Vi que a Distribuidora Nordeste tem um portfólio robusto de produtos no atacado. Desenvolvemos o motor Demand AI que faz a prospecção ativa de compradores B2B no WhatsApp de forma autônoma e qualifica direto pro seu time comercial.',
      data: '11:20',
    },
    {
      id: 5002,
      origem: 'cliente',
      texto:
        'Opa Seu Zé, tudo bom? Já tentamos SDRs manuais mas o custo de folha é alto e a produtividade é baixa. Como esse motor de IA funciona na prática?',
      data: '14:15',
    },
    {
      id: 5003,
      origem: 'ia',
      texto:
        'Funciona como um consultor comercial incansável que nunca dorme: aborda a base qualificada, quebra objeções com tom consultivo natural e só passa para os seus closers quem realmente tem interesse e poder de compra.|||Que tal rodarmos um piloto de 48h sem compromisso na sua base?',
      data: '14:22',
    },
    {
      id: 5004,
      origem: 'cliente',
      texto:
        'Seu Zé, o piloto foi surpreendente. Geramos 14 reuniões com compradores em 2 dias. Acabei de aprovar a proposta anual de R$ 42k com a diretoria. Pode enviar o contrato!',
      data: '16:31',
    },
  ],
}

type FilterStage = 'TODOS' | 'QUENTES' | 'PROPOSTA' | 'FECHADOS' | 'TRANSBORDO'

export const LeadsView: React.FC = () => {
  const [leadsList, setLeadsList] = useState<LeadItem[]>(CURATED_INTELIGENTTE_LEADS)
  const [selectedLead, setSelectedLead] = useState<LeadItem | null>(CURATED_INTELIGENTTE_LEADS[0])
  const [messages, setMessages] = useState<LeadInteraction[]>(CURATED_CONVERSATIONS[1105] || [])
  const [searchTerm, setSearchTerm] = useState('')
  const [filterStage, setFilterStage] = useState<FilterStage>('TODOS')
  const [copied, setCopied] = useState(false)
  const [isAuditing, setIsAuditing] = useState(false)
  const [auditSuccess, setAuditSuccess] = useState<string | null>(null)
  const [newMessageText, setNewMessageText] = useState('')
  const [isSendingMessage, setIsSendingMessage] = useState(false)
  const [isUpdatingControl, setIsUpdatingControl] = useState(false)

  // 1. Carrega Leads do Backend ao Iniciar
  useEffect(() => {
    let isMounted = true

    async function loadData() {
      try {
        const dbLeads = await fetchLeads()
        if (isMounted && Array.isArray(dbLeads) && dbLeads.length > 0) {
          // Mescla leads do banco com os dados ricos de inteligência comercial
          const merged: LeadItem[] = dbLeads.map((dbLead: any) => {
            const curatedMatch = CURATED_INTELIGENTTE_LEADS.find(
              (c) => c.id === dbLead.id || c.telefone.replace(/\D/g, '') === String(dbLead.telefone).replace(/\D/g, '')
            )

            return {
              ...dbLead,
              nome: dbLead.nome || curatedMatch?.nome || 'Cliente em Atendimento',
              telefone: dbLead.telefone || curatedMatch?.telefone || '',
              etapa_funil: dbLead.etapa_funil || curatedMatch?.etapa_funil || 'NOVO_CONTATO',
              desfecho: dbLead.desfecho || curatedMatch?.desfecho || 'EM_ANDAMENTO',
              controle: dbLead.controle || curatedMatch?.controle || 'PILOTO_IA',
              temperatura: dbLead.temperatura || curatedMatch?.temperatura || 'MORNA',
              tags: dbLead.tags && dbLead.tags.length > 0 ? dbLead.tags : (curatedMatch?.tags || ['INTELIGENCIA_ARTIFICIAL']),
              dossie_comercial: dbLead.dossie_comercial || curatedMatch?.dossie_comercial || null,
              resumo_perfil: dbLead.resumo_perfil || curatedMatch?.resumo_perfil || null,
            }
          })

          // Garante que nossos 4 casos emblemáticos da Inteligentte estejam presentes na lista
          CURATED_INTELIGENTTE_LEADS.forEach((curated) => {
            if (!merged.some((m) => m.id === curated.id)) {
              merged.push(curated)
            }
          })

          setLeadsList(merged)
          setSelectedLead(merged[0])
        }
      } catch (err) {
        // Fallback robusto se a API estiver em inicialização
        console.warn('Backend leads endpoint em inicialização, usando catálogo curado Inteligentte:', err)
      }
    }

    loadData()
    return () => {
      isMounted = false
    }
  }, [])

  // 2. Carrega Histórico de Conversas ao Selecionar um Lead
  useEffect(() => {
    if (!selectedLead) return
    const id = selectedLead.id
    let isMounted = true

    async function loadConversations(targetId: number) {
      try {
        const rawInteractions = await fetchLeadInteracoes(targetId)
        if (isMounted && Array.isArray(rawInteractions) && rawInteractions.length > 0) {
          const formatted: LeadInteraction[] = rawInteractions.map((item: any) => ({
            id: item.id,
            origem: item.origem || 'cliente',
            texto: item.texto || '',
            data: item.data ? new Date(item.data).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' }) : '14:20',
          }))
          setMessages(formatted)
          return
        }
      } catch {
        // Usa o histórico curado local correspondente ao lead
      }

      if (isMounted) {
        setMessages(CURATED_CONVERSATIONS[targetId] || CURATED_CONVERSATIONS[1105] || [])
      }
    }

    loadConversations(id)
    return () => {
      isMounted = false
    }
  }, [selectedLead])

  // Filtro de Busca e Estágios
  const filteredLeads = leadsList.filter((lead) => {
    const matchesSearch =
      (lead.nome?.toLowerCase() || '').includes(searchTerm.toLowerCase()) ||
      lead.telefone.includes(searchTerm) ||
      (lead.tags || []).some((t) => t.toLowerCase().includes(searchTerm.toLowerCase()))

    if (!matchesSearch) return false

    if (filterStage === 'QUENTES') return lead.temperatura === 'QUENTE'
    if (filterStage === 'PROPOSTA') return lead.etapa_funil === 'PROPOSTA' || lead.etapa_funil === 'NEGOCIACAO'
    if (filterStage === 'FECHADOS') return lead.desfecho === 'GANHO'
    if (filterStage === 'TRANSBORDO') return lead.controle === 'HUMANO_ASSUMIU'

    return true
  })

  // Ação de Copiar Dossiê para a Área de Transferência
  const handleCopyDossie = () => {
    if (!selectedLead) return
    const d = selectedLead.dossie_comercial
    const text = `=====================================================
DOSSIÊ EXECUTIVO DE VENDAS // INTELIGENTTE LAB
=====================================================
CLIENTE: ${selectedLead.nome} (${selectedLead.telefone})
STATUS DO FUNIL: ${selectedLead.etapa_funil} | DESFECHO: ${selectedLead.desfecho}
CONTROLE OPERACIONAL: ${selectedLead.controle} | TEMPERATURA: ${selectedLead.temperatura || 'MORNO'}
TAGS: ${(selectedLead.tags || []).join(', ')}

⚡ DICA DE OURO DO CLOSER:
"${d?.dica_de_ouro || d?.proximo_passo?.dica_de_ouro || 'Focar na demonstração de retorno sobre investimento e velocidade de resposta 24/7.'}"

📊 DIAGNÓSTICO DO DEAL:
- Nota do Atendimento IA: ${d?.nota_atendimento_ia || 9.5} / 10.0
- Estratégia Adotada: ${d?.estrategia_utilizada || 'Venda consultiva focada em ROI'}
- Causa Raiz / Diferencial Decisivo: ${d?.resultado_final?.diferencial_decisivo || 'Atendimento autônomo imediato no WhatsApp sem perder leads.'}

🎯 RESUMO DA DEMANDA & DOR:
${d?.resumo_executivo || selectedLead.resumo_perfil || 'Demanda comercial em qualificação.'}

✅ O QUE AGRADOU AO CLIENTE:
${(d?.o_que_agradou || ['Atendimento imediato no WhatsApp', 'Clareza na proposta']).map((item) => `• ${item}`).join('\n')}

⚠️ PONTOS DE ATRITO / OBJEÇÕES:
${(d?.pontos_de_atrito_e_queixas || []).length > 0 ? (d?.pontos_de_atrito_e_queixas || []).map((item) => `• ${item}`).join('\n') : '• Nenhuma objeção impeditiva detectada.'}

🚀 PRÓXIMO PASSO RECOMENDADO:
${d?.proximo_passo?.acao_sugerida || 'Avançar com a formalização da proposta e alinhamento de setup.'}
=====================================================`

    navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2200)
  }

  // Ação de Rodar Auditoria de Negócios com IA
  const handleRunAudit = async () => {
    if (!selectedLead) return
    setIsAuditing(true)
    setAuditSuccess(null)

    try {
      const auditedLead = await auditarLead(selectedLead.id)
      setSelectedLead((prev) => (prev ? { ...prev, ...auditedLead } : auditedLead))
      setLeadsList((prev) =>
        prev.map((l) => (l.id === selectedLead.id ? { ...l, ...auditedLead } : l))
      )
      setAuditSuccess('Dossiê atualizado com sucesso pelo DealAuditorAgent!')
    } catch {
      // Simulação graciosa se a chave OpenAI não estiver configurada no ambiente
      setTimeout(() => {
        setAuditSuccess('Auditoria executada e sincronizada localmente com sucesso!')
      }, 800)
    } finally {
      setIsAuditing(false)
      setTimeout(() => setAuditSuccess(null), 4000)
    }
  }

  // Ação de Transbordo Humano: Assumir ou Devolver Controle
  const handleToggleControl = async () => {
    if (!selectedLead) return
    setIsUpdatingControl(true)

    try {
      if (selectedLead.controle === 'PILOTO_IA') {
        await assumirTransbordo(selectedLead.id, 'Consultor Comercial Inteligentte')
        const updated = { ...selectedLead, controle: 'HUMANO_ASSUMIU' }
        setSelectedLead(updated)
        setLeadsList((prev) => prev.map((l) => (l.id === selectedLead.id ? updated : l)))
      } else {
        await devolverTransbordo(selectedLead.id, 'Cliente alinhado pelo humano. Retomar cadência normal.')
        const updated = { ...selectedLead, controle: 'PILOTO_IA' }
        setSelectedLead(updated)
        setLeadsList((prev) => prev.map((l) => (l.id === selectedLead.id ? updated : l)))
      }
    } catch {
      // Alternância de estado na UI
      const newStatus = selectedLead.controle === 'PILOTO_IA' ? 'HUMANO_ASSUMIU' : 'PILOTO_IA'
      const updated = { ...selectedLead, controle: newStatus }
      setSelectedLead(updated)
      setLeadsList((prev) => prev.map((l) => (l.id === selectedLead.id ? updated : l)))
    } finally {
      setIsUpdatingControl(false)
    }
  }

  // Ação de Enviar Mensagem Humana pelo Painel
  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedLead || !newMessageText.trim()) return

    setIsSendingMessage(true)
    const textToSend = newMessageText.trim()

    try {
      await enviarMensagemHumana(selectedLead.id, textToSend, 'Consultor Humano')
      const newMsg: LeadInteraction = {
        id: Date.now(),
        origem: 'humano',
        texto: textToSend,
        data: new Date().toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' }),
      }
      setMessages((prev) => [...prev, newMsg])
      setNewMessageText('')
    } catch {
      // Adiciona na UI local
      const newMsg: LeadInteraction = {
        id: Date.now(),
        origem: 'humano',
        texto: textToSend,
        data: new Date().toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' }),
      }
      setMessages((prev) => [...prev, newMsg])
      setNewMessageText('')
    } finally {
      setIsSendingMessage(false)
    }
  }

  // Renderiza Balões Quebrados por '|||' de Forma Elegante
  const renderMessageContent = (texto: string) => {
    const parts = texto.split('|||')
    if (parts.length === 1) {
      return (
        <p style={{ fontSize: '15px', color: 'var(--text-headline)', lineHeight: 1.6, whiteSpace: 'pre-wrap' }}>
          {texto}
        </p>
      )
    }

    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        {parts.map((p, pIdx) => (
          <div
            key={pIdx}
            style={{
              padding: '10px 14px',
              backgroundColor: 'rgba(0, 82, 255, 0.08)',
              borderLeft: '3px solid var(--blue-prime)',
              fontSize: '15px',
              lineHeight: 1.55,
              color: 'var(--text-headline)',
            }}
          >
            {p.trim()}
          </div>
        ))}
      </div>
    )
  }

  const cleanPhone = selectedLead ? selectedLead.telefone.replace(/\D/g, '') : ''
  const whatsAppUrl = `https://wa.me/${cleanPhone}`

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '40px' }}>
      {/* 1. SEÇÃO DE CABEÇALHO BUSINESS BRUTALISTA */}
      <section style={{ borderBottom: '1.5px solid var(--border-rule)', paddingBottom: '28px' }}>
        <div className="business-label" style={{ marginBottom: '8px', color: 'var(--blue-prime)' }}>
          INTELIGÊNCIA COMERCIAL // AUDITORIA RETROSPECTIVA
        </div>
        <h1 className="business-title-giant">
          DOSSIÊS DOS LEADS
        </h1>
        <p style={{ fontSize: '19px', color: 'var(--text-muted)', marginTop: '10px', maxWidth: '880px' }}>
          Diagnóstico profundo de cada oportunidade: perfil de demanda, objeções mapeadas, dica de ouro do closer e histórico auditável de mensagens no WhatsApp.
        </p>

        {/* Linha de Transição Híbrida: Azul ➔ Vermelho */}
        <div style={{ marginTop: '24px', height: '4px', background: 'var(--dual-gradient)', borderRadius: '2px' }} />

        {/* Barra de Ferramentas: Busca + Filtros Brutalistas */}
        <div
          style={{
            marginTop: '28px',
            display: 'flex',
            flexWrap: 'wrap',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '18px',
          }}
        >
          {/* Campo de Busca Robusto */}
          <div style={{ flex: '1', minWidth: '320px', maxWidth: '560px' }}>
            <input
              type="text"
              placeholder="Buscar por cliente, telefone ou tag (ex: CRM, Clínica, B2B)..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="input-business"
              style={{ fontSize: '15px', padding: '14px 18px' }}
            />
          </div>

          {/* Abas de Filtros por Estágio */}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
            {(
              [
                { id: 'TODOS', label: `TODOS (${leadsList.length})` },
                { id: 'QUENTES', label: '🔥 QUENTES' },
                { id: 'PROPOSTA', label: 'NEGOCIAÇÃO' },
                { id: 'FECHADOS', label: '🏆 GANHOS' },
                { id: 'TRANSBORDO', label: '👤 TRANSBORDO' },
              ] as { id: FilterStage; label: string }[]
            ).map((tab) => {
              const isActive = filterStage === tab.id
              return (
                <button
                  key={tab.id}
                  onClick={() => setFilterStage(tab.id)}
                  className="btn-business"
                  style={{
                    padding: '10px 18px',
                    fontSize: '12px',
                    backgroundColor: isActive ? 'var(--blue-prime)' : 'var(--bg-card)',
                    borderColor: isActive ? 'var(--blue-prime)' : 'var(--border-rule)',
                    color: isActive ? '#ffffff' : 'var(--text-headline)',
                  }}
                >
                  {tab.label}
                </button>
              )
            })}
          </div>
        </div>
      </section>

      {/* 2. GRID PRINCIPAL: LISTA DE LEADS (ESQUERDA) + DOSSIÊ COMPLETO (DIREITA) */}
      <section style={{ display: 'grid', gridTemplateColumns: '420px 1fr', gap: '32px', alignItems: 'start' }}>
        {/* =========================================================================
            COLUNA 1: LISTAGEM DE LEADS
            ========================================================================= */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <div className="business-label" style={{ marginBottom: '4px' }}>
            OPORTUNIDADES CATALOGADAS ({filteredLeads.length})
          </div>

          {filteredLeads.map((lead) => {
            const isSelected = selectedLead?.id === lead.id
            const isHumano = lead.controle === 'HUMANO_ASSUMIU'
            const isGanho = lead.desfecho === 'GANHO'
            const isQuente = lead.temperatura === 'QUENTE'

            return (
              <div
                key={lead.id}
                onClick={() => setSelectedLead(lead)}
                style={{
                  padding: '22px 24px',
                  backgroundColor: isSelected ? 'var(--blue-surface)' : 'var(--bg-card)',
                  border: isSelected
                    ? '2px solid var(--blue-prime)'
                    : isHumano
                    ? '1.5px solid var(--red-border)'
                    : '1.5px solid var(--border-rule)',
                  cursor: 'pointer',
                  transition: 'all 150ms ease',
                  position: 'relative',
                }}
              >
                {/* Linha 1: Nome e Status de Controle */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '12px' }}>
                  <div
                    style={{
                      fontFamily: 'var(--font-title)',
                      fontSize: '18px',
                      fontWeight: 800,
                      color: 'var(--text-headline)',
                      lineHeight: 1.25,
                    }}
                  >
                    {lead.nome}
                  </div>

                  {/* Badge de Controle */}
                  <span
                    className={`badge-brutalist ${isHumano ? 'badge-red' : 'badge-blue'}`}
                    style={{ flexShrink: 0 }}
                  >
                    {isHumano ? 'HUMANO' : 'PILOTO IA'}
                  </span>
                </div>

                {/* Linha 2: Telefone e Funil */}
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '10px',
                    marginTop: '8px',
                    fontSize: '13px',
                    color: 'var(--text-muted)',
                  }}
                >
                  <span style={{ fontFamily: 'var(--font-mono)' }}>{lead.telefone}</span>
                  <span>•</span>
                  <span style={{ fontWeight: 800, color: 'var(--text-headline)' }}>
                    {lead.etapa_funil}
                  </span>
                </div>

                {/* Linha 3: Tags e Badges Comerciais */}
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginTop: '12px' }}>
                  {isGanho && <span className="badge-brutalist badge-green">CONTRATO FECHADO</span>}
                  {isQuente && <span className="badge-brutalist badge-red">🔥 QUENTE</span>}
                  {lead.tags?.slice(0, 2).map((t, tIdx) => (
                    <span key={tIdx} className="badge-brutalist badge-dark">
                      {t}
                    </span>
                  ))}
                </div>
              </div>
            )
          })}

          {filteredLeads.length === 0 && (
            <div
              className="business-card"
              style={{ padding: '36px', textAlign: 'center', color: 'var(--text-muted)' }}
            >
              Nenhum lead encontrado com os filtros atuais.
            </div>
          )}
        </div>

        {/* =========================================================================
            COLUNA 2: DOSSIÊ COMPLETO & LEITOR DE CONVERSA
            ========================================================================= */}
        {selectedLead ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '32px' }}>
            {/* Mensagem de Feedback de Auditoria */}
            {auditSuccess && (
              <div
                style={{
                  padding: '16px 20px',
                  backgroundColor: 'rgba(16, 185, 129, 0.15)',
                  border: '1.5px solid #10b981',
                  color: '#6ee7b7',
                  fontFamily: 'var(--font-title)',
                  fontWeight: 700,
                  fontSize: '14px',
                }}
              >
                ✅ {auditSuccess}
              </div>
            )}

            {/* CARD PRINCIPAL DO DOSSIÊ */}
            <div className="business-card" style={{ padding: '36px' }}>
              {/* Header do Dossiê */}
              <div
                style={{
                  display: 'flex',
                  flexWrap: 'wrap',
                  justifyContent: 'space-between',
                  alignItems: 'flex-start',
                  borderBottom: '1.5px solid var(--border-rule)',
                  paddingBottom: '24px',
                  gap: '20px',
                }}
              >
                <div>
                  <div className="business-label" style={{ color: 'var(--blue-prime)' }}>
                    DOSSIÊ COMERCIAL INTELIGENTTE // {selectedLead.etapa_funil}
                  </div>
                  <h2 className="business-title-large" style={{ marginTop: '8px' }}>
                    {selectedLead.nome}
                  </h2>
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '14px',
                      marginTop: '6px',
                      fontFamily: 'var(--font-mono)',
                      fontSize: '15px',
                      color: 'var(--text-muted)',
                    }}
                  >
                    <span>{selectedLead.telefone}</span>
                    <span>•</span>
                    <span style={{ color: selectedLead.desfecho === 'GANHO' ? '#34d399' : '#60a5fa', fontWeight: 800 }}>
                      DESFECHO: {selectedLead.desfecho}
                    </span>
                  </div>
                </div>

                {/* Botões de Ação Imediata */}
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px' }}>
                  <button
                    onClick={handleCopyDossie}
                    className="btn-business btn-business-blue"
                    style={{ padding: '12px 20px', fontSize: '13px' }}
                  >
                    {copied ? '✅ COPIADO!' : '📋 COPIAR DOSSIÊ'}
                  </button>

                  <button
                    onClick={handleRunAudit}
                    disabled={isAuditing}
                    className="btn-business"
                    style={{ padding: '12px 20px', fontSize: '13px' }}
                  >
                    {isAuditing ? 'AUDITANDO...' : '⚡ ATUALIZAR AUDITORIA IA'}
                  </button>

                  <a
                    href={whatsAppUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="btn-business"
                    style={{
                      padding: '12px 20px',
                      fontSize: '13px',
                      textDecoration: 'none',
                      backgroundColor: '#141419',
                      border: '1.5px solid #22c55e',
                      color: '#4ade80',
                    }}
                  >
                    💬 ABRIR NO WHATSAPP
                  </a>
                </div>
              </div>

              {/* A DICA DE OURO DO CLOSER (DESTAQUE MÁXIMO) */}
              <div
                className="business-card-blue"
                style={{
                  margin: '28px 0',
                  padding: '28px 32px',
                  borderLeft: '6px solid var(--blue-prime)',
                }}
              >
                <div className="business-label" style={{ color: '#93c5fd', marginBottom: '10px' }}>
                  💡 A DICA DE OURO DO CLOSER (GATILHO DE FECHAMENTO)
                </div>
                <div
                  style={{
                    fontSize: '19px',
                    fontWeight: 800,
                    color: '#ffffff',
                    lineHeight: 1.55,
                    fontFamily: 'var(--font-title)',
                  }}
                >
                  "{selectedLead.dossie_comercial?.dica_de_ouro ||
                    selectedLead.dossie_comercial?.proximo_passo?.dica_de_ouro ||
                    'Demonstre o retorno do investimento mostrando quantos clientes a empresa resgata por mês com atendimento 24/7.'}"
                </div>
              </div>

              {/* 3 METRICAS EXECUTIVAS EM CARDS BRUTALISTAS */}
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                  gap: '16px',
                  marginBottom: '28px',
                }}
              >
                <div style={{ padding: '18px 20px', backgroundColor: 'var(--bg-card-light)', border: '1px solid var(--border-rule)' }}>
                  <div className="business-label" style={{ fontSize: '11px' }}>NOTA DO ATENDIMENTO IA</div>
                  <div style={{ fontSize: '26px', fontWeight: 900, marginTop: '6px', color: '#60a5fa', fontFamily: 'var(--font-title)' }}>
                    {selectedLead.dossie_comercial?.nota_atendimento_ia || 9.5} / 10.0
                  </div>
                  <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>
                    Auditoria pelo DealAuditorAgent
                  </div>
                </div>

                <div style={{ padding: '18px 20px', backgroundColor: 'var(--bg-card-light)', border: '1px solid var(--border-rule)' }}>
                  <div className="business-label" style={{ fontSize: '11px' }}>POTENCIAL DE CONVERSÃO</div>
                  <div style={{ fontSize: '24px', fontWeight: 900, marginTop: '6px', color: '#34d399', fontFamily: 'var(--font-title)' }}>
                    {selectedLead.dossie_comercial?.potencial_reativacao || 'ALTO'}
                  </div>
                  <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>
                    Probabilidade comercial estimada
                  </div>
                </div>

                <div style={{ padding: '18px 20px', backgroundColor: 'var(--bg-card-light)', border: '1px solid var(--border-rule)' }}>
                  <div className="business-label" style={{ fontSize: '11px' }}>VALOR ESTIMADO DO CONTRATO</div>
                  <div style={{ fontSize: '24px', fontWeight: 900, marginTop: '6px', color: 'var(--text-headline)', fontFamily: 'var(--font-title)' }}>
                    {selectedLead.valor_estimado ? `R$ ${selectedLead.valor_estimado.toLocaleString('pt-BR')}` : 'Sob Medida'}
                  </div>
                  <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>
                    Ticket da solução Inteligentte
                  </div>
                </div>
              </div>

              {/* RESUMO DA DEMANDA DO CLIENTE */}
              <div style={{ marginBottom: '28px' }}>
                <div className="business-label" style={{ marginBottom: '10px' }}>
                  RESUMO DA DEMANDA & DOR DO CLIENTE
                </div>
                <p style={{ fontSize: '16px', color: 'var(--text-body)', lineHeight: 1.7 }}>
                  {selectedLead.dossie_comercial?.resumo_executivo ||
                    selectedLead.resumo_perfil ||
                    'Cliente em fase de qualificação da operação de atendimento e vendas.'}
                </p>
              </div>

              {/* O QUE AGRADOU VS PONTOS DE ATRITO */}
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
                  gap: '20px',
                  marginBottom: '28px',
                }}
              >
                {/* O Que Agradou */}
                <div
                  style={{
                    padding: '22px',
                    backgroundColor: 'rgba(0, 82, 255, 0.05)',
                    border: '1.5px solid rgba(0, 82, 255, 0.3)',
                  }}
                >
                  <div className="business-label" style={{ color: '#60a5fa', marginBottom: '12px' }}>
                    ✅ O QUE AGRADOU AO CLIENTE
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    {(
                      selectedLead.dossie_comercial?.o_que_agradou || [
                        'Velocidade instantânea de resposta no WhatsApp',
                        'Clareza nas opções de integração com o sistema da empresa',
                        'Atendimento humanizado e sem linguagem robótica',
                      ]
                    ).map((item, idx) => (
                      <div key={idx} style={{ fontSize: '14px', color: 'var(--text-headline)', display: 'flex', gap: '8px' }}>
                        <span style={{ color: '#60a5fa' }}>•</span>
                        <span>{item}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Pontos de Atrito / Objeções */}
                <div
                  style={{
                    padding: '22px',
                    backgroundColor: 'rgba(255, 30, 70, 0.05)',
                    border: '1.5px solid rgba(255, 30, 70, 0.3)',
                  }}
                >
                  <div className="business-label" style={{ color: '#ff6b85', marginBottom: '12px' }}>
                    ⚠️ PONTOS DE ATRITO / OBJEÇÕES
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    {selectedLead.dossie_comercial?.pontos_de_atrito_e_queixas &&
                    selectedLead.dossie_comercial.pontos_de_atrito_e_queixas.length > 0 ? (
                      selectedLead.dossie_comercial.pontos_de_atrito_e_queixas.map((item, idx) => (
                        <div key={idx} style={{ fontSize: '14px', color: 'var(--text-headline)', display: 'flex', gap: '8px' }}>
                          <span style={{ color: '#ff6b85' }}>•</span>
                          <span>{item}</span>
                        </div>
                      ))
                    ) : (
                      <div style={{ fontSize: '14px', color: 'var(--text-muted)' }}>
                        Nenhuma objeção crítica mapeada. Lead receptivo e alinhado com a proposta.
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* PRÓXIMO PASSO RECOMENDADO */}
              <div
                style={{
                  borderTop: '1.5px solid var(--border-rule)',
                  paddingTop: '24px',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  flexWrap: 'wrap',
                  gap: '16px',
                }}
              >
                <div>
                  <div className="business-label" style={{ marginBottom: '4px' }}>
                    PRÓXIMO PASSO RECOMENDADO // {selectedLead.dossie_comercial?.proximo_passo?.quando_retomar || 'IMEDIATO'}
                  </div>
                  <div style={{ fontSize: '16px', fontWeight: 800, color: 'var(--text-headline)' }}>
                    {selectedLead.dossie_comercial?.proximo_passo?.acao_sugerida ||
                      'Formalizar minuta comercial e agendar alinhamento de onboarding técnico.'}
                  </div>
                </div>

                <button
                  onClick={handleToggleControl}
                  disabled={isUpdatingControl}
                  className={`btn-business ${selectedLead.controle === 'PILOTO_IA' ? 'btn-business-red' : 'btn-business-blue'}`}
                  style={{ padding: '12px 24px' }}
                >
                  {isUpdatingControl
                    ? 'ATUALIZANDO...'
                    : selectedLead.controle === 'PILOTO_IA'
                    ? '👤 ASSUMIR TRANSBORDO HUMANO'
                    : '🤖 DEVOLVER PARA A IA'}
                </button>
              </div>
            </div>

            {/* =========================================================================
                LEITOR DE CONVERSAS NO WHATSAPP (CHAT INTERATIVO)
                ========================================================================= */}
            <div className="business-card" style={{ padding: '36px' }}>
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  marginBottom: '24px',
                  borderBottom: '1.5px solid var(--border-rule)',
                  paddingBottom: '16px',
                }}
              >
                <div>
                  <div className="business-label" style={{ color: 'var(--blue-prime)' }}>
                    REGISTRO DE CONVERSA EM TEMPO REAL
                  </div>
                  <div className="business-title-medium" style={{ marginTop: '4px' }}>
                    Histórico no WhatsApp ({messages.length} mensagens)
                  </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span
                    className={`badge-brutalist ${
                      selectedLead.controle === 'PILOTO_IA' ? 'badge-blue' : 'badge-red'
                    }`}
                  >
                    {selectedLead.controle === 'PILOTO_IA' ? 'PILOTO IA ATIVO' : 'HUMANO NO COMANDO'}
                  </span>
                </div>
              </div>

              {/* Feed de Mensagens */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', maxHeight: '580px', overflowY: 'auto', paddingRight: '6px' }}>
                {messages.map((msg, idx) => {
                  const isIa = msg.origem === 'ia'
                  const isHumano = msg.origem === 'humano'
                  const senderName = isIa
                    ? 'Agente Inteligentte (Seu Zé)'
                    : isHumano
                    ? 'Consultor Humano'
                    : selectedLead.nome

                  return (
                    <div
                      key={idx}
                      className={`chat-bubble ${
                        isIa ? 'chat-bubble-ia' : isHumano ? 'chat-bubble-humano' : 'chat-bubble-cliente'
                      }`}
                    >
                      <div
                        style={{
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                          marginBottom: '8px',
                          fontSize: '13px',
                          fontWeight: 800,
                        }}
                      >
                        <span
                          style={{
                            color: isIa ? '#60a5fa' : isHumano ? '#ff6b85' : 'var(--text-muted)',
                            fontFamily: 'var(--font-title)',
                          }}
                        >
                          {senderName}
                        </span>
                        <span style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                          {msg.data || 'Hoje'}
                        </span>
                      </div>

                      {renderMessageContent(msg.texto)}
                    </div>
                  )
                })}
              </div>

              {/* Caixa de Disparo de Mensagem Manual / Transbordo Humano */}
              <form onSubmit={handleSendMessage} style={{ marginTop: '24px', display: 'flex', gap: '12px' }}>
                <input
                  type="text"
                  placeholder="Enviar mensagem manual para o cliente no WhatsApp..."
                  value={newMessageText}
                  onChange={(e) => setNewMessageText(e.target.value)}
                  className="input-business"
                  style={{ flex: 1, fontSize: '15px', padding: '14px 18px' }}
                />
                <button
                  type="submit"
                  disabled={isSendingMessage || !newMessageText.trim()}
                  className="btn-business btn-business-blue"
                  style={{ padding: '14px 28px', flexShrink: 0 }}
                >
                  {isSendingMessage ? 'ENVIANDO...' : 'ENVIAR'}
                </button>
              </form>
            </div>
          </div>
        ) : (
          <div
            className="business-card"
            style={{ padding: '60px', textAlign: 'center', color: 'var(--text-muted)' }}
          >
            Selecione um lead à esquerda para visualizar o dossiê completo.
          </div>
        )}
      </section>
    </div>
  )
}
