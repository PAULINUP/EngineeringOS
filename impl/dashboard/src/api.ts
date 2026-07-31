// Endereço da API do EngineeringOS.
//
// IMPORTANTE: use 127.0.0.1, não "localhost". No Windows, "localhost" resolve
// primeiro para o IPv6 ::1; como o servidor escuta em IPv4 (0.0.0.0), cada
// requisição espera ~2s pelo timeout antes de cair para IPv4 — um overhead
// fixo que degradava toda a interface.
export const API_BASE =
  (import.meta.env.VITE_API_BASE as string | undefined) ?? "http://127.0.0.1:8000/api";
