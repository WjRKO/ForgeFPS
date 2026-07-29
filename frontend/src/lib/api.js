import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

const api = axios.create({
  baseURL: API,
  withCredentials: true,
});

// Auto-refresh della sessione: al primo 401 tenta /auth/refresh (refresh token
// httpOnly, 7 giorni sliding) e riprova la richiesta originale. Le richieste
// concorrenti condividono la stessa promise di refresh.
const NO_REFRESH = ["/auth/refresh", "/auth/login", "/auth/register", "/auth/logout"];
let refreshPromise = null;

api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config;
    const status = error.response?.status;
    const url = original?.url || "";
    if (status !== 401 || !original || original._retry || NO_REFRESH.some((p) => url.includes(p))) {
      return Promise.reject(error);
    }
    original._retry = true;
    try {
      if (!refreshPromise) {
        refreshPromise = api.post("/auth/refresh").finally(() => { refreshPromise = null; });
      }
      await refreshPromise;
      return api(original);
    } catch {
      return Promise.reject(error);
    }
  }
);

export function formatApiErrorDetail(detail) {
  if (detail == null) return "Qualcosa è andato storto. Riprova.";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail))
    return detail.map((e) => (e && typeof e.msg === "string" ? e.msg : JSON.stringify(e))).filter(Boolean).join(" ");
  if (detail && typeof detail.msg === "string") return detail.msg;
  return String(detail);
}

export default api;
