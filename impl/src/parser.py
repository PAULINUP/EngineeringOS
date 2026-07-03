import re
from typing import Any, Dict, List, Tuple, Optional

def tokenize(text: str) -> List[Tuple[str, Any]]:
    # Remove single-line comments like -- ... or # ...
    text = re.sub(r'(--|#).*', '', text)
    
    token_specification = [
        ('STRING',   r'"[^"\\]*(?:\\.[^"\\]*)*"'),
        ('NUMBER',   r'\d+(?:\.\d+)?'),
        ('LBRACE',   r'\{'),
        ('RBRACE',   r'\}'),
        ('LBRACKET', r'\['),
        ('RBRACKET', r'\]'),
        ('COLON',    r':'),
        ('COMMA',    r','),
        ('ID',       r'[a-zA-Z_][a-zA-Z0-9_.-]*'),
        ('SKIP',     r'[ \t\n\r]+'),
        ('MISMATCH', r'.'),
    ]
    
    tok_regex = '|'.join('(?P<%s>%s)' % pair for pair in token_specification)
    tokens: List[Tuple[str, Any]] = []
    
    for mo in re.finditer(tok_regex, text):
        kind = mo.lastgroup
        value: Any = mo.group()
        if kind == 'SKIP':
            continue
        elif kind == 'STRING':
            value = value[1:-1]  # strip quotes
        elif kind == 'NUMBER':
            value = float(value) if '.' in value else int(value)
        elif kind == 'MISMATCH':
            raise RuntimeError(f'Unexpected character {value!r}')
        tokens.append((kind, value))
        
    return tokens

class EOSParser:
    def __init__(self, tokens: List[Tuple[str, Any]]):
        self.tokens = tokens
        self.pos = 0

    def peek(self) -> Optional[Tuple[str, Any]]:
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return None

    def advance(self) -> Tuple[str, Any]:
        t = self.peek()
        self.pos += 1
        return t  # type: ignore

    def expect(self, kind: str, val: Optional[Any] = None) -> Tuple[str, Any]:
        t = self.peek()
        if not t:
            raise RuntimeError(f"Expected token of type {kind}, got EOF")
        if t[0] != kind or (val is not None and t[1] != val):
            raise RuntimeError(f"Expected token {kind}({val if val else ''}), got {t[0]}({t[1]})")
        return self.advance()

    def parse(self) -> List[Dict[str, Any]]:
        declarations = []
        while self.peek():
            declarations.append(self.parse_declaration())
        return declarations

    def parse_declaration(self) -> Dict[str, Any]:
        t = self.peek()
        if not t or t[0] != 'ID':
            raise RuntimeError(f"Expected declaration type (KU, MISSION, SKILL, etc.), got {t}")
        
        dec_type = self.advance()[1].upper()
        if dec_type not in ('KU', 'MISSION', 'SKILL', 'EVIDENCE'):
            raise RuntimeError(f"Unknown declaration type: {dec_type}")
        
        if dec_type == 'EVIDENCE':
            # EVIDENCE id "for" id : block
            ev_id = self.expect('ID')[1]
            self.expect('ID', 'for')
            target_id = self.expect('ID')[1]
            if self.peek() and self.peek()[0] == 'COLON':
                self.advance()
            block = self.parse_block()
            return {
                "type": "EVIDENCE",
                "id": ev_id,
                "target": target_id,
                "data": block
            }
        else:
            # KU id : block OR KU id block
            node_id = self.expect('ID')[1]
            if self.peek() and self.peek()[0] == 'COLON':
                self.advance()
            block = self.parse_block()
            return {
                "type": dec_type,
                "id": node_id,
                "data": block
            }

    def parse_block(self) -> Dict[str, Any]:
        self.expect('LBRACE')
        block: Dict[str, Any] = {}
        while self.peek() and self.peek()[0] != 'RBRACE':
            k = self.expect('ID')[1]
            self.expect('COLON')
            v = self.parse_value()
            block[k] = v
            # optional comma
            if self.peek() and self.peek()[0] == 'COMMA':
                self.advance()
        self.expect('RBRACE')
        return block

    def parse_value(self) -> Any:
        t = self.peek()
        if not t:
            raise RuntimeError("Unexpected EOF")
        if t[0] in ('STRING', 'NUMBER'):
            return self.advance()[1]
        elif t[0] == 'ID':
            return self.advance()[1]
        elif t[0] == 'LBRACKET':
            return self.parse_list()
        elif t[0] == 'LBRACE':
            return self.parse_block()
        else:
            raise RuntimeError(f"Unexpected token in value: {t}")

    def parse_list(self) -> List[Any]:
        self.expect('LBRACKET')
        lst = []
        while self.peek() and self.peek()[0] != 'RBRACKET':
            lst.append(self.parse_value())
            if self.peek() and self.peek()[0] == 'COMMA':
                self.advance()
        self.expect('RBRACKET')
        return lst

def parse_dsl_content(dsl_text: str) -> List[Dict[str, Any]]:
    tokens = tokenize(dsl_text)
    parser = EOSParser(tokens)
    return parser.parse()
