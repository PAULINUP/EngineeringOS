"""
Analisador sintático da linguagem EOS.

Descida recursiva, um token de antecipação. A gramática é pequena de
propósito: quem escreve currículo é professor, não compilador.

    arquivo      = { diretiva | declaração }
    diretiva     = "@" IDENT valor
    declaração   = tipo IDENT [ nível ] [ ":" ] bloco
    tipo         = knowledge | mission | skill | topic
    bloco        = "{" { chave ":" valor [","] } "}"
    valor        = STRING | NUMBER | VERSION | IDENT | lista | bloco
    lista        = "[" [ valor { "," valor } ] "]"
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .ast import Curriculum, Knowledge, Level, Mission, Skill, Source, Topic
from .errors import EOSSyntaxError
from .lexer import Token, TokenType, tokenize

_TIPOS = {"knowledge", "mission", "skill", "topic",
          "competence", "assessment", "evidence", "project", "agent"}
_NIVEIS = {l.value for l in Level}


class Parser:
    def __init__(self, tokens: List[Token], file: Optional[str] = None):
        self.tokens = tokens
        self.pos = 0
        self.file = file

    # ---- utilidades ----
    def peek(self) -> Token:
        return self.tokens[self.pos]

    def advance(self) -> Token:
        tok = self.tokens[self.pos]
        if tok.type is not TokenType.EOF:
            self.pos += 1
        return tok

    def erro(self, msg: str, tok: Optional[Token] = None) -> EOSSyntaxError:
        t = tok or self.peek()
        return EOSSyntaxError(msg, line=t.line, column=t.column,
                              source_line=t.source_line, file=self.file)

    def expect(self, tipo: TokenType) -> Token:
        tok = self.peek()
        if tok.type is not tipo:
            achado = "fim do arquivo" if tok.type is TokenType.EOF else repr(tok.value)
            raise self.erro(f"esperava {tipo.value}, encontrei {achado}")
        return self.advance()

    # ---- programa ----
    def parse(self) -> Curriculum:
        cur = Curriculum()
        if self.file:
            cur.source_files.append(self.file)

        while self.peek().type is not TokenType.EOF:
            tok = self.peek()
            if tok.type is TokenType.DIRECTIVE:
                chave, valor = self.parse_directive()
                cur.directives[chave] = valor
            elif tok.type is TokenType.IDENT:
                self.parse_declaration(cur)
            else:
                raise self.erro(f"declaração inesperada: {tok.value!r}")
        return cur

    def parse_directive(self):
        tok = self.expect(TokenType.DIRECTIVE)
        chave = str(tok.value)[1:]
        prox = self.peek()
        if prox.type not in (TokenType.STRING, TokenType.IDENT,
                             TokenType.NUMBER, TokenType.VERSION):
            raise self.erro(f"a diretiva @{chave} precisa de um valor")
        return chave, self.advance().value

    def parse_declaration(self, cur: Curriculum) -> None:
        tok_tipo = self.expect(TokenType.IDENT)
        tipo = str(tok_tipo.value).lower()
        if tipo not in _TIPOS:
            raise self.erro(
                f"tipo desconhecido: {tok_tipo.value!r}. "
                f"Use um de: {', '.join(sorted(_TIPOS))}",
                tok_tipo,
            )

        tok_id = self.expect(TokenType.IDENT)
        ident = str(tok_id.value)

        # nível opcional após o identificador: `knowledge x ADVANCED { ... }`
        nivel: Optional[Level] = None
        if (self.peek().type is TokenType.IDENT
                and str(self.peek().value).lower() in _NIVEIS):
            nivel = Level.parse(str(self.advance().value))

        if self.peek().type is TokenType.COLON:
            self.advance()

        bloco = self.parse_block()

        if tipo == "knowledge":
            cur.knowledge[ident] = self._build_knowledge(ident, bloco, nivel, tok_id.line)
        elif tipo == "mission":
            cur.missions[ident] = self._build_mission(ident, bloco, tok_id.line)
        elif tipo == "skill":
            cur.skills[ident] = Skill(id=ident, label=str(bloco.get("label", "")),
                                      domain=str(bloco.get("domain", "")), line=tok_id.line)
        elif tipo == "topic":
            cur.topics[ident] = Topic(id=ident, label=str(bloco.get("label", "")),
                                      domain=str(bloco.get("domain", "")), line=tok_id.line)
        # demais tipos são aceitos e ignorados: mantêm arquivos antigos
        # compilando enquanto a linguagem cresce

    # ---- construtores ----
    @staticmethod
    def _lista(valor: Any) -> List[str]:
        if valor is None:
            return []
        if isinstance(valor, list):
            return [str(v["id"]) if isinstance(v, dict) and "id" in v else str(v)
                    for v in valor]
        return [str(valor)]

    def _build_knowledge(self, ident: str, b: Dict[str, Any],
                         nivel: Optional[Level], linha: int) -> Knowledge:
        conhecidas = {"title", "definition", "domain", "level", "requires", "enables",
                      "interactivity", "element_interactivity", "decay_rate",
                      "domain_decay_rate", "source", "sources", "tags", "prerequisites"}
        fontes: List[Source] = []
        bruto = b.get("sources") or b.get("source")
        if bruto is not None:
            for s in (bruto if isinstance(bruto, list) else [bruto]):
                if isinstance(s, dict):
                    spec = s.get("spec", s)
                    fontes.append(Source(
                        reference=str(spec.get("ref") or spec.get("reference") or ""),
                        type=str(spec.get("type", "unspecified")),
                        weight=float(spec.get("weight", 1.0)),
                    ))
                else:
                    fontes.append(Source(reference=str(s)))

        if nivel is None and "level" in b:
            nivel = Level.parse(str(b["level"]))

        try:
            return Knowledge(
                id=ident,
                title=str(b.get("title", "")),
                definition=str(b.get("definition", "")),
                domain=str(b.get("domain", "")),
                level=nivel or Level.FOUNDATIONAL,
                requires=self._lista(b.get("requires") or b.get("prerequisites")),
                enables=self._lista(b.get("enables")),
                interactivity=int(b.get("interactivity",
                                        b.get("element_interactivity", 4))),
                decay_rate=float(b.get("decay_rate", b.get("domain_decay_rate", 0.05))),
                sources=fontes,
                tags=self._lista(b.get("tags")),
                extra={k: v for k, v in b.items() if k not in conhecidas},
                line=linha,
            )
        except ValueError as e:
            raise EOSSyntaxError(str(e), line=linha, file=self.file) from e

    def _build_mission(self, ident: str, b: Dict[str, Any], linha: int) -> Mission:
        conhecidas = {"label", "requires", "required_kus", "optional", "optional_kus",
                      "critical", "critical_kus", "threshold", "terminal_threshold",
                      "critical_threshold", "cost_weights", "cost"}
        pesos = b.get("cost_weights") or b.get("cost") or {}
        try:
            return Mission(
                id=ident,
                label=str(b.get("label", "")),
                requires=self._lista(b.get("requires") or b.get("required_kus")),
                optional=self._lista(b.get("optional") or b.get("optional_kus")),
                critical=self._lista(b.get("critical") or b.get("critical_kus")),
                threshold=float(b.get("threshold", b.get("terminal_threshold", 0.85))),
                critical_threshold=float(b.get("critical_threshold", 0.90)),
                cost_weights={k: float(v) for k, v in pesos.items()}
                if isinstance(pesos, dict) else {},
                extra={k: v for k, v in b.items() if k not in conhecidas},
                line=linha,
            )
        except ValueError as e:
            raise EOSSyntaxError(str(e), line=linha, file=self.file) from e

    # ---- blocos e valores ----
    def parse_block(self) -> Dict[str, Any]:
        self.expect(TokenType.LBRACE)
        bloco: Dict[str, Any] = {}
        while self.peek().type is not TokenType.RBRACE:
            if self.peek().type is TokenType.EOF:
                raise self.erro("bloco não fechado: faltou '}'")
            chave = str(self.expect(TokenType.IDENT).value)
            self.expect(TokenType.COLON)
            bloco[chave] = self.parse_value()
            if self.peek().type is TokenType.COMMA:
                self.advance()
        self.expect(TokenType.RBRACE)
        return bloco

    def parse_value(self) -> Any:
        tok = self.peek()
        if tok.type in (TokenType.STRING, TokenType.NUMBER, TokenType.VERSION):
            return self.advance().value
        if tok.type is TokenType.IDENT:
            ident = str(self.advance().value)
            if self.peek().type is TokenType.LBRACE:      # ident seguido de bloco
                return {"id": ident, "spec": self.parse_block()}
            return ident
        if tok.type is TokenType.LBRACKET:
            return self.parse_list()
        if tok.type is TokenType.LBRACE:
            return self.parse_block()
        raise self.erro(f"valor inválido: {tok.value!r}")

    def parse_list(self) -> List[Any]:
        self.expect(TokenType.LBRACKET)
        itens: List[Any] = []
        while self.peek().type is not TokenType.RBRACKET:
            if self.peek().type is TokenType.EOF:
                raise self.erro("lista não fechada: faltou ']'")
            itens.append(self.parse_value())
            if self.peek().type is TokenType.COMMA:
                self.advance()
        self.expect(TokenType.RBRACKET)
        return itens


def parse(text: str, file: Optional[str] = None) -> Curriculum:
    """Lê texto EOS e devolve o currículo (sem validar semântica)."""
    return Parser(tokenize(text, file), file).parse()
