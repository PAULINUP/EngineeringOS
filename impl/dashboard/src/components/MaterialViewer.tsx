import React, { useState, useEffect } from "react";
import { BookOpen, ExternalLink, FileText, Link2, Loader2, Play, Star } from "lucide-react";

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

const TYPE_STYLE: Record<string, { icon: React.ReactNode; chip: string }> = {
  video: {
    icon: <Play className="w-4 h-4 text-rose-300" />,
    chip: "bg-rose-500/15 border-rose-500/25",
  },
  article: {
    icon: <FileText className="w-4 h-4 text-sky-300" />,
    chip: "bg-sky-500/15 border-sky-500/25",
  },
  pdf: {
    icon: <FileText className="w-4 h-4 text-amber-300" />,
    chip: "bg-amber-500/15 border-amber-500/25",
  },
  link: {
    icon: <Link2 className="w-4 h-4 text-violet-300" />,
    chip: "bg-violet-500/15 border-violet-500/25",
  },
};

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

  return (
    <div className="border-t border-slate-400/10 pt-5">
      <h3 className="text-[10px] uppercase tracking-[0.14em] text-slate-500 font-bold flex items-center gap-1.5 mb-3">
        <BookOpen className="w-3.5 h-3.5 text-sky-400" /> Materiais de estudo
      </h3>

      {loading ? (
        <div className="flex justify-center items-center py-6">
          <Loader2 className="w-5 h-5 text-sky-400 animate-spin" />
        </div>
      ) : materials.length === 0 ? (
        <p className="text-[11px] text-slate-500 text-center py-5 card hover:transform-none">
          Nenhum material cadastrado para esta unidade ainda.
        </p>
      ) : (
        <div className="flex flex-col gap-2">
          {materials.map((mat) => {
            const style = TYPE_STYLE[mat.type] || TYPE_STYLE.link;
            return (
              <a
                key={mat.id}
                href={mat.url || "#"}
                target="_blank"
                rel="noreferrer"
                className="card group flex items-center gap-3 p-3"
              >
                <div
                  className={`w-9 h-9 rounded-xl border flex items-center justify-center shrink-0 ${style.chip}`}
                >
                  {style.icon}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-bold text-white truncate" title={mat.title}>
                    {mat.title}
                  </p>
                  <div className="flex gap-2.5 items-center mt-0.5">
                    <span className="text-[9px] uppercase font-bold text-slate-500 tracking-wider">
                      {mat.type}
                    </span>
                    <span className="flex items-center gap-0.5 text-[9px] font-semibold text-amber-300/90">
                      <Star className="w-2.5 h-2.5 fill-current" /> {mat.quality_score.toFixed(1)}
                    </span>
                  </div>
                </div>
                <ExternalLink className="w-3.5 h-3.5 text-slate-600 group-hover:text-slate-300 transition shrink-0" />
              </a>
            );
          })}
        </div>
      )}
    </div>
  );
};
