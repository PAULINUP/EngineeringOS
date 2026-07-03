import React, { useState, useEffect } from "react";
import { Award, CheckCircle2, Sparkles } from "lucide-react";

interface Node {
  id: string;
  title: string;
  domain: string;
  concept: string;
  level: string;
  definition: string;
  element_interactivity: number;
  mastery: number;
}

interface CCEChallengeProps {
  selectedNode: Node | null;
  onSubmitEvidence: (evidence: {
    ku_id: string;
    type: string;
    source_weight: number;
    reviewer_agreement: number;
    recency_factor: number;
  }) => Promise<void>;
}

export const CCEChallenge: React.FC<CCEChallengeProps> = ({
  selectedNode,
  onSubmitEvidence,
}) => {
  const [evidenceType, setEvidenceType] = useState("solution");
  const [sourceType, setSourceType] = useState("expert"); // expert, standard, benchmark, ai
  const [agreement, setAgreement] = useState(1.0);
  const [recency, setRecency] = useState(1.0);
  const [answer, setAnswer] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [challengeQuestion, setChallengeQuestion] = useState("");

  // Gera uma questão de desafio baseada na KU selecionada
  useEffect(() => {
    if (!selectedNode) return;

    const qMap: Record<string, string> = {
      "linear_algebra.matrix_definition.v1": "Dadas as dimensões A ∈ ℝ²³ e B ∈ ℝ³⁴, qual o número total de elementos na matriz A?",
      "linear_algebra.dot_product.v1": "Calcule o produto escalar dos vetores u = [2, -1, 3] e v = [1, 4, 2].",
      "linear_algebra.matrix_multiplication.v1": "Dadas A = [[1, 2], [3, 4]] e B = [[2, 0], [1, 2]], qual o valor do elemento C₁₁ do produto C = A·B?",
      "linear_algebra.eigenvalues.v1": "Para a matriz diagonal A = [[3, 0], [0, 5]], liste os seus autovalores.",
      "calculus.partial_derivatives.v1": "Calcule a derivada parcial em relação a x de f(x, y) = 3x²y + 5y³ no ponto (1, 2).",
      "ml.gradient_descent.v1": "Se a taxa de aprendizado η = 0.1 e o gradiente da função de custo no ponto atual é 4.0, qual a magnitude do passo de atualização?",
    };

    setChallengeQuestion(
      qMap[selectedNode.id] || `Escreva uma explicação formal do conceito de "${selectedNode.title}".`
    );
    setAnswer("");
  }, [selectedNode]);

  if (!selectedNode) {
    return (
      <div className="glass-panel p-6 h-full flex flex-col justify-center items-center text-center min-h-[300px]">
        <Award className="w-12 h-12 text-gray-500 mb-4 animate-bounce" />
        <h3 className="text-lg font-semibold title-font mb-2">Desafio Cognitivo</h3>
        <p className="text-sm text-gray-400 max-w-[280px]">
          Selecione qualquer nó no grafo para visualizar o conceito e submeter evidências de competência.
        </p>
      </div>
    );
  }

  const handleFormSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!answer.trim()) return;

    setIsSubmitting(true);

    // Mapeia tipo de fonte para peso da especificação (Definition 10.2)
    let sourceWeight = 0.40; // Default AI
    if (sourceType === "standard") sourceWeight = 0.90;
    else if (sourceType === "expert") sourceWeight = 0.80;
    else if (sourceType === "benchmark") sourceWeight = 0.60;

    try {
      await onSubmitEvidence({
        ku_id: selectedNode.id,
        type: evidenceType,
        source_weight: sourceWeight,
        reviewer_agreement: agreement,
        recency_factor: recency,
      });
      setAnswer("");
    } catch (err) {
      console.error("Erro ao enviar evidência:", err);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="glass-panel p-6 h-full flex flex-col justify-between min-h-[480px]">
      <div>
        <div className="flex justify-between items-start mb-4">
          <div>
            <span className="text-[10px] uppercase tracking-wider text-violet-400 px-2 py-0.5 bg-violet-950/50 border border-violet-800/30 rounded-full font-semibold">
              CCE — Challenge Engine
            </span>
            <h3 className="text-xl font-bold title-font mt-1 text-white">{selectedNode.title}</h3>
          </div>
          <span className="text-xs font-semibold px-2 py-1 bg-gray-800 border border-gray-700 rounded-md capitalize text-gray-300">
            Dificuldade: {selectedNode.level}
          </span>
        </div>

        <div className="bg-gray-950/40 border border-white/5 rounded-lg p-3 text-xs text-gray-300 mb-4 italic">
          <strong>Definição Formal:</strong> {selectedNode.definition}
        </div>

        <form onSubmit={handleFormSubmit} className="space-y-4">
          <div className="border border-white/5 rounded-lg p-4 bg-gray-950/30">
            <h4 className="text-xs font-bold uppercase text-gray-400 mb-2 flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5 text-amber-500" /> Desafio de Competência
            </h4>
            <p className="text-sm text-gray-200 mb-3">{challengeQuestion}</p>
            <textarea
              className="w-full text-sm bg-gray-950/70 border border-white/10 rounded-md p-2.5 focus:border-violet-500 focus:outline-none placeholder-gray-600 h-20 resize-none"
              placeholder="Digite sua solução matemática ou justificativa analítica..."
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              disabled={isSubmitting}
            />
          </div>

          <div className="grid grid-cols-2 gap-3 text-xs">
            <div>
              <label className="block text-gray-400 font-semibold mb-1">Tipo de Evidência</label>
              <select
                className="w-full bg-gray-900 border border-white/10 rounded px-2.5 py-1.5 focus:outline-none focus:border-violet-500"
                value={evidenceType}
                onChange={(e) => setEvidenceType(e.target.value)}
                disabled={isSubmitting}
              >
                <option value="solution">Solução Algébrica</option>
                <option value="explanation">Explicação Teórica</option>
                <option value="artifact">Artefato de Software</option>
                <option value="decision">Decisão de Projeto</option>
                <option value="benchmark">Resultados de Benchmark</option>
              </select>
            </div>

            <div>
              <label className="block text-gray-400 font-semibold mb-1">Peso da Fonte (Grounding)</label>
              <select
                className="w-full bg-gray-900 border border-white/10 rounded px-2.5 py-1.5 focus:outline-none focus:border-violet-500"
                value={sourceType}
                onChange={(e) => setSourceType(e.target.value)}
                disabled={isSubmitting}
              >
                <option value="standard">Padrão Internacional (W3C/ISO) [0.90]</option>
                <option value="expert">Consenso de Especialistas [0.80]</option>
                <option value="benchmark">Benchmark Reprodutível [0.60]</option>
                <option value="ai">Resultado de Agente de IA [0.40]</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3 text-xs">
            <div>
              <label className="block text-gray-400 font-semibold mb-1">
                Acordo dos Revisores: {Math.round(agreement * 100)}%
              </label>
              <input
                type="range"
                min="0.5"
                max="1.0"
                step="0.05"
                className="w-full accent-violet-500 cursor-pointer"
                value={agreement}
                onChange={(e) => setAgreement(parseFloat(e.target.value))}
                disabled={isSubmitting}
              />
            </div>

            <div>
              <label className="block text-gray-400 font-semibold mb-1">
                Recência: {Math.round(recency * 100)}%
              </label>
              <input
                type="range"
                min="0.5"
                max="1.0"
                step="0.05"
                className="w-full accent-violet-500 cursor-pointer"
                value={recency}
                onChange={(e) => setRecency(parseFloat(e.target.value))}
                disabled={isSubmitting}
              />
            </div>
          </div>
        </form>
      </div>

      <div className="mt-6 pt-4 border-t border-white/5 flex gap-3">
        <button
          onClick={handleFormSubmit}
          disabled={isSubmitting || !answer.trim()}
          className="flex-1 flex justify-center items-center gap-1.5 bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white font-bold py-2.5 px-4 rounded-lg transition-all text-sm disabled:opacity-40 disabled:cursor-not-allowed glow-violet"
        >
          {isSubmitting ? (
            "Processando no Motor..."
          ) : (
            <>
              <CheckCircle2 className="w-4 h-4" /> Submeter Evidência
            </>
          )}
        </button>
      </div>
    </div>
  );
};
