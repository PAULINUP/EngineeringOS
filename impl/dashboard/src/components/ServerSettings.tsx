import { useState } from "react";
import { Database, X, Check } from "lucide-react";
import { resolveApiBase, setApiBase } from "../api";

/**
 * Tela/configuração do servidor da API.
 *
 * O dashboard é servido pelo próprio backend em produção; no APK não existe
 * "mesma origem", então o usuário aponta para o endereço do servidor
 * (local/LAN durante o desenvolvimento, produção depois).
 */
export function ServerSettings({ onClose }: { onClose?: () => void }) {
  const [url, setUrl] = useState(resolveApiBase());
  const [erro, setErro] = useState<string | null>(null);

  const salvar = () => {
    const valor = url.trim();
    if (!valor) {
      setErro("Informe o endereço do servidor.");
      return;
    }
    if (!/^https?:\/\//.test(valor)) {
      setErro("O endereço precisa começar com http:// ou https://");
      return;
    }
    setApiBase(valor);
    // A base é lida no carregamento do módulo; recarregar aplica o novo valor.
    window.location.reload();
  };

  return (
    <div className="fixed inset-0 z-[200] flex items-center justify-center bg-[#040610] p-5">
      <div className="aurora" />
      <div className="grid-overlay" />
      <div className="relative panel w-full max-w-md p-6 md:p-8 flex flex-col gap-5">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-cyan-500/20 to-violet-500/20 border border-cyan-400/30 flex items-center justify-center">
              <Database className="w-5 h-5 text-cyan-300" />
            </div>
            <div>
              <h2 className="font-display font-bold text-white">Servidor da API</h2>
              <p className="text-xs text-slate-400">Onde o EngineeringOS busca seus dados</p>
            </div>
          </div>
          {onClose && (
            <button onClick={onClose} className="btn-ghost p-2 rounded-lg" aria-label="Fechar">
              <X className="w-4 h-4" />
            </button>
          )}
        </div>

        <label className="flex flex-col gap-1.5">
          <span className="text-[10px] uppercase tracking-[0.14em] text-slate-500 font-bold">
            Endereço
          </span>
          <input
            autoFocus
            value={url}
            onChange={(e) => {
              setUrl(e.target.value);
              setErro(null);
            }}
            placeholder="http://10.0.2.2:8000/api"
            className="input-eos w-full text-sm"
            inputMode="url"
            autoCapitalize="none"
            autoCorrect="off"
            spellCheck={false}
          />
          <span className="text-[10px] text-slate-500">
            Ex.: http://10.0.2.2:8000/api (emulador) · http://192.168.0.10:8000/api (rede local) ·
            https://seu-backend.up.railway.app/api (produção)
          </span>
        </label>

        {erro && (
          <p className="text-xs text-rose-400 bg-rose-500/10 border border-rose-500/25 rounded-lg px-3 py-2">
            {erro}
          </p>
        )}

        <button
          onClick={salvar}
          className="btn-primary font-display px-5 py-3 text-sm flex items-center justify-center gap-2"
        >
          <Check className="w-4 h-4" /> Salvar e conectar
        </button>
      </div>
    </div>
  );
}
