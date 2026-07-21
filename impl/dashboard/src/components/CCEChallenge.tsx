import React, { useState, useEffect, useCallback } from "react";
import {
  ArrowRight,
  CheckCircle2,
  Loader2,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  XCircle,
  Zap,
} from "lucide-react";

const API_BASE = "http://localhost:8000/api";

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

interface Challenge {
  id: string;
  ku_id: string;
  prompt: string;
  answer_type: string;
  difficulty: number;
}

interface AttemptResult {
  correct: boolean;
  detail: string;
  feedback: string | null;
  evidence_status: string | null;
  new_mastery: number | null;
}

interface CCEChallengeProps {
  selectedNode: Node | null;
  learnerId: string;
  onSubmitEvidence: (evidence: {
    ku_id: string;
    type: string;
    source_weight: number;
    reviewer_agreement: number;
    recency_factor: number;
  }) => Promise<void>;
  onAfterAttempt: () => Promise<void>;
}

const LEVEL_LABEL: Record<string, string> = {
  foundational: "Fundamentos",
  intermediate: "Intermediário",
  advanced: "Avançado",
  expert: "Expert",
};

export const CCEChallenge: React.FC<CCEChallengeProps> = ({
  selectedNode,
  learnerId,
  onSubmitEvidence,
  onAfterAttempt,
}) => {
  // --- desafios do servidor ---
  const [challenges, setChallenges] = useState<Challenge[]>([]);
  const [challengeIdx, setChallengeIdx] = useState(0);
  const [loadingChallenges, setLoadingChallenges] = useState(false);
  const [attemptResult, setAttemptResult] = useState<AttemptResult | null>(null);

  // --- comum ---
  const [answer, setAnswer] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  // --- fallback: auto-estudo (peso fixado pelo servidor em 0.40) ---
  const [evidenceType, setEvidenceType] = useState("explanation");

  const fetchChallenges = useCallback(async () => {
    if (!selectedNode) return;
    setLoadingChallenges(true);
    setChallenges([]);
    setChallengeIdx(0);
    setAttemptResult(null);
    setAnswer("");
    try {
      const res = await fetch(`${API_BASE}/kus/${selectedNode.id}/challenges`);
      const data = await res.json();
      setChallenges(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error("Erro ao buscar desafios:", err);
    } finally {
      setLoadingChallenges(false);
    }
  }, [selectedNode?.id]);

  useEffect(() => {
    fetchChallenges();
  }, [fetchChallenges]);

  if (!selectedNode) return null;

  const mastery = selectedNode.effective_mastery ?? selectedNode.mastery ?? 0;
  const currentChallenge = challenges[challengeIdx] || null;
  const hasServerChallenges = challenges.length > 0;

  // ---------- Modo 1: desafio corrigido pelo servidor ----------
  const handleAttempt = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!answer.trim() || !currentChallenge) return;
    setIsSubmitting(true);
    try {
      const res = await fetch(`${API_BASE}/challenges/${currentChallenge.id}/attempt`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${localStorage.getItem("eos_token")}`,
        },
        body: JSON.stringify({ learner_id: learnerId, answer }),
      });
      const data: AttemptResult = await res.json();
      setAttemptResult(data);
      if (data.correct) {
        await onAfterAttempt();
      }
    } catch (err) {
      console.error("Erro ao submeter tentativa:", err);
    } finally {
      setIsSubmitting(false);
    }
  };

  const goToNextChallenge = () => {
    setAttemptResult(null);
    setAnswer("");
    setChallengeIdx((i) => (i + 1) % challenges.length);
  };

  const retryChallenge = () => {
    setAttemptResult(null);
    setAnswer("");
  };

  // ---------- Modo 2 (fallback): auto-estudo ----------
  // O peso é decidido pelo SERVIDOR (0.40, auto-estudo). Nada de peso
  // autodeclarado — P9: só verificação objetiva valida uma competência.
  const handleManualSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!answer.trim()) return;
    setIsSubmitting(true);
    try {
      await onSubmitEvidence({
        ku_id: selectedNode.id,
        type: evidenceType,
        source_weight: 0.4,
        reviewer_agreement: 1.0,
        recency_factor: 1.0,
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
          {hasServerChallenges && (
            <span className="flex items-center gap-1 text-[9px] uppercase tracking-wider font-bold text-emerald-300 bg-emerald-500/10 border border-emerald-500/25 rounded-full px-2.5 py-1">
              <ShieldCheck className="w-3 h-3" /> Correção automática
            </span>
          )}
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

      {loadingChallenges ? (
        <div className="flex justify-center py-8">
          <Loader2 className="w-5 h-5 text-fuchsia-400 animate-spin" />
        </div>
      ) : hasServerChallenges && currentChallenge ? (
        /* ================= MODO DESAFIO (server-graded) ================= */
        <form onSubmit={handleAttempt} className="flex flex-col gap-4">
          <div className="rounded-2xl border border-fuchsia-500/25 bg-gradient-to-br from-fuchsia-500/[0.07] to-violet-500/[0.04] p-4">
            <div className="flex items-center justify-between mb-2">
              <p className="text-[10px] uppercase tracking-[0.14em] text-fuchsia-300 font-bold flex items-center gap-1.5">
                <Sparkles className="w-3.5 h-3.5" /> Desafio {challengeIdx + 1} de {challenges.length}
              </p>
              <div className="flex gap-1">
                {challenges.map((_, i) => (
                  <span
                    key={i}
                    className={`w-1.5 h-1.5 rounded-full ${
                      i === challengeIdx ? "bg-fuchsia-400" : "bg-slate-600"
                    }`}
                  />
                ))}
              </div>
            </div>
            <p className="text-sm text-slate-100 font-medium leading-relaxed mb-3">
              {currentChallenge.prompt}
            </p>

            {attemptResult ? (
              /* Resultado da correção */
              <div
                className={`rounded-xl border p-3.5 ${
                  attemptResult.correct
                    ? "border-emerald-500/35 bg-emerald-500/10"
                    : "border-rose-500/35 bg-rose-500/10"
                }`}
              >
                <p
                  className={`text-sm font-bold flex items-center gap-1.5 ${
                    attemptResult.correct ? "text-emerald-300" : "text-rose-300"
                  }`}
                >
                  {attemptResult.correct ? (
                    <>
                      <CheckCircle2 className="w-4 h-4" /> Correto!
                    </>
                  ) : (
                    <>
                      <XCircle className="w-4 h-4" /> Ainda não…
                    </>
                  )}
                </p>
                {attemptResult.correct && attemptResult.feedback && (
                  <p className="text-xs text-slate-300 mt-1.5 leading-relaxed">
                    {attemptResult.feedback}
                  </p>
                )}
                {!attemptResult.correct && (
                  <p className="text-xs text-slate-400 mt-1.5">{attemptResult.detail}</p>
                )}
                {attemptResult.correct && attemptResult.new_mastery !== null && (
                  <p className="text-xs font-semibold text-emerald-200 mt-2">
                    Evidência registrada (benchmark 0.60) → maestria:{" "}
                    {Math.round(attemptResult.new_mastery * 100)}%
                  </p>
                )}
              </div>
            ) : (
              <input
                type="text"
                className="input-eos w-full text-sm p-3 placeholder-slate-600"
                placeholder={
                  currentChallenge.answer_type === "numeric"
                    ? "Digite o valor numérico da resposta…"
                    : "Digite sua resposta…"
                }
                value={answer}
                onChange={(e) => setAnswer(e.target.value)}
                disabled={isSubmitting}
                autoFocus
              />
            )}
          </div>

          {attemptResult ? (
            <div className="flex gap-2">
              {!attemptResult.correct && (
                <button
                  type="button"
                  onClick={retryChallenge}
                  className="btn-ghost flex-1 flex justify-center items-center gap-1.5 py-3 text-sm font-bold"
                >
                  <RefreshCw className="w-4 h-4" /> Tentar de novo
                </button>
              )}
              <button
                type="button"
                onClick={goToNextChallenge}
                className="btn-primary font-display flex-1 flex justify-center items-center gap-1.5 py-3 text-sm"
              >
                Próximo desafio <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          ) : (
            <button
              type="submit"
              disabled={isSubmitting || !answer.trim()}
              className="btn-primary font-display w-full flex justify-center items-center gap-2 py-3 text-sm"
            >
              {isSubmitting ? (
                <>
                  <div className="w-4 h-4 border-2 border-white/80 border-t-transparent rounded-full animate-spin" />
                  Corrigindo…
                </>
              ) : (
                <>
                  <CheckCircle2 className="w-4 h-4" /> Verificar resposta
                </>
              )}
            </button>
          )}

          <p className="flex items-start gap-1.5 text-[10px] text-slate-500 leading-relaxed">
            <ShieldCheck className="w-3.5 h-3.5 shrink-0 mt-px text-emerald-400/70" />
            Correção determinística no servidor. Cada acerto vira evidência de peso 0.60
            (benchmark reprodutível) — pela agregação noisy-OR, ≈3 desafios distintos corretos
            validam a competência (θ = 85%).
          </p>
        </form>
      ) : (
        /* ================= FALLBACK: evidência manual ================= */
        <form onSubmit={handleManualSubmit} className="flex flex-col gap-4">
          <div className="rounded-2xl border border-amber-500/25 bg-amber-500/[0.05] p-4">
            <p className="text-[10px] uppercase tracking-[0.14em] text-amber-400 font-bold mb-3 flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5" /> Auditoria de Competência
            </p>
            <div className="text-xs text-slate-300 mb-4 space-y-2 leading-relaxed">
              <p>
                Esta matéria não possui testes automáticos. Para provar sua competência em <strong>{selectedNode.title}</strong>, anexe uma evidência manual na caixa abaixo:
              </p>
              <ul className="list-disc pl-4 space-y-2 text-slate-400 mt-2">
                <li><strong>Código/Projeto:</strong> Cole um trecho de código ou link do GitHub aplicando o conceito de <em>{selectedNode.title}</em>.</li>
                <li><strong>Explicação Teórica:</strong> Explique como funciona <em>{selectedNode.title}</em> detalhadamente com as suas próprias palavras.</li>
                <li><strong>Caso Real:</strong> Descreva um problema que você resolveu no trabalho que envolvia <em>{selectedNode.title}</em>.</li>
              </ul>
            </div>
            <textarea
              className="input-eos w-full text-sm p-3 h-32 resize-none placeholder-slate-500"
              placeholder={`Ex: Para aplicar os conceitos de ${selectedNode.title}, eu fiz o seguinte...`}
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              disabled={isSubmitting}
            />
          </div>

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
              <option value="explanation">Explicação teórica</option>
              <option value="solution">Solução de exercício</option>
              <option value="artifact">Artefato de software</option>
              <option value="decision">Decisão de projeto</option>
            </select>
          </div>

          <button
            type="submit"
            disabled={isSubmitting || !answer.trim()}
            className="btn-primary font-display w-full flex justify-center items-center gap-2 py-3 text-sm"
          >
            {isSubmitting ? (
              <>
                <div className="w-4 h-4 border-2 border-white/80 border-t-transparent rounded-full animate-spin" />
                Processando…
              </>
            ) : (
              <>
                <CheckCircle2 className="w-4 h-4" /> Registrar auto-estudo
              </>
            )}
          </button>

          <p className="flex items-start gap-1.5 text-[10px] text-slate-500 leading-relaxed">
            <ShieldCheck className="w-3.5 h-3.5 shrink-0 mt-px text-amber-400/70" />
            Auto-estudo tem peso fixo 0.40 (definido pelo servidor) e leva a maestria até no
            máximo <strong className="text-slate-300">60%</strong>. A validação (85%) exige
            verificação objetiva — desafios corrigidos automaticamente ou, no futuro, revisão
            por professores (P9 — Validação Objetiva).
          </p>
        </form>
      )}
    </div>
  );
};
