# Deploy — Railway e produção

## A pergunta: dá para subir no Railway já?

**Não hoje, e a razão não é opinião.** Antes desta rodada o deploy quebraria no
primeiro segundo:

| O que estava errado | Consequência no Railway |
|---|---|
| `CMD ["uvicorn", "src.api:app"]` — `src/api.py` só define o router, o app vive em `main.py` | contêiner em loop de reinício, sem subir uma vez |
| Porta fixa 8000 | Railway injeta `$PORT`; com porta fixa, nada é roteado |
| SQLite como banco padrão | **sistema de arquivos efêmero: todo o acervo some no primeiro reinício** |
| `JWT_SECRET_KEY` de exemplo versionado | qualquer pessoa forja token de admin |
| Sem healthcheck | a plataforma não sabe se a aplicação está pronta |

Os quatro primeiros já foram corrigidos. **O bloqueio real que resta é o banco.**

---

## Ordem correta para subir

### 1. PostgreSQL primeiro — inegociável
No Railway, cada deploy recria o contêiner. Com SQLite você perde 1.814
unidades, 2.215 evidências e todo o progresso, sem aviso.

```bash
# provisione um Postgres no Railway e copie a connection string
set TARGET_DATABASE_URL=postgresql+asyncpg://usuario:senha@host:5432/railway

python tools/backup.py criar                       # rede de segurança
python tools/migrate_to_postgres.py --verificar-antes
python tools/migrate_to_postgres.py                # copia e confere contagens
```
O script copia na ordem das chaves estrangeiras e **compara tabela a tabela** no
fim. Ensaio já feito: 18.734 linhas, 11 tabelas conferindo.

> Atenção: a URL do Railway vem como `postgresql://`. Troque para
> `postgresql+asyncpg://` — o driver assíncrono é o que a aplicação usa.

### 2. Variáveis de ambiente
```
EOS_ENV=production
JWT_SECRET_KEY=<python -c "import secrets; print(secrets.token_urlsafe(48))">
DATABASE_URL=postgresql+asyncpg://...
EOS_CORS_ORIGINS=https://seu-frontend.up.railway.app
ACCESS_TOKEN_EXPIRE_MINUTES=720
SENTRY_DSN=            # opcional
```
Com `EOS_ENV=production`, a aplicação **se recusa a subir** sem um
`JWT_SECRET_KEY` de 32+ caracteres. É proposital: melhor não subir do que subir
com segredo conhecido.

### 3. Deploy
`railway.json` já define: `alembic upgrade head` antes do start, healthcheck em
`/health/ready`, reinício apenas em falha.

### 4. Conferir depois de subir
```bash
curl https://SEU-APP.up.railway.app/health/ready
# {"status":"ready","database":"ok","knowledge_units":1814}

curl -X POST .../api/token -d '{"username":"x","password":"y"}'   # deve dar 404
```
O `/token` respondendo 404 em produção é sinal de que o atalho de
desenvolvimento está corretamente desligado.

---

## Antes de abrir para outras pessoas

- [ ] Frontend publicado e o domínio dele em `EOS_CORS_ORIGINS`
- [ ] Backup automático agendado (`tools/backup.py criar`) — e uma restauração
      testada de verdade
- [ ] Rate limiting: hoje o estado é por processo. Com mais de uma réplica,
      trocar por Redis (a interface em `src/ratelimit.py` não muda)
- [ ] Sentry configurado — sem ele, um erro só aparece se alguém ler o log
- [ ] `WEB_CONCURRENCY` conforme a memória do plano contratado

## Custo (ordem de grandeza, Railway)

| Item | Estimativa |
|---|---|
| API (512 MB) | ~5 USD/mês |
| PostgreSQL (1 GB) | ~5 USD/mês |
| Redis (só se usar Celery de verdade) | ~5 USD/mês |

O Celery hoje roda em modo *eager* (síncrono). Enquanto for assim, **não
provisione Redis** — é custo sem função.

---

## O que ainda não foi verificado

Honestidade sobre o alcance dos testes: a imagem Docker **não foi construída**
(Docker não está instalado na máquina de desenvolvimento) e o caminho
PostgreSQL foi exercitado apenas pelo ensaio de migração, não contra um
servidor Postgres real. O primeiro `docker build` e um `docker compose up`
local devem ser feitos antes do deploy de verdade.
