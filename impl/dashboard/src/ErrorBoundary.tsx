import React from "react";

interface State {
  error: Error | null;
  info: string;
}

/**
 * Sem isto, qualquer erro de render derruba a árvore React inteira e o que
 * sobra é o fundo escuro do body — indistinguível de uma "tela preta" de
 * compositor. Com isto, o erro aparece na tela e vira diagnóstico.
 */
export class ErrorBoundary extends React.Component<{ children: React.ReactNode }, State> {
  state: State = { error: null, info: "" };

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error("EngineeringOS — erro de render:", error, info);
    this.setState({ info: (info.componentStack || "").split("\n").slice(0, 6).join("\n") });
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="min-h-screen flex items-center justify-center p-8 bg-[#0f1425] text-slate-200">
        <div className="max-w-lg w-full rounded-2xl border border-rose-500/30 bg-rose-500/[0.06] p-6">
          <h1 className="font-display text-lg font-bold text-rose-300 mb-2">
            A interface encontrou um erro
          </h1>
          <p className="text-sm text-slate-300 mb-4">
            A tela não ficou preta: isto é o erro que a causaria. Copie a mensagem abaixo — ela
            identifica exatamente o ponto da falha.
          </p>
          <pre className="text-[11px] text-rose-200/90 bg-black/40 rounded-lg p-3 overflow-auto max-h-56 whitespace-pre-wrap">
            {String(this.state.error?.message || this.state.error)}
            {this.state.info ? "\n" + this.state.info : ""}
          </pre>
          <button
            onClick={() => window.location.reload()}
            className="btn-primary mt-4 px-5 py-2.5 text-sm font-display"
          >
            Recarregar
          </button>
        </div>
      </div>
    );
  }
}
