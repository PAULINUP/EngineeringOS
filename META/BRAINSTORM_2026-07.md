# Brainstorm — o que os dados do Impontuality dizem sobre o futuro

**Data:** 2026-07-31
**Base empírica:** 5 gerações do agente Impontuality · 1.643 KUs estudadas ·
1.692 tentativas de desafio · 1.076 achados de QA · telemetria de ~4.000 requisições

Este documento não é opinião. Cada afirmação abaixo vem de um número que o
agente produziu ao usar a plataforma como um aluno usaria.

---

## 1. O que aprendemos

### 1.1 A plataforma tinha um deadlock que ninguém veria sem um aluno

O agente estudou 1.097 unidades e validou **zero**. A causa não era dificuldade:
era matemática. O `prereq_factor` multiplicativo zerava o aprendizado sempre que
um pré-requisito estava em 0 — a KU `mbas.1-2-add-whole-numbers` acumulou
**23 evidências objetivas** (acertos verificados pelo servidor) mantendo
**maestria 0.000**.

Nenhum teste unitário pegaria isso: cada função estava correta isoladamente.
Só um aprendiz percorrendo a escada inteira, do zero, exporia o efeito composto.
Corrigido (piso de 0.25); a mesma KU foi a 0.522 na sessão seguinte.

**Lição de método:** a Parte X da constituição pedia validação empírica. O
Impontuality é a primeira execução dela — e achou um erro estrutural na
Definição 3 em menos de uma hora.

### 1.2 85% do acervo é, hoje, inavaliável

| | KUs | com desafio objetivo |
|---|---|---|
| Matemática (básica → faculdade) | 335 | **247 (74%)** |
| Física, química, biologia, astronomia, economia, programação | 1.470 | **0 (0%)** |
| Estatística | 159 | 8 (5%) |

Sob o P9 (Validação Objetiva), uma KU sem desafio trava em 60% para sempre.
Ou seja: **a plataforma sabe ensinar 1.814 assuntos e sabe avaliar 261.**
O agente sentiu isso na pele — 794 achados `sem_desafio`.

Isso não é um bug, é a fronteira honesta do sistema. Mas define a prioridade
número um.

### 1.3 Três bugs de experiência que só aparecem em uso real

| Bug | Impacto | Como apareceu |
|---|---|---|
| SVG de 63.580px no mapa | tela preta + 6s de render | você reportou; reproduzido e medido |
| `localhost` → IPv6 → timeout | **2,0s fixos em toda requisição** (1000× mais lento que `127.0.0.1`) | o agente mediu 3,5s por tentativa e eu fui atrás |
| JWT de 15 min sem refresh | sessão de estudo morre calada; 38 respostas 401 | telemetria da sessão do agente |

Os três estavam invisíveis para os testes automatizados — todos passavam.

### 1.4 O agente evolui, e isso mede a plataforma

| Geração | KUs | Acurácia | O que mudou |
|---|---|---|---|
| 1 | 3 | 33,3% | primeira exposição |
| 3 | 546 | 7,9% | escala real: todos os domínios |
| 4 | 546 | 9,0% | memória começa a pagar |
| 5 | 546 | 9,0% | deadlock corrigido; maestria passa a se mover |

Duas leituras honestas destes números:

**A memória funciona perfeitamente** — a estratégia `memoria` acerta **106/106
(100%)**. Tudo que ele aprendeu uma vez, nunca mais errou.

**A acurácia global estagnou em ~9%** e isso diz respeito ao *agente*, não à
plataforma: as heurísticas simbólicas dele resolvem aritmética explícita
(11%) mas não cálculo, estatística ou álgebra simbólica. As estratégias de chute
(`ultimo_numero` 1,3%, `soma_numeros` 2,2%) confirmam algo importante sobre o
sistema: **a plataforma não é "chutável"** — chutar dá ~2% de acerto. Quem não
sabe, não passa. É uma validação forte do desenho de avaliação por resposta
construída, em contraste com múltipla escolha (onde o chute vale 20–25%).

### 1.5 O custo de estudar fora de ordem agora é mensurável

Com o piso corrigido, dá para calcular quantos acertos uma KU exige até validar
(θ = 0.85), em função de quanto o aluno domina os pré-requisitos:

| Base do aluno | Acertos até validar |
|---|---|
| pré-requisitos dominados | **~5** |
| pré-requisitos pela metade | ~8 |
| pré-requisitos zerados | **~22** |

Esse é o incentivo pedagógico do sistema em números: estudar na ordem certa é
**4× mais barato**. Antes da correção, a última linha era literalmente infinita.
Vale calibrar `η` e `PREREQ_FLOOR` contra dados reais para que "~5" seja o número
que um professor consideraria justo.

### 1.6 A qualidade dos desafios extraídos tem um teto

- 27% dos desafios pedem **múltiplos valores** (`3;5.6`) — enunciado costuma
  perder a estrutura de itens (a/b/c) na extração
- 20% têm enunciado com menos de 60 caracteres — dependem de contexto que ficou
  na página
- A tradução automática corrompeu marcadores matemáticos em alguns casos
  (`a.` virou `uma.`)

---

## 2. Para onde ir — ordenado por retorno sobre esforço

