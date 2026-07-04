# Changelog - EngineeringOS

## [v2.1.0] - 2026-07-03
### Added
- Limitador dinâmico de 4 KUs (Knowledge Units) na `cce.py` (Cognitive Challenge Engine) para evitar fadiga cognitiva extrema em alunos TDAH.
- Parser customizado para a linguagem `.eos` (`eos_parser.py`) com isolamento de domínio.
- Primeira missão (Patient Zero): `calculus.eos`.
- Proteção contra ciclos matemáticos no Universal Learning Architecture via `networkx.find_cycle`.

### Fixed
- SQLAlchemy *MissingGreenlet*: Vazamento de estado Assíncrono pós-commit foi fixado (`await db.refresh`).
- *UnboundLocalError*: Variável global de ambiente `curr_state` estabilizada no endpoint principal da API.
- Sobrecarga e Concorrência de IO: Incremento agressivo de Timeout (20.0s) no driver SQLite Async para mitigar Data Locking provocado pela sincronização Git massiva do Swarm.
- Refatoração dos nomes singulares e plurais nas tabelas SQL do módulo de cache JSON.
