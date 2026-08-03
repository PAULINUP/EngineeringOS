# Sentinela e backups

Antes: um produto com backup (EngineeringOS) e nenhuma vigilância. Agora: os
quatro produtos com dados têm cópia verificada, e o Agent avisa no Telegram
quando algo muda.

## Backups

O plano da conta no Railway permite **zero backups de volume**
(`maxBackupsCount: 0`). Não é uma configuração esquecida — o recurso não está
disponível. Tudo abaixo existe porque o nativo não é opção.

| Produto | O que é copiado | Tamanho | Frequência |
|---|---|---|---|
| `singularity-finance` | SQLite do volume — clientes, chaves, histórico | 2,7 MB comprimido, 22.668 linhas | 6 h |
| `omnigrowth` | Postgres — campanhas e gasto real | 172 KB, 805 linhas | 6 h |
| `agent` | SQLite — decisões e estados | 96 KB, 1.326 linhas | diário |
| `engineeringos` | Postgres — progresso de aprendizagem | 638 KB, 9.227 linhas | diário |

Tudo no bucket `eos-backups`, com prefixo por produto e retenção de 14 cópias.

### O que "verificado" significa aqui

Depois de enviar, a cópia é **baixada de volta do bucket**, aberta e recontada:
SQLite passa por `integrity_check` e contagem por tabela; Postgres tem as
linhas recontadas por tabela. Divergência devolve falha, não sucesso.

"O upload retornou 200" não é a mesma coisa que "existe um backup
restaurável". A diferença entre as duas só aparece no dia em que você precisa
restaurar, que é o pior dia possível para descobrir.

Isso foi testado nos dois sentidos: um objeto propositalmente corrompido é
**reprovado** (`backup ilegível como banco`), e uma contagem esperada que não
bate é **reprovada** (`contagem divergente`).

### Snapshot de SQLite não é cópia de arquivo

O snapshot sai pela API `backup()` do próprio SQLite, que respeita as
transações em andamento. Copiar o `.db` com a aplicação escrevendo produz um
arquivo que **abre normalmente** e só falha na hora de restaurar.

### Por que não `pg_dump`

O `pg_dump` exige versão igual ou maior que a do servidor, e a imagem passaria
a depender do repositório do PostgreSQL só por isso. A exportação lógica por
SQLAlchemy funciona com qualquer versão e permite a verificação por contagem. O
esquema não vai no arquivo — quem o reconstrói são as migrações do próprio app.

## Sentinela

O Agent (`/sentinela`) vigia os sete produtos a cada 10 minutos.

**Só avisa quando o estado muda.** Serviço que caiu manda um alerta, não um por
ciclo; quando volta, manda a recuperação. Alerta repetido vira ruído, ruído
vira alerta ignorado, e alerta ignorado é o mesmo que não ter alerta.

**Vigia o backup, não só a aplicação.** Serviço no ar com backup de cinco dias
é um desastre esperando a hora. A ausência de backup não dá sintoma nenhum até
o dia em que faz falta — por isso é vigiada ativamente, e não presumida.

**Responder 200 não basta.** Cada alvo pode declarar um trecho que precisa
aparecer no corpo, porque página de erro também responde 200. O gateway do
Chimera, por exemplo, tem de dizer `operational`.

Resumo completo uma vez por dia às 12h UTC; alertas a qualquer hora.

## Segurança

- **`CHIMERA_API_KEY` era `chimera-dev-key`** — 15 caracteres, com "dev" no
  nome, e a única coisa entre a internet e um serviço que roda circuitos
  quânticos. Substituída por chave de 52 caracteres nos dois lados.
- **O `.env` do repositório `Agent` estava versionado**, com
  `STRIPE_SECRET_KEY` de produção (`sk_live_`), tokens do Telegram e do
  Twitter, chaves de e-mail e a `ADMIN_API_KEY`. O repositório é privado, então
  não houve exposição aberta — mas segredo no histórico do git é segredo
  comprometido. O arquivo saiu do versionamento e entrou um `.env.example`.
  **Remover não apaga o histórico: as chaves precisam ser giradas.**
- Healthcheck declarado onde existe endpoint de verdade, para a plataforma
  reiniciar serviço travado-mas-vivo, e não só serviço morto.

## O que precisa da sua mão

**Girar as chaves que estavam no `.env` versionado.** Nenhuma pode ser girada
por mim — são credenciais financeiras e de conta:

1. **Stripe** — `sk_live_` e `whsec_`: painel do Stripe, *Developers → API keys*
2. **Telegram** — token do bot: `/revoke` no @BotFather
3. **Twitter/X** — as cinco credenciais, no portal de desenvolvedor
4. **Gmail** — a senha de aplicativo em `EMAIL_PASS`
5. **DeepSeek, Resend, Gemini** — nos respectivos painéis

Depois de girar, atualize as variáveis no serviço `Agent` no Railway. O
`.env.example` lista todos os nomes esperados.

## Sondas de integração

A sentinela vigia se cada serviço responde. Isso não é a mesma coisa que as
**ligações entre eles** funcionarem, e a diferença custou caro duas vezes num
único dia — com os dois lados verdes o tempo todo:

1. O Chimera mudou de projeto e o `CHIMERA_GATEWAY_URL` do API1.0 ficou
   apontando para o domínio antigo. Monte Carlo e ESG pararam.
2. A QUBO passou de 6 para 16 qubits e o `/optimize` foi de 15 s para 200 s,
   acima do timeout de 180 s do cliente. De novo: `/health` verde nos dois.

Nenhuma checagem de saúde pegaria isso, porque nada estava fora do ar.

Três sondas executam trabalho de verdade, de hora em hora:

| Sonda | O que faz | Limite do consumidor |
|---|---|---|
| Chimera calcula certo | manda um Max-Cut de ótimo conhecido e **confere o valor** | 180 s |
| API1.0 → Chimera | lê o `/readyz` do API1.0, que tenta a chamada com a chave que ele tem | 5 s |
| omnigrowth → API1.0 | chama o endpoint que ele consome, com a chave dele | 30 s |

Duas decisões que vieram de medição:

**Margem.** Cada sonda conhece o timeout *real* do consumidor e acusa aos 60%
dele. Uma integração a 170 s contra limite de 180 s ainda "funciona" e quebra
no próximo aumento de carga — é assim que o caso 2 teria sido pego antes.

**Confirmação.** Na primeira execução a sonda acusou o Chimera como
inalcançável; era transitório — o serviço tinha acabado de reiniciar e o
`/health`, que consulta três serviços internos, passou de 4 s naquele instante.
Meia dúzia de medições depois: 0,6 s. Falha transitória que vira alerta é pior
que nenhum alerta, porque ensina a ignorar o canal. Agora a falha precisa se
repetir; recuperação vale na primeira.

Inspeção sob demanda em `GET /integracoes`.
