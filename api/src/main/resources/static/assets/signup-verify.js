import { getMe } from "./auth.js";

function qs(id){ return document.getElementById(id); }

function setStatus(msg, ok = false){
  const el = qs("verifyStatus");
  if (!el) return;
  el.textContent = msg || "";
  el.className = "authStatus" + (ok ? " ok" : "");
}

async function verifyCode(email, code){
  const res = await fetch("/auth/email/verify", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ email, code })
  });

  if (!res.ok) {
    const txt = await res.text();
    let message = txt;
    try {
      const json = JSON.parse(txt);
      message = json?.message || message;
    } catch {}
    throw new Error(message || "인증 실패");
  }
  return res.json();
}

async function resendCode(email){
  const res = await fetch("/auth/email/resend", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ email })
  });

  if (!res.ok) {
    const txt = await res.text();
    let message = txt;
    try {
      const json = JSON.parse(txt);
      message = json?.message || message;
    } catch {}
    throw new Error(message || "재전송 실패");
  }
  return res.json();
}

async function boot(){
  const me = await getMe();
  if (me) {
    location.href = "/app";
    return;
  }

  const params = new URLSearchParams(location.search);
  const email = params.get("email") || "";
  qs("verifyEmailView").textContent = email;

  qs("verifyForm")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const code = (qs("verifyCode")?.value || "").trim();

    if (!email) {
      setStatus("이메일 정보가 없습니다. 가입을 다시 진행해 주세요.");
      return;
    }
    if (!/^\d{6}$/.test(code)) {
      setStatus("6자리 인증 코드를 입력해 주세요.");
      return;
    }

    setStatus("인증 중...");
    try {
      await verifyCode(email, code);
      setStatus("인증 성공! 로그인 페이지로 이동합니다.", true);
      setTimeout(() => {
        location.href = "/login";
      }, 800);
    } catch (err) {
      setStatus(err?.message || "인증 실패");
    }
  });

  qs("resendCodeBtn")?.addEventListener("click", async () => {
    if (!email) {
      setStatus("이메일 정보가 없습니다. 가입을 다시 진행해 주세요.");
      return;
    }

    setStatus("인증코드 재전송 중...");
    try {
      await resendCode(email);
      setStatus("인증코드를 다시 보냈습니다.", true);
    } catch (err) {
      setStatus(err?.message || "재전송 실패");
    }
  });
}

boot();
