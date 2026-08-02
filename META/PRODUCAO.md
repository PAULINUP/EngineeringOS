# EngineeringOS em produção

**URL:** https://api-production-c9ab.up.railway.app
**Projeto Railway:** `engineeringos` · serviços `api` + `Postgres`
**Publicado em:** 2026-08-02

## Estado verificado

| Verificação | Resultado |
|---|---|
| `/health/ready` | `ready` · database `ok` · **1.814 unidades** |
| Dashboard na raiz | HTML servido pelo backend (mesma origem da API) |
| Cadastro + login | funcionando (conta criada e sessão carregada na nuvem) |
| Trilhas disponíveis | 19 |
| `/api/token` (atalho de dev) | **404** — desligado em produção |
| Escrita sem token | **401** |
| `/seed` sem admin | **401** |

## Variáveis configuradas

`EOS_ENV=production` · `JWT_SECRET_KEY` (64 caracteres, gerado no deploy) ·
`DATABASE_URL` (referência ao serviço Postgres) · `ACCESS_TOKEN_EXPIRE_MINUTES=720` ·
`BCRYPT_ROUNDS=12` · `EOS_RATE_LIMIT=1`

## Como o ambiente se popula sozinho

`data_export.json.gz` (1,1 MB, 18.700 linhas) viaja com a imagem. No boot, se o
banco estiver vazio, a aplicação importa o acervo. Só age em banco vazio —
nunca sobrescreve dados. Desligue com `EOS_AUTO_IMPORT=0`.

## O que o primeiro deploy ensinou

Sete tentativas até subir. Cada falha foi de uma categoria diferente, e todas
eram invisíveis em desenvolvimento:

| # | Falha | Por que só apareceu no deploy |
|---|---|---|
| 1 | `CMD` apontava para `src.api:app` | o módulo não existe; localmente ninguém usa o Dockerfile |
| 2 | Alembic com driver síncrono | Railway entrega `postgresql://`, a app precisa de `+asyncpg` |
| 3 | `env.py` desfazia a própria normalização | reescrevia a URL com o valor cru três linhas depois |
| 4 | Migração baseline com `DROP INDEX` | autogenerate comparou com o SQLite local |
| 5 | `alembic upgrade && uvicorn` no startCommand | falha da primeira metade matava o processo em silêncio |
| 6 | `concept` estourava `varchar(100)` | **SQLite ignora limites de tamanho; Postgres não** |
| 7 | Evidências órfãs | **SQLite não aplica cascata sem `foreign_keys=ON`** |
| 8 | Dashboard ausente | `dist/` está no `.gitignore` e o Railway o respeita |

Os itens 6 e 7 merecem destaque: eram **defeitos reais que existiam há meses**,
escondidos pela permissividade do SQLite. Nenhum teste local os encontraria.

## Próximos passos

- [ ] Rodar o agente Impontuality contra produção para validar sob carga real
- [ ] Configurar `SENTRY_DSN` (hoje um erro só aparece se alguém ler o log)
- [ ] Backup agendado do Postgres do Railway
- [ ] Domínio próprio e `EOS_CORS_ORIGINS` correspondente
