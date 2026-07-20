# Changelog - EngineeringOS

## [v3.3.0] - 2026-07-19
### Added
- **Importador OpenStax (`tools/openstax_importer.py`)** — pipeline UCEF de ingestão: busca o sumário do livro (1 requisição via CMS API + `__PRELOADED_STATE__`), extrai os *Learning Objectives* de cada seção como definição da KU, gera o `.eos` constitucional (1 seção = 1 KU, pré-requisitos em espinha de livro), valida no compilador (anti-ciclo), injeta no banco e registra os materiais (URL de cada seção, CC BY 4.0 com atribuição no `source.ref`).
- **`tools/import_ladder.py`** — escada curricular completa encadeada por `--after`: Matemática básica (Prealgebra) → média (Álgebra Elementar) → avançada (Pré-Cálculo) → faculdade (Cálculo Vol. 1–3); Física média (College Physics) → faculdade (Física Universitária Vol. 1–3). Uma missão por livro.
- **Dashboard em escala**: filtro por domínio no mapa e na matriz (auto-seleciona o domínio dominante da missão ativa), layout serpentina para currículos lineares de livro, paginação "Mostrar mais" na matriz.
- `inject_seed.py` passa a respeitar o campo `title` das declarações KNOWLEDGE.

## [v3.2.0] - 2026-07-19
### Added
- **Correção automática de desafios (CCE server-side grading)** — fecha o buraco da evidência autodeclarada para casos objetivos:
  - Novo modelo `Challenge` (prompt, tipo de resposta, gabarito, tolerância, feedback); o gabarito nunca sai do servidor.
  - Motor de correção em `cce.py`: respostas numéricas com tolerância (aceita vírgula decimal BR e conjuntos de valores) e correção por palavras-chave insensível a acentos.
  - Endpoints `GET /kus/{id}/challenges` (sem gabarito) e `POST /challenges/{id}/attempt` — corrige, audita a tentativa como `Assessment`, e em caso de acerto gera `EvidenceRecord` com peso fixo de benchmark reprodutível (0.60) reutilizando o pipeline constitucional (noisy-OR + delta de aprendizado). ≈3 desafios distintos corretos validam a KU (θ = 85%).
  - Banco de 18 desafios padrão (fontes: Strang 2016, Stewart 2015, Goodfellow et al. 2016), semeado de forma idempotente no startup e em `/seed`.
  - UI: painel de estudo agora mostra desafios com correção instantânea, feedback com resolução e progresso "Desafio N de M"; KUs sem desafios caem no formulário de evidência aberta (com pesos, agora explicitamente marcado como sujeito a revisão).

## [v3.1.0] - 2026-07-19
### Added
- **Especificação Constitucional completa** em `META/ENGINEERINGOS_SPECIFICATION.md` (a v3.0.0 continha apenas o sumário): Partes 0–X, Definições 1–12, gramática EBNF da DSL, axiomas ontológicos, hipóteses de validação H1–H5 e provas formais.
- **Dashboard "Aurora"** — redesign completo da interface (React + Tailwind v4): sidebar de produto, hero com anel de progresso e ranks, cards de estatísticas (progresso, validadas, trilha π*, carga cognitiva), mapa de conhecimento SVG com anéis de maestria/estados bloqueados/badges de passo, trilha vertical como jornada, matriz de competências com filtros, e painel lateral de sessão de estudo (desafio CCE + materiais).
- Constante constitucional `WORKING_MEMORY_CAPACITY = 4` em `cognitive_engine.py`, consumida pela ULA e pelo CCE (antes duplicada e hardcoded).

### Fixed
- `NameError` em `run_heavy_math_simulation`: `cognitive_engine.py` usava `asyncio.sleep` sem importar `asyncio`.
- Limite de 4 KUs hardcoded dentro de `optimize_learning_trajectory` promovido a parâmetro `wm_capacity`.
- CSS do dashboard migrado para a sintaxe do Tailwind v4 (`@import "tailwindcss"`), eliminando as diretivas `@tailwind` legadas.

## [v2.1.0] - 2026-07-03
### Added
- Limitador dinâmico de 4 KUs (Knowledge Units) na `cce.py` (Cognitive Challenge Engine) para evitar fadiga cognitiva extrema em alunos TDAH.
- Parser customizado para a linguagem `.eos` (`eos_parser.py`) com isolamento de domínio.
- Primeira missão (Patient Zero): `calculus.eos`.
- Proteção contra ciclos matemáticos no Universal Learning Architecture via `networkx.find_cycle`.

### Fixed
- SQLAlchemy *MissingGreenlet*: Vazamento de estado Assíncrono pós-commit foi fixado (`await db.refresh`).
- *UnboundLocalError*: Variável global de ambiente `curr_state` estabilizada no endpoint principal da API.
- Sobrecarga e Concorrência de IO: Incremento agressivo de Timeout (20.0s) no driver SQLite Async para mitigar Data Locking provocado pela sincronização Git massiva do Swarm.
- Refatoração dos nomes singulares e plurais nas tabelas SQL do módulo de cache JSON.
