# Qualidade do catálogo

O conteúdo do EngineeringOS não é escrito à mão: 1.723 desafios foram extraídos
de 18 livros do OpenStax por raspagem. Raspagem erra, e o erro chega ao aluno na
forma pior possível — uma pergunta sem resposta certa, com o aluno concluindo
que o errado é ele.

Este documento registra os defeitos encontrados, por que cada um passou, e o
mecanismo que existe hoje para que o próximo seja pego sem depender de alguém
reclamar.

## O caso que abriu o assunto

Um aluno respondeu à pergunta "determine quais dos seguintes números são
inteiros: 0, 2/3, 5, 8.1, 125" e não havia resposta que o servidor aceitasse. O
gabarito gravado era **5125** — um número que não aparece em lugar nenhum do
exercício.

A causa estava numa linha só. O MathML do OpenStax parte números em tokens, e
`1.234` chega ao raspador como `1 , 234`; havia uma regex para remontar isso:

```python
re.sub(r"(\d)\s*,\s*(\d{3})(?!\d)", r"\1\2", text)
```

O `\s*` aceita zero espaços, então a mesma regex casa com vírgula de lista. O
gabarito do livro era `(a) 5, 125 (b) 0, 5, 125`; virou `(a) 5125 (b) 0, 5125`.

O que separa os dois casos é o espaço **antes** da vírgula: ele existe no número
mutilado (`2 , 162`, tokens colados com espaço) e não existe na lista em prosa
inglesa (`5, 125`). A correção usa exatamente esse sinal:

```python
text = re.sub(r"(\d)\s+,\s*(\d{3})(?!\d)", r"\1\2", text)   # número mutilado
text = re.sub(r"(\d),(\d{3})(?!\d)", r"\1\2", text)          # número já correto
```

## Os três defeitos, e o que foi feito com cada um

| Defeito | Como se manifestava | Quantos | Tratamento |
|---|---|---|---|
| Fração lida como dois números | `(243/32)` virou o conjunto `243;32` | 38 | **Reparado**: gabarito recalculado para `7.59375` |
| Vírgula de lista colada | `(a) 5, 125` virou `5125` | — | Corrigido na origem; os afetados caem na linha abaixo |
| Resposta em partes fundida | `(a) … (b) …` virou um conjunto só | 59 | **Quarentena**: são duas perguntas, não há gabarito único |
| Variável traduzida como pronome | o vetor `u` virou `você = i + j` | 5 | **Quarentena**: enunciado sem sentido |

Resultado: 1.659 desafios servíveis, 64 fora do ar, 38 consertados.

Os reparos e a quarentena são aplicados por
[`tools/repair_challenges.py`](../impl/tools/repair_challenges.py), com regras
determinísticas — nenhuma decisão sai de modelo de linguagem. Cada decisão se
apoia no texto original do gabarito, que ficou preservado no campo `feedback`.

## Quarentena, não exclusão

Desafio retirado recebe `active = false` e continua no banco. Três razões:

1. Evidências já registradas apontam para ele por `source_ref`; apagar deixaria
   a mestria de alguém apoiada num registro órfão.
2. A decisão pode estar errada, e errar de forma reversível é barato.
3. O histórico do defeito é o que permite melhorar o importador.

`repair_challenges.py --restore` devolve todos ao catálogo.

## Como o próximo defeito é pego

O importador foi corrigido, mas nenhuma regra de extração cobre um corpus de
1.700 exercícios sem deixar resto. A rede que sobra é o aluno — sem transformar
isso em poder de destruir conteúdo alheio.

**Denúncia com quórum** (`POST /challenges/{id}/report`):

- o desafio sai **imediatamente** da trilha de quem denunciou, para ninguém
  ficar travado num item defeituoso;
- sai do catálogo **para todos** quando `QUORUM_DENUNCIA = 3` alunos distintos
  apontam o mesmo problema, ou quando um administrador denuncia;
- um aluno, um voto (restrição única em `(challenge_id, learner_id)`);
- desafio em quarentena responde 410 a tentativas: gabarito sob suspeita não
  gera evidência, senão a mestria seria contaminada pelo próprio defeito.

Três é o mesmo número que a agregação noisy-OR exige para validar uma
competência. Se três evidências independentes bastam para afirmar que alguém
sabe, três denúncias independentes bastam para afirmar que o item está ruim. É o
P9 aplicado ao conteúdo: julgamento por sinal agregado, não por opinião isolada.

`DELETE /challenges/{id}` continua existindo para lixo confirmado, restrito a
administradores. Antes desta revisão a rota **não exigia autenticação alguma** —
qualquer requisição anônima apagava, para todos os alunos, qualquer desafio do
catálogo.

## O que continua em aberto

- **Sinal de dificuldade anômala.** Um desafio que todos erram é suspeito antes
  de qualquer denúncia. Hoje as tentativas erradas não são gravadas, então esse
  sinal não existe. É a próxima peça óbvia.
- **Reimportação.** Os 59 em quarentena por resposta em partes são recuperáveis
  se o importador passar a tratar `(a)`/`(b)` como dois desafios distintos.
- **Tradução.** O caso `u` → `você` mostra que o tradutor não distingue variável
  de palavra. Um glossário de símbolos protegidos resolveria a classe inteira.
