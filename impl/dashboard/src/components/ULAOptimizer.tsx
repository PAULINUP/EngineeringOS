import React from "react";
import { ArrowRight, Cpu, PartyPopper, Route, Zap } from "lucide-react";

interface PathNode {
  id: string;
  title: string;
  level: string;
  element_interactivity: number;
  definition: string;
}

interface TrilhaPanelProps {
  path: PathNode[];
  satisfied: boolean;
  isOptimizing: boolean;
  hasMission: boolean;
  onStudy: (kuId: string) => void;
}

const LEVEL_STYLE: Record<string, string> = {
  foundational: "text-cyan-300 bg-cyan-500/10 border-cyan-500/25",
  intermediate: "text-violet-300 bg-violet-500/10 border-violet-500/25",
  advanced: "text-fuchsia-300 bg-fuchsia-500/10 border-fuchsia-500/25",
  expert: "text-amber-300 bg-amber-500/10 border-amber-500/25",
};

const LEVEL_LABEL: Record<string, string> = {
  foundational: "Fundamentos",
  intermediate: "Intermediário",
  advanced: "Avançado",
  expert: "Expert",
};

export const TrilhaPanel: React.FC<TrilhaPanelProps> = ({
  path,
  satisfied,
  isOptimizing,
  hasMission,
  onStudy,
}) => {
  return (
    <div className="panel flex flex-col h-full min-h-[560px]">
      {/* Header */}
      <div className="flex items-center gap-2.5 px-6 pt-5 pb-4 border-b border-slate-400/10">
        <div className="w-8 h-8 rounded-lg bg-fuchsia-500/15 border border-fuchsia-500/25 flex items-center justify-center">
          <Route className="w-4 h-4 text-fuchsia-300" />
        </div>
        <div>
          <h2 className="font-display text-sm font-bold text-white">Minha Trilha</h2>
          <p className="text-[10px] text-slate-500">Trajetória ótima π* · agendador ULA</p>
        </div>
      </div>

      <div className="flex-1 px-6 py-5 overflow-y-auto">
        {!hasMission ? (
          <div className="h-full flex flex-col items-center justify-center text-center gap-3 py-10">
            <Route className="w-10 h-10 text-slate-600" />
            <p className="text-sm font-semibold text-slate-300">Nenhuma missão ativa</p>
            <p className="text-xs text-slate-500 max-w-[240px]">
              Escolha uma missão na barra lateral para o motor calcular sua rota ideal.
            </p>
          </div>
        ) : isOptimizing ? (
          <div className="h-full flex flex-col items-center justify-center text-center gap-4 py-10">
            <div className="relative w-14 h-14">
              <div className="absolute inset-0 border-[3px] border-violet-500/70 border-t-transparent rounded-full animate-spin" />
              <Cpu className="w-5 h-5 text-violet-300 absolute inset-0 m-auto" />
            </div>
            <div>
              <p className="text-sm font-bold shimmer-text">Otimizando trajetória…</p>
              <p className="text-[11px] text-slate-500 mt-1.5 max-w-[250px]">
                O motor cognitivo minimiza custo de carga e maximiza transferência semântica no
                sub-grafo da fronteira.
              </p>
            </div>
          </div>
        ) : path.length === 0 || satisfied ? (
          <div className="h-full flex flex-col items-center justify-center text-center gap-4 py-10">
            <div className="w-16 h-16 rounded-2xl bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center">
              <PartyPopper className="w-7 h-7 text-emerald-300" />
            </div>
            <div>
              <p className="font-display text-base font-bold text-white">Missão concluída! 🎉</p>
              <p className="text-xs text-slate-400 mt-1.5 max-w-[250px]">
                Todas as unidades requeridas foram validadas por evidência. Selecione uma nova
                missão para expandir sua fronteira.
              </p>
            </div>
          </div>
        ) : (
          <ol className="relative flex flex-col">
            {/* Linha vertical conectora */}
            <div className="absolute left-[15px] top-4 bottom-6 w-px bg-gradient-to-b from-violet-500/60 via-fuchsia-500/30 to-transparent" />

            {path.map((step, idx) => {
              const isNext = idx === 0;
              return (
                <li key={step.id} className="relative pl-11 pb-4 last:pb-0">
                  {/* Marcador numerado */}
                  <div
                    className={`absolute left-0 top-1 w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold border-2 ${
                      isNext
                        ? "bg-gradient-to-br from-violet-600 to-fuchsia-600 border-fuchsia-400/50 text-white shadow-lg shadow-fuchsia-900/50"
                        : "bg-[#0d1226] border-slate-600/40 text-slate-400"
                    }`}
                  >
                    {idx + 1}
                  </div>

                  <button
                    onClick={() => onStudy(step.id)}
                    className={`card w-full text-left p-3.5 ${
                      isNext ? "border-fuchsia-500/30 bg-fuchsia-500/[0.06]" : ""
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <p className="text-[13px] font-bold text-white leading-snug">{step.title}</p>
                      {isNext && (
                        <span className="shrink-0 text-[9px] font-bold uppercase tracking-wider text-fuchsia-300 bg-fuchsia-500/15 border border-fuchsia-500/30 rounded-full px-2 py-0.5">
                          Próximo
                        </span>
                      )}
                    </div>
                    <p className="text-[11px] text-slate-400 mt-1 line-clamp-2">{step.definition}</p>
                    <div className="flex items-center gap-2 mt-2.5">
                      <span
                        className={`text-[9px] font-bold uppercase tracking-wide border rounded-md px-1.5 py-0.5 ${
                          LEVEL_STYLE[step.level] || LEVEL_STYLE.intermediate
                        }`}
                      >
                        {LEVEL_LABEL[step.level] || step.level}
                      </span>
                      <span className="flex items-center gap-1 text-[9px] font-semibold text-slate-500">
                        <Zap className="w-3 h-3 text-amber-400/80" />
                        Carga {step.element_interactivity}/10
                      </span>
                      {isNext && (
                        <span className="ml-auto flex items-center gap-1 text-[10px] font-bold text-fuchsia-300">
                          Estudar <ArrowRight className="w-3 h-3" />
                        </span>
                      )}
                    </div>
                  </button>
                </li>
              );
            })}
          </ol>
        )}
      </div>

      {/* Rodapé constitucional */}
      <div className="px-6 py-3.5 border-t border-slate-400/10 flex items-start gap-2">
        <Cpu className="w-3.5 h-3.5 text-violet-400 shrink-0 mt-0.5" />
        <p className="text-[10px] text-slate-500 leading-relaxed">
          Rota limitada pela capacidade da memória de trabalho —{" "}
          <span className="text-slate-400 font-semibold">máx. 4 KUs inéditas por sessão</span>{" "}
          (Cowan, P4).
        </p>
      </div>
    </div>
  );
};
