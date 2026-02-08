import { register, getMe } from "./auth.js";

function qs(id){ return document.getElementById(id); }
function setStatus(msg, ok=false){
  const el = qs("regStatus");
  el.textContent = msg || "";
  el.className = "status " + (ok ? "ok" : "");
}

async function boot(){
  const me = await getMe();
  if (me) location.href = "/app";
}

qs("registerBtn").addEventListener("click", async () => {
  const username = qs("regUser").value.trim();
  const password = qs("regPass").value;
  if(!username || !password){ setStatus("아이디/비밀번호를 입력해 주세요."); return; }
  if(username.length < 3 || username.length > 64){ setStatus("아이디는 3~64자여야 합니다."); return; }
  if(password.length < 6 || password.length > 200){ setStatus("비밀번호는 6~200자여야 합니다."); return; }
  setStatus("가입 중...");
  try{
    await register(username, password);
    setStatus("회원가입 성공! 로그인 페이지로 이동합니다...", true);
    setTimeout(() => {
      location.href = "/login";
    }, 1500);
  }catch(e){
    setStatus("회원가입 실패: " + (e?.message || "unknown"));
  }
});

qs("regPass").addEventListener("keydown", (e)=>{ if(e.key==="Enter") qs("registerBtn").click(); });
boot();
