import re
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from typing import Any, Dict, List, Tuple, Optional

class EOSSyntaxError(Exception):
    def __init__(self, message: str):
        super().__init__(f"Sintaxe inválida: {message}")

def tokenize(text: str) -> List[Tuple[str, Any]]:
    text = re.sub(r'(--|#).*', '', text)
    
    token_specification = [
        ('DIRECTIVE', r'@[a-zA-Z_]+'),
        ('STRING',    r'"[^"\\]*(?:\\.[^"\\]*)*"'),
        ('VERSION',   r'\d+\.\d+\.\d+'),
        ('NUMBER',    r'-?\d+(?:\.\d+)?'),
        ('LBRACE',    r'\{'),
        ('RBRACE',    r'\}'),
        ('LBRACKET',  r'\['),
        ('RBRACKET',  r'\]'),
        ('COLON',     r':'),
        ('COMMA',     r','),
        ('ID',        r'[a-zA-Z_][a-zA-Z0-9_.-]*'),
        ('SKIP',      r'[ \t\n\r]+'),
        ('MISMATCH',  r'.'),
    ]
    
    tok_regex = '|'.join('(?P<%s>%s)' % pair for pair in token_specification)
    tokens: List[Tuple[str, Any]] = []
    
    for mo in re.finditer(tok_regex, text):
        kind = mo.lastgroup
        value: Any = mo.group()
        if kind == 'SKIP':
            continue
        elif kind == 'STRING':
            value = value[1:-1]
        elif kind == 'NUMBER':
            value = float(value) if '.' in value else int(value)
        elif kind == 'MISMATCH':
            raise EOSSyntaxError(f'Unexpected character {value!r}')
        tokens.append((kind, value))
        
    return tokens

class EOSParser:
    def __init__(self, tokens: List[Tuple[str, Any]] = []):
        self.tokens = tokens
        self.pos = 0

    def parse_file(self, filepath: str) -> List[Dict[str, Any]]:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        self.tokens = tokenize(content)
        self.pos = 0
        return self.parse()

    def parse_content(self, content: str) -> List[Dict[str, Any]]:
        self.tokens = tokenize(content)
        self.pos = 0
        return self.parse()

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
            raise EOSSyntaxError(f"Expected token of type {kind}, got EOF")
        if t[0] != kind or (val is not None and str(t[1]).lower() != str(val).lower()):
            raise EOSSyntaxError(f"Expected token {kind}({val if val else ''}), got {t[0]}({t[1]})")
        return self.advance()

    def parse(self) -> List[Dict[str, Any]]:
        declarations = []
        while self.peek():
            t = self.peek()
            if t[0] == 'DIRECTIVE':
                declarations.append(self.parse_directive())
            elif t[0] == 'ID':
                declarations.append(self.parse_declaration())
            else:
                raise EOSSyntaxError(f"Unexpected top-level token: {t}")
                
        # DRY-RUN: Validação Estrita de AST e Anti-Ciclo
        from src.cognitive_engine import build_prerequisite_dag, CyclicDependencyError
        relations = []
        for dec in declarations:
            if dec.get("type") == "KNOWLEDGE":
                ku_id = dec["id"]
                data = dec.get("data", {})
                reqs = data.get("requires", [])
                if isinstance(reqs, list):
                    for req in reqs:
                        relations.append({
                            "type": "prerequisite",
                            "source_id": req,
                            "target_id": ku_id,
                            "weight": 1.0
                        })
        try:
            build_prerequisite_dag(relations)
        except CyclicDependencyError as e:
            raise ValueError(f"FALHA FATAL NA AST: Paradoxo detectado. {str(e)}")
            
        return declarations

    def parse_directive(self) -> Dict[str, Any]:
        t = self.expect('DIRECTIVE')
        key = t[1][1:] # remove @
        if self.peek() and self.peek()[0] in ('STRING', 'ID', 'NUMBER', 'VERSION'):
            val = self.advance()[1]
        else:
            raise EOSSyntaxError(f"Expected value for directive @{key}")
        return {"type": "DIRECTIVE", "key": key, "value": val}

    def parse_declaration(self) -> Dict[str, Any]:
        t = self.peek()
        if not t or t[0] != 'ID':
            raise EOSSyntaxError(f"Expected declaration type, got {t}")
        
        dec_type = self.advance()[1].upper()
        valid_types = ('KNOWLEDGE', 'COMPETENCE', 'MISSION', 'ASSESSMENT', 'EVIDENCE', 'SKILL', 'PROJECT', 'AGENT', 'TOPIC')
        if dec_type not in valid_types:
            raise EOSSyntaxError(f"Unknown declaration type: {dec_type}")
        
        if dec_type == 'EVIDENCE':
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
        elif dec_type == 'KNOWLEDGE':
            node_id = self.expect('ID')[1]
            level = None
            if self.peek() and self.peek()[0] == 'ID' and self.peek()[1].upper() in ('FOUNDATIONAL', 'INTERMEDIATE', 'ADVANCED', 'EXPERT'):
                level = self.advance()[1].upper()
            if self.peek() and self.peek()[0] == 'COLON':
                self.advance()
            block = self.parse_block()
            res = {"type": "KNOWLEDGE", "id": node_id, "data": block}
            if level:
                res["level"] = level
            return res
        else:
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
            if self.peek() and self.peek()[0] == 'COMMA':
                self.advance()
        self.expect('RBRACE')
        return block

    def parse_value(self) -> Any:
        t = self.peek()
        if not t:
            raise EOSSyntaxError("Unexpected EOF")
        if t[0] in ('STRING', 'NUMBER', 'VERSION'):
            return self.advance()[1]
        elif t[0] == 'ID':
            val_id = self.advance()[1]
            if self.peek() and self.peek()[0] == 'LBRACE':
                block = self.parse_block()
                return {"id": val_id, "spec": block}
            return val_id
        elif t[0] == 'LBRACKET':
            return self.parse_list()
        elif t[0] == 'LBRACE':
            return self.parse_block()
        else:
            raise EOSSyntaxError(f"Unexpected token in value: {t}")

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
    parser = EOSParser()
    return parser.parse_content(dsl_text)

if __name__ == "__main__":
    import sys
    import json
    if len(sys.argv) > 1:
        parser = EOSParser()
        try:
            result = parser.parse_file(sys.argv[1])
            print(json.dumps(result, indent=2, ensure_ascii=False))
        except Exception as e:
            print(f"Erro no Parser: {e}")
