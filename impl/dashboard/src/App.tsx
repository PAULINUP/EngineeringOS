import { useState, useEffect } from "react";
import { Award, Layers, Plus, Sparkles, Users } from "lucide-react";

import { GraphView } from "./components/GraphView";
import { ULAOptimizer } from "./components/ULAOptimizer";
import { CCEChallenge } from "./components/CCEChallenge";
import { CompetenceMatrix } from "./components/CompetenceMatrix";
import { MaterialViewer } from "./components/MaterialViewer";

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
  mastery_score: number;
  effective_mastery: number;
  confidence: number;
  decay_factor: number;
}

interface Edge {
  id: number;
  source: string;
  target: string;
  type: string;
  weight: number;
}

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

function App() {
  const [learners, setLearners] = useState<Learner[]>([]);
  const [selectedLearnerId, setSelectedLearnerId] = useState<string>("");
  const [missions, setMissions] = useState<Mission[]>([]);
  const [selectedMissionId, setSelectedMissionId] = useState<string>("");
  
  const [nodes, setNodes] = useState<Node[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);
  const [activePath, setActivePath] = useState<PathNode[]>([]);
  const [satisfied, setSatisfied] = useState<boolean>(false);
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);
  
  const [showAddLearner, setShowAddLearner] = useState(false);
  const [newLearnerName, setNewLearnerName] = useState("");
  const [notification, setNotification] = useState<{ type: string; msg: string } | null>(null);
  const [isOptimizing, setIsOptimizing] = useState(false);

  // Busca inicializadores e dados
  useEffect(() => {
    fetchInitialData();
  }, []);

  // Recarrega estados do estudante e caminhos quando o estudante ou a missão mudar
  useEffect(() => {
    if (selectedLearnerId) {
      fetchGraphAndPath();
    } else {
      setNodes([]);
      setEdges([]);
      setActivePath([]);
      setSelectedNode(null);
    }
  }, [selectedLearnerId, selectedMissionId]);

  const fetchInitialData = async () => {
    try {
      // 1. Busca Estudantes
      const lRes = await fetch(`${API_BASE}/learners`);
      const lData = await lRes.json();
      setLearners(lData);
      
      // Auto-seleciona primeiro se houver
      if (lData.length > 0) {
        setSelectedLearnerId(lData[0].id);
      } else {
        // Se vazio, cria um estudante default para onboarding
        const createRes = await fetch(`${API_BASE}/learners`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name: "Constitutional Learner" }),
        });
        const newL = await createRes.json();
        setLearners([newL]);
        setSelectedLearnerId(newL.id);
      }

      // 2. Busca Missões
      const mRes = await fetch(`${API_BASE}/missions`);
      const mData = await mRes.json();
      setMissions(mData);
      
      if (mData.length > 0) {
        setSelectedMissionId(mData[0].id);
      }
    } catch (err) {
      showToast("error", "Erro ao conectar na API. O servidor FastAPI está de pé?");
    }
  };

  const fetchGraphAndPath = async () => {
    if (!selectedLearnerId) return;
    try {
      // Busca grafo formatado
      const gRes = await fetch(`${API_BASE}/graph?learner_id=${selectedLearnerId}`);
      const gData = await gRes.json();
      setNodes(gData.nodes);
      setEdges(gData.edges);

      // Atualiza o nó selecionado para refletir nova maestria
      if (selectedNode) {
        const updated = gData.nodes.find((n: Node) => n.id === selectedNode.id);
        if (updated) setSelectedNode(updated);
      }

      // Busca caminho otimizado se a missão estiver selecionada
      if (selectedMissionId) {
        setIsOptimizing(true);
        const pRes = await fetch(
          `${API_BASE}/learners/${selectedLearnerId}/missions/${selectedMissionId}/path`
        );
        const pData = await pRes.json();
        
        if (pData.status === "processing" && pData.task_id) {
          // Iniciar polling
          pollTaskStatus(pData.task_id);
        } else if (pData.path) {
          // Fallback síncrono
          setActivePath(pData.path);
          setSatisfied(pData.satisfied);
          setIsOptimizing(false);
        }
      } else {
        setActivePath([]);
        setSatisfied(false);
        setIsOptimizing(false);
      }
    } catch (err) {
      console.error("Erro ao carregar dados do grafo:", err);
      setIsOptimizing(false);
    }
  };

  const pollTaskStatus = async (taskId: string) => {
    try {
      const res = await fetch(`${API_BASE}/tasks/${taskId}`);
      const data = await res.json();
      
      if (data.status === "SUCCESS") {
        setActivePath(data.result.path);
        setSatisfied(data.result.satisfied);
        setIsOptimizing(false);
      } else if (data.status === "FAILURE") {
        showToast("error", "Erro ao otimizar a trajetória.");
        setIsOptimizing(false);
      } else {
        // CONTINUA POLLING
        setTimeout(() => pollTaskStatus(taskId), 1500);
      }
    } catch (e) {
      console.error("Erro no polling:", e);
      setIsOptimizing(false);
    }
  };


  const handleCreateLearner = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newLearnerName.trim()) return;

    try {
      const res = await fetch(`${API_BASE}/learners`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: newLearnerName }),
      });
      const data = await res.json();
      setLearners((prev) => [...prev, data]);
      setSelectedLearnerId(data.id);
      setNewLearnerName("");
      setShowAddLearner(false);
      showToast("success", `Estudante "${data.name}" criado!`);
    } catch (err) {
      showToast("error", "Erro ao criar estudante");
    }
  };

  const handleSubmitEvidence = async (evidence: {
    ku_id: string;
    type: string;
    source_weight: number;
    reviewer_agreement: number;
    recency_factor: number;
  }) => {
    try {
      const res = await fetch(`${API_BASE}/evidence`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          learner_id: selectedLearnerId,
          ...evidence,
          reviewers: [{ reviewer_id: "human_reviewer_01", reviewer_type: "human", verdict: "accept" }],
        }),
      });
      const data = await res.json();

      if (data.status === "validated") {
        showToast("success", `Evidência validada! Maestria de ${data.ku_id} atualizada.`);
      } else {
        showToast("warning", `Evidência registrada como "${data.status}". Requer revisão.`);
      }
      
      // Recarrega dados
      await fetchGraphAndPath();
    } catch (err) {
      showToast("error", "Erro ao registrar evidência");
    }
  };



  const handleTriggerCurriculumSeed = async () => {
    try {
      const res = await fetch(`${API_BASE}/seed-curriculum`, { method: "POST" });
      const data = await res.json();
      showToast("success", data.message);
      
      // Recarrega tudo
      await fetchInitialData();
      if (selectedLearnerId) await fetchGraphAndPath();
    } catch (err) {
      showToast("error", "Erro ao executar seed do currículo customizado");
    }
  };

  const showToast = (type: string, msg: string) => {
    setNotification({ type, msg });
    setTimeout(() => setNotification(null), 4000);
  };

  const activePathIds = activePath.map((p) => p.id);

  return (
    <div className="min-h-screen flex flex-col justify-between">
      {/* HEADER */}
      <header className="border-b border-white/5 bg-black/40 backdrop-blur-md sticky top-0 z-50 px-6 py-4 flex justify-between items-center">
        <div className="flex items-center gap-3">
          <Layers className="w-8 h-8 text-violet-500" />
          <div>
            <h1 className="text-xl font-bold title-font text-white flex items-center gap-2">
              EngineeringOS <span className="text-[10px] px-2 py-0.5 bg-violet-950/80 border border-violet-800/40 rounded-full text-violet-300">Constitutional Reference</span>
            </h1>
            <p className="text-[10px] text-gray-400">Specification version 2.0.0 — Constitution Layer</p>
          </div>
        </div>

        {/* Estudante Atual */}
        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowAddLearner(true)}
            className="flex items-center gap-1 text-xs bg-white/5 border border-white/10 hover:bg-white/10 px-3 py-1.5 rounded-lg text-white font-medium transition"
          >
            <Plus className="w-3.5 h-3.5" /> Novo Estudante
          </button>
        </div>
      </header>

      {/* NOTIFICAÇÃO TOAST */}
      {notification && (
        <div className="fixed bottom-6 right-6 z-50 glass-panel p-4 max-w-sm flex items-start gap-3 border-l-4 animate-slide-in shadow-2xl transition-all duration-300 border-l-violet-500">
          <Sparkles className="w-5 h-5 text-violet-400 shrink-0 mt-0.5" />
          <p className="text-xs text-gray-200">{notification.msg}</p>
        </div>
      )}

      {/* MODAL ADICIONAR ESTUDANTE */}
      {showAddLearner && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex justify-center items-center p-4">
          <div className="glass-panel p-6 max-w-sm w-full">
            <h3 className="text-lg font-bold title-font text-white mb-4 flex items-center gap-2">
              <Users className="w-5 h-5 text-violet-400" /> Cadastrar Estudante
            </h3>
            <form onSubmit={handleCreateLearner} className="space-y-4">
              <div>
                <label className="block text-xs text-gray-400 font-semibold mb-1">Nome Completo</label>
                <input
                  type="text"
                  className="w-full bg-gray-900 border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-violet-500"
                  placeholder="Ex: Alan Turing"
                  value={newLearnerName}
                  onChange={(e) => setNewLearnerName(e.target.value)}
                  autoFocus
                />
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowAddLearner(false)}
                  className="text-xs bg-transparent hover:bg-white/5 text-gray-400 font-medium px-4 py-2 rounded-lg transition"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  className="text-xs bg-violet-600 hover:bg-violet-500 text-white font-bold px-4 py-2 rounded-lg transition"
                >
                  Salvar
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MAIN CONTAINER */}
      <main className="flex-1 p-6 max-w-7xl w-full mx-auto grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Lado Esquerdo: ULA Pathfinder & CCE Desafio */}
        <div className="lg:col-span-1 flex flex-col gap-6">
          <ULAOptimizer
            learners={learners}
            selectedLearnerId={selectedLearnerId}
            onSelectLearner={setSelectedLearnerId}
            missions={missions}
            selectedMissionId={selectedMissionId}
            onSelectMission={setSelectedMissionId}
            path={activePath}
            satisfied={satisfied}
            isOptimizing={isOptimizing}
            onTriggerSeed={handleTriggerCurriculumSeed}
          />

          <CCEChallenge
            selectedNode={selectedNode}
            onSubmitEvidence={handleSubmitEvidence}
          />

          <MaterialViewer selectedNodeId={selectedNode ? selectedNode.id : null} />
        </div>

        {/* Lado Direito: Grafo SVG e Matrix de Competências */}
        <div className="lg:col-span-2 flex flex-col gap-6">
          <div className="flex flex-col gap-2">
            <div className="flex justify-between items-center px-2">
              <h2 className="text-sm font-bold uppercase tracking-wider text-gray-400 flex items-center gap-1.5">
                <Layers className="w-4 h-4 text-violet-400" /> KNOWLEDGE SPACE (Espaço do Conhecimento K)
              </h2>
              {satisfied && (
                <span className="text-[10px] font-bold text-emerald-400 bg-emerald-950/60 border border-emerald-500/20 px-2 py-0.5 rounded-full flex items-center gap-1">
                  <Award className="w-3.5 h-3.5" /> Missão Satisfeita!
                </span>
              )}
            </div>
            <GraphView
              nodes={nodes}
              edges={edges}
              activePathIds={activePathIds}
              selectedNodeId={selectedNode ? selectedNode.id : null}
              onSelectNode={setSelectedNode}
            />
          </div>

          <CompetenceMatrix
            nodes={nodes}
            onSelectNode={setSelectedNode}
            selectedNodeId={selectedNode ? selectedNode.id : null}
          />
        </div>
      </main>
    </div>
  );
}

export default App;
