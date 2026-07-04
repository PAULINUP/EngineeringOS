import React from "react";
import { Check, BookOpen, AlertCircle } from "lucide-react";

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

export const CompetenceMatrix: React.FC<CompetenceMatrixProps> = ({
  nodes,
  onSelectNode,
  selectedNodeId,
}) => {
  return (
    <div className="glass-panel p-6 h-full flex flex-col min-h-[300px]">
      <div className="flex items-center gap-2 mb-4">
        <BookOpen className="w-5 h-5 text-emerald-500" />
        <h3 className="text-lg font-bold title-font text-white">Matriz de Competências</h3>
      </div>

      {nodes.length === 0 ? (
        <div className="text-gray-400 text-sm text-center my-auto">
          Nenhuma unidade de conhecimento cadastrada no sistema.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 overflow-y-auto max-h-[320px] pr-1">
          {nodes.map((node) => {
            const masteryVal = node.effective_mastery || node.mastery;
            const isValidated = masteryVal >= 0.85;
            const isPending = masteryVal > 0 && masteryVal < 0.85;
            const isSelected = selectedNodeId === node.id;

            // Cores do card
            let cardBorder = "border-white/5";
            let statusBadge = null;

            if (isValidated) {
              cardBorder = "border-emerald-500/20 bg-emerald-950/5";
              statusBadge = (
                <span className="flex items-center gap-0.5 text-[9px] font-bold text-emerald-400 bg-emerald-950/60 border border-emerald-500/20 px-1.5 py-0.5 rounded">
                  <Check className="w-2.5 h-2.5" /> Validado
                </span>
              );
            } else if (isPending) {
              cardBorder = "border-violet-500/20 bg-violet-950/5";
              statusBadge = (
                <span className="flex items-center gap-0.5 text-[9px] font-bold text-violet-400 bg-violet-950/60 border border-violet-500/20 px-1.5 py-0.5 rounded">
                  <AlertCircle className="w-2.5 h-2.5" /> Pendente
                </span>
              );
            }

            if (isSelected) {
              cardBorder = "border-amber-500";
            }

            return (
              <div
                key={node.id}
                onClick={() => onSelectNode(node)}
                className={`glass-card p-3 flex flex-col justify-between border cursor-pointer ${cardBorder}`}
              >
                <div>
                  <div className="flex justify-between items-start gap-2 mb-1.5">
                    <h4 className="text-xs font-bold text-white truncate max-w-[140px]">
                      {node.title}
                    </h4>
                    {statusBadge}
                  </div>
                  <p className="text-[10px] text-gray-400 line-clamp-2 mb-3">
                    {node.definition}
                  </p>
                </div>

                <div>
                  <div className="flex justify-between items-center text-[9px] text-gray-400 mb-1">
                    <span>Nível: {node.level}</span>
                    <span>Maestria: {Math.round(masteryVal * 100)}% | Confiança: {Math.round((node.confidence || 0) * 100)}%</span>
                  </div>
                  <div className="w-full bg-gray-950/80 border border-white/5 rounded-full h-1.5 overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all duration-500 ${
                        isValidated ? "bg-emerald-500" : isPending ? "bg-violet-500" : "bg-gray-800"
                      }`}
                      style={{ width: `${masteryVal * 100}%` }}
                    />
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
