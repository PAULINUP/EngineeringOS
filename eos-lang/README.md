# eos-lang

**Currículo como código.** Escreva conhecimento num arquivo de texto, com pré-requisitos
explícitos, e receba de volta um currículo **verificado**: sem referências quebradas e sem
dependências circulares.

A ideia central é simples: *se compila, é percorrível*. Um ciclo entre pré-requisitos não é
aviso — é erro de compilação, porque significa que nenhuma das unidades envolvidas pode ser
a primeira, e o currículo é impossível de estudar.

```bash
pip install eos-lang
```

## Em 30 segundos

```eos
@version 1.0.0
@domain "matematica"

knowledge algebra FOUNDATIONAL {
  title: "Álgebra básica"
  definition: "Manipular expressões com incógnitas."
  interactivity: 3
  source: { type: "standard", ref: "OpenStax: Prealgebra", weight: 0.9 }
}

knowledge equacoes INTERMEDIATE {
  title: "Equações do primeiro grau"
  definition: "Isolar a incógnita."
  requires: [algebra]
}

mission fundamentos {
  label: "Fundamentos de matemática"
  requires: [algebra, equacoes]
  threshold: 0.85
}
```

```python
from eoslang import compile_file

curso = compile_file("matematica.eos")

curso.path_to("equacoes")       # ['algebra', 'equacoes'] — ordem de estudo
curso.roots()                   # ['algebra'] — por onde começar
curso.dependents_of("algebra")  # ['equacoes'] — o que isso destrava
curso.stats()                   # contagens por nível, domínio, relações
```

## Por que isto existe

Currículo costuma ser digitado em formulário, guardado em banco e revisado no olho. O
resultado é conhecido: pré-requisito que aponta para o nada, ciclo que ninguém percebe,
nenhum histórico de quem mudou o quê.

Tratar currículo como código resolve isso pelo caminho que a engenharia de software já
percorreu: texto em Git, *diff*, revisão por *pull request*, e um compilador que recusa o
que está errado **antes** de chegar ao aluno.

## Linha de comando

```bash
eos validate curso/*.eos              # sai != 0 se falhar — serve em CI
eos validate curso/*.eos --strict     # avisos viram erros
eos compile curso/*.eos -o curso.json
eos graph curso.eos --format mermaid  # diagrama para revisão
eos path curso/*.eos calculo_1        # o que estudar antes
eos stats curso/*.eos
```

Os erros apontam o lugar exato:

```
curso.eos:12:3: 'equacoes' referencia 'algebra_avancada', que não foi declarado
  requires: [algebra_avancada]
  ^
```

E ciclos vêm com o caminho completo, não só a notícia de que existem:

```
curso.eos:4:1: dependência circular: a → b → c → a
```

## No seu CI

```yaml
- name: Validar currículo
  run: |
    pip install eos-lang
    eos validate curriculo/**/*.eos --strict
```

Currículo que não compila não entra — a mesma regra que já vale para código.

## A linguagem

| Construção | Para quê |
|---|---|
| `knowledge` | unidade de conhecimento: a menor coisa que se aprende e se demonstra |
| `mission` | objetivo terminal: o conjunto que define "pronto" |
| `skill` | capacidade operacional desenvolvida por uma ou mais unidades |
| `topic` | agrupamento temático (navegação, não dependência) |
| `@diretiva` | metadados do arquivo (`@version`, `@domain`, `@author`) |

Campos de `knowledge`:

| Campo | Tipo | Padrão | Significado |
|---|---|---|---|
| `title` | texto | — | nome legível |
| `definition` | texto | — | o que a pessoa saberá fazer |
| `domain` | texto | — | área do conhecimento |
| `requires` | lista | `[]` | pré-requisitos (validados) |
| `interactivity` | 1–10 | 4 | carga cognitiva intrínseca |
| `decay_rate` | 0–1 | 0.05 | esquecimento por dia |
| `source` | bloco | — | proveniência: `{ type, ref, weight }` |
| `tags` | lista | `[]` | rótulos livres |

O nível vem depois do identificador: `knowledge x ADVANCED { … }` — `FOUNDATIONAL`,
`INTERMEDIATE`, `ADVANCED` ou `EXPERT`.

Campos desconhecidos não quebram a compilação: ficam em `extra`, para que a linguagem possa
crescer sem invalidar arquivos existentes.

## Vários arquivos, um currículo

Trilhas costumam viver em arquivos separados e se referenciar. Validar cada um isolado daria
falso positivo de referência quebrada, então compile todos juntos:

```python
from eoslang import compile_files
from pathlib import Path

curso = compile_files(sorted(Path("curriculo").glob("*.eos")))
print(len(curso.path_to("calculo_3")))   # a escada inteira, em ordem
```

## Saídas

```python
from eoslang import to_json, to_mermaid, to_dot, to_graph

to_json(curso)      # estrutura portátil
to_mermaid(curso)   # diagrama (o corte é anunciado dentro do próprio diagrama)
to_dot(curso)       # Graphviz
to_graph(curso)     # NetworkX — requer: pip install eos-lang[graph]
```

## Erros como parte da API

```python
from eoslang import compile_file, EOSCycleError, EOSReferenceError

try:
    curso = compile_file("curso.eos")
except EOSCycleError as e:
    print("ciclo:", " → ".join(e.cycle))      # o caminho, não só a existência
except EOSReferenceError as e:
    print(f"{e.origin} aponta para {e.reference}, que não existe")
```

## Escala

Testado com **1.808 unidades e 1.805 relações** (18 livros didáticos importados),
compilando e validando em menos de um segundo. A suíte inclui um teste que falha se o
compilador virar quadrático.

## Estabilidade

Sem dependências de runtime — decisão de projeto: quanto menor a superfície, mais fácil
embutir em qualquer lugar. NetworkX é opcional, só para exportar grafo.

## Licença

Apache License 2.0 — © 2026 Paulo Geovane da Silva Souza.

A escolha é deliberada: permite uso comercial e adoção ampla, exige preservação da
atribuição e inclui concessão expressa de patente, o que protege tanto quem usa quanto o
autor. Ver [LICENSE](LICENSE).

## Origem

Extraída do [EngineeringOS](https://github.com/PAULINUP/EngineeringOS), onde compila o
currículo que sustenta a plataforma em produção. A biblioteca é independente: não conhece
banco de dados, servidor nem modelo de aprendizagem — só a linguagem.
