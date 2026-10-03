const BASE = import.meta.env.VITE_API_URL || "";
let access = "",
  refresh = "",
  organization = "";
export function setTokens(t: { access_token: string; refresh_token: string }) {
  access = t.access_token;
  refresh = t.refresh_token;
}
export function setOrganization(id: string) {
  organization = id;
}
export function clearTokens() {
  access = "";
  refresh = "";
  organization = "";
}
let rotating: Promise<void> | null = null;
export async function api<T = any>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const execute = () =>
    fetch(`${BASE}${path}`, {
      ...options,
      headers: {
        ...(options.body instanceof FormData
          ? {}
          : { "Content-Type": "application/json" }),
        ...(access ? { Authorization: `Bearer ${access}` } : {}),
        ...(organization ? { "X-Organization-ID": organization } : {}),
        ...options.headers,
      },
    });
  let response = await execute();
  if (response.status === 401 && refresh && !path.startsWith("/api/auth")) {
    if (!rotating)
      rotating = fetch(`${BASE}/api/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refresh }),
      })
        .then(async (r) => {
          if (!r.ok) {
            clearTokens();
            throw Error("Your session expired. Please sign in again.");
          }
          setTokens(await r.json());
        })
        .finally(() => {
          rotating = null;
        });
    await rotating;
    response = await execute();
  }
  if (!response.ok) {
    const e = await response
      .json()
      .catch(() => ({ detail: "Service is unavailable" }));
    throw Error(
      typeof e.detail === "string"
        ? e.detail
        : Array.isArray(e.detail)
          ? e.detail
              .map((d: any) => `${d.loc?.slice(1).join(".")}: ${d.msg}`)
              .join("; ")
          : "Request failed",
    );
  }
  return response.json();
}
export function post<T = any>(path: string, data: unknown, method = "POST") {
  return api<T>(path, { method, body: JSON.stringify(data) });
}
export async function download(path: string, name: string) {
  const r = await fetch(`${BASE}${path}`, {
    headers: {
      Authorization: `Bearer ${access}`,
      "X-Organization-ID": organization,
    },
  });
  if (!r.ok) throw Error("Export failed");
  const url = URL.createObjectURL(await r.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}
export async function signOut() {
  try {
    await post("/api/auth/logout", { refresh_token: refresh });
  } finally {
    clearTokens();
  }
}
