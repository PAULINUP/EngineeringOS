import React from "react";
import { Compass, Cpu, Layers } from "lucide-react";

interface PathNode {
  id: string;
  title: string;
  level: string;
  element_interactivity: number;
  definition: string;
}

interface Mission {
  id: string;
  label: string;
}

interface Learner {
  id: string;
  name: string;
}

interface ULAOptimizerProps {
  learners: Learner[];
  selectedLearnerId: string;
  onSelectLearner: (id: string) => void;
  missions: Mission[];
  selectedMissionId: string;
  onSelectMission: (id: string) => void;
  path: PathNode[];
  satisfied: boolean;
  onTriggerSeed: () => void;
}

export const ULAOptimizer: React.FC<ULAOptimizerProps> = ({
  learners,
  selectedLearnerId,
  onSelectLearner,
  missions,
  selectedMissionId,
  onSelectMission,
  path,
  satisfied,
  onTriggerSeed,
}) => {
  return (
    <div className="glass-panel p-6 h-full flex flex-col justify-between min-h-[480px]">
      <div>
        <div className="flex justify-between items-center mb-5">
          <div className="flex items-center gap-2">
            <Compass className="w-5 h-5 text-violet-500" />
            <h3 className="text-lg font-bold title-font text-white">ULA — Trajectory Optimizer</h3>
          </div>
          <button
            onClick={onTriggerSeed}
            className="text-[10px] bg-white/5 hover:bg-white/10 border border-white/10 hover:border-white/20 text-gray-300 font-bold px-2 py-1 rounded transition"
          >
            Reset/Seed Database
          </button>
        </div>

        {/* Configurações de Entrada */}
        <div className="space-y-3 mb-5">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-[10px] uppercase tracking-wider text-gray-400 font-bold mb-1">Estudante (Learner)</label>
              <select
                className="w-full text-sm bg-gray-900 border border-white/10 rounded px-2.5 py-1.5 focus:outline-none focus:border-violet-500"
                value={selectedLearnerId}
                onChange={(e) => onSelectLearner(e.target.value)}
              >
                <option value="">Selecione um Estudante</option>
                {learners.map((l) => (
                  <option key={l.id} value={l.id}>
                    {l.name}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-[10px] uppercase tracking-wider text-gray-400 font-bold mb-1 flex justify-between items-center">
                <span>Missão de Aprendizado</span>
                {satisfied && <span className="text-[9px] text-emerald-400 font-bold">✓ Satisfeita</span>}
              </label>
              <select
                className="w-full text-sm bg-gray-900 border border-white/10 rounded px-2.5 py-1.5 focus:outline-none focus:border-violet-500"
                value={selectedMissionId}
                onChange={(e) => onSelectMission(e.target.value)}
                disabled={!selectedLearnerId}
              >
                <option value="">Selecione uma Missão</option>
                {missions.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* Informações da Trajetória Otimizada */}
        {selectedMissionId && (
          <div className="mt-4">
            <h4 className="text-xs font-bold uppercase text-gray-400 mb-3 flex items-center gap-1.5">
              <Layers className="w-3.5 h-3.5 text-violet-400" /> Trajetória de Aprendizado pi*
            </h4>

            {path.length === 0 ? (
              <div className="bg-emerald-950/20 border border-emerald-800/20 rounded-xl p-5 text-center">
                <p className="text-sm text-emerald-400 font-semibold mb-1">🎉 Missão Concluída!</p>
                <p className="text-xs text-gray-400">
                  Todas as unidades de conhecimento requeridas para esta missão foram validadas com sucesso.
                </p>
              </div>
            ) : (
              <div className="space-y-2 max-h-[220px] overflow-y-auto pr-1">
                {path.map((step, idx) => (
                  <div
                    key={step.id}
                    className="flex items-center gap-3 bg-white/2 border border-white/5 rounded-lg p-2.5 text-left hover:bg-white/5 transition"
                  >
                    <div className="w-6 h-6 flex justify-center items-center bg-violet-950/50 border border-violet-800/40 text-violet-300 font-bold text-xs rounded-full">
                      {idx + 1}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-bold text-white truncate">{step.title}</p>
                      <p className="text-[10px] text-gray-400 truncate">{step.definition}</p>
                    </div>
                    <span className="text-[9px] bg-gray-800 border border-gray-700 px-2 py-0.5 rounded text-gray-300">
                      Interatividade: {step.element_interactivity}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      <div className="mt-6 pt-4 border-t border-white/5 bg-gray-950/20 rounded-lg p-3 border border-white/5 flex gap-2 items-start text-[10px] text-gray-400">
        <Cpu className="w-4 h-4 text-violet-400 shrink-0 mt-0.5" />
        <div>
          <strong>Parâmetros de Custo ULA:</strong> Otimização baseada em carga intrínseca e transferência semântica. 
          Caminho gerado sob a restrição da capacidade da memória de trabalho (Cowan WM Load &le; 4).
        </div>
      </div>
    </div>
  );
};
