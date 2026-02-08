import { initHeader, apiFetch } from "./auth.js";

function qs(id){ return document.getElementById(id); }
function escapeHtml(s){
  return (s||"").replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;");
}

async function fetchMyJobs(){
  const res = await apiFetch("/v1/me/jobs");
  if(!res.ok) throw new Error(await res.text());
  return await res.json();
}

function fmt(ts){
  if(!ts) return "";
  try{
    const d = new Date(ts);
    return d.toLocaleString();
  }catch{ return String(ts); }
}

function renderList(items){
  const list = qs("jobList");
  if(!items?.length){
    list.innerHTML = '<div class="muted2">아직 만든 기록이 없습니다.</div>';
    return;
  }
  list.innerHTML = items.map(it=>{
    const videoStatus = it.videoStatus || "NONE";
    const videoLink = it.hasVideo ? `<a class="btn ghost sm" href="/v1/jobs/${it.jobId}/video" target="_blank" rel="noopener">영상 보기</a>` : '';
    const createdLabel = fmt(it.createdAt) || "생성 시간 정보 없음";
    return `
      <div class="rowItem">
        <div class="rowMain">
          <div class="rowTitle">${escapeHtml(createdLabel)}</div>
          <div class="rowMeta">풀이:${escapeHtml(it.status)} · 영상:${escapeHtml(videoStatus)} · ${escapeHtml(fmt(it.createdAt))}</div>
        </div>
        <div class="rowActions">
          <a class="btn sm" href="/app?jobId=${encodeURIComponent(it.jobId)}">열기</a>
          ${videoLink}
        </div>
      </div>
    `;
  }).join("");
}

async function boot(){
  const me = await initHeader("mypage", { requireAuth: true });
  if(!me) return;

  async function refresh(){
    try{
      const items = await fetchMyJobs();
      renderList(items);
    }catch(e){
      alert("기록 불러오기에 실패했습니다.");
    }
  }

  qs("refreshBtn").addEventListener("click", refresh);
  refresh();
}
boot();
