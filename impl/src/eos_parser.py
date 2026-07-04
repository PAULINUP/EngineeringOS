import re
from typing import Dict, List, Any

class EOSSyntaxError(Exception):
    """Lançada quando o parser encontra um formato inválido no arquivo .eos."""
    def __init__(self, line_num: int, line: str, message: str):
        super().__init__(f"Sintaxe inválida na linha {line_num}: {message} -> '{line.strip()}'")

class EOSParser:
    """
    Motor de Parsing para a linguagem de domínio específico .eos do EngineeringOS.
    """
    
    def parse_file(self, filepath: str) -> Dict[str, Any]:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        return self.parse_content(lines)
        
    def parse_content(self, lines: List[str]) -> Dict[str, Any]:
        parsed_data = {
            "module_name": None,
            "description": None,
            "kus": []
        }
        
        current_ku = None
        
        for idx, raw_line in enumerate(lines):
            line_num = idx + 1
            line = raw_line.strip()
            
            # Ignora linhas vazias e comentários
            if not line or line.startswith("#"):
                continue
                
            # Declaração de Módulo
            if line.startswith("module "):
                if parsed_data["module_name"]:
                    raise EOSSyntaxError(line_num, line, "Declaração múltipla de módulos no mesmo arquivo")
                parsed_data["module_name"] = line[7:].strip()
                continue
                
            # Declaração de Descrição do módulo
            if line.startswith("description "):
                parsed_data["description"] = self._extract_quotes(line, line_num)
                continue
                
            # Declaração de KU (Knowledge Unit)
            if line.startswith("ku "):
                if current_ku:
                    parsed_data["kus"].append(current_ku)
                
                ku_name = line[3:].strip()
                if not ku_name:
                    raise EOSSyntaxError(line_num, line, "Nome da KU em branco")
                    
                current_ku = {
                    "name": ku_name,
                    "prerequisites": [],
                    "content": ""
                }
                continue
                
            # Atributos de KU
            if current_ku is not None:
                if line.startswith("@prerequisite "):
                    req = line[14:].strip()
                    current_ku["prerequisites"].append(req)
                elif line.startswith("@content "):
                    current_ku["content"] = self._extract_quotes(line, line_num)
                else:
                    raise EOSSyntaxError(line_num, line, "Instrução não reconhecida no bloco de KU")
            else:
                raise EOSSyntaxError(line_num, line, "Atributo solto sem um módulo ou KU atrelado")
                
        if current_ku:
            parsed_data["kus"].append(current_ku)
            
        if not parsed_data["module_name"]:
            raise ValueError("O arquivo .eos deve conter um 'module NomeDoModulo'")
            
        # DRY-RUN: Validação Estrita de AST e Anti-Ciclo
        from src.cognitive_engine import build_prerequisite_dag, CyclicDependencyError
        
        relations = []
        for ku in parsed_data["kus"]:
            for req in ku["prerequisites"]:
                relations.append({
                    "type": "prerequisite",
                    "source_id": req,
                    "target_id": ku["name"],
                    "weight": 1.0
                })
        
        try:
            build_prerequisite_dag(relations)
        except CyclicDependencyError as e:
            raise ValueError(f"FALHA FATAL NA AST: Paradoxo detectado. {str(e)}")
            
        return parsed_data

    def _extract_quotes(self, line: str, line_num: int) -> str:
        match = re.search(r'"(.*?)"', line)
        if not match:
            raise EOSSyntaxError(line_num, line, "Atributo requer um valor entre aspas")
        return match.group(1)

# Ponto de acesso rápido se executado por CLI
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
