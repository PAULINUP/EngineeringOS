import React, { useMemo, useState } from "react";
import { CheckCircle2, CircleDashed, GraduationCap, Sparkles } from "lucide-react";

interface Node {
  id: string;
  title: string;
  domain: string;
  concept: string;
  level: string;
  definition: string;
  element_interactivity: number;
  mastery_score: number;
  effective_mastery: number;
  confidence: number;
  decay_factor: number;
  mastery: number;
}

interface CompetenceMatrixProps {
  nodes: Node[];
  onSelectNode: (node: Node) => void;
  selectedNodeId: string | null;
}

type Filter = "all" | "validated" | "progress" | "todo";

const MASTERY_THRESHOLD = 0.85;

export const CompetenceMatrix: React.FC<CompetenceMatrixProps> = ({
  nodes,
  onSelectNode,
  selectedNodeId,
}) => {
  const [filter, setFilter] = useState<Filter>("all");
  const [visibleCount, setVisibleCount] = useState(30);

  const masteryOf = (n: Node) => n.effective_mastery || n.mastery;

  const counts = useMemo(() => {
    const validated = nodes.filter((n) => masteryOf(n) >= MASTERY_THRESHOLD).length;
    const progress = nodes.filter((n) => {
      const m = masteryOf(n);
      return m > 0 && m < MASTERY_THRESHOLD;
    }).length;
    return { all: nodes.length, validated, progress, todo: nodes.length - validated - progress };
  }, [nodes]);

  const filtered = useMemo(() => {
    switch (filter) {
      case "validated":
        return nodes.filter((n) => masteryOf(n) >= MASTERY_THRESHOLD);
      case "progress":
        return nodes.filter((n) => {
          const m = masteryOf(n);
          return m > 0 && m < MASTERY_THRESHOLD;
        });
      case "todo":
        return nodes.filter((n) => masteryOf(n) === 0);
      default:
        return nodes;
    }
  }, [nodes, filter]);

  const FILTERS: { key: Filter; label: string; count: number }[] = [
    { key: "all", label: "Todas", count: counts.all },
    { key: "validated", label: "Validadas", count: counts.validated },
    { key: "progress", label: "Em progresso", count: counts.progress },
    { key: "todo", label: "A iniciar", count: counts.todo },
  ];

  return (
    <div className="panel flex flex-col">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 px-6 pt-5 pb-4 border-b border-slate-400/10">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-emerald-500/15 border border-emerald-500/25 flex items-center justify-center">
            <GraduationCap className="w-4 h-4 text-emerald-300" />
          </div>
          <div>
            <h2 className="font-display text-sm font-bold text-white">Matriz de Competências</h2>
            <p className="text-[10px] text-slate-500">Estado de maestria por unidade de conhecimento</p>
          </div>
        </div>

        {/* Filtros */}
        <div className="flex gap-1.5 flex-wrap">
          {FILTERS.map((f) => (
            <button
              key={f.key}
              onClick={() => {
                setFilter(f.key);
                setVisibleCount(30);
              }}
              className={`text-[11px] font-bold px-3 py-1.5 rounded-lg border transition ${
                filter === f.key
                  ? "bg-violet-500/20 border-violet-500/40 text-white"
                  : "bg-transparent border-slate-500/20 text-slate-400 hover:text-white hover:border-slate-400/40"
              }`}
            >
              {f.label} <span className="opacity-60">· {f.count}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Grid de cards */}
      <div className="p-5">
        {filtered.length === 0 ? (
          <div className="text-slate-500 text-xs text-center py-10">
            Nenhuma unidade neste filtro.
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3">
            {filtered.slice(0, visibleCount).map((node) => {
              const m = masteryOf(node);
              const isValidated = m >= MASTERY_THRESHOLD;
              const isProgress = m > 0 && !isValidated;
              const isSelected = selectedNodeId === node.id;

              return (
                <button
                  key={node.id}
                  onClick={() => onSelectNode(node)}
                  className={`card text-left p-4 relative overflow-hidden ${
                    isSelected
                      ? "border-amber-400/60"
                      : isValidated
                      ? "border-emerald-500/20"
                      : isProgress
                      ? "border-violet-500/20"
                      : ""
                  }`}
                >
                  {/* brilho de fundo para validadas */}
                  {isValidated && (
                    <div className="absolute -top-8 -right-8 w-24 h-24 rounded-full bg-emerald-500/10 blur-2xl pointer-events-none" />
                  )}

                  <div className="flex items-start justify-between gap-2 mb-1.5">
                    <h4 className="text-[13px] font-bold text-white leading-snug">{node.title}</h4>
                    {isValidated ? (
                      <span className="shrink-0 flex items-center gap-1 text-[9px] font-bold uppercase text-emerald-300 bg-emerald-500/15 border border-emerald-500/30 px-2 py-0.5 rounded-full">
                        <CheckCircle2 className="w-2.5 h-2.5" /> Validada
                      </span>
                    ) : isProgress ? (
                      <span className="shrink-0 flex items-center gap-1 text-[9px] font-bold uppercase text-violet-300 bg-violet-500/15 border border-violet-500/30 px-2 py-0.5 rounded-full">
                        <Sparkles className="w-2.5 h-2.5" /> Em curso
                      </span>
                    ) : (
                      <span className="shrink-0 flex items-center gap-1 text-[9px] font-bold uppercase text-slate-500 bg-slate-500/10 border border-slate-500/25 px-2 py-0.5 rounded-full">
                        <CircleDashed className="w-2.5 h-2.5" /> A iniciar
                      </span>
                    )}
                  </div>

                  <p className="text-[11px] text-slate-400 line-clamp-2 mb-3.5 leading-relaxed">
                    {node.definition}
                  </p>

                  <div className="flex justify-between items-center text-[9.5px] font-semibold text-slate-500 mb-1.5">
                    <span className="capitalize">{node.level}</span>
                    <span>
                      <span className={isValidated ? "text-emerald-300" : "text-slate-300"}>
                        {Math.round(m * 100)}%
                      </span>{" "}
                      · conf. {Math.round((node.confidence || 0) * 100)}%
                    </span>
                  </div>
                  <div className="w-full h-1.5 rounded-full bg-slate-400/10 overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all duration-700 ${
                        isValidated
                          ? "bg-gradient-to-r from-emerald-500 to-teal-400"
                          : isProgress
                          ? "bg-gradient-to-r from-violet-500 to-fuchsia-500"
                          : "bg-slate-700"
                      }`}
                      style={{ width: `${Math.max(m * 100, isProgress || isValidated ? 4 : 0)}%` }}
                    />
                  </div>
                </button>
              );
            })}
          </div>
        )}
        {filtered.length > visibleCount && (
          <div className="flex justify-center mt-4">
            <button
              onClick={() => setVisibleCount((c) => c + 60)}
              className="btn-ghost text-xs font-bold px-5 py-2.5"
            >
              Mostrar mais ({filtered.length - visibleCount} restantes)
            </button>
          </div>
        )}
      </div>
    </div>
  );
};
