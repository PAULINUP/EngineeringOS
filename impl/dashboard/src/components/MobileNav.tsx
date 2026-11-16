import { BrainCircuit, GraduationCap, Layers, Route } from "lucide-react";

export type MobileSection = "overview" | "mapa" | "trilha" | "competencias";

const ITEMS: { id: MobileSection; label: string; icon: typeof Layers }[] = [
  { id: "overview", label: "Visão geral", icon: Layers },
  { id: "mapa", label: "Mapa", icon: BrainCircuit },
  { id: "trilha", label: "Trilha", icon: Route },
  { id: "competencias", label: "Competências", icon: GraduationCap },
];

export function MobileNav({ active, onSelect }: { active: MobileSection; onSelect: (s: MobileSection) => void }) {
  return (
    <nav className="mobile-nav lg:hidden fixed bottom-0 inset-x-0 z-40 pb-safe">
      <div className="flex items-stretch justify-around border-t border-slate-400/10 bg-[#080d1a]/95">
        {ITEMS.map(({ id, label, icon: Icon }) => {
          const isActive = active === id;
          return (
            <button
              key={id}
              onClick={() => onSelect(id)}
              className="flex flex-col items-center justify-center gap-1 py-2.5 px-2 min-w-0 flex-1 active:scale-[0.97] transition-transform"
            >
              <Icon
                className={`w-5 h-5 ${isActive ? "text-violet-300" : "text-slate-500"}`}
                strokeWidth={isActive ? 2.4 : 2}
              />
              <span
                className={`text-[9px] font-bold tracking-wide ${
                  isActive ? "text-violet-200" : "text-slate-500"
                }`}
              >
                {label}
              </span>
            </button>
          );
        })}
      </div>
    </nav>
  );
}
