import { useState, useEffect, useMemo } from "react";
import {
  Award,
  BrainCircuit,
  ChevronDown,
  Compass,
  Database,
  Flame,
  GraduationCap,
  Hexagon,
  Layers,
  LogOut,
  Route,
  Sparkles,
  Target,
  X,
} from "lucide-react";

import { GraphView } from "./components/GraphView";
import { TrilhaPanel } from "./components/ULAOptimizer";
import { CCEChallenge } from "./components/CCEChallenge";
import { CompetenceMatrix } from "./components/CompetenceMatrix";
import { MaterialViewer } from "./components/MaterialViewer";
import { Login, type Sessao } from "./components/Login";

import { API_BASE } from "./api";

const MASTERY_THRESHOLD = 0.85;

export interface KNode {
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

export interface KEdge {
  id: number;
  source: string;
  target: string;
  type: string;
  weight: number;
}

export interface PathNode {
  id: string;
  title: string;
  level: string;
  element_interactivity: number;
  definition: string;
}

interface Mission {
  id: string;
  label: string;
  required_kus?: string[];
}

export function prettyDomain(d: string): string {
  return d
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

interface Learner {
  id: string;
  name: string;
}

const RANKS: [number, string][] = [
  [0.0, "Iniciante"],
  [0.15, "Aprendiz"],
  [0.35, "Praticante"],
  [0.55, "Analista"],
  [0.75, "Engenheiro"],
  [0.9, "Arquiteto"],
  [1.0, "Mestre"],
];

function rankFor(progress: number): string {
  let rank = RANKS[0][1];
  for (const [min, label] of RANKS) {
    if (progress >= min) rank = label;
  }
  return rank;
}

function App() {
  // Sessão real: o aluno é quem está autenticado, não uma escolha de lista.
  const [sessao, setSessao] = useState<Sessao | null>(() => {
    try {
      const bruto = localStorage.getItem("eos_sessao");
      return bruto ? (JSON.parse(bruto) as Sessao) : null;
    } catch {
      return null;
    }
  });
  const [learners, setLearners] = useState<Learner[]>([]);
  const [selectedLearnerId, setSelectedLearnerId] = useState<string>("");
  const [missions, setMissions] = useState<Mission[]>([]);
  const [selectedMissionId, setSelectedMissionId] = useState<string>("");

  const [nodes, setNodes] = useState<KNode[]>([]);
  const [edges, setEdges] = useState<KEdge[]>([]);
  const [activePath, setActivePath] = useState<PathNode[]>([]);
  const [satisfied, setSatisfied] = useState<boolean>(false);
  const [selectedNode, setSelectedNode] = useState<KNode | null>(null);

  const [selectedDomain, setSelectedDomain] = useState<string>("all");
  const [notification, setNotification] = useState<{ type: string; msg: string } | null>(null);
  const [isOptimizing, setIsOptimizing] = useState(false);

  useEffect(() => {
    if (sessao) fetchInitialData();
  }, [sessao?.learner_id]);

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
      if (!sessao) return;
      localStorage.setItem("eos_token", sessao.access_token);
      const authHeaders = { Authorization: `Bearer ${sessao.access_token}` };

      const lRes = await fetch(`${API_BASE}/learners`, { headers: authHeaders });
      const lData = await lRes.json();
      setLearners(lData);

      setSelectedLearnerId(sessao.learner_id);

      const mRes = await fetch(`${API_BASE}/missions`);
      const mData = await mRes.json();
      setMissions(mData);
      if (mData.length > 0) setSelectedMissionId(mData[0].id);
    } catch (err) {
      showToast("error", "Erro ao conectar na API. O servidor FastAPI está de pé?");
    }
  };

