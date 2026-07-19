import re
import unicodedata
from typing import List, Dict, Any, Optional, Tuple
import networkx as nx
from src.cognitive_engine import get_knowledge_frontier, WORKING_MEMORY_CAPACITY

# ===========================================================================
# Correção automática de desafios (server-side grading)
#
# Correção determinística e reprodutível ⇒ a evidência gerada recebe
# source_weight = 0.60 ("benchmark reprodutível", Definition 1 da spec).
# Uma resposta correta NÃO valida a KU sozinha: pela agregação noisy-OR,
# 1-(1-0.6)^n exige ~3 desafios distintos corretos para cruzar θ = 0.85.
# ===========================================================================

AUTO_GRADED_SOURCE_WEIGHT = 0.60

def _normalize_text(text: str) -> str:
    """minúsculas, sem acentos, espaços colapsados."""
    text = unicodedata.normalize("NFD", text.lower())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", text).strip()

def _extract_numbers(text: str) -> List[float]:
    """Extrai todos os números da resposta (aceita vírgula decimal brasileira)."""
    normalized = re.sub(r"(?<=\d),(?=\d)", ".", text)
    return [float(m) for m in re.findall(r"-?\d+(?:\.\d+)?", normalized)]

def grade_answer(
    answer_type: str,
    expected_answer: str,
    tolerance: float,
    student_answer: str,
) -> Tuple[bool, str]:
    """
    Corrige a resposta do estudante. Retorna (correto, detalhe).
    - numeric: compara o último número da resposta com o esperado (± tolerância).
      Vários números esperados (separados por ';') exigem que todos apareçam.
    - keywords: exige que todos os termos esperados (separados por ';')
      apareçam na resposta, sem sensibilidade a acentos/caixa.
    """
    student_answer = student_answer.strip()
    if not student_answer:
        return False, "Resposta vazia."

    if answer_type == "numeric":
        expected_values = [float(v.strip()) for v in expected_answer.split(";")]
        found = _extract_numbers(student_answer)
        if not found:
            return False, "Nenhum valor numérico encontrado na resposta."
        if len(expected_values) == 1:
            # Usa o último número citado (padrão: aluno conclui com o resultado)
            candidate = found[-1]
            ok = abs(candidate - expected_values[0]) <= tolerance
            return ok, f"Valor interpretado: {candidate:g}"
        # Conjunto de valores: todos devem estar presentes
        missing = [
            e for e in expected_values
            if not any(abs(f - e) <= tolerance for f in found)
        ]
        if missing:
            return False, f"Valores ausentes ou incorretos: {len(missing)} de {len(expected_values)}"
        return True, "Todos os valores corretos."

    if answer_type == "keywords":
        expected_terms = [_normalize_text(t) for t in expected_answer.split(";") if t.strip()]
        normalized = _normalize_text(student_answer)
        missing = [t for t in expected_terms if t not in normalized]
        if missing:
            return False, f"Conceitos ausentes: {len(missing)} de {len(expected_terms)}"
        return True, "Todos os conceitos presentes."

    return False, f"Tipo de correção desconhecido: {answer_type}"

