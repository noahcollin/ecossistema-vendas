# REGRAS DE DESIGN SYSTEM, UI/UX E IDENTIDADE VISUAL
## Ecossistema de Vendas — Inteligentte Lab
*Documento de Diretrizes Compulsoriamente Carregado pelo Agente em Todas as Interações*

---

### 1. Postura de Design & Princípio da Autenticidade
- **Abordagem de Estúdio Especializado:** Trate cada tela como a identidade única de um cliente exigente. O cliente já rejeitou layouts que parecem templates prontos de biblioteca, dashboards genéricos de admin ou saídas convencionais de IA.
- **O que é o Ecossistema de Vendas:** É a **Mesa de Operações e Centro de Inteligência Comercial da Inteligentte Lab**. É o ambiente de trabalho diário de diretores comerciais e closers que negociam contratos de alto valor (R$ 25k - R$ 54k) gerados por agentes autônomos de WhatsApp e orquestrados com o CRM Kommo.
- **Anti-Pattern Central de IA:** O design gerado por IA tende a repetir o mesmo vício: *fundo preto chapado + 4 cards idênticos alinhados em grid + número gigante + label em cima + sombra neon brilhante*. Isso é o clichê do clichê. É feio, genérico, infantil e desprovido de alma. **ESTÁ ESTRITAMENTE PROIBIDO.**

---

### 2. A Paleta de Cores: Harmonia, Teoria e Calibração
A paleta definida pelo cliente é: **Azul, Vermelho, Preto e o Gradiente entre Azul e Vermelho**.
Cores NÃO são tintas decorativas jogadas aleatoriamente em cada bloco. Em um design de classe mundial, as cores conversam entre si seguindo leis físicas e perceptuais:

1. **A Base Preta (Obsidiana / Grafite Profundo):**
   - Não use preto absoluto `#000000` estéril em tudo.
   - Use uma escala de elevação tonal com sutilíssima temperatura fria:
     - `Background Base (Void):` `#07080C` (obsidiana com 2% de saturação azul-aço).
     - `Surface 1 (Pisos e Painéis):` `#0C0E16`
     - `Surface 2 (Componentes e Mesas):` `#121522`
     - `Border Rule (Fita Estrutural):` `#1E2336` (bordas nítidas, estruturais, sem brilho neon).
2. **O Azul (`#0052FF` / `#1E6BFF`): O Polo da Automação & Inteligência:**
   - Significa: O motor invisível, os agentes autônomos trabalhando, a triagem instantânea, o faturamento formalizado.
   - Aplicação: Acentos de dados de entrada, fluxos de automação, dados consolidados e estado ativo do sistema.
3. **O Vermelho (`#FF1E46` / `#E6193C`): O Polo do Closer & Intervenção Humana:**
   - Significa: O dinheiro em risco, a urgência, o lead esfriando na mesa, o transbordo tático para o closer, a parada de emergência (Kill-Switch).
   - Aplicação: Alertas de ação imediata, transbordo de atendimento, deals sob negociação crítica e travas de segurança.
4. **O Gradiente Dual (Azul ➔ Vermelho): A Sinergia IA + Humano:**
   - Significa: A fusão onde a IA pré-qualifica e resgata, e o closer humano converte. O valor supremo da Inteligentte Lab.
   - Aplicação: **Assinatura de Prestígio.** Uma viga de transição horizontal, um selo institucional, uma linha de alta densidade no cabeçalho ou o indicador de receita resgatada. **NUNCA como preenchimento de fundo de um card comum.**
5. **A Harmonia entre Azul e Vermelho (Prevenção de Cromostereopsia):**
   - Azul puro e vermelho puro colocados lado a lado com saturação 100% sobre fundo preto causam fadiga visual e distorção óptica nos olhos humanos (cromostereopsia).
   - Calibre sempre a luminância e a saturação: o azul e o vermelho devem se comportar como instrumentos iluminados de um cockpit de luxo, não como luzes de um arcade.

---

### 3. Tipografia: Musicalidade, Escala e Relação
As fontes não podem gritar ao mesmo tempo. A tipografia deve ter hierarquia musical:

- **Display & Títulos:** `Plus Jakarta Sans`
  - Pesos: 800 e 900.
  - Tracking: `-0.03em` a `-0.05em` (apertado, denso, editorial).
  - Uso: Reservado estritamente para o que comanda a tela. Se tudo está em 900 negrito, nada tem destaque.
- **Corpo & Rótulos:** `Inter`
  - Pesos: 400 (corpo secundário), 500 (leitura clara), 600 (sub-destaques).
  - Rótulos/Eyebrows: `11px` a `12px`, caixa alta, tracking sutilmente aberto (`+0.05em`), em tom atenuado (`#64748B` a `#94A3B8`). O rótulo deve **sussurrar** para que o dado possa **falar**.
- **Dados & Telemetria:** `JetBrains Mono`
  - Pesos: 600 e 700.
  - Uso: Moeda, timestamps, indicadores percentuais, chips de auditoria, IPs e latências. Sempre com `font-variant-numeric: tabular-nums` para que números nunca oscilem de largura.

---

### 4. Layout & Composição: Rompendo com o "Grid de 4 Caixinhas"
- **Fim da Caixa Genérica:** Pare de desenhar 4 retângulos idênticos com um número no meio e borda colorida. Isso é preguiça visual.
- **Hierarquia Assimétrica:**
  - Em uma mesa executiva, a receita realizada e o pipeline em risco têm pesos cognitivos diferentes.
  - Crie momentos de respiro. O espaço negativo é material de design tão importante quanto a cor.
  - Alinhamentos arquiteturais: use linhas guias rígidas, divisores técnicos finos de 1px com baixa opacidade, e blocos integrados que pareçam esculpidos no mesmo painel de ardósia/titânio.
- **Informações com Propósito (Zero Decoração Gratuita):**
  - Cada número na tela deve ter um contexto imediato: *Em relação a quê? Quem é responsável? Qual é a próxima ação?*
  - Não coloque badges coloridos apenas para preencher espaço. Se um badge não altera a tomada de decisão do usuário, elimine-o.

---

### 5. Lista Negra de Erros (Anti-Patterns Proibidos)
1. ❌ **Arco-Íris de Cards:** Pintar fundos de cards vizinhos com azul, vermelho e degradê como se fossem post-its coloridos.
2. ❌ **Glow Neon Artificial:** `box-shadow` exagerado parecendo luz de discoteca ou tema de editor de código cyberpunk.
3. ❌ **Quebras de Linha Desleixadas:** Deixar o `R$` em cima e o valor embaixo, ou títulos com palavras soltas (*"Follow- / up"*).
4. ❌ **Tipografia Gritante e Monótona:** Títulos, rótulos e textos todos em caixa alta e negrito 900.
5. ❌ **Falta de Alma:** Usar componentes padrão sem ancoragem no universo real do produto (WhatsApp, conversas, áudios, propostas, contratos, CRM).
