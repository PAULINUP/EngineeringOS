import React, { useMemo } from "react";
import { BrainCircuit, Lock } from "lucide-react";

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

interface Edge {
  id: number;
  source: string;
  target: string;
  type: string;
  weight: number;
}

interface GraphViewProps {
  nodes: Node[];
  edges: Edge[];
  activePathIds: string[];
  selectedNodeId: string | null;
  onSelectNode: (node: Node) => void;
}

const MASTERY_THRESHOLD = 0.85;
const NODE_R = 30;
const RING_R = 26;
const RING_C = 2 * Math.PI * RING_R;

export const GraphView: React.FC<GraphViewProps> = ({
  nodes,
  edges,
  activePathIds,
  selectedNodeId,
  onSelectNode,
}) => {
  // Layout em camadas (profundidade topológica → coluna)
  const { layout, width, height } = useMemo(() => {
    const empty = { layout: new Map<string, { x: number; y: number }>(), width: 900, height: 520 };
    if (nodes.length === 0) return empty;

    const adj = new Map<string, string[]>();
    const inDegree = new Map<string, number>();

    nodes.forEach((n) => {
      adj.set(n.id, []);
      inDegree.set(n.id, 0);
    });

    edges.forEach((e) => {
      if (e.type === "prerequisite" && adj.has(e.source) && adj.has(e.target)) {
        adj.get(e.source)!.push(e.target);
        inDegree.set(e.target, inDegree.get(e.target)! + 1);
      }
    });

    const depths = new Map<string, number>();
    const queue: string[] = [];
    nodes.forEach((n) => {
      if (inDegree.get(n.id) === 0) {
        depths.set(n.id, 0);
        queue.push(n.id);
      }
    });
    while (queue.length > 0) {
      const u = queue.shift()!;
      const d = depths.get(u) || 0;
      adj.get(u)!.forEach((v) => {
        depths.set(v, Math.max(depths.get(v) || 0, d + 1));
        queue.push(v);
      });
    }
    nodes.forEach((n) => {
      if (!depths.has(n.id)) depths.set(n.id, 0);
    });

    const groups = new Map<number, string[]>();
    depths.forEach((depth, id) => {
      if (!groups.has(depth)) groups.set(depth, []);
      groups.get(depth)!.push(id);
    });

    const X_SPACING = 220;
    const Y_SPACING = 150;
    const PAD_X = 120;
    const maxDepth = Math.max(...Array.from(groups.keys()));
    const maxCol = Math.max(...Array.from(groups.values()).map((g) => g.length));

    const w = Math.max(900, maxDepth * X_SPACING + PAD_X * 2);
    const h = Math.max(520, maxCol * Y_SPACING + 120);

    const coords = new Map<string, { x: number; y: number }>();
    groups.forEach((ids, depth) => {
      const x = depth * X_SPACING + PAD_X;
      ids.forEach((id, idx) => {
        const y = h / 2 + (idx - (ids.length - 1) / 2) * Y_SPACING;
        coords.set(id, { x, y });
      });
    });

    return { layout: coords, width: w, height: h };
  }, [nodes, edges]);

  // Pré-requisitos de cada nó, para estado "bloqueado"
  const prereqMap = useMemo(() => {
    const map = new Map<string, string[]>();
    edges.forEach((e) => {
      if (e.type !== "prerequisite") return;
      if (!map.has(e.target)) map.set(e.target, []);
      map.get(e.target)!.push(e.source);
    });
    return map;
  }, [edges]);

  const masteryOf = (id: string) => {
    const n = nodes.find((x) => x.id === id);
    return n ? n.effective_mastery || n.mastery : 0;
  };

  return (
    <div className="panel overflow-hidden flex flex-col h-full min-h-[560px]">
      {/* Header do card */}
      <div className="flex items-center justify-between px-6 pt-5 pb-4 border-b border-slate-400/10">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-violet-500/15 border border-violet-500/25 flex items-center justify-center">
            <BrainCircuit className="w-4 h-4 text-violet-300" />
          </div>
          <div>
            <h2 className="font-display text-sm font-bold text-white">Mapa de Conhecimento</h2>
            <p className="text-[10px] text-slate-500">Grafo de pré-requisitos · espaço 𝕂</p>
          </div>
        </div>
        {/* Legenda */}
        <div className="hidden md:flex items-center gap-4 text-[10px] font-semibold text-slate-400">
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)]" /> Dominada
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-fuchsia-400 shadow-[0_0_8px_rgba(232,121,249,0.8)]" /> Na trilha
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-slate-600" /> Futura
          </span>
        </div>
      </div>

      <div className="flex-1 overflow-auto relative">
        {nodes.length === 0 ? (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-3">
            <div className="w-10 h-10 border-[3px] border-violet-500/70 border-t-transparent rounded-full animate-spin" />
            <p className="text-xs shimmer-text font-semibold">Compilando o espaço de conhecimento…</p>
          </div>
        ) : (
          <svg
            viewBox={`0 0 ${width} ${height}`}
            style={{ width, height, minWidth: "100%" }}
            className="select-none"
          >
            <defs>
              <linearGradient id="edgeActive" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stopColor="#a78bfa" />
                <stop offset="100%" stopColor="#e879f9" />
              </linearGradient>
              <linearGradient id="nodeRingPath" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#a78bfa" />
                <stop offset="100%" stopColor="#e879f9" />
              </linearGradient>
              <radialGradient id="nodeFillDone" cx="50%" cy="35%" r="80%">
                <stop offset="0%" stopColor="rgba(52,211,153,0.28)" />
                <stop offset="100%" stopColor="rgba(6,20,16,0.9)" />
              </radialGradient>
              <radialGradient id="nodeFillPath" cx="50%" cy="35%" r="80%">
                <stop offset="0%" stopColor="rgba(168,85,247,0.30)" />
                <stop offset="100%" stopColor="rgba(15,10,30,0.92)" />
              </radialGradient>
              <radialGradient id="nodeFillIdle" cx="50%" cy="35%" r="80%">
                <stop offset="0%" stopColor="rgba(51,65,85,0.55)" />
                <stop offset="100%" stopColor="rgba(8,12,24,0.95)" />
              </radialGradient>
              <filter id="softGlow" x="-40%" y="-40%" width="180%" height="180%">
                <feGaussianBlur stdDeviation="6" result="blur" />
                <feComposite in="SourceGraphic" in2="blur" operator="over" />
              </filter>
            </defs>

            {/* Arestas */}
            {edges.map((edge) => {
              const p1 = layout.get(edge.source);
              const p2 = layout.get(edge.target);
              if (!p1 || !p2) return null;

              const isActiveLink =
                activePathIds.includes(edge.source) && activePathIds.includes(edge.target);
              const isDoneLink =
                masteryOf(edge.source) >= MASTERY_THRESHOLD &&
                masteryOf(edge.target) >= MASTERY_THRESHOLD;

              const midX = (p1.x + p2.x) / 2;
              const d = `M ${p1.x + NODE_R} ${p1.y} C ${midX} ${p1.y}, ${midX} ${p2.y}, ${p2.x - NODE_R} ${p2.y}`;

              return (
                <g key={edge.id}>
                  {isActiveLink ? (
                    <>
                      <path d={d} fill="none" stroke="url(#edgeActive)" strokeWidth={6} strokeOpacity={0.18} />
                      <path d={d} fill="none" stroke="url(#edgeActive)" strokeWidth={2} className="animated-dash" />
                    </>
                  ) : (
                    <path
                      d={d}
                      fill="none"
                      stroke={isDoneLink ? "rgba(52,211,153,0.35)" : "rgba(148,163,184,0.12)"}
                      strokeWidth={1.5}
                    />
                  )}
                </g>
              );
            })}

            {/* Nós */}
            {nodes.map((node) => {
              const coord = layout.get(node.id);
              if (!coord) return null;

              const mastery = node.effective_mastery || node.mastery;
              const isSelected = selectedNodeId === node.id;
              const isOnPath = activePathIds.includes(node.id);
              const isDone = mastery >= MASTERY_THRESHOLD;
              const prereqs = prereqMap.get(node.id) || [];
              const isLocked =
                !isDone && !isOnPath && prereqs.some((p) => masteryOf(p) < MASTERY_THRESHOLD);
              const stepNumber = isOnPath ? activePathIds.indexOf(node.id) + 1 : null;

              let ringStroke = "rgba(148,163,184,0.35)";
              let fill = "url(#nodeFillIdle)";
              let outline = "rgba(148,163,184,0.22)";
              if (isDone) {
                ringStroke = "#34d399";
                fill = "url(#nodeFillDone)";
                outline = "rgba(52,211,153,0.6)";
              } else if (isOnPath) {
                ringStroke = "url(#nodeRingPath)";
                fill = "url(#nodeFillPath)";
                outline = "rgba(168,85,247,0.55)";
              }

              const titleWords = node.title.split(" ");
              const line1 = titleWords.slice(0, 2).join(" ");
              const line2 = titleWords.slice(2, 5).join(" ");

              return (
                <g
                  key={node.id}
                  transform={`translate(${coord.x}, ${coord.y})`}
                  className="cursor-pointer group"
                  onClick={() => onSelectNode(node)}
                  opacity={isLocked ? 0.55 : 1}
                >
                  {/* Halo de seleção */}
                  {isSelected && (
                    <circle r={NODE_R + 9} fill="none" stroke="#fbbf24" strokeWidth={2} strokeDasharray="4 5" opacity={0.9}>
                      <animateTransform
                        attributeName="transform"
                        type="rotate"
                        from="0"
                        to="360"
                        dur="14s"
                        repeatCount="indefinite"
                      />
                    </circle>
                  )}

                  {/* Pulso emerald para validados */}
                  {isDone && (
                    <circle r={NODE_R + 5} fill="none" stroke="#34d399" strokeWidth={2} strokeOpacity={0.35} className="pulse-emerald" />
                  )}

                  {/* Corpo do nó */}
                  <circle
                    r={NODE_R}
                    fill={fill}
                    stroke={outline}
                    strokeWidth={isSelected ? 2.5 : 1.5}
                    style={isDone ? { filter: "url(#softGlow)" } : undefined}
                    className="transition-all duration-300"
                  />

                  {/* Anel de progresso */}
                  <circle r={RING_R} fill="none" stroke="rgba(148,163,184,0.10)" strokeWidth={3} />
                  {mastery > 0 && (
                    <circle
                      r={RING_R}
                      fill="none"
                      stroke={ringStroke}
                      strokeWidth={3}
                      strokeLinecap="round"
                      strokeDasharray={`${mastery * RING_C} ${RING_C}`}
                      transform="rotate(-90)"
                      style={{ transition: "stroke-dasharray 0.7s ease" }}
                    />
                  )}

                  {/* Conteúdo central */}
                  {isLocked ? (
                    <g transform="translate(-6,-6)" opacity={0.8}>
                      <Lock width={12} height={12} color="#94a3b8" />
                    </g>
                  ) : (
                    <text
                      textAnchor="middle"
                      dy="5"
                      fill="white"
                      fontSize="13"
                      fontWeight={700}
                      className="font-display pointer-events-none"
                    >
                      {Math.round(mastery * 100)}
                      <tspan fontSize="8" fill="rgba(255,255,255,0.55)">
                        %
                      </tspan>
                    </text>
                  )}

                  {/* Badge de passo da trilha */}
                  {stepNumber !== null && (
                    <g transform={`translate(${NODE_R - 8}, ${-NODE_R + 8})`}>
                      <circle r={9} fill="#a855f7" stroke="#0a0f1e" strokeWidth={2} />
                      <text textAnchor="middle" dy="3.5" fill="white" fontSize="10" fontWeight={800}>
                        {stepNumber}
                      </text>
                    </g>
                  )}

                  {/* Rótulo abaixo do nó */}
                  <text
                    textAnchor="middle"
                    y={NODE_R + 18}
                    fill={isDone ? "#a7f3d0" : isOnPath ? "#e9d5ff" : "#94a3b8"}
                    fontSize="11"
                    fontWeight={600}
                    className="pointer-events-none"
                  >
                    {line1}
                  </text>
                  {line2 && (
                    <text
                      textAnchor="middle"
                      y={NODE_R + 31}
                      fill="rgba(148,163,184,0.7)"
                      fontSize="10"
                      className="pointer-events-none"
                    >
                      {line2}
                    </text>
                  )}
                </g>
              );
            })}
          </svg>
        )}
      </div>
    </div>
  );
};
