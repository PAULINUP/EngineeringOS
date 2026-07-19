import React, { useState, useEffect } from "react";
import { CheckCircle2, ShieldCheck, Sparkles, Zap } from "lucide-react";

interface Node {
  id: string;
  title: string;
  domain: string;
  concept: string;
  level: string;
  definition: string;
  element_interactivity: number;
  mastery: number;
  effective_mastery?: number;
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

const LEVEL_LABEL: Record<string, string> = {
  foundational: "Fundamentos",
  intermediate: "Intermediário",
  advanced: "Avançado",
  expert: "Expert",
};

export const CCEChallenge: React.FC<CCEChallengeProps> = ({
  selectedNode,
  onSubmitEvidence,
}) => {
  const [evidenceType, setEvidenceType] = useState("solution");
  const [sourceType, setSourceType] = useState("expert");
  const [agreement, setAgreement] = useState(1.0);
  const [recency, setRecency] = useState(1.0);
  const [answer, setAnswer] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [challengeQuestion, setChallengeQuestion] = useState("");

  useEffect(() => {
    if (!selectedNode) return;

    const qMap: Record<string, string> = {
      "linear_algebra.matrix_definition.v1":
        "Dadas as dimensões A ∈ ℝ²³ e B ∈ ℝ³⁴, qual o número total de elementos na matriz A?",
      "linear_algebra.dot_product.v1":
        "Calcule o produto escalar dos vetores u = [2, -1, 3] e v = [1, 4, 2].",
      "linear_algebra.matrix_multiplication.v1":
        "Dadas A = [[1, 2], [3, 4]] e B = [[2, 0], [1, 2]], qual o valor do elemento C₁₁ do produto C = A·B?",
      "linear_algebra.eigenvalues.v1":
        "Para a matriz diagonal A = [[3, 0], [0, 5]], liste os seus autovalores.",
      "calculus.partial_derivatives.v1":
        "Calcule a derivada parcial em relação a x de f(x, y) = 3x²y + 5y³ no ponto (1, 2).",
      "ml.gradient_descent.v1":
        "Se a taxa de aprendizado η = 0.1 e o gradiente da função de custo no ponto atual é 4.0, qual a magnitude do passo de atualização?",
    };

    setChallengeQuestion(
      qMap[selectedNode.id] ||
        `Escreva uma explicação formal do conceito de "${selectedNode.title}".`
    );
    setAnswer("");
  }, [selectedNode]);

  if (!selectedNode) return null;

  const mastery = selectedNode.effective_mastery ?? selectedNode.mastery ?? 0;

  const handleFormSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!answer.trim()) return;

    setIsSubmitting(true);

    let sourceWeight = 0.4;
    if (sourceType === "standard") sourceWeight = 0.9;
    else if (sourceType === "expert") sourceWeight = 0.8;
    else if (sourceType === "benchmark") sourceWeight = 0.6;

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
    <div className="flex flex-col gap-5">
      {/* Cabeçalho da KU */}
      <div>
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-[9px] uppercase tracking-wider font-bold text-violet-300 bg-violet-500/15 border border-violet-500/30 rounded-full px-2.5 py-1">
            {LEVEL_LABEL[selectedNode.level] || selectedNode.level}
          </span>
          <span className="flex items-center gap-1 text-[9px] uppercase tracking-wider font-bold text-amber-300/90 bg-amber-500/10 border border-amber-500/25 rounded-full px-2.5 py-1">
            <Zap className="w-3 h-3" /> Carga {selectedNode.element_interactivity}/10
          </span>
        </div>
        <h3 className="font-display text-[22px] font-bold text-white mt-2.5 leading-tight">
          {selectedNode.title}
        </h3>

