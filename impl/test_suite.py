import unittest
import asyncio
import networkx as nx
from typing import Dict, Any

from src.parser import tokenize, EOSParser, parse_dsl_content
from src import cognitive_engine

class TestEOSParser(unittest.TestCase):
    def test_tokenization(self):
        dsl = """
        SKILL skill.test {
            label: "Test Label"
            domain: "math"
        }
        """
        tokens = tokenize(dsl)
        self.assertTrue(len(tokens) > 0)
        self.assertEqual(tokens[0][1], "SKILL")

    def test_parsing(self):
        dsl = """
        KU linear_algebra.matrix_definition.v1 {
            title: "Matrix Definition"
            domain: "linear_algebra"
            level: foundational
            element_interactivity: 2
            sources: [
                { type: "academic", reference: "Strang, G.", weight: 1.0 }
            ]
        }
        """
        decs = parse_dsl_content(dsl)
        self.assertEqual(len(decs), 1)
        self.assertEqual(decs[0]["type"], "KU")
        self.assertEqual(decs[0]["id"], "linear_algebra.matrix_definition.v1")
        self.assertEqual(decs[0]["data"]["title"], "Matrix Definition")
        self.assertEqual(decs[0]["data"]["element_interactivity"], 2)
        self.assertEqual(len(decs[0]["data"]["sources"]), 1)
        self.assertEqual(decs[0]["data"]["sources"][0]["type"], "academic")

class TestCognitiveMath(unittest.TestCase):
    def setUp(self):
        # Cria um DAG de pré-requisitos simples
        # A -> B -> C
        self.relations = [
            {"source_id": "A", "target_id": "B", "type": "prerequisite", "weight": 1.0},
            {"source_id": "B", "target_id": "C", "type": "prerequisite", "weight": 1.0}
        ]
        self.dag = cognitive_engine.build_prerequisite_dag(self.relations)

    def test_dag_structure(self):
        self.assertTrue(self.dag.has_edge("A", "B"))
        self.assertTrue(self.dag.has_edge("B", "C"))
        self.assertFalse(self.dag.has_edge("A", "C"))
        self.assertEqual(list(nx.topological_sort(self.dag)), ["A", "B", "C"])

    def test_jaccard_similarity(self):
        # A não tem ancestrais (apenas ele mesmo no conjunto estendido: {A})
        # B tem ancestral A (conjunto estendido: {A, B})
        # C tem ancestrais A e B (conjunto estendido: {A, B, C})
        
        # sim(A, B) = |{A} ∩ {A, B}| / |{A} ∪ {A, B}| = 1 / 2 = 0.5
        sim_ab = cognitive_engine.calculate_jaccard_similarity(self.dag, "A", "B")
        self.assertEqual(sim_ab, 0.5)
        
        # sim(A, C) = |{A} ∩ {A, B, C}| / |{A} ∪ {A, B, C}| = 1 / 3 ≈ 0.333
        sim_ac = cognitive_engine.calculate_jaccard_similarity(self.dag, "A", "C")
        self.assertAlmostEqual(sim_ac, 0.3333333, places=4)
        
        # sim(B, C) = |{A, B} ∩ {A, B, C}| / |{A, B} ∪ {A, B, C}| = 2 / 3 ≈ 0.667
        sim_bc = cognitive_engine.calculate_jaccard_similarity(self.dag, "B", "C")
        self.assertAlmostEqual(sim_bc, 0.6666666, places=4)

    def test_transfer_coefficient(self):
        # Relação direta de pré-requisito A -> B (relevance = 1.0)
        # tau(A -> B) = sim(A, B) * 1.0 = 0.5 * 1.0 = 0.5
        tau_ab = cognitive_engine.calculate_transfer_coefficient(self.dag, "A", "B", "prerequisite")
        self.assertEqual(tau_ab, 0.5)

    def test_evidence_aggregation(self):
        # Única evidência com conf = 0.4 * 1.0 * 1.0 = 0.4
        ev1 = {"source_weight": 0.4, "reviewer_agreement": 1.0, "recency_factor": 1.0}
        conf1 = cognitive_engine.aggregate_evidence_confidence([ev1])
        self.assertEqual(conf1, 0.4)
        
        # Duas evidências com conf = 0.4 cada
        # conf_agg = 1 - (1-0.4)*(1-0.4) = 1 - 0.36 = 0.64
        ev2 = {"source_weight": 0.4, "reviewer_agreement": 1.0, "recency_factor": 1.0}
        conf_agg = cognitive_engine.aggregate_evidence_confidence([ev1, ev2])
        self.assertAlmostEqual(conf_agg, 0.64, places=2)

    def test_learning_delta(self):
        # Teste da atualização de maestria
        # Se os pré-requisitos estão validados (prereq_factor = 1.0),
        # maestria atual = 0.0, conf_ev = 0.8, eta = 0.5
        delta = cognitive_engine.calculate_learning_delta(
            current_mastery=0.0,
            evidence_conf=0.8,
            prereq_factor=1.0,
            eta_eff=0.5
        )
        self.assertEqual(delta, 0.4) # 0.5 * (0.8 - 0.0) * 1.0 = 0.4
        
        # Se os pré-requisitos não estão totalmente validados (prereq_factor = 0.5)
        delta2 = cognitive_engine.calculate_learning_delta(
            current_mastery=0.0,
            evidence_conf=0.8,
            prereq_factor=0.5,
            eta_eff=0.5
        )
        self.assertEqual(delta2, 0.2) # 0.5 * (0.8 - 0.0) * 0.5 = 0.2

    def test_knowledge_frontier(self):
        # A, B, C.
        # Se nada está validadado, F(a,t) deve conter apenas 'A' (único nó com prereqs satisfeitos/sem prereqs)
        mastery = {"A": 0.0, "B": 0.0, "C": 0.0}
        frontier = cognitive_engine.get_knowledge_frontier(self.dag, mastery, ["A", "B", "C"])
        self.assertEqual(frontier, ["A"])
        
        # Se A está validado, B deve entrar na fronteira
        mastery2 = {"A": 0.85, "B": 0.0, "C": 0.0}
        frontier2 = cognitive_engine.get_knowledge_frontier(self.dag, mastery2, ["A", "B", "C"])
        self.assertEqual(frontier2, ["B"])

    def test_ula_trajectory_optimizer(self):
        # KUs
        kus_dict = {
            "A": {"element_interactivity": 2},
            "B": {"element_interactivity": 4},
            "C": {"element_interactivity": 6}
        }
        # Se o learner não sabe nada, e a missão exige 'C'
        # O ULA deve encontrar o caminho completo: A -> B -> C
        mastery = {}
        path = cognitive_engine.optimize_learning_trajectory(
            graph=self.dag,
            current_mastery=mastery,
            all_kus_dict=kus_dict,
            relations=self.relations,
            mission_required_kus=["C"],
            cost_weights={"alpha": 0.4, "beta": 0.3, "gamma": 0.3}
        )
        self.assertEqual(path, ["A", "B", "C"])
        
        # Se A já está validado, o caminho deve ser apenas: B -> C
        mastery2 = {"A": 0.85}
        path2 = cognitive_engine.optimize_learning_trajectory(
            graph=self.dag,
            current_mastery=mastery2,
            all_kus_dict=kus_dict,
            relations=self.relations,
            mission_required_kus=["C"],
            cost_weights={"alpha": 0.4, "beta": 0.3, "gamma": 0.3}
        )
        self.assertEqual(path2, ["B", "C"])

if __name__ == "__main__":
    unittest.main()
