import React, { useMemo } from "react";

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

export const GraphView: React.FC<GraphViewProps> = ({
  nodes,
  edges,
  activePathIds,
  selectedNodeId,
  onSelectNode,
}) => {
  // Computa a profundidade de cada nó para ordenação em camadas (Skill Tree)
  const nodeLayout = useMemo(() => {
    if (nodes.length === 0) return new Map<string, { x: number; y: number }>();

    // 1. Constrói listas de adjacência (pré-requisitos)
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

    // 2. BFS para calcular níveis (depth)
    const depths = new Map<string, number>();
    const queue: string[] = [];

    // Inicia com nós raiz (grau de entrada = 0)
    nodes.forEach((n) => {
      if (inDegree.get(n.id) === 0) {
        depths.set(n.id, 0);
        queue.push(n.id);
      }
    });

    while (queue.length > 0) {
      const u = queue.shift()!;
      const currentDepth = depths.get(u) || 0;

      adj.get(u)!.forEach((v) => {
        const nextDepth = Math.max(depths.get(v) || 0, currentDepth + 1);
        depths.set(v, nextDepth);
        queue.push(v);
      });
    }

    // Garante que todos os nós tenham profundidade
    nodes.forEach((n) => {
      if (!depths.has(n.id)) {
        depths.set(n.id, 0);
      }
    });

    // 3. Agrupa nós por profundidade
    const groups = new Map<number, string[]>();
    depths.forEach((depth, id) => {
      if (!groups.has(depth)) groups.set(depth, []);
      groups.get(depth)!.push(id);
    });

    // 4. Calcula coordenadas finais
    const coords = new Map<string, { x: number; y: number }>();
    const X_SPACING = 240;
    const Y_SPACING = 140;
    const WIDTH_OFFSET = 80;
    const HEIGHT_OFFSET = 300;

    groups.forEach((nodeIds, depth) => {
      const x = depth * X_SPACING + WIDTH_OFFSET;
      const count = nodeIds.length;
      
      nodeIds.forEach((id, idx) => {
        // Centraliza verticalmente a coluna
        const y = idx * Y_SPACING + HEIGHT_OFFSET - ((count - 1) * Y_SPACING) / 2;
        coords.set(id, { x, y });
      });
    });

    return coords;
  }, [nodes, edges]);

  // Coordenadas calculadas
  const width = 1200;
  const height = 600;

  return (
    <div className="w-full overflow-x-auto overflow-y-hidden glass-panel p-6 min-h-[580px] relative flex justify-center items-center">
      {nodes.length === 0 ? (
        <div className="text-gray-400 text-sm">Carregando mapa de conhecimento...</div>
      ) : (
        <svg viewBox={`0 0 ${width} ${height}`} className="w-[1200px] h-[600px] select-none">
          {/* Definições de Gradientes e Filtros */}
          <defs>
            <filter id="glow-valid" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="8" result="blur" />
              <feComposite in="SourceGraphic" in2="blur" operator="over" />
            </filter>
            <linearGradient id="activeGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#8b5cf6" />
              <stop offset="100%" stopColor="#ec4899" />
            </linearGradient>
          </defs>

          {/* Renderiza as Conexões (Arestas) */}
          {edges.map((edge) => {
            const p1 = nodeLayout.get(edge.source);
            const p2 = nodeLayout.get(edge.target);
            if (!p1 || !p2) return null;

            const isActiveLink =
              activePathIds.includes(edge.source) && activePathIds.includes(edge.target);

            // Desenha curva Bezier cúbica suave
            const cX1 = (p1.x + p2.x) / 2;
            const cY1 = p1.y;
            const cX2 = (p1.x + p2.x) / 2;
            const cY2 = p2.y;

            const d = `M ${p1.x} ${p1.y} C ${cX1} ${cY1}, ${cX2} ${cY2}, ${p2.x} ${p2.y}`;

            return (
              <g key={edge.id}>
                {isActiveLink ? (
                  <>
                    {/* Linha de brilho traseira */}
                    <path
                      d={d}
                      fill="none"
                      stroke="url(#activeGrad)"
                      strokeWidth={5}
                      strokeOpacity={0.3}
                    />
                    {/* Linha ativa principal com traço animado */}
                    <path
                      d={d}
                      fill="none"
                      stroke="url(#activeGrad)"
                      strokeWidth={2}
                      className="animated-dash"
                    />
                  </>
                ) : (
                  // Conexão padrão
                  <path
                    d={d}
                    fill="none"
                    stroke="rgba(255,255,255,0.08)"
                    strokeWidth={1.5}
                  />
                )}
              </g>
            );
          })}

          {/* Renderiza os Nós */}
          {nodes.map((node) => {
            const coord = nodeLayout.get(node.id);
            if (!coord) return null;

            const isSelected = selectedNodeId === node.id;
            const isOnActivePath = activePathIds.includes(node.id);
            const isValidated = node.mastery >= 0.85;

            // Determina as cores baseado no estado
            let strokeColor = "rgba(255,255,255,0.15)";
            let fillColor = "rgba(17,24,39,0.85)";
            let glowFilter = "";
            let pulseClass = "";

            if (isValidated) {
              strokeColor = "#10b981"; // Emerald
              fillColor = "rgba(16,185,129,0.08)";
              glowFilter = "url(#glow-valid)";
              pulseClass = "pulse-emerald";
            } else if (isOnActivePath) {
              strokeColor = "#8b5cf6"; // Violet
              fillColor = "rgba(139,92,246,0.08)";
            }

            if (isSelected) {
              strokeColor = "#f59e0b"; // Amber (selected)
            }

            return (
              <g
                key={node.id}
                transform={`translate(${coord.x}, ${coord.y})`}
                className="cursor-pointer"
                onClick={() => onSelectNode(node)}
              >
                {/* Círculo de Brilho Traseiro se validado */}
                {isValidated && (
                  <circle
                    r={36}
                    fill="none"
                    stroke="#10b981"
                    strokeWidth={3}
                    strokeOpacity={0.4}
                    className={pulseClass}
                  />
                )}

                {/* Base do Nó */}
                <circle
                  r={32}
                  fill={fillColor}
                  stroke={strokeColor}
                  strokeWidth={isSelected ? 3 : 1.5}
                  style={{ filter: glowFilter }}
                  className="transition-all duration-300"
                />

                {/* Porcentagem de Maestria (Anel Externo Parcial) */}
                <circle
                  r={28}
                  fill="none"
                  stroke="rgba(255,255,255,0.05)"
                  strokeWidth={2}
                />
                {node.mastery > 0 && (
                  <circle
                    r={28}
                    fill="none"
                    stroke={isValidated ? "#10b981" : "#8b5cf6"}
                    strokeWidth={2}
                    strokeDasharray={`${node.mastery * 175.9} 175.9`} // 2 * pi * r = 175.9
                    transform="rotate(-90)"
                  />
                )}

                {/* Ícone ou Texto de Identificação */}
                <text
                  textAnchor="middle"
                  dy="-4"
                  fill="#ffffff"
                  fontSize="10"
                  fontWeight="600"
                  className="title-font pointer-events-none"
                >
                  {node.title.split(" ").slice(0, 2).join(" ")}
                </text>
                <text
                  textAnchor="middle"
                  dy="12"
                  fill="rgba(255,255,255,0.4)"
                  fontSize="9"
                  className="pointer-events-none"
                >
                  {Math.round(node.mastery * 100)}%
                </text>
              </g>
            );
          })}
        </svg>
      )}
    </div>
  );
};