# ---------------------------------------------------------------------------
# Banco de desafios padrão (currículo DSL de referência).
# Fonte: Strang (2016), Stewart (2015), Goodfellow et al. (2016) — as mesmas
# fontes declaradas nas KUs correspondentes do seed.
# ---------------------------------------------------------------------------
DEFAULT_CHALLENGE_BANK: Dict[str, List[Dict[str, Any]]] = {
    "linear_algebra.matrix_definition.v1": [
        {"prompt": "Uma matriz A ∈ ℝ²ˣ³ possui quantos elementos no total?",
         "answer_type": "numeric", "expected_answer": "6", "tolerance": 0.0,
         "feedback": "Uma matriz m×n tem m·n elementos: 2·3 = 6.", "difficulty": 0.2},
        {"prompt": "Para que o produto A·B exista, com A ∈ ℝ²ˣ³, quantas linhas B precisa ter?",
         "answer_type": "numeric", "expected_answer": "3", "tolerance": 0.0,
         "feedback": "O número de colunas de A deve igualar o número de linhas de B.", "difficulty": 0.3},
        {"prompt": "Qual o elemento a₂₁ da matriz A = [[7, 1], [4, 9]]?",
         "answer_type": "numeric", "expected_answer": "4", "tolerance": 0.0,
         "feedback": "aᵢⱼ é o elemento da linha i, coluna j: linha 2, coluna 1 → 4.", "difficulty": 0.2},
    ],
    "linear_algebra.dot_product.v1": [
        {"prompt": "Calcule o produto escalar de u = [2, -1, 3] e v = [1, 4, 2].",
         "answer_type": "numeric", "expected_answer": "4", "tolerance": 0.001,
         "feedback": "u·v = 2·1 + (-1)·4 + 3·2 = 2 - 4 + 6 = 4.", "difficulty": 0.3},
        {"prompt": "Se u·v = 0 e ambos os vetores são não-nulos, qual o ângulo entre eles em graus?",
         "answer_type": "numeric", "expected_answer": "90", "tolerance": 0.001,
         "feedback": "Produto escalar nulo entre vetores não-nulos ⇒ ortogonalidade (90°).", "difficulty": 0.4},
        {"prompt": "Calcule ||v||² (norma ao quadrado) para v = [3, 4].",
         "answer_type": "numeric", "expected_answer": "25", "tolerance": 0.001,
         "feedback": "||v||² = v·v = 9 + 16 = 25.", "difficulty": 0.3},
    ],
    "linear_algebra.matrix_multiplication.v1": [
        {"prompt": "Dadas A = [[1, 2], [3, 4]] e B = [[2, 0], [1, 2]], qual o valor do elemento C₁₁ de C = A·B?",
         "answer_type": "numeric", "expected_answer": "4", "tolerance": 0.001,
         "feedback": "C₁₁ = 1·2 + 2·1 = 4 (linha 1 de A vezes coluna 1 de B).", "difficulty": 0.4},
        {"prompt": "Com as mesmas A e B, calcule o elemento C₂₂ de C = A·B.",
         "answer_type": "numeric", "expected_answer": "8", "tolerance": 0.001,
         "feedback": "C₂₂ = 3·0 + 4·2 = 8.", "difficulty": 0.4},
        {"prompt": "O produto de matrizes é comutativo? Responda citando 'não' e a propriedade que se mantém: 'associativa'.",
         "answer_type": "keywords", "expected_answer": "nao;associativa", "tolerance": 0.0,
         "feedback": "A·B ≠ B·A em geral (não comutativo), mas (A·B)·C = A·(B·C) (associativo).", "difficulty": 0.5},
    ],
    "linear_algebra.eigenvalues.v1": [
        {"prompt": "Para a matriz diagonal A = [[3, 0], [0, 5]], liste os autovalores.",
         "answer_type": "numeric", "expected_answer": "3;5", "tolerance": 0.001,
         "feedback": "Os autovalores de uma matriz diagonal são os elementos da diagonal: 3 e 5.", "difficulty": 0.4},
        {"prompt": "Se A·v = 7v para v ≠ 0, qual o autovalor associado a v?",
         "answer_type": "numeric", "expected_answer": "7", "tolerance": 0.001,
         "feedback": "Direto da definição A·v = λ·v ⇒ λ = 7.", "difficulty": 0.3},
        {"prompt": "Qual o determinante de A = [[3, 0], [0, 5]]? (produto dos autovalores)",
         "answer_type": "numeric", "expected_answer": "15", "tolerance": 0.001,
         "feedback": "det(A) = produto dos autovalores = 3·5 = 15.", "difficulty": 0.5},
    ],
    "calculus.partial_derivatives.v1": [
        {"prompt": "Calcule ∂f/∂x de f(x, y) = 3x²y + 5y³ no ponto (1, 2).",
         "answer_type": "numeric", "expected_answer": "12", "tolerance": 0.001,
         "feedback": "∂f/∂x = 6xy (y tratado como constante); em (1,2): 6·1·2 = 12.", "difficulty": 0.5},
        {"prompt": "Calcule ∂f/∂y de f(x, y) = 3x²y + 5y³ no ponto (1, 1).",
         "answer_type": "numeric", "expected_answer": "18", "tolerance": 0.001,
         "feedback": "∂f/∂y = 3x² + 15y²; em (1,1): 3 + 15 = 18.", "difficulty": 0.5},
        {"prompt": "Para f(x, y) = x·y, quanto vale ∂f/∂x em (a, b)? Responda em termos de b (dê o valor para b = 4).",
         "answer_type": "numeric", "expected_answer": "4", "tolerance": 0.001,
         "feedback": "∂(xy)/∂x = y; avaliada em b = 4 → 4.", "difficulty": 0.4},
    ],
    "ml.gradient_descent.v1": [
        {"prompt": "Se a taxa de aprendizado η = 0.1 e o gradiente no ponto atual é 4.0, qual a magnitude do passo de atualização?",
         "answer_type": "numeric", "expected_answer": "0.4", "tolerance": 0.001,
         "feedback": "passo = η·∇J = 0.1 · 4.0 = 0.4.", "difficulty": 0.4},
        {"prompt": "Minimizando J(w) = w², com w = 3 e η = 0.1, qual o novo valor de w após um passo? (∇J = 2w)",
         "answer_type": "numeric", "expected_answer": "2.4", "tolerance": 0.001,
         "feedback": "w ← w - η·2w = 3 - 0.1·6 = 2.4.", "difficulty": 0.6},
        {"prompt": "O gradiente descendente caminha na direção de maior crescimento ou decrescimento da função de custo? Responda citando 'decrescimento' e o sinal do passo: 'negativo'.",
         "answer_type": "keywords", "expected_answer": "decrescimento;negativo", "tolerance": 0.0,
         "feedback": "O passo é -η·∇J: direção oposta ao gradiente, de maior decrescimento local.", "difficulty": 0.4},
    ],
}

