# Impontuality — aprendiz sintético e QA autônomo do EngineeringOS

Um agente que **estuda todas as trilhas da plataforma como um aluno de verdade** e,
ao mesmo tempo, funciona como teste de integração vivo: cada bug, lentidão ou
lacuna de conteúdo que ele encontra vira um registro auditável.

Ele não é um script de teste que roda e esquece. Ele **evolui**: o que aprendeu
numa sessão fica no HD e melhora o desempenho da próxima.

## O HD (`memory/`)

| Arquivo | O que guarda | Cresce |
|---|---|---|
| `identity.json` | quem ele é: geração, XP, competência acumulada, histórico de cada sessão | a cada sessão |
| `knowledge.jsonl` | o que aprendeu — respostas corretas (com a estratégia que funcionou) e conceitos estudados | a cada acerto |
| `episodes.jsonl` | histórico completo de execução: toda tentativa, resposta, estratégia, resultado, maestria | a cada tentativa |
| `skills.json` | desempenho de cada estratégia de raciocínio (acertos/tentativas) | a cada tentativa |
| `findings.jsonl` | anomalias da plataforma: erros HTTP, latência alta, KU sem material, KU sem desafio | quando observa |

Apagar `memory/` reinicia o agente do zero (geração 1, sem memória).

## Como ele pensa

Seis estratégias de resolução, escolhidas por desempenho histórico
(bandit epsilon-greedy, ε = 0.15 para exploração):

- `memoria` — já acertou este desafio antes; responde direto do HD
- `aritmetica` — resolve a operação explícita no enunciado (`2 + 4`)
- `extenso` — converte número por extenso em dígitos (`trezentos e quarenta e dois mil e seis`)
- `arredondamento` — arredonda para a casa pedida
- `ultimo_numero` / `soma_numeros` — heurísticas de fallback

O ciclo evolutivo: erra → não recebe o gabarito (o servidor só entrega a
resolução no acerto, como deve ser) → tenta outra estratégia → quando acerta,
grava a resposta e reforça a estratégia vencedora. Na sessão seguinte,
`memoria` resolve na hora o que antes custou várias tentativas.

## Uso

```bash
python agents/impontuality/agent.py                  # todas as trilhas, 25 KUs cada
python agents/impontuality/agent.py --max-kus 60     # sessão mais longa
python agents/impontuality/agent.py --missions mission.mbas.v1
python agents/impontuality/agent.py --report         # lê o HD e mostra a evolução
```

## O que ele já descobriu

- **Overhead de ~2s em toda requisição** (resolução IPv6 de `localhost` no Windows
  contra servidor IPv4) — degradava a plataforma inteira; corrigido usando `127.0.0.1`.
- **KUs sem desafio objetivo** ficam presas no teto de 60% do P9 — o agente mede
  exatamente quantas e em quais domínios.
- **KUs sem material de estudo** — lacunas de conteúdo por domínio.