### Prioridade 1 — Fechar a lacuna de avaliação (o gargalo do produto)

**1.1 Extrair os exercícios de fim de capítulo das ciências.** Física, química e
biologia têm milhares de exercícios com gabarito no Answer Key, em páginas que o
extrator atual não mapeia (`/pages/{n}-problems`, `/pages/{n}-review-questions`).
É o mesmo pipeline já validado, apontado para outras URLs.
*Impacto estimado: de 14% para 55–70% de cobertura de avaliação.*

**1.2 Novos tipos de desafio além de numérico.** Um corretor de múltipla escolha
determinística (as questões de "review" da OpenStax são MC com gabarito) cobre
biologia, economia e astronomia — domínios onde resposta numérica não existe.
*Impacto: destrava os 4 domínios hoje em 0%.*

**1.3 Corretor de código para a trilha de Python.** Rodar o snippet do aluno
contra casos de teste é a evidência objetiva mais forte que existe (peso 0.60
plenamente justificado) e é natural para a trilha de programação.

### Prioridade 2 — Usar o agente como infraestrutura permanente

**2.1 Regressão pedagógica no CI.** O Impontuality vira um teste: "uma geração
completa deve validar ≥ N KUs e manter acurácia ≥ X%". Se alguém mexer numa
constante da Definição 3, o CI acusa — foi exatamente assim que o deadlock
apareceu.

**2.2 Calibrar as constantes com dados, não com palpite.** `η = 0.4`,
`PREREQ_FLOOR = 0.25`, `θ = 0.85`, pesos de fonte: hoje são chutes fundamentados
(a própria constituição admite em P8). Com o agente dá para varrer o espaço de
parâmetros e medir: quantas evidências até validar? A curva é pedagogicamente
plausível? *Isso transforma a Parte X de promessa em resultado.*

**2.3 Personas de aprendiz.** Clonar o agente com perfis diferentes (rápido e
desatento; lento e consistente; especialista em um domínio) e ver como a ULA
responde. É o teste do modelo cognitivo que a Parte V descreve mas nunca exercitou.

**2.4 Dar um cérebro melhor ao agente.** Hoje ele resolve com heurísticas
simbólicas e trava em ~9% fora da aritmética. Plugar um LLM como *solver*
(mantendo a memória e o reforço) elevaria a acurácia o bastante para ele validar
KUs de verdade e exercitar o sistema até o topo da escada — e mediria, de quebra,
a dificuldade real de cada trilha. Cuidado de projeto: o LLM entra como
raciocínio do *aluno*, jamais como autoridade de correção (P7).

### Prioridade 3 — A camada humana, quando existir

**3.1 Revisor humano como fonte 0.80.** A arquitetura P9 já reserva o lugar; falta
o CRUD de revisor e uma fila de revisão para as evidências abertas (hoje 100%
delas fica em `pending` sem destino).

**3.2 Revisão por pares entre alunos.** Dois alunos que já validaram a KU X podem
revisar a evidência aberta de um terceiro. Concordância entre pares vira
`reviewer_agreement` — o campo já existe no schema e nunca foi usado de verdade.
Isso escala validação sem professores, mantendo o princípio de que o próprio
aluno não se valida.

**3.3 IA como revisora subordinada (peso 0.40, nunca mais).** Um LLM avaliando a
explicação do aluno contra a definição formal da KU dá um sinal melhor que nada —
e o P7 já define exatamente esse teto. Combinado com noisy-OR, três avaliações
de IA independentes ainda não validam sozinhas: correto por construção.

### Prioridade 4 — Produto e performance

**4.1 Latência de escrita.** `/api/evidence` está com p95 de 1,19s porque cada
submissão reconstrói o DAG inteiro e recalcula transferência contra todas as KUs
validadas. Cachear o grafo e indexar as relações deixa isso em dezenas de ms.

**4.2 O mapa precisa de níveis de zoom.** A amostragem de 320 nós resolveu a tela
preta, mas a experiência certa para 1.814 unidades é hierárquica: domínio →
capítulo → seção, com o grafo detalhado só na vizinhança da fronteira.

**4.3 Revisão humana da tradução nos termos técnicos.** A tradução automática
serve para instruções; para definições formais, vale um passe de revisão nos
termos-chave por domínio (glossário) — ou usar as traduções oficiais da LibreTexts
onde existem.

---

## 3. A tese que os dados sustentam

O EngineeringOS não é um LMS nem um tutor. O que ele tem de genuinamente raro,
confirmado por esta rodada:

1. **Currículo como código** — 1.814 unidades de 18 livros importadas, compiladas
   e versionadas por um pipeline reprodutível. Ninguém mais trata currículo assim.
2. **Recusa a validar o que não consegue verificar** — o teto de 60% é uma
   escolha de integridade que quase nenhuma plataforma faz.
3. **Um agente que aprende, testa e critica o próprio sistema** — e cujo HD
   guarda a evidência de cada afirmação deste documento.

O caminho para o valor não passa por mais conteúdo (já há demais). Passa por
**tornar avaliável o que já foi importado** — e por usar o Impontuality para
provar, com números, que o modelo cognitivo funciona.