  const fetchGraphAndPath = async () => {
    if (!selectedLearnerId) return;
    try {
      const gRes = await fetch(`${API_BASE}/graph?learner_id=${selectedLearnerId}`);
      const gData = await gRes.json();
      setNodes(gData.nodes);
      setEdges(gData.edges);

      if (selectedNode) {
        const updated = gData.nodes.find((n: KNode) => n.id === selectedNode.id);
        if (updated) setSelectedNode(updated);
      }

      if (selectedMissionId) {
        setIsOptimizing(true);
        const pRes = await fetch(
          `${API_BASE}/learners/${selectedLearnerId}/missions/${selectedMissionId}/path`
        );
        const pData = await pRes.json();

        if (pData.status === "processing" && pData.task_id) {
          pollTaskStatus(pData.task_id);
        } else if (pData.path) {
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

      if (data.status === "completed") {
        setActivePath(data.result.path);
        setSatisfied(data.result.satisfied);
        setIsOptimizing(false);
      } else if (data.status === "failed") {
        showToast("error", "Erro ao otimizar a trajetória.");
        setIsOptimizing(false);
      } else {
        setTimeout(() => pollTaskStatus(taskId), 1500);
      }
    } catch (e) {
      console.error("Erro no polling:", e);
      setIsOptimizing(false);
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
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${localStorage.getItem("eos_token")}`,
        },
        body: JSON.stringify({
          learner_id: selectedLearnerId,
          ...evidence,
          reviewers: [
            { reviewer_id: "self_learner", reviewer_type: "self", verdict: "accept" },
          ],
        }),
      });
      const data = await res.json();

      if (data.status === "validated") {
        showToast("success", `Evidência validada! Maestria de ${data.ku_id} atualizada.`);
      } else {
        showToast("warning", `Evidência registrada como "${data.status}". Requer revisão.`);
      }

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

  const handleSelectNodeById = (id: string) => {
    const node = nodes.find((n) => n.id === id);
    if (node) setSelectedNode(node);
  };

  const activePathIds = activePath.map((p) => p.id);
  const currentLearner = learners.find((l) => l.id === selectedLearnerId);

  // ------- Domínios e filtragem -------
  const domains = useMemo(() => {
    const set = new Set(nodes.map((n) => n.domain));
    return Array.from(set).sort();
  }, [nodes]);

  // Ao trocar de missão num grafo grande, foca no domínio dominante da missão
  useEffect(() => {
    if (nodes.length <= 60 || !selectedMissionId) return;
    const mission = missions.find((m) => m.id === selectedMissionId);
    if (!mission?.required_kus?.length) return;
    const required = new Set(mission.required_kus);
    const counts = new Map<string, number>();
    nodes.forEach((n) => {
      if (required.has(n.id)) counts.set(n.domain, (counts.get(n.domain) || 0) + 1);
    });
    let best: string | null = null;
    counts.forEach((c, d) => {
      if (best === null || c > (counts.get(best) || 0)) best = d;
    });
    if (best) setSelectedDomain(best);
  }, [selectedMissionId, missions, nodes.length]);

  const visibleNodes = useMemo(
    () => (selectedDomain === "all" ? nodes : nodes.filter((n) => n.domain === selectedDomain)),
    [nodes, selectedDomain]
  );
  const visibleIds = useMemo(() => new Set(visibleNodes.map((n) => n.id)), [visibleNodes]);
  const visibleEdges = useMemo(
    () => edges.filter((e) => visibleIds.has(e.source) && visibleIds.has(e.target)),
    [edges, visibleIds]
  );

  // ------- Estatísticas derivadas -------
  const stats = useMemo(() => {
    const total = nodes.length;
    const validated = nodes.filter(
      (n) => (n.effective_mastery || n.mastery) >= MASTERY_THRESHOLD
    ).length;
    const inProgress = nodes.filter((n) => {
      const m = n.effective_mastery || n.mastery;
      return m > 0 && m < MASTERY_THRESHOLD;
    }).length;
    const avgMastery =
      total > 0
        ? nodes.reduce((acc, n) => acc + (n.effective_mastery || n.mastery), 0) / total
        : 0;
    const cognitiveLoad = activePath.reduce((acc, p) => acc + p.element_interactivity, 0);
    return { total, validated, inProgress, avgMastery, cognitiveLoad };
  }, [nodes, activePath]);

  const progressPct = Math.round(stats.avgMastery * 100);
  const ring = 2 * Math.PI * 30;

  // Sem sessão, a única tela possível é a de entrada
  if (!sessao) {
    return <Login onEntrar={setSessao} />;
  }

  const sair = () => {
    localStorage.removeItem("eos_sessao");
    localStorage.removeItem("eos_token");
    setSessao(null);
    setSelectedLearnerId("");
    setNodes([]);
    setEdges([]);
    setActivePath([]);
  };

  return (
    <div className="min-h-screen flex text-slate-200">
      <div className="aurora" />
      <div className="grid-overlay" />

      {/* ============ SIDEBAR ============ */}
      <aside className="hidden lg:flex flex-col w-[264px] shrink-0 h-screen sticky top-0 border-r border-slate-400/10 bg-[#090d1a] px-5 py-6 gap-6">
        {/* Brand */}
        <div className="flex items-center gap-3">
          <div className="relative w-10 h-10 rounded-xl bg-gradient-to-br from-violet-600 via-purple-600 to-fuchsia-600 flex items-center justify-center shadow-lg shadow-violet-900/50">
            <Hexagon className="w-5 h-5 text-white" strokeWidth={2.4} />
          </div>
          <div>
            <h1 className="font-display font-800 font-bold text-[15px] text-white leading-tight">
              Engineering<span className="text-gradient">OS</span>
            </h1>
            <p className="text-[10px] text-slate-500 font-medium">Knowledge Engineering v3.1</p>
          </div>
        </div>

        {/* Missão */}
        <div>
          <label className="block text-[10px] uppercase tracking-[0.14em] text-slate-500 font-bold mb-2">
            Missão ativa
          </label>
          <div className="relative">
            <select
              className="input-eos w-full text-[13px] font-semibold appearance-none px-3 py-2.5 pr-8 cursor-pointer"
              value={selectedMissionId}
              onChange={(e) => setSelectedMissionId(e.target.value)}
              disabled={!selectedLearnerId}
            >
              <option value="">Selecionar missão…</option>
              {missions.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.label}
                </option>
              ))}
            </select>
            <ChevronDown className="w-4 h-4 text-slate-500 absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
          </div>
          {satisfied && (
            <div className="mt-2 flex items-center gap-1.5 text-[11px] font-bold text-emerald-400 bg-emerald-500/10 border border-emerald-500/25 rounded-lg px-2.5 py-1.5">
              <Award className="w-3.5 h-3.5" /> Missão satisfeita
            </div>
          )}
        </div>

        {/* Navegação (âncoras) */}
        <nav className="flex flex-col gap-1">
          <span className="text-[10px] uppercase tracking-[0.14em] text-slate-500 font-bold mb-1 px-1">
            Painel
          </span>
          <a href="#overview" className="nav-item active">
            <Layers className="w-4 h-4" /> Visão geral
          </a>
          <a href="#mapa" className="nav-item">
            <BrainCircuit className="w-4 h-4" /> Mapa de conhecimento
          </a>
          <a href="#trilha" className="nav-item">
            <Route className="w-4 h-4" /> Minha trilha
          </a>
          <a href="#competencias" className="nav-item">
            <GraduationCap className="w-4 h-4" /> Competências
          </a>
        </nav>

        <div className="mt-auto flex flex-col gap-3">
          {/* Conta ativa: o aluno é quem está autenticado — não há mais troca
              de aluno pela interface, porque o progresso pertence ao token. */}
          <div className="card p-3 hover:transform-none">
            <p className="text-[10px] uppercase tracking-[0.14em] text-slate-500 font-bold mb-1.5">
              Conta
            </p>
            <p className="text-[13px] font-bold text-white truncate" title={sessao.name}>
              {sessao.name}
            </p>
            <p className="text-[10px] text-slate-500 capitalize">{sessao.role}</p>
          </div>

          {sessao.role === "admin" && (
            <>
              <div className="relative">
                <select
                  className="input-eos w-full text-[13px] font-semibold appearance-none px-3 py-2.5 pr-8 cursor-pointer"
                  value={selectedLearnerId}
                  onChange={(e) => setSelectedLearnerId(e.target.value)}
                  title="Visão de administrador"
                >
                  {learners.map((l) => (
                    <option key={l.id} value={l.id}>
                      {l.name}
                    </option>
                  ))}
                </select>
                <ChevronDown className="w-4 h-4 text-slate-500 absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
              </div>
              <button
                onClick={handleTriggerCurriculumSeed}
                className="flex items-center justify-center gap-1.5 text-[11px] font-semibold text-slate-500 hover:text-slate-300 transition py-1.5"
                title="Recompila os seeds .eos e repovoa o banco"
              >
                <Database className="w-3.5 h-3.5" /> Reset / Seed do currículo
              </button>
            </>
          )}

          <button
            onClick={sair}
            className="btn-ghost flex items-center justify-center gap-1.5 text-xs font-bold px-3 py-2.5"
          >
            <LogOut className="w-3.5 h-3.5" /> Sair
          </button>
        </div>
      </aside>

      {/* ============ MAIN ============ */}
      <main className="flex-1 min-w-0 px-5 md:px-9 py-7 max-w-[1400px] mx-auto w-full">
        {/* -------- HERO -------- */}
        <section id="overview" className="animate-fade-up">
          <div className="panel relative overflow-hidden px-6 md:px-9 py-7">
            {/* glow decorativo */}
            {/* brilho por gradiente (sem filter: blur, que força camada de GPU) */}
            <div
              className="absolute inset-0 pointer-events-none"
              style={{
                background:
                  "radial-gradient(40% 60% at 88% 0%, rgba(124,58,237,0.18), transparent 70%), radial-gradient(35% 55% at 35% 100%, rgba(217,70,239,0.12), transparent 70%)",
              }}
            />

            <div className="relative flex flex-col md:flex-row md:items-center gap-6 md:gap-10">
              {/* Progress ring */}
              <div className="relative w-[92px] h-[92px] shrink-0">
                <svg viewBox="0 0 72 72" className="w-full h-full -rotate-90">
                  <circle cx="36" cy="36" r="30" fill="none" strokeWidth="6" className="ring-track" />
                  <circle
                    cx="36"
                    cy="36"
                    r="30"
                    fill="none"
                    strokeWidth="6"
                    strokeLinecap="round"
                    stroke="url(#heroGrad)"
                    strokeDasharray={`${stats.avgMastery * ring} ${ring}`}
                    style={{ transition: "stroke-dasharray 0.8s cubic-bezier(0.22,1,0.36,1)" }}
                  />
                  <defs>
                    <linearGradient id="heroGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                      <stop offset="0%" stopColor="#a78bfa" />
                      <stop offset="100%" stopColor="#e879f9" />
                    </linearGradient>
                  </defs>
                </svg>
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                  <span className="font-display font-bold text-lg text-white leading-none">
                    {progressPct}%
                  </span>
                </div>
              </div>

              <div className="flex-1 min-w-0">
                <p className="text-[11px] uppercase tracking-[0.18em] text-violet-300/80 font-bold mb-1">
                  {rankFor(stats.avgMastery)} · nível de domínio
                </p>
                <h2 className="font-display text-2xl md:text-[28px] font-bold text-white leading-tight">
                  {currentLearner ? `Bem-vindo de volta, ${currentLearner.name.split(" ")[0]}` : "Bem-vindo ao EngineeringOS"}
                </h2>
                <p className="text-[13px] text-slate-400 mt-1.5 max-w-xl">
                  {activePath.length > 0
                    ? `Sua trilha ótima tem ${activePath.length} unidade${activePath.length > 1 ? "s" : ""} na fronteira do seu conhecimento. Próximo passo: `
                    : satisfied
                    ? "Todas as unidades desta missão foram validadas. Escolha uma nova missão para continuar evoluindo."
                    : "Selecione uma missão para o motor cognitivo calcular sua trilha ideal de aprendizado."}
                  {activePath.length > 0 && (
                    <button
                      onClick={() => handleSelectNodeById(activePath[0].id)}
                      className="font-bold text-transparent bg-clip-text bg-gradient-to-r from-violet-300 to-fuchsia-300 hover:from-violet-200 hover:to-fuchsia-200 transition"
                    >
                      {activePath[0].title} →
                    </button>
                  )}
                </p>
              </div>

              {activePath.length > 0 && (
                <button
                  onClick={() => handleSelectNodeById(activePath[0].id)}
                  className="btn-primary font-display px-6 py-3 text-sm shrink-0 flex items-center gap-2"
                >
                  <Flame className="w-4 h-4" /> Continuar estudando
                </button>
              )}
            </div>
          </div>
        </section>

        {/* -------- STATS -------- */}
        <section className="grid grid-cols-2 xl:grid-cols-4 gap-4 mt-5">
          {[
            {
              icon: <Target className="w-4.5 h-4.5 text-violet-300" />,
              iconBg: "bg-violet-500/15 border-violet-500/25",
              label: "Progresso geral",
              value: `${progressPct}%`,
              sub: "média de maestria efetiva",
              delay: "delay-1",
            },
            {
              icon: <Award className="w-4.5 h-4.5 text-emerald-300" />,
              iconBg: "bg-emerald-500/15 border-emerald-500/25",
              label: "Validadas",
              value: `${stats.validated}/${stats.total}`,
              sub: "unidades de conhecimento",
              delay: "delay-2",
            },
            {
              icon: <Compass className="w-4.5 h-4.5 text-fuchsia-300" />,
              iconBg: "bg-fuchsia-500/15 border-fuchsia-500/25",
              label: "Na trilha π*",
              value: `${activePath.length}`,
              sub: "próximos passos otimizados",
              delay: "delay-3",
            },
            {
              icon: <BrainCircuit className="w-4.5 h-4.5 text-cyan-300" />,
              iconBg: "bg-cyan-500/15 border-cyan-500/25",
              label: "Carga cognitiva",
              value: `${stats.cognitiveLoad}`,
              sub: "interatividade da sessão (Cowan ≤ 4 KUs)",
              delay: "delay-4",
            },
          ].map((s) => (
            <div key={s.label} className={`panel px-5 py-4 animate-fade-up ${s.delay}`}>
              <div className="flex items-center gap-3">
                <div className={`w-9 h-9 rounded-xl border flex items-center justify-center shrink-0 ${s.iconBg}`}>
                  {s.icon}
                </div>
                <div className="min-w-0">
                  <p className="font-display text-xl font-bold text-white leading-none">{s.value}</p>
                  <p className="text-[10px] uppercase tracking-wider text-slate-500 font-bold mt-1">
                    {s.label}
                  </p>
                </div>
              </div>
              <p className="text-[10px] text-slate-500 mt-2.5 truncate">{s.sub}</p>
            </div>
          ))}
        </section>

        {/* -------- MAPA + TRILHA -------- */}
        <section className="grid grid-cols-1 xl:grid-cols-3 gap-5 mt-5">
          <div id="mapa" className="xl:col-span-2 animate-fade-up delay-2">
            <GraphView
              nodes={visibleNodes}
              edges={visibleEdges}
              activePathIds={activePathIds}
              selectedNodeId={selectedNode ? selectedNode.id : null}
              onSelectNode={setSelectedNode}
              domains={domains}
              selectedDomain={selectedDomain}
              onSelectDomain={setSelectedDomain}
            />
          </div>

          <div id="trilha" className="animate-fade-up delay-3">
            <TrilhaPanel
              path={activePath}
              satisfied={satisfied}
              isOptimizing={isOptimizing}
              hasMission={!!selectedMissionId}
              onStudy={handleSelectNodeById}
            />
          </div>
        </section>

        {/* -------- COMPETÊNCIAS -------- */}
        <section id="competencias" className="mt-5 animate-fade-up delay-4">
          <CompetenceMatrix
            nodes={visibleNodes}
            onSelectNode={setSelectedNode}
            selectedNodeId={selectedNode ? selectedNode.id : null}
          />
        </section>

        <footer className="mt-10 mb-4 flex items-center justify-between text-[10px] text-slate-600">
          <span>EngineeringOS — Constitutional Specification v3.1.0</span>
          <span className="font-mono-eos">ULA · UKG · CCE · DCST</span>
        </footer>
      </main>

      {/* ============ PAINEL DE ESTUDO (slide-over) ============ */}
      {selectedNode && (
        <div className="fixed inset-0 z-[90] flex justify-end">
          <div
            className="absolute inset-0 bg-black/60"
            onClick={() => setSelectedNode(null)}
          />
          <div className="relative w-full max-w-[480px] h-full bg-[#0a0f1e] border-l border-slate-400/10 shadow-2xl animate-slide-in-right overflow-y-auto">
            <div className="sticky top-0 z-10 bg-[#0a0f1e] border-b border-slate-400/10 px-6 py-4 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-fuchsia-400" />
                <span className="text-[11px] uppercase tracking-[0.16em] text-slate-400 font-bold">
                  Sessão de estudo
                </span>
              </div>
              <button
                onClick={() => setSelectedNode(null)}
                className="btn-ghost p-2 rounded-lg"
                aria-label="Fechar painel"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="px-6 py-5 flex flex-col gap-5">
              <CCEChallenge
                selectedNode={selectedNode}
                learnerId={selectedLearnerId}
                onSubmitEvidence={handleSubmitEvidence}
                onAfterAttempt={fetchGraphAndPath}
              />
              <MaterialViewer selectedNodeId={selectedNode.id} />
            </div>
          </div>
        </div>
      )}

      {/* ============ TOAST ============ */}
      {notification && (
        <div
          className={`fixed bottom-6 right-6 z-[120] panel px-4 py-3.5 max-w-sm flex items-start gap-3 animate-toast-in border-l-4 ${
            notification.type === "success"
              ? "border-l-emerald-400"
              : notification.type === "warning"
              ? "border-l-amber-400"
              : "border-l-rose-500"
          }`}
        >
          <Sparkles
            className={`w-4.5 h-4.5 shrink-0 mt-0.5 ${
              notification.type === "success"
                ? "text-emerald-400"
                : notification.type === "warning"
                ? "text-amber-400"
                : "text-rose-400"
            }`}
          />
          <p className="text-xs text-slate-200 leading-relaxed">{notification.msg}</p>
        </div>
      )}

    </div>
  );
}

export default App;
