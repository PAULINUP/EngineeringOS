# Chimera: até onde vai, e por quê

Tudo aqui foi medido contra **verdade calculada de forma independente** — o
ótimo exato por força bruta, ou a fórmula fechada do Max-Cut em anel (n se par,
n−1 se ímpar). Nenhum número veio de "pareceu funcionar".

## O mapa completo

| n | Estados | Motor | Resultado | Tempo |
|---|---|---|---|---|
| ≤ 20 | até 1.048.576 | `qiskit_aer` (QAOA real) | ótimo | 17 s → 135 s |
| 21–24 | até 16.777.216 | `busca_exaustiva` | ótimo garantido | 6,7 s → 41 s |
| ≥ 25 | — | recusa | **HTTP 400** com o motivo | 0,5 s |
| p=6, n=20 | — | corte da borda | **HTTP 502 aos 300 s** | — |

## O achado que importa

Aos 20 qubits o espaço tem 1.048.576 estados e o motor gasta 4.096 tiros —
0,4% do espaço. É o primeiro tamanho em que o QAOA **precisa** funcionar, em
vez de tropeçar no ótimo por cobertura.

Com o mesmo orçamento de tiros:

| Método | Corte obtido | Acha o ótimo |
|---|---|---|
| Sorteio uniforme | 18 | **0 de 20** execuções |
| QAOA p=2 (como estava) | 18 | 0 |
| **QAOA p=4** | **20** | **3 de 4** |

Com p=2, o QAOA entregava exatamente o que o acaso entrega. Não por defeito do
algoritmo — por uma constante escrita no código.

Bate com a teoria: para Max-Cut em anel, p=1 tem razão de aproximação 0,75 e a
exatidão exige p crescendo com n. E p=4 ainda é **mais rápido** que p=2
(107–141 s contra 152 s), porque o COBYLA converge melhor num ansatz
expressivo em vez de gastar iterações num espaço de parâmetros pobre demais.

Vale ser exato sobre o que isso é: **o QAOA supera a amostragem aleatória com
orçamento igual**. Não é vantagem quântica sobre computação clássica — a busca
exaustiva acha o mesmo ótimo em 7 segundos. É o algoritmo fazendo trabalho real
em vez de sorte.

## Por que o teto anterior escondia isso

O limite era 12 qubits, fixo no código. Nesse tamanho o espaço tem 4.096
estados e a amostragem gasta 4.096 tiros — cobre ~63% do espaço por acaso.
Medido: sorteio uniforme acha o ótimo em **100%** das execuções, e metade do
orçamento já bastaria.

Ou seja: o motor estava preso no único regime onde era impossível demonstrar
qualquer coisa. Dez instâncias resolvidas com ótimo perfeito não provavam nada
sobre o algoritmo — provavam que o espaço era pequeno.

## Limites reais, e o que fazer com eles

**A borda da plataforma corta em ~300 s.** O timeout da aplicação foi elevado
para 900 s, mas HTTP 502 chegou aos 300,7 s com p=6 — é a Railway, não o
código. Otimização longa não cabe em requisição síncrona.

O caminho é o mesmo que o EngineeringOS já usa: **devolver `task_id` e deixar o
cliente consultar**. Enquanto for síncrono, o teto prático é p=4 a 20 qubits,
com folga de menos de 2× até o corte.

**Acima de 24 qubits, nada.** 2²⁵ = 33 milhões de estados leva a busca
exaustiva a mais de um minuto e a memória a subir sem necessidade. O `HTTP 400`
diz o teto e sugere decompor o problema — antes era `HTTP 500`, que acusava o
serviço de quebrado quando o pedido é que era grande demais.

## Correções aplicadas

- Teto do QAOA de 12 para `MAX_QUBITS_QAOA` (padrão 20)
- `QAOA_LAYERS` (padrão 4) e `QAOA_SHOTS` deixam de ser constantes no código
- `n > MAX_QUBITS_EXAUSTIVA` responde **400**, não 500
- `numpy_simulator` → `busca_exaustiva`, e a resposta ganha `metodo`
  (`qaoa` | `classico_exato`): o nome antigo se lia como simulador quântico
  quando não havia circuito nenhum
- A busca exaustiva deixou de montar um dicionário com os 2ⁿ estados para tirar
  o mínimo no fim. Agora avalia em blocos vetorizados com memória constante:
  n=18 caiu de 2075 ms para 448 ms, e n=24 passou a ser viável

## O que ainda incomoda

- **`quantum_advantage` só é calculado quando há `warm_start_bitstring`.** Sem
  ele o campo é sempre `false`, o que se lê como "não houve vantagem" quando o
  correto seria "não foi medida".
- **A resposta de erro do gateway vem com JSON aninhado**
  (`{"detail":"{\"detail\":\"...\"}"}`) — o corpo do serviço interno é embrulhado
  como texto em vez de repassado.
- **Otimização síncrona.** Enquanto for requisição direta, 300 s é o teto e
  nenhuma configuração muda isso.
