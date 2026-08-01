import React, { useState } from "react";
import { Hexagon, LogIn, ShieldCheck, UserPlus } from "lucide-react";
import { API_BASE } from "../api";

export interface Sessao {
  access_token: string;
  learner_id: string;
  name: string;
  role: string;
}

interface LoginProps {
  onEntrar: (s: Sessao) => void;
}

export const Login: React.FC<LoginProps> = ({ onEntrar }) => {
  const [modo, setModo] = useState<"entrar" | "criar">("entrar");
  const [nome, setNome] = useState("");
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  const enviar = async (e: React.FormEvent) => {
    e.preventDefault();
    setErro(null);
    setEnviando(true);
    try {
      const rota = modo === "entrar" ? "/auth/login" : "/auth/register";
      const corpo =
        modo === "entrar" ? { email, password: senha } : { name: nome, email, password: senha };
      const res = await fetch(`${API_BASE}${rota}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(corpo),
      });
      const dados = await res.json();
      if (!res.ok) {
        const detalhe = Array.isArray(dados.detail)
          ? dados.detail[0]?.msg ?? "Dados inválidos."
          : dados.detail ?? "Não foi possível continuar.";
        setErro(String(detalhe));
        return;
      }
      localStorage.setItem("eos_sessao", JSON.stringify(dados));
      onEntrar(dados as Sessao);
    } catch {
      setErro("Não consegui falar com o servidor. Ele está no ar?");
    } finally {
      setEnviando(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-6 text-slate-200">
      <div className="aurora" />
      <div className="w-full max-w-md">
        <div className="flex items-center gap-3 mb-7 justify-center">
          <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-violet-600 via-purple-600 to-fuchsia-600 flex items-center justify-center shadow-lg shadow-violet-900/50">
            <Hexagon className="w-6 h-6 text-white" strokeWidth={2.4} />
          </div>
          <div>
            <h1 className="font-display font-bold text-lg text-white leading-tight">
              Engineering<span className="text-gradient">OS</span>
            </h1>
            <p className="text-[10px] text-slate-500 font-medium">
              Engenharia do Conhecimento v3.4
            </p>
          </div>
        </div>

        <div className="panel p-7">
          <h2 className="font-display text-xl font-bold text-white mb-1">
            {modo === "entrar" ? "Entrar" : "Criar conta"}
          </h2>
          <p className="text-xs text-slate-400 mb-6">
            {modo === "entrar"
              ? "Seu progresso é vinculado à sua conta."
              : "Já tem progresso registrado com este nome? A conta será reaproveitada."}
          </p>

          <form onSubmit={enviar} className="space-y-4">
            {modo === "criar" && (
              <div>
                <label className="block text-[10px] uppercase tracking-wider text-slate-500 font-bold mb-1.5">
                  Nome completo
                </label>
                <input
                  className="input-eos w-full px-3.5 py-2.5 text-sm"
                  value={nome}
                  onChange={(e) => setNome(e.target.value)}
                  required
                  minLength={2}
                  autoFocus
                />
              </div>
            )}

            <div>
              <label className="block text-[10px] uppercase tracking-wider text-slate-500 font-bold mb-1.5">
                E-mail
              </label>
              <input
                type="email"
                className="input-eos w-full px-3.5 py-2.5 text-sm"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoFocus={modo === "entrar"}
              />
            </div>

            <div>
              <label className="block text-[10px] uppercase tracking-wider text-slate-500 font-bold mb-1.5">
                Senha
              </label>
              <input
                type="password"
                className="input-eos w-full px-3.5 py-2.5 text-sm"
                value={senha}
                onChange={(e) => setSenha(e.target.value)}
                required
                minLength={modo === "criar" ? 8 : undefined}
              />
              {modo === "criar" && (
                <p className="text-[10px] text-slate-500 mt-1.5">Mínimo de 8 caracteres.</p>
              )}
            </div>

            {erro && (
              <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 px-3.5 py-2.5">
                <p className="text-xs text-rose-200">{erro}</p>
              </div>
            )}

            <button
              type="submit"
              disabled={enviando}
              className="btn-primary font-display w-full flex justify-center items-center gap-2 py-3 text-sm"
            >
              {enviando ? (
                <>
                  <div className="w-4 h-4 border-2 border-white/80 border-t-transparent rounded-full animate-spin" />
                  Aguarde…
                </>
              ) : modo === "entrar" ? (
                <>
                  <LogIn className="w-4 h-4" /> Entrar
                </>
              ) : (
                <>
                  <UserPlus className="w-4 h-4" /> Criar conta
                </>
              )}
            </button>
          </form>

          <button
            onClick={() => {
              setModo(modo === "entrar" ? "criar" : "entrar");
              setErro(null);
            }}
            className="w-full text-center text-xs text-slate-400 hover:text-white mt-5 transition"
          >
            {modo === "entrar"
              ? "Não tem conta? Criar uma"
              : "Já tem conta? Entrar"}
          </button>
        </div>

        <p className="flex items-start gap-1.5 text-[10px] text-slate-500 leading-relaxed mt-5 px-1">
          <ShieldCheck className="w-3.5 h-3.5 shrink-0 mt-px text-emerald-400/70" />
          Sua senha é guardada apenas como hash bcrypt, e cada evidência de
          competência fica vinculada à sua conta — ninguém registra progresso em seu nome.
        </p>
      </div>
    </div>
  );
};
