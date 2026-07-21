import asyncio
import math
import networkx as nx
from typing import Any, Dict, List, Set, Tuple

# Capacidade da memória de trabalho (Cowan, 2001): máximo de KUs novas por sessão.
# Constante constitucional — ver ENGINEERINGOS_SPECIFICATION Parte V (Cognitive Model).
WORKING_MEMORY_CAPACITY = 4

# P9 — Validação Objetiva: sem ao menos uma evidência objetiva (peso >= 0.60,
# gerada por processo verificável do sistema), a maestria por auto-estudo
# trava neste teto. Auto-estudo pratica; só verificação objetiva valida.
SELF_STUDY_MASTERY_CAP = 0.60
OBJECTIVE_EVIDENCE_WEIGHT = 0.60

def calculate_evidence_confidence(
    source_weight: float,
    reviewer_agreement: float,
    recency_factor: float
) -> float:
    """
    Calcula a confiança de um único registro de evidência:
    conf(E) = source_weight * reviewer_agreement * recency_factor
    """
    return source_weight * reviewer_agreement * recency_factor

def aggregate_evidence_confidence(evidences: List[Dict[str, Any]]) -> float:
    """
    Aplica a fórmula complementar de probabilidade para agregar a confiança de múltiplas evidências:
    conf_agg = 1 - prod(1 - conf(E_i))
    """
    if not evidences:
        return 0.0
    
    prod = 1.0
    for ev in evidences:
        # Extrai os pesos de confiabilidade de forma defensiva
        sw = ev.get("source_weight", 0.4)
        ra = ev.get("reviewer_agreement", 1.0)
        rf = ev.get("recency_factor", 1.0)
        conf = calculate_evidence_confidence(sw, ra, rf)
        prod *= (1.0 - conf)
        
    return 1.0 - prod

class CyclicDependencyError(Exception):
    """Lançado quando uma dependência cíclica é detectada no currículo."""
    pass

def build_prerequisite_dag(relations: List[Dict[str, Any]]) -> nx.DiGraph:
    """Gera um grafo direcionado NetworkX a partir das relações de pré-requisito."""
    g = nx.DiGraph()
    for rel in relations:
        if rel.get("type") == "prerequisite":
            # source é pré-requisito de target. Logo, a dependência direcionada é: source -> target
            g.add_edge(rel["source_id"], rel["target_id"], weight=rel.get("weight", 1.0))
            
    # Proteção de Arquitetura: Verificar se existe dependência cíclica
    try:
        cycles = list(nx.find_cycle(g, orientation="original"))
        if cycles:
            raise CyclicDependencyError(f"Dependência cíclica detectada no currículo: {cycles}")
    except nx.NetworkXNoCycle:
        pass
        
    return g

def calculate_jaccard_similarity(graph: nx.DiGraph, node_a: str, node_b: str) -> float:
    """
    Calcula a similaridade semântica Jaccard baseada nos conjuntos de ancestrais:
    sim_K(node_a, node_b) = |ancestors(a) ∩ ancestors(b)| / |ancestors(a) ∪ ancestors(b)|
    Inclui o próprio nó no conjunto de ancestrais para evitar indefinição em nós raiz.
    """
    if node_a == node_b:
        return 1.0
    
    # Busca ancestrais recursivos no DAG de pré-requisitos
    # Se os nós não existirem no grafo, consideramos apenas eles mesmos
    anc_a = (nx.ancestors(graph, node_a) if graph.has_node(node_a) else set()) | {node_a}
    anc_b = (nx.ancestors(graph, node_b) if graph.has_node(node_b) else set()) | {node_b}
    
    intersection = len(anc_a & anc_b)
    union = len(anc_a | anc_b)
    
    return intersection / union if union > 0 else 0.0

def calculate_transfer_coefficient(
    graph: nx.DiGraph,
    node_a: str,
    node_b: str,
    relation_type: str = "none"
) -> float:
    """
    Calcula o coeficiente de transferência:
    tau(node_a -> node_b) = sim_K(node_a, node_b) * relevance(node_a, node_b)
    """
    # Define a relevância baseada na relação (Definition 13.1)
    relevance = 0.1
    if relation_type == "prerequisite":
        relevance = 1.0
    elif relation_type in ("extends", "extended_by"):
        relevance = 0.7
    elif relation_type == "applies_to":
        relevance = 0.4
        
    sim = calculate_jaccard_similarity(graph, node_a, node_b)
    return sim * relevance

def get_knowledge_frontier(
    graph: nx.DiGraph,
    mastery_dict: Dict[str, float],
    all_kus: List[str],
    threshold: float = 0.85
) -> List[str]:
    """
    Retorna a Fronteira de Conhecimento F(a, t):
    Nós com maestria < threshold e cujos pré-requisitos todos possuem maestria >= threshold.
    """
    frontier = []
    for node in all_kus:
        mastery = mastery_dict.get(node, 0.0)
        if mastery >= threshold:
            continue
        
        # Verifica pré-requisitos
        prereqs = list(graph.predecessors(node)) if graph.has_node(node) else []
        prereqs_satisfied = True
        for pr in prereqs:
            if mastery_dict.get(pr, 0.0) < threshold:
                prereqs_satisfied = False
                break
                
        if prereqs_satisfied:
            frontier.append(node)
            
    return frontier

