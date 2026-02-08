import { getMe } from "./auth.js";

function qs(id){ return document.getElementById(id); }

function setStatus(msg, ok = false){
  const el = qs("signupStatus");
  if (!el) return;
  el.textContent = msg || "";
  el.className = "authStatus" + (ok ? " ok" : "");
}

async function signupByEmail(email, password){
  const res = await fetch("/auth/email/signup-start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ email, password })
  });

  if (!res.ok) {
    const txt = await res.text();
    let message = txt;
    try {
      const json = JSON.parse(txt);
      message = json?.message || message;
    } catch {}
    throw new Error(message || "가입 요청에 실패했습니다.");
  }
  return res.json();
}

async function boot(){
  const me = await getMe();
  if (me) {
    location.href = "/app";
    return;
  }

  qs("emailSignupForm")?.addEventListener("submit", async (e) => {
    e.preventDefault();

    const email = qs("signupEmail")?.value?.trim() || "";
    const password = qs("signupPassword")?.value || "";

    if (!email || !password) {
      setStatus("이메일과 비밀번호를 입력해 주세요.");
      return;
    }

    setStatus("인증 메일 발송 중...");
    try {
      const data = await signupByEmail(email, password);
      setStatus("인증 메일을 보냈습니다. 인증 페이지로 이동합니다.", true);
      location.href = data?.next || `/signup/verify?email=${encodeURIComponent(email)}`;
    } catch (err) {
      setStatus(err?.message || "가입 요청 실패");
    }
  });
}

boot();