        {/* Barra de maestria */}
        <div className="mt-3">
          <div className="flex justify-between text-[10px] font-semibold text-slate-400 mb-1.5">
            <span>Maestria atual</span>
            <span className={mastery >= 0.85 ? "text-emerald-300" : "text-fuchsia-300"}>
              {Math.round(mastery * 100)}% {mastery >= 0.85 ? "· validada" : "· meta 85%"}
            </span>
          </div>
          <div className="w-full h-2 rounded-full bg-slate-400/10 overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-700 ${
                mastery >= 0.85
                  ? "bg-gradient-to-r from-emerald-500 to-teal-400"
                  : "bg-gradient-to-r from-violet-500 to-fuchsia-500"
              }`}
              style={{ width: `${Math.max(mastery * 100, 2)}%` }}
            />
          </div>
        </div>
      </div>

      {/* Definição formal */}
      <div className="card p-4 hover:transform-none">
        <p className="text-[10px] uppercase tracking-[0.14em] text-slate-500 font-bold mb-1.5">
          Definição formal
        </p>
        <p className="text-[12.5px] text-slate-300 leading-relaxed">{selectedNode.definition}</p>
      </div>

      {/* Desafio */}
      <form onSubmit={handleFormSubmit} className="flex flex-col gap-4">
        <div className="rounded-2xl border border-fuchsia-500/25 bg-gradient-to-br from-fuchsia-500/[0.07] to-violet-500/[0.04] p-4">
          <p className="text-[10px] uppercase tracking-[0.14em] text-fuchsia-300 font-bold mb-2 flex items-center gap-1.5">
            <Sparkles className="w-3.5 h-3.5" /> Desafio de competência
          </p>
          <p className="text-sm text-slate-100 font-medium leading-relaxed mb-3">
            {challengeQuestion}
          </p>
          <textarea
            className="input-eos w-full text-sm p-3 h-24 resize-none placeholder-slate-600"
            placeholder="Digite sua solução matemática ou justificativa analítica…"
            value={answer}
            onChange={(e) => setAnswer(e.target.value)}
            disabled={isSubmitting}
          />
        </div>

        {/* Metadados da evidência */}
        <div className="grid grid-cols-2 gap-3 text-xs">
          <div>
            <label className="block text-[10px] uppercase tracking-wider text-slate-500 font-bold mb-1.5">
              Tipo de evidência
            </label>
            <select
              className="input-eos w-full px-2.5 py-2 text-xs font-semibold cursor-pointer"
              value={evidenceType}
              onChange={(e) => setEvidenceType(e.target.value)}
              disabled={isSubmitting}
            >
              <option value="solution">Solução algébrica</option>
              <option value="explanation">Explicação teórica</option>
              <option value="artifact">Artefato de software</option>
              <option value="decision">Decisão de projeto</option>
              <option value="benchmark">Resultados de benchmark</option>
            </select>
          </div>

          <div>
            <label className="block text-[10px] uppercase tracking-wider text-slate-500 font-bold mb-1.5">
              Peso da fonte
            </label>
            <select
              className="input-eos w-full px-2.5 py-2 text-xs font-semibold cursor-pointer"
              value={sourceType}
              onChange={(e) => setSourceType(e.target.value)}
              disabled={isSubmitting}
            >
              <option value="standard">Padrão internacional · 0.90</option>
              <option value="expert">Consenso de especialistas · 0.80</option>
              <option value="benchmark">Benchmark reprodutível · 0.60</option>
              <option value="ai">Agente de IA · 0.40</option>
            </select>
          </div>

          <div>
            <label className="block text-[10px] uppercase tracking-wider text-slate-500 font-bold mb-2">
              Acordo dos revisores · {Math.round(agreement * 100)}%
            </label>
            <input
              type="range"
              min="0.5"
              max="1.0"
              step="0.05"
              className="w-full"
              value={agreement}
              onChange={(e) => setAgreement(parseFloat(e.target.value))}
              disabled={isSubmitting}
            />
          </div>

          <div>
            <label className="block text-[10px] uppercase tracking-wider text-slate-500 font-bold mb-2">
              Recência · {Math.round(recency * 100)}%
            </label>
            <input
              type="range"
              min="0.5"
              max="1.0"
              step="0.05"
              className="w-full"
              value={recency}
              onChange={(e) => setRecency(parseFloat(e.target.value))}
              disabled={isSubmitting}
            />
          </div>
        </div>

        <button
          type="submit"
          disabled={isSubmitting || !answer.trim()}
          className="btn-primary font-display w-full flex justify-center items-center gap-2 py-3 text-sm"
        >
          {isSubmitting ? (
            <>
              <div className="w-4 h-4 border-2 border-white/80 border-t-transparent rounded-full animate-spin" />
              Processando no motor…
            </>
          ) : (
            <>
              <CheckCircle2 className="w-4 h-4" /> Submeter evidência
            </>
          )}
        </button>

        <p className="flex items-start gap-1.5 text-[10px] text-slate-500 leading-relaxed">
          <ShieldCheck className="w-3.5 h-3.5 shrink-0 mt-px text-emerald-400/70" />
          Sua evidência passa pela agregação noisy-OR (Def. 2) e atualiza a maestria via delta de
          aprendizado (Def. 3) — nada de nota por múltipla escolha.
        </p>
      </form>
    </div>
  );
};
