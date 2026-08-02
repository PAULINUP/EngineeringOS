"""
eos-lang — currículo como código.

Escreva conhecimento num arquivo de texto, com pré-requisitos explícitos, e
receba de volta um currículo **verificado**: sem referências quebradas e sem
dependências circulares. O que compila é percorrível.

    from eoslang import compile_string

    curriculo = compile_string('''
        knowledge algebra FOUNDATIONAL {
          title: "Álgebra básica"
          definition: "Manipular expressões com incógnitas."
        }
        knowledge equacoes INTERMEDIATE {
          title: "Equações do primeiro grau"
          requires: [algebra]
        }
    ''')

    curriculo.path_to("equacoes")   # ['algebra', 'equacoes']
    curriculo.roots()               # ['algebra']

Um ciclo entre pré-requisitos é erro de compilação, não aviso: se A exige B e
B exige A, nenhuma das duas pode ser a primeira e o currículo é impossível.
"""
from .ast import (
    Curriculum,
    Knowledge,
    Level,
    Mission,
    Relation,
    RelationType,
    Skill,
    Source,
    Topic,
)
from .compiler import to_dict, to_dot, to_graph, to_json, to_mermaid
from .errors import (
    EOSCycleError,
    EOSError,
    EOSReferenceError,
    EOSSyntaxError,
    EOSValidationError,
)
from .lexer import Token, TokenType, tokenize
from .parser import Parser, parse
from .validator import ValidationResult, find_cycle, validate

__version__ = "1.0.0"

__all__ = [
    # entrada
    "compile_string", "compile_file", "compile_files", "parse", "validate",
    # modelo
    "Curriculum", "Knowledge", "Mission", "Skill", "Topic", "Source",
    "Relation", "RelationType", "Level",
    # saída
    "to_dict", "to_json", "to_graph", "to_mermaid", "to_dot",
    # erros
    "EOSError", "EOSSyntaxError", "EOSValidationError",
    "EOSCycleError", "EOSReferenceError",
    # internos úteis
    "Parser", "Token", "TokenType", "tokenize", "ValidationResult", "find_cycle",
    "__version__",
]


def compile_string(text: str, *, file: str = None,
                   validate_output: bool = True, strict: bool = False) -> Curriculum:
    """
    Compila texto EOS. Levanta na primeira falha — currículo inválido não
    deve seguir adiante em silêncio.
    """
    cur = parse(text, file)
    if validate_output:
        validate(cur, strict=strict).raise_if_invalid()
    return cur


def compile_file(path, *, validate_output: bool = True,
                 strict: bool = False) -> Curriculum:
    """Compila um arquivo .eos."""
    from pathlib import Path
    p = Path(path)
    return compile_string(p.read_text(encoding="utf-8"), file=str(p),
                          validate_output=validate_output, strict=strict)


def compile_files(paths, *, validate_output: bool = True,
                  strict: bool = False) -> Curriculum:
    """
    Compila vários arquivos como UM currículo.

    É o caso real: uma trilha por arquivo, referências cruzando os limites —
    validar cada um isoladamente daria falso positivo de referência quebrada.
    """
    from pathlib import Path

    combinado = Curriculum()
    for path in paths:
        p = Path(path)
        parcial = parse(p.read_text(encoding="utf-8"), str(p))
        combinado.knowledge.update(parcial.knowledge)
        combinado.missions.update(parcial.missions)
        combinado.skills.update(parcial.skills)
        combinado.topics.update(parcial.topics)
        combinado.directives.update(parcial.directives)
        combinado.source_files.append(str(p))

    if validate_output:
        validate(combinado, strict=strict).raise_if_invalid()
    return combinado
