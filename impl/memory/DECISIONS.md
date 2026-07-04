# Registro de Decisões Técnicas (Architecture Decision Records)

## ADR-001: Mitigação de Complexidade do DAG (Dependências Cíclicas)
- **Contexto:** Professores e conteudistas que utilizam a `.eos` DSL podem cometer o erro de referenciar conhecimentos em um ciclo lógico infinito (A exige B, B exige A).
- **Decisão:** A inserção de novos grafos de Conhecimento passará obrigatoriamente pela validação matemática de ciclos, utilizando `networkx.find_cycle()`. 
- **Justificativa:** É preferível uma quebra determinística na compilação do arquivo `.eos` do que um vazamento de recursão infinita que quebre o motor do Backend em produção. Exceções fortemente tipadas (`CyclicDependencyError`) protegem o Universal Learning Architecture (ULA).

## ADR-002: Hard Limit Cognitivo (O Teto de Vidro)
- **Contexto:** A proposta de neurociência pede que a sobrecarga e fadiga em perfis hiperativos ou TDAH sejam tratadas preventivamente.
- **Decisão:** O Cognitive Challenge Engine (`cce.py`) deverá buscar as competências dominadas e liberar o próximo bloco da Fronteira do Conhecimento com um teto imutável (hard limit) de 4 KUs (Knowledge Units) novos.
- **Justificativa:** Sem isso, um nó base destravado ("Álgebra Elementar") poderia inundar a tela do aluno com 20 novas trilhas simultâneas, causando paralisia por análise. O limite de 4 impõe cadência focada.

## ADR-003: Separação de Preocupações na DSL
- **Contexto:** Converter texto bruto `.eos` para estruturas do grafo.
- **Decisão:** O `eos_parser.py` será um módulo isolado. Ele lerá um arquivo, detectará blocos `module`, `ku` e tags como `@prerequisite`, gerando dicionários limpos. Ele não tocará em classes de banco de dados.
- **Justificativa:** Facilita a criação de testes de unidade puramente textuais e matemáticos, respeitando os preceitos de Arquitetura Limpa.
