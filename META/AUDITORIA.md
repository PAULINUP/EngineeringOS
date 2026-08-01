# Auditoria do EngineeringOS — o que verificar antes de confiar

**Data:** 2026-08-01
**Motivo:** o usuário apontou, com razão, que problemas graves só apareceram
porque ele os encontrou usando o sistema. Este documento é a varredura que
deveria ter sido feita desde o início — e o checklist para que a próxima seja
sistemática, não reativa.

Cada item abaixo foi **verificado no código deste repositório**, não copiado de
uma lista genérica. Severidade: 🔴 crítico · 🟠 alto · 🟡 médio.

---

## 1. Segurança — o que está aberto agora

| | Achado | Onde | Consequência |
|---|---|---|---|
| 🔴 | **`/token` aceita qualquer usuário e senha** e emite token com `role: admin` | `api.py:84` | Não existe autenticação. Qualquer pessoa com acesso à porta vira admin. *Isto foi identificado na primeira análise do projeto e nunca corrigido.* |
| 🔴 | **Qualquer autenticado escreve no progresso de qualquer aluno** — `learner_id` vem do corpo da requisição, não do token | `api.py:291,316` | Não há vínculo entre identidade e dados. Um aluno pode forjar competências de outro. |
| 🔴 | **`SECRET_KEY` com valor padrão embutido** (`"chave-secreta-padrao-apenas-para-dev"`) | `security.py:9` | Se subir sem a variável de ambiente, qualquer um forja tokens válidos. |
| 🟠 | **CORS `allow_origins=["*"]` junto com `allow_credentials=True`** | `main.py:63` | Combinação proibida pela especificação e perigosa: qualquer site pode chamar a API com credenciais. |
| 🟠 | **10 dos 18 endpoints sem autenticação nenhuma** (incl. `/graph`, `/kus`, `/missions`, `/tasks/{id}`) | `api.py` | Todo o acervo e o progresso são legíveis sem credencial. |
| 🟡 | **Sem rate limiting** em nenhuma rota | — | `/challenges/{id}/attempt` pode ser bombardeado para forçar respostas por tentativa e erro. |
| 🟡 | **`eval()` no solver do agente** (mitigado por validação de regex) | `agent.py` | Seguro hoje porque a expressão é validada, mas é um padrão que não deve entrar em código de produção. |

**Ordem de correção:** vincular token ↔ learner (resolve os dois primeiros de
uma vez) → senha real com hash → segredo obrigatório por env → CORS restrito.

---

## 2. Dados — o que pode ser perdido ou corrompido

| | Achado | Consequência |
|---|---|---|
| 🔴 | **Pasta `alembic/versions/` vazia — zero migrações** | O schema evolui por `create_all()`, que **não altera tabelas existentes**. Hoje foi preciso rodar `ALTER TABLE` na mão para adicionar `source_ref`. Em produção isso é perda de dados ou downtime. |
| 🟠 | **SQLite como banco principal** com escrita concorrente (API + agente + scripts) | Trava sob concorrência (`database is locked`); já houve timeout de 20s configurado como paliativo. Para múltiplos usuários: PostgreSQL. |
| 🟠 | **Sem backup automático** | Só existe o backup manual criado hoje pelo script de consolidação. |
| 🟠 | **Sem paginação em nenhum endpoint** | `GET /kus` devolve 1.814 registros; `GET /graph` devolve o grafo inteiro. Não escala e é vetor de negação de serviço. |
| 🟡 | **Integridade só agora garantida em `learners.name`** | O banco fragmentou em 291 cadastros com 20 cópias da mesma pessoa. Faltam `unique`/`check` em outras tabelas (ex.: `challenges` aceita duplicatas do mesmo enunciado). |
| 🟡 | **Sem histórico de maestria** | `competences` guarda só o estado atual; não dá para auditar a evolução nem reverter um cálculo errado — como o do deadlock, que exigiu zerar tudo. |

---

## 3. Correção e confiabilidade — o que já falhou

Estes não são hipotéticos: **todos aconteceram neste projeto**.

