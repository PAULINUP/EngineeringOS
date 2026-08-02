# A conta Railway, projeto por projeto

Antes: dois projetos com serviços e três projetos vazios. Um deles,
`selfless-vitality`, guardava **seis aplicações diferentes** empilhadas — 13
serviços, três instâncias de PostgreSQL, e nenhuma fronteira entre elas.

Depois: sete projetos, um por aplicação.

| Projeto | Serviços | Estado |
|---|---|---|
| `engineeringos` | api, worker, Postgres, Redis | plataforma de estudo |
| `singularity-finance` | API1.0 (+ volume 295 MB) | **www.singularityfinance.com.br** — Stripe e Binance ativos |
| `chimera` | api-gateway, frontend, classical-preprocessor, quantum-optimizer, evaluator, Postgres | pipeline de otimização quântica |
| `omnigrowth` | omnigrowth, Postgres | automação de campanhas, gasto real de anúncios |
| `agent` | Agent (+ volume) | agente de decisões |
| `lading-singularity` | lading-singularity | landing page |
| `labirinto-dos-sonhos` | site | site estático |

O `singularity-finance` é o antigo `selfless-vitality`, apenas renomeado. Foi
decisão deliberada: ele carrega domínio próprio, cobrança e 295 MB num volume.
Manter o projeto e tirar os outros de dentro dele separou tudo **sem tirar do
ar o único produto que fatura**.

## Como a migração foi feita

O Railway não move serviço entre projetos. Cada aplicação foi recriada no
destino a partir do mesmo repositório, com as variáveis copiadas, e só depois
removida da origem — nunca antes de a nova responder.

Os dados não viajam com o serviço:

| Dado | Origem | Como foi | Conferência |
|---|---|---|---|
| Banco do omnigrowth | Postgres-GAyy | esquema recriado pelas migrações Alembic do próprio app; dados copiados tabela a tabela | **804 linhas, recontadas nas duas pontas** |
| Banco do Chimera | Postgres | esquema por reflexão + dados | 1 linha, recontada |
| Volume do Agent | decisions-data | download e upload dos arquivos | `PRAGMA integrity_check` **dentro do contêiner**: 999 decisões, 327 estados |

O esquema do omnigrowth usa `pgvector`, que a reflexão do SQLAlchemy não sabe
recriar — daí deixar o app criar o esquema pelas próprias migrações e copiar
só os dados.

Cópia de segurança do volume do Agent guardada em
`eos-backups/migracao-2026-08/agent/`.

## Defeitos encontrados no caminho

**Comunicação interna saindo pela internet.** O `api-gateway` chamava
preprocessor, optimizer e evaluator pelos domínios públicos. Cada requisição
entre dois contêineres vizinhos deixava o datacenter e voltava — latência,
custo de egress, e três serviços expostos sem necessidade. Agora usam o
domínio privado. Exigiu trocar `--host 0.0.0.0` por `--host ::` nos
Dockerfiles: a rede privada do Railway resolve para IPv6, e `0.0.0.0` só
atende IPv4.

**Build do Chimera quebrado, sem ninguém saber.** O construtor da plataforma
passou a instalar Python 3.13, e `pandas==2.1.4` só publica wheel até cp312.
Os cinco serviços seguiam no ar apenas porque rodavam uma imagem antiga; o
próximo rebuild falharia. Corrigido com `.python-version` fixando 3.11 — a
versão mais recente coberta pelas dependências já fixadas.

**Home do Labirinto dos Sonhos respondia 404.** O Caddyfile gerado testava
`{path}`, `{path}.html` e `{path}/index.html`; para a raiz nenhum casa.
`/index.html` respondia 200, `/` não. Um Caddyfile no repositório fecha o
buraco e tira a dependência da versão do gerador.

**Um PostgreSQL rodando sem servir ninguém.** `Postgres-RZ7N` tinha 199 MB de
volume e **zero tabelas** — 7,6 MB de banco vazio. Removido.

**A chave que o omnigrowth usa para falar com o API1.0 não é a que o API1.0
tem na variável `API_KEY`.** A do omnigrowth é aceita (o API1.0 valida contra
o banco); a da variável é recusada com 403. A variável está obsoleta.

**A integração omnigrowth → API1.0 está quebrada.** A chamada autentica e
devolve **500** (`Erro interno no processamento`). Autenticação não é o
problema; algo no processamento é. Não investiguei — está fora do escopo desta
arrumação, mas precisa de atenção.

**`/v1/health` do API1.0 exige credencial.** Endpoint de saúde fechado impede
qualquer monitoramento externo de detectar que o produto caiu.

## Pendências

- **Dois volumes soltos no projeto `chimera`**: `n8n-volume` (150 MB) e
  `postgres-volume` (224 MB), herdados do projeto vazio reaproveitado. Nunca
  vi o conteúdo — não removi. Junto com os quatro de `singularity-finance` (já
  migrados e conferidos), a API aceita a remoção mas eles continuam listados;
  provavelmente precisam sair pelo painel.
- **Nome do serviço `API1.0`**: o ponto impede referenciá-lo por
  `${{API1.0.VARIAVEL}}` — a referência resolve vazio. Renomear para algo sem
  ponto resolveria, se um dia precisar.
- **A chave SSH que registrei para a migração foi removida.** Para voltar a ter
  shell nos contêineres: `railway ssh keys add`.