class CognitiveChallengeEngine:
    """
    Motor de Desafios Cognitivos (CCE).
    Orquestra a geração de missões para o estudante garantindo que limites
    neurológicos (carga cognitiva, mitigação de TDAH) sejam rigorosamente respeitados.
    """
    
    def __init__(self, dag: nx.DiGraph, mastery_dict: Dict[str, float]):
        self.dag = dag
        self.mastery = mastery_dict
        
        # Hard constraint imposto pela ADR-002: Mitigação de Fadiga Cognitiva.
        # Nunca sobrecarregue o aluno com mais frentes simultâneas de aprendizado
        # inédito do que a capacidade da memória de trabalho (Cowan, 2001).
        self.MAX_CONCURRENT_KUS = WORKING_MEMORY_CAPACITY
        
    def generate_mission(self, threshold: float = 0.85) -> Dict[str, Any]:
        """
        Calcula a Fronteira de Conhecimento e gera a missão atual.
        """
        all_kus = list(self.dag.nodes)
        
        # 1. Obtém a fronteira matemática do DAG
        frontier = get_knowledge_frontier(self.dag, self.mastery, all_kus, threshold)
        
        # 2. Aplicação da Restrição Neurológica (Hard Limit)
        # Priorização simples (ordem alfabética para estabilidade), limitando a 4.
        # Num cenário futuro, a ordenação pode ser por maior impacto de transferência Jaccard.
        selected_kus = sorted(frontier)[:self.MAX_CONCURRENT_KUS]
        
        mission_payload = {
            "mission_id": "auto_generated_cce",
            "status": "ready",
            "metadata": {
                "total_frontier_size": len(frontier),
                "presented_kus_count": len(selected_kus),
                "cognitive_limit_applied": len(frontier) > self.MAX_CONCURRENT_KUS
            },
            "challenge_kus": selected_kus
        }
        
        return mission_payload