| Falha | Como foi encontrada | O que teria evitado |
|---|---|---|
| `prereq_factor` zerava o aprendizado (23 acertos, maestria 0) | agente sintético percorrendo a trilha | teste de propriedade: "toda evidência válida aumenta a maestria" |
| Repetir o mesmo exercício validava a competência | auditoria de evidências por origem | invariante: "validar exige N origens distintas" |
| Enunciados sem operador (`27 3` era `27÷3`) | tentativa de resolver os exercícios | validação de conteúdo pós-importação |
| Latência de 2s em toda requisição | medição de tempo do agente | teste de performance com limiar |
| Sessão expirando em 15 min | 38 respostas 401 no log | monitoramento de taxa de erro |
| Tela preta (4 rodadas até a causa raiz) | o usuário, repetidamente | auditoria de compositing na primeira ocorrência |

**Cobertura de testes hoje: 9 testes unitários, zero de integração, zero CI.**
Para um sistema com 1.814 unidades de conteúdo e um motor matemático, isso é
insuficiente por uma ordem de grandeza.

---

## 4. Checklist permanente — o que verificar sempre

### Antes de aceitar qualquer mudança minha
- [ ] O que eu disse que corrigi tem **evidência de execução** (log, medição, teste)?
- [ ] A correção trata a **causa** ou o sintoma? (pergunte: "que outras coisas causam isso?")
- [ ] Existe **teste que falha sem a correção** e passa com ela?
- [ ] A mudança **piora** alguma outra coisa? (o `contain: paint` piorou a tela preta)

### Segurança (a cada release)
- [ ] Nenhum segredo no código; todos por variável de ambiente, com falha se ausente
- [ ] Autenticação real; autorização por recurso (quem pode ler/escrever o quê)
- [ ] Toda rota que muda estado exige token; token vinculado à identidade dos dados
- [ ] CORS restrito à origem do frontend
- [ ] Rate limiting nas rotas de escrita e nas caras
- [ ] Entrada validada e limitada em tamanho (Pydantic já faz parte disso)
- [ ] Dependências sem CVE conhecido (`pip-audit`, `npm audit`)

### Dados
- [ ] Toda mudança de schema tem migração versionada e reversível
- [ ] Backup automático + restauração testada (backup não testado não é backup)
- [ ] Constraints no banco, não só na aplicação
- [ ] Paginação obrigatória em qualquer listagem
- [ ] Dados de teste separados dos reais

### Operação
- [ ] Health check e métricas (latência p95, taxa de erro) com limiar de alerta
- [ ] Logs estruturados sem dados sensíveis
- [ ] CI que roda testes, lint e build a cada commit
- [ ] Rollback documentado e testado

### Qualidade do conteúdo (específico deste projeto)
- [ ] Todo desafio importado tem gabarito verificável e enunciado legível
- [ ] Amostragem manual após cada importação em massa
- [ ] Invariantes pedagógicas testadas: evidência aumenta maestria; repetição não valida; ordem correta é mais barata

---

## 5. Ferramentas recomendadas

| Necessidade | Ferramenta | Por quê |
|---|---|---|
| Banco | **PostgreSQL** | Concorrência real; SQLite trava com múltiplos escritores |
| Migrações | **Alembic** (já instalado, **sem uso**) | Versiona o schema; hoje o projeto não tem nenhuma migração |
| Testes | **pytest + httpx** | Testes de integração da API, que hoje não existem |
| Propriedades | **Hypothesis** | Geraria os casos que o agente encontrou por acaso |
| Segurança | **pip-audit**, **bandit**, **npm audit** | CVEs e padrões inseguros |
| CI | **GitHub Actions** | O repositório não tem nenhum workflow |
| Erros | **Sentry** | Hoje um erro de render vira tela preta silenciosa |
| Carga | **Locust** ou **k6** | Mede o que o agente mediu por acidente |
| Container | **Docker Compose** (já existe) | Falta Postgres no compose |

---

## 6. O que eu recomendo fazer primeiro

Se for para escolher **três** coisas:

1. **Autenticação real com vínculo token ↔ learner.** Enquanto isso não existir,
   todo o resto do modelo de evidência é decorativo: qualquer um pode escrever
   qualquer coisa em nome de qualquer pessoa.
2. **Primeira migração Alembic + backup automatizado.** Sem isso, cada evolução
   de schema é um risco de perder o que já foi construído.
3. **CI com os testes existentes + testes de integração da API.** É o que
   transforma "eu verifiquei" em algo que não depende da minha palavra.

O agente Impontuality já é, de fato, o começo do item 3: ele é um teste de
integração vivo. Colocá-lo no CI com limiares ("uma geração deve validar ≥ N
unidades") fecha o ciclo.
