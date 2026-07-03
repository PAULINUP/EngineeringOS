import React, { useState, useEffect } from "react";
import { BookOpen, FileText, Play, Link, Loader2 } from "lucide-react";

const API_BASE = "http://localhost:8000/api";

interface StudyMaterial {
  id: string;
  ku_id: string;
  title: string;
  type: string;
  url: string | null;
  quality_score: number;
}

interface MaterialViewerProps {
  selectedNodeId: string | null;
}

export const MaterialViewer: React.FC<MaterialViewerProps> = ({ selectedNodeId }) => {
  const [materials, setMaterials] = useState<StudyMaterial[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!selectedNodeId) {
      setMaterials([]);
      return;
    }

    const fetchMaterials = async () => {
      setLoading(true);
      try {
        const res = await fetch(`${API_BASE}/kus/${selectedNodeId}/materials`);
        const data = await res.json();
        setMaterials(data);
      } catch (err) {
        console.error("Failed to fetch materials:", err);
      } finally {
        setLoading(false);
      }
    };

    fetchMaterials();
  }, [selectedNodeId]);

  if (!selectedNodeId) return null;

  const getIcon = (type: string) => {
    switch (type) {
      case "video": return <Play className="w-4 h-4 text-rose-400" />;
      case "article": return <FileText className="w-4 h-4 text-blue-400" />;
      case "pdf": return <FileText className="w-4 h-4 text-amber-400" />;
      default: return <Link className="w-4 h-4 text-violet-400" />;
    }
  };

  return (
    <div className="glass-panel p-5 flex flex-col gap-4 animate-fade-in relative overflow-hidden group">
      {/* Decorative Glow */}
      <div className="absolute -top-10 -right-10 w-32 h-32 bg-blue-500/10 rounded-full blur-3xl group-hover:bg-blue-500/20 transition-colors duration-500 pointer-events-none" />

      <h3 className="text-sm font-bold uppercase tracking-wider text-gray-400 flex items-center gap-1.5">
        <BookOpen className="w-4 h-4 text-blue-400" /> Base Infinita de Materiais
      </h3>

      {loading ? (
        <div className="flex justify-center items-center py-4">
          <Loader2 className="w-5 h-5 text-blue-500 animate-spin" />
        </div>
      ) : materials.length === 0 ? (
        <p className="text-xs text-gray-500 text-center py-4 bg-black/20 rounded border border-white/5">
          Nenhum material base encontrado para esta competência.
        </p>
      ) : (
        <div className="flex flex-col gap-2">
          {materials.map((mat) => (
            <a
              key={mat.id}
              href={mat.url || "#"}
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-3 p-3 bg-white/5 hover:bg-white/10 border border-white/5 hover:border-white/20 rounded-lg transition-all"
            >
              <div className="w-8 h-8 rounded-full bg-black/40 flex items-center justify-center shrink-0 border border-white/5">
                {getIcon(mat.type)}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-xs font-semibold text-white truncate" title={mat.title}>{mat.title}</p>
                <div className="flex gap-2 items-center mt-1">
                  <span className="text-[9px] uppercase font-bold text-gray-500 tracking-wider">
                    {mat.type}
                  </span>
                  <span className="text-[9px] text-emerald-500 font-medium bg-emerald-950/40 px-1.5 py-0.5 rounded">
                    Score: {mat.quality_score}
                  </span>
                </div>
              </div>
            </a>
          ))}
        </div>
      )}
    </div>
  );
};