async def run_heavy_math_simulation(learner_id: str, ku_id: str, new_mastery: float):
    """
    Simula uma operação pesada no Grafo (Neo4j) e recálculo da matriz de Jaccard
    para centenas de dependências Jaccard-Transfer.
    Essa rotina agora roda completamente desacoplada do Loop do FastAPI.
    """
    await asyncio.sleep(2) # Simula 2 segundos de CPU blocking math processing
    return {"calculated_mastery": new_mastery, "transfers_applied": 14}

def calculate_learning_delta(
    current_mastery: float,
    evidence_conf: float,
    prereq_factor: float,
    eta_eff: float
) -> float:
    """
    Aplica a equação de atualização da função de aprendizado (Definition 8.2):
    delta = eta_eff * (evidence_conf - current_mastery) * prereq_factor
    """
    return eta_eff * (evidence_conf - current_mastery) * prereq_factor

def optimize_learning_trajectory(
    graph: nx.DiGraph,
    current_mastery: Dict[str, float],
    all_kus_dict: Dict[str, Dict[str, Any]],  # Detalhes de KUs (element_interactivity, etc)
    relations: List[Dict[str, Any]],
    mission_required_kus: List[str],
    cost_weights: Dict[str, float],
    threshold: float = 0.85,
    wm_capacity: int = WORKING_MEMORY_CAPACITY
) -> List[str]:
    """
    Gera o caminho ideal ULA (trajetória pi*) usando um agendador guloso que minimiza 
    o custo cumulativo e respeita a capacidade da memória de trabalho (miller/cowan).
    """
    alpha = cost_weights.get("alpha", 0.4)
    beta = cost_weights.get("beta", 0.3)
    gamma = cost_weights.get("gamma", 0.3)
    
    # 1. Expandir transitivamente todos os pré-requisitos necessários não validados
    all_needed: Set[str] = set()
    to_visit = list(mission_required_kus)
    
    while to_visit:
        curr = to_visit.pop(0)
        if current_mastery.get(curr, 0.0) < threshold:
            if curr not in all_needed:
                all_needed.add(curr)
                # Adiciona predecessores
                if graph.has_node(curr):
                    to_visit.extend(list(graph.predecessors(curr)))
                    
    if not all_needed:
        return []
        
    # Prepara o conjunto de nós validados ou agendados
    completed_set = {node for node, val in current_mastery.items() if val >= threshold}
    path: List[str] = []
    
    # 2. Agendamento passo a passo baseado na minimização de custo
    while len(path) < len(all_needed):
        # Determina os candidatos disponíveis na fronteira do conjunto que precisamos aprender
        candidates = []
        for node in all_needed:
            if node in path or node in completed_set:
                continue
            
            # Todos os pré-requisitos deste nó estão no path ou já estão validados?
            prereqs = list(graph.predecessors(node)) if graph.has_node(node) else []
            if all(pr in completed_set or pr in path for pr in prereqs):
                candidates.append(node)
                
        if not candidates:
            # Se não há candidatos, há uma quebra de ciclicidade ou dependência órfã
            # Retornamos o ordenamento topológico direto dos nós restantes como fallback
            remaining = all_needed - set(path)
            subgraph = graph.subgraph(remaining)
            try:
                fallback_sort = list(nx.topological_sort(subgraph))
                path.extend(fallback_sort)
            except nx.NetworkXUnfeasible:
                # Se houver ciclos, adiciona em ordem arbitrária
                path.extend(list(remaining))
            break
            
        # Avalia o custo de cada candidato
        best_candidate = None
        best_cost = float('inf')
        
        for cand in candidates:
            ku_info = all_kus_dict.get(cand, {})
            interactivity = ku_info.get("element_interactivity", 4)
            
            # Calcula o ganho de transferência máximo a partir de nós já conhecidos
            max_transfer = 0.0
            for completed in (completed_set | set(path)):
                # Determina o tipo de relação
                rel_type = "none"
                for rel in relations:
                    if rel["source_id"] == completed and rel["target_id"] == cand:
                        rel_type = rel["type"]
                        break
                    elif rel["target_id"] == completed and rel["source_id"] == cand:
                        # Relação inversa
                        if rel["type"] == "extends":
                            rel_type = "extended_by"
                        break
                
                transfer = calculate_transfer_coefficient(graph, completed, cand, rel_type)
                if transfer > max_transfer:
                    max_transfer = transfer
                    
            # Novelty é o complemento da transferência semântica
            novelty = max(0.0, 1.0 - max_transfer)
            
            # Custo cognitivo (Miller/Cowan)
            cognitive_load = interactivity * novelty
            
            # Custo final: alpha * time(interactivity) + beta * load - gamma * expected_conf(0.6 default)
            expected_conf = 0.6  # valor médio esperado de evidência
            cost = alpha * interactivity + beta * cognitive_load - gamma * expected_conf
            
            if cost < best_cost:
                best_cost = cost
                best_candidate = cand
                
        if best_candidate:
            path.append(best_candidate)
            if len(path) >= wm_capacity:
                break
            
    return path
