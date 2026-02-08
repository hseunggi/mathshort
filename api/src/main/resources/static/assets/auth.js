export const LOGIN_URL = "/login";

export async function apiFetch(url, options = {}) {
  const opts = { credentials: "include", ...options };
  const res = await fetch(url, opts);
  return res;
}

export async function getMe() {
  const res = await fetch("/auth/me", { credentials: "include" });
  if (res.status === 401) return null;   
  if (!res.ok) throw new Error(await res.text());
  return await res.json();
}

export async function requireLogin() {
  const me = await getMe();
  if (!me) {
    location.href = LOGIN_URL;
    return null;
  }
  return me;
}

export async function login(username, password) {
  const res = await apiFetch("/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password })
  });
  if (!res.ok) throw new Error(await res.text());
  return await res.json();
}

export async function register(username, password) {
  const res = await apiFetch("/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password })
  });
  if (!res.ok) throw new Error(await res.text());
  return await res.json();
}

export async function logout() {
  await apiFetch("/auth/logout", { method: "POST" });
}

export function setActiveTab(tab) {
  document.querySelectorAll("[data-nav]").forEach((el) => {
    el.classList.toggle("active", el.dataset.nav === tab);
  });
}

export async function initHeader(tab, { requireAuth = false } = {}) {
  setActiveTab(tab);

  const me = await getMe();
  const loginBtn = document.getElementById("headerLoginBtn");
  const user = document.getElementById("headerUser");
  const logoutBtn = document.getElementById("headerLogoutBtn");

  if (me?.username) {
    if (user) user.style.display = "none";
    if (logoutBtn) logoutBtn.style.display = "";
    if (loginBtn) loginBtn.style.display = "none";

    if (logoutBtn) {
      logoutBtn.onclick = async () => {
        try {
          await logout();
        } finally {
          location.href = "/";
        }
      };
    }
  } else {
    if (user) user.style.display = "none";
    if (logoutBtn) logoutBtn.style.display = "none";
    if (loginBtn) {
      loginBtn.style.display = "";
      loginBtn.onclick = () => (location.href = LOGIN_URL);
    }

    if (requireAuth) {
      location.href = LOGIN_URL;
      return null;
    }
  }

  return me;
}

// backward-compat
export function wireNav(me) {
  const who = document.getElementById("whoami") || document.getElementById("headerUser");
  if (who) who.style.display = "none";
}
