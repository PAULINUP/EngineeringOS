from typing import List, Dict, Any
import networkx as nx
from src.cognitive_engine import get_knowledge_frontier, WORKING_MEMORY_CAPACITY

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
