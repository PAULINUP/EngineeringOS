"""
Testes do eos-lang.

O foco está nas garantias que a linguagem promete — referência válida e
ausência de ciclo — porque são elas que fazem "compilou" significar
"percorrível".
"""
import pytest

from eoslang import (
    EOSCycleError,
    EOSReferenceError,
    EOSSyntaxError,
    EOSValidationError,
    Level,
    compile_string,
    find_cycle,
    parse,
    to_dict,
    to_json,
    to_mermaid,
    validate,
)

SIMPLES = """
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
"""


# ---------------------------------------------------------------- parsing
def test_compila_curriculo_simples():
    cur = compile_string(SIMPLES)
    assert len(cur) == 2
    assert "algebra" in cur
    assert cur["equacoes"].requires == ["algebra"]
    assert cur["algebra"].level is Level.FOUNDATIONAL
    assert cur["equacoes"].level is Level.INTERMEDIATE


def test_diretivas_e_fontes():
    cur = compile_string(SIMPLES)
    assert cur.directives["version"] == "1.0.0"
    assert cur.directives["domain"] == "matematica"
    fonte = cur["algebra"].sources[0]
    assert fonte.reference == "OpenStax: Prealgebra"
    assert fonte.weight == 0.9


def test_comentarios_sao_ignorados():
    cur = compile_string("""
        -- comentário de traço
        # comentário de cerquilha
        knowledge x { title: "X" }
    """)
    assert len(cur) == 1


def test_erro_de_sintaxe_aponta_a_linha():
    with pytest.raises(EOSSyntaxError) as exc:
        compile_string("knowledge x {\n  title: \n}")
    assert exc.value.line >= 2


def test_bloco_nao_fechado():
    with pytest.raises(EOSSyntaxError, match="não fechado"):
        compile_string('knowledge x { title: "sem fim"')


def test_tipo_desconhecido():
    with pytest.raises(EOSSyntaxError, match="tipo desconhecido"):
        compile_string('planeta marte { title: "x" }')


# ------------------------------------------------------------- validação
def test_referencia_quebrada():
    with pytest.raises(EOSReferenceError) as exc:
        compile_string("knowledge b { requires: [inexistente] }")
    assert "inexistente" in str(exc.value)


def test_ciclo_direto_e_fatal():
    with pytest.raises(EOSCycleError):
        compile_string("""
            knowledge a { requires: [b] }
            knowledge b { requires: [a] }
        """)


def test_ciclo_indireto_com_caminho():
    with pytest.raises(EOSCycleError) as exc:
        compile_string("""
            knowledge a { requires: [c] }
            knowledge b { requires: [a] }
            knowledge c { requires: [b] }
        """)
    assert set(exc.value.cycle) == {"a", "b", "c"}


def test_auto_referencia():
    with pytest.raises(EOSValidationError, match="a si mesmo"):
        compile_string("knowledge a { requires: [a] }")


def test_find_cycle_isolado():
    assert find_cycle({"a": ["b"], "b": ["c"], "c": []}) is None
    ciclo = find_cycle({"a": ["b"], "b": ["a"]})
    assert ciclo and set(ciclo) == {"a", "b"}


def test_missao_referencia_unidade_inexistente():
    with pytest.raises(EOSReferenceError):
        compile_string("""
            knowledge a { title: "A" }
            mission m { requires: [a, fantasma] }
        """)


def test_avisos_nao_impedem_compilacao():
    cur = compile_string("knowledge a { }")     # sem título, definição ou fonte
    res = validate(cur)
    assert res.ok
    assert res.warnings


def test_modo_estrito_promove_avisos():
    cur = parse("knowledge a { }")
    assert not validate(cur, strict=True).ok


def test_limites_de_valor():
    with pytest.raises(EOSSyntaxError):
        compile_string("knowledge a { interactivity: 99 }")
    with pytest.raises(EOSSyntaxError):
        compile_string("knowledge a { decay_rate: 5 }")


# ------------------------------------------------------------- navegação
def test_caminho_ate_a_unidade():
    cur = compile_string("""
        knowledge a { title: "A" }
        knowledge b { requires: [a] }
        knowledge c { requires: [b] }
    """)
    assert cur.path_to("c") == ["a", "b", "c"]


def test_raizes_folhas_e_dependentes():
    cur = compile_string("""
        knowledge a { title: "A" }
        knowledge b { requires: [a] }
        knowledge c { requires: [a] }
    """)
    assert cur.roots() == ["a"]
    assert cur.leaves() == ["b", "c"]
    assert cur.dependents_of("a") == ["b", "c"]


def test_estatisticas():
    s = compile_string(SIMPLES).stats()
    assert s["knowledge_units"] == 2
    assert s["relations"] == 1
    assert s["missions"] == 1
    assert s["by_level"]["foundational"] == 1


# ------------------------------------------------------------- compilação
def test_saida_json_e_dict():
    cur = compile_string(SIMPLES)
    d = to_dict(cur)
    assert len(d["knowledge"]) == 2
    assert d["relations"][0] == {"source": "algebra", "target": "equacoes",
                                 "type": "prerequisite", "weight": 1.0}
    import json
    assert json.loads(to_json(cur))["stats"]["knowledge_units"] == 2


def test_mermaid_anuncia_o_corte():
    fonte = "\n".join(f'knowledge k{i} {{ title: "K{i}" }}' for i in range(10))
    saida = to_mermaid(compile_string(fonte), max_nodes=3)
    assert saida.startswith("graph LR")
    assert "omitidas" in saida          # corte nunca é silencioso


def test_grafo_networkx():
    nx = pytest.importorskip("networkx")
    from eoslang import to_graph
    g = to_graph(compile_string(SIMPLES))
    assert g.number_of_nodes() == 2
    assert g.has_edge("algebra", "equacoes")
    assert nx.is_directed_acyclic_graph(g)


# ------------------------------------------------------------- integração
def test_varios_arquivos_com_referencia_cruzada(tmp_path):
    from eoslang import compile_files
    (tmp_path / "base.eos").write_text('knowledge base { title: "Base" }',
                                       encoding="utf-8")
    (tmp_path / "avancado.eos").write_text(
        'knowledge avancado { requires: [base] }', encoding="utf-8")
    # cada arquivo isolado falharia; juntos, compilam
    cur = compile_files([tmp_path / "base.eos", tmp_path / "avancado.eos"])
    assert cur.path_to("avancado") == ["base", "avancado"]


def test_curriculo_grande_permanece_rapido():
    """Uma cadeia de 500 unidades: o compilador não pode ser quadrático."""
    import time
    linhas = ['knowledge k0 { title: "K0" }']
    linhas += [f'knowledge k{i} {{ requires: [k{i-1}] }}' for i in range(1, 500)]
    inicio = time.time()
    cur = compile_string("\n".join(linhas))
    duracao = time.time() - inicio
    assert len(cur) == 500
    assert duracao < 3.0, f"lento demais: {duracao:.2f}s"
