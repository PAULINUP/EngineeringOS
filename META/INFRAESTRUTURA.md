# Infraestrutura no Railway

Projeto `engineeringos`, ambiente `production`. Este documento é o mapa: o que
existe, por que está onde está, e o que continua faltando.

## Serviços

| Serviço | Papel | Como sobe | Saúde |
|---|---|---|---|
| `api` | FastAPI + dashboard servido na mesma origem | `EOS_ROLE=api` → uvicorn | `GET /health/ready` (banco + contagem de KUs) |
| `worker` | Celery: trajetórias pesadas e backup diário | `EOS_ROLE=worker` → celery worker `--beat` | `GET /health/ready` na sonda da porta 8080 |
| `Postgres` | banco de produção | imagem oficial, volume 5 GB | — |
| `Redis` | broker da fila e contador do rate limit | imagem oficial, volume 5 GB | — |

`api` e `worker` compartilham **a mesma imagem**. Quem decide o papel é
`EOS_ROLE`, lido pelo `entrypoint.sh`. Duas imagens diferentes já quebraram um
deploy em silêncio quando só uma foi atualizada.

O `worker` roda o beat **embutido** (`celery worker --beat`). Com uma réplica
só não há risco de dois agendadores disparando a mesma tarefa, e é um contêiner
a menos para pagar e manter.

## Variáveis: referência, nunca cópia

`DATABASE_URL`, `REDIS_URL` e `JWT_SECRET_KEY` eram **texto literal duplicado**
em `api` e `worker`. Girar a senha do Postgres ou recriar o Redis quebraria as
duas aplicações sem nenhum aviso, e dois valores de `JWT_SECRET_KEY` podem
divergir sem que ninguém perceba até um token válido ser recusado.

Hoje são referências resolvidas pela plataforma:

```
api    DATABASE_URL   = ${{Postgres.DATABASE_URL}}
api    REDIS_URL      = ${{Redis.REDIS_URL}}
worker DATABASE_URL   = ${{Postgres.DATABASE_URL}}
worker REDIS_URL      = ${{Redis.REDIS_URL}}
worker JWT_SECRET_KEY = ${{api.JWT_SECRET_KEY}}
```

O segredo do JWT tem uma origem só: o serviço `api`. Trocar lá propaga.

## Backup

**O plano da conta permite zero backups de volume** (`maxBackupsCount: 0` nos
limites do plano). O backup nativo do Railway não é uma opção sem upgrade —
tentar agendar devolve "Not Authorized".

O que existe no lugar:

- bucket `eos-backups`, região `iad`, a mesma do Postgres;
- `src/backup.py` exporta o banco por SQLAlchemy (JSONL comprimido), envia,
  **relê o objeto do bucket e reconta linha por tabela**. Divergência devolve
  falha, não sucesso — backup não verificado não é backup;
- tarefa `backup_do_banco` no Celery, diária às 05:30 UTC (02:30 em Brasília);
- retenção de 14 cópias (`BACKUP_RETENCAO`);
- na subida, o worker verifica a idade da cópia mais recente e repõe se passou
  de 20 horas (`BACKUP_MAX_HORAS`). O estado do beat vive em `/tmp` e some a
  cada reinício; sem essa checagem, um restart às 05:29 pularia o dia inteiro.

Exportação lógica em vez de `pg_dump` porque o `pg_dump` exige versão igual ou
maior que a do servidor, e a imagem passaria a depender do repositório do
PostgreSQL só por isso. O esquema não vai no arquivo: quem o reconstrói é o
Alembic. Restaurar é `alembic upgrade head` e depois carregar os dados.

Operação manual:

```bash
python -m src.backup criar
python -m src.backup listar
python -m src.backup verificar postgres/2026-08-02T05-30-00Z.jsonl.gz
```

## Rede

Nem Postgres nem Redis têm endereço público — só o domínio interno
(`postgres.railway.internal`, `redis.railway.internal`). É a configuração certa
e vale manter: o custo é que ferramenta local não alcança o banco direto.

## O que falta

- **`SENTRY_DSN` não está definido.** O `sentry-sdk[fastapi]` está instalado e
  o `main.py` já sabe inicializá-lo, mas sem DSN nada é enviado: erro de
  produção hoje morre no log e ninguém fica sabendo. Basta criar um projeto no
  Sentry e definir a variável no serviço `api`.
- **Não existe ambiente de staging.** Todo deploy vai direto para produção. Um
  ambiente `staging` no mesmo projeto resolveria, ao custo de mais um Postgres e
  mais um Redis.
- **Domínio próprio.** O endereço é `api-production-c9ab.up.railway.app`.
  Um domínio seu exigiria apenas apontar o DNS.
- **Restauração nunca foi exercitada.** O backup é verificado por releitura e
  recontagem, o que prova que o arquivo está íntegro e completo — não prova que
  o procedimento de restauração funciona ponta a ponta. Fazer isso exige um
  banco descartável; o ambiente de staging resolveria os dois de uma vez.

## Fora deste projeto

A conta tem outros projetos:

- `selfless-vitality` — 13 serviços, incluindo **três instâncias de Postgres**.
  Vale conferir o que ainda está em uso: banco parado continua custando.
- `artistic-integrity`, `enchanting-adaptation`, `astonishing-caring` — vazios,
  sem nenhum serviço. Não custam nada, mas poluem a listagem.
