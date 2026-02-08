import { getMe } from "./auth.js";

function qs(id){ return document.getElementById(id); }

function setStatus(msg, ok = false){
  const el = qs("loginStatus");
  if (!el) return;
  el.textContent = msg || "";
  el.className = "authStatus" + (ok ? " ok" : "");
}

async function emailLogin(email, password){
  const res = await fetch("/auth/email/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ email, password })
  });

  if (!res.ok) {
    const txt = await res.text();
    throw new Error(txt || "로그인에 실패했습니다.");
  }
  return res.json();
}

async function boot(){
  const me = await getMe();
  if (me) {
    location.href = "/app";
    return;
  }

  const showBtn = qs("showEmailLoginBtn");
  const form = qs("emailLoginForm");

  if (showBtn && form) {
    showBtn.addEventListener("click", () => {
      form.style.display = "flex";
      showBtn.style.display = "none";
      qs("loginEmail")?.focus();
    });
  }

  form?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const email = qs("loginEmail")?.value?.trim() || "";
    const password = qs("loginPassword")?.value || "";

    if (!email || !password) {
      setStatus("이메일과 비밀번호를 입력해 주세요.");
      return;
    }

    setStatus("로그인 중...");
    try {
      await emailLogin(email, password);
      setStatus("로그인 성공! 이동 중...", true);
      location.href = "/app";
    } catch (err) {
      setStatus(err?.message || "로그인 실패");
    }
  });
}

boot();
