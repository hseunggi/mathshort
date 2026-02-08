import { initHeader, apiFetch } from "./auth.js";

let pollTimer = null;
let currentJobId = null;
let previewObjectUrl = null;

function qs(id){ return document.getElementById(id); }
function setSolveStatus(msg, ok=false){
  const el = qs("jobStatus");
  if(!el) return;
  el.textContent = msg || "";
  el.className = "status " + (ok ? "ok" : "");
}
function setVideoStatus(msg, ok=false){
  const el = qs("videoStatus");
  if(!el) return;
  el.textContent = msg || "";
  el.className = "status " + (ok ? "ok" : "");
}
function escapeHtml(s){
  return (s||"").replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;");
}

function normalizeLegacyMathText(s){
  let t = String(s ?? "");
  t = t.replaceAll("₩", String.fromCharCode(92));
  // 기존 기록에 남은 W토큰/LaTeX 토큰 최소 치환
  t = t.replaceAll("Wcdot", "×")
       .replaceAll("Wtimes", "×")
       .replaceAll("WRightarrow", "→")
       .replaceAll("Wrightarrow", "→")
       .replaceAll("Wle", "≤")
       .replaceAll("Wge", "≥")
       .replaceAll("Wneq", "≠")
       .replaceAll("\\cdot", "×")
       .replaceAll("\\times", "×")
       .replaceAll("\\Rightarrow", "→")
       .replaceAll("\\rightarrow", "→")
       .replaceAll("\\le", "≤")
       .replaceAll("\\ge", "≥")
       .replaceAll("\\neq", "≠");
  return t;
}

function setVideoButtonState(enabled, reason=""){
  const btn = qs("videoBtn");
  if(!btn) return;
  btn.disabled = !enabled;
  btn.title = enabled ? "" : (reason || "풀이 완료 후 영상 생성이 가능합니다.");
}

async function createJob(file){
  const fd = new FormData();
  fd.append("file", file);
  const res = await apiFetch("/v1/jobs", { method:"POST", body: fd });
  if(!res.ok) throw new Error(await res.text());
  return await res.json();
}

async function requestVideo(jobId){
  const res = await apiFetch(`/v1/jobs/${jobId}/video`, { method:"POST" });
  if(!res.ok) throw new Error(await res.text());
  return await res.json();
}

async function getJob(jobId){
  const res = await apiFetch(`/v1/jobs/${jobId}`);
  if(!res.ok) throw new Error(await res.text());
  return await res.json();
}

function solveStatusMessage(job){
  if(job.status === "PENDING") return "풀이 생성 대기 중입니다…";
  if(job.status === "RUNNING") return "풀이 생성 중입니다…";
  if(job.status === "DONE") return "풀이 생성이 완료되었습니다.";
  if(job.status === "FAIL") return "풀이 생성 오류가 발생했습니다.";
  return job.status;
}

function videoStatusMessage(job){
  const videoStatus = job.videoStatus || "NONE";
  if(videoStatus === "PENDING") return "영상 생성 대기 중입니다…";
  if(videoStatus === "RUNNING") return "영상 생성 중입니다…";
  if(videoStatus === "DONE") return "영상 생성이 완료되었습니다.";
  if(videoStatus === "FAIL") return "영상 생성 오류가 발생했습니다.";
  return "";
}

async function renderJob(job){
  const videoStatus = job.videoStatus || "NONE";
  setSolveStatus(solveStatusMessage(job), job.status === "DONE");
  setVideoStatus(videoStatusMessage(job), videoStatus === "DONE");

  const solutionToggleBtn = qs("solutionToggleBtn");
  if(solutionToggleBtn){
    const canToggleSolution = job.status === "DONE" && !!job.detailJson;
    solutionToggleBtn.style.display = canToggleSolution ? "" : "none";
  }

  const canRequestVideo = (job.status === "DONE") || !!job.detailJson;
  setVideoButtonState(canRequestVideo, "먼저 풀이 만들기를 완료해 주세요.");

  // video
  const player = qs("player");
  const dl = qs("downloadBtn");
  if(job.outputMp4Path){
    const url = `/v1/jobs/${job.jobId}/video`;
    player.src = url;
    player.style.display = "";
    dl.href = url;
    dl.style.display = "";
  }else{
    player.removeAttribute("src");
    player.style.display = "none";
    dl.style.display = "none";
  }

  // solution
  const box = qs("solutionBox");
  box.innerHTML = "";
  if(job.detailJson){
    try{
      const d = JSON.parse(job.detailJson);
      if(Array.isArray(d.steps)){
        const parts = [];
        for(const st of d.steps){
          const t = st.title ? `<div class="stepTitle">${escapeHtml(st.title)}</div>` : "";
          const f = st.formula
            ? `<div class="stepBody"><b>수식:</b> <span class="formula math">\\(${st.formula}\\)</span></div>`
            : "";
          const b = st.explanation
            ? `<div class="stepBody">${escapeHtml(normalizeLegacyMathText(st.explanation)).replaceAll("\n","<br/>")}</div>`
            : (st.body ? `<div class="stepBody">${escapeHtml(normalizeLegacyMathText(st.body)).replaceAll("\n","<br/>")}</div>` : "");
          const c = st.check
            ? `<div class="stepBody"><b>점검:</b> ${escapeHtml(normalizeLegacyMathText(st.check)).replaceAll("\n","<br/>")}</div>`
            : "";
          parts.push(`<div class="step">${t}${f}${b}${c}</div>`);
        }

        if(d.finalAnswer){
          parts.push(`<div class="step"><div class="stepTitle">정답</div><div class="stepBody">${escapeHtml(d.finalAnswer).replaceAll("\n","<br/>")}</div></div>`);
        }

        if(Array.isArray(d.notes) && d.notes.length){
          const notesHtml = d.notes.map(n => `<li>${escapeHtml(String(n))}</li>`).join("");
          parts.push(`<div class="step"><div class="stepTitle">노트</div><div class="stepBody"><ul>${notesHtml}</ul></div></div>`);
        }

        box.innerHTML = parts.join("");
      }else{
        box.innerHTML = `<pre class="pre">${escapeHtml(job.detailJson)}</pre>`;
      }
      if(window.MathJax?.typesetPromise) window.MathJax.typesetPromise();
    }catch(_e){
      box.innerHTML = `<pre class="pre">${escapeHtml(job.detailJson)}</pre>`;
    }
  }else if(job.errorMessage){
    box.innerHTML = `<div class="err">${escapeHtml(job.errorMessage)}</div>`;
  }else{
    box.innerHTML = `<div class="muted2">아직 풀이가 없습니다.</div>`;
  }
}

function startPolling(jobId){
  if(pollTimer) clearInterval(pollTimer);
  pollTimer = setInterval(async ()=>{
    try{
      const job = await getJob(jobId);
      await renderJob(job);
      const solveDone = (job.status === "DONE" || job.status === "FAIL");
      const videoStatus = job.videoStatus || "NONE";
      const videoDone = (videoStatus === "NONE" || videoStatus === "DONE" || videoStatus === "FAIL");
      if(solveDone && videoDone){
        clearInterval(pollTimer);
        pollTimer = null;
      }
    }catch(e){
      clearInterval(pollTimer);
      pollTimer = null;
      setSolveStatus("조회 실패: " + (e?.message||""));
      setVideoStatus("조회 실패: " + (e?.message||""));
    }
  }, 1500);
}

function getQueryJobId(){
  const u = new URL(location.href);
  return u.searchParams.get("jobId");
}

function bindUploadPreview(){
  const input = qs("fileInput");
  const img = qs("previewImg");
  const dropzone = qs("uploadDropzone");
  if(!input || !img || !dropzone) return;

  const setFileToInput = (file)=>{
    const dt = new DataTransfer();
    dt.items.add(file);
    input.files = dt.files;
  };

  const renderPreview = (file)=>{
    if(previewObjectUrl){
      URL.revokeObjectURL(previewObjectUrl);
      previewObjectUrl = null;
    }

    if(!file || !file.type.startsWith("image/")){
      img.removeAttribute("src");
      img.classList.remove("show");
      dropzone.classList.remove("hasImage");
      return;
    }

    previewObjectUrl = URL.createObjectURL(file);
    img.src = previewObjectUrl;
    img.classList.add("show");
    dropzone.classList.add("hasImage");
  };

  const handleSelectedFile = (file)=>{
    if(!file) return;
    setFileToInput(file);
    renderPreview(file);
  };

  dropzone.addEventListener("click", ()=> input.click());
  dropzone.addEventListener("keydown", (e)=>{
    if(e.key === "Enter" || e.key === " "){
      e.preventDefault();
      input.click();
    }
  });

  ["dragenter", "dragover"].forEach((evt)=>{
    dropzone.addEventListener(evt, (e)=>{
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.add("dragover");
    });
  });

  ["dragleave", "dragend", "drop"].forEach((evt)=>{
    dropzone.addEventListener(evt, (e)=>{
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.remove("dragover");
    });
  });

  dropzone.addEventListener("drop", (e)=>{
    const file = e.dataTransfer?.files?.[0];
    if(!file) return;
    handleSelectedFile(file);
  });

  input.addEventListener("change", ()=>{
    const file = input.files?.[0];
    renderPreview(file);
  });
}

function bindSolutionToggle(){
  const btn = qs("solutionToggleBtn");
  const body = qs("solutionBody");
  if(!btn || !body) return;

  const setCollapsed = (collapsed)=>{
    body.style.display = collapsed ? "none" : "";
    btn.textContent = collapsed ? "펼치기" : "접기";
    btn.setAttribute("aria-expanded", collapsed ? "false" : "true");
  };

  let collapsed = false;
  btn.addEventListener("click", ()=>{
    collapsed = !collapsed;
    setCollapsed(collapsed);
  });

  setCollapsed(false);
}

async function boot(){
  const me = await initHeader("upload", { requireAuth: true });
  if(!me) return;
  bindSolutionToggle();
  bindUploadPreview();
  setVideoButtonState(false, "먼저 풀이 만들기를 완료해 주세요.");
  setVideoStatus("");

  qs("solveBtn").addEventListener("click", async ()=>{
    const file = qs("fileInput").files?.[0];
    if(!file){ setSolveStatus("PNG 파일을 선택해 주세요."); return; }
    if(!file.name.toLowerCase().endsWith(".png")){ setSolveStatus("PNG 파일만 업로드 가능합니다."); return; }

    setSolveStatus("업로드 및 풀이 생성 요청 중...");
    try{
      const created = await createJob(file);
      const jobId = created.jobId;
      currentJobId = jobId;
      setVideoButtonState(false, "풀이 생성 완료 후 영상 만들기가 가능합니다.");
      setSolveStatus("풀이 생성이 시작되었습니다.", true);

      const u = new URL(location.href);
      u.searchParams.set("jobId", jobId);
      history.replaceState({}, "", u.toString());
      startPolling(jobId);
    }catch(e){
      setSolveStatus("업로드 실패: " + (e?.message||""));
    }
  });

  qs("videoBtn").addEventListener("click", async ()=>{
    const targetJobId = currentJobId || getQueryJobId();
    if(!targetJobId){
      setVideoStatus("먼저 '풀이 만들기'를 통해 job을 생성해 주세요.");
      return;
    }

    try{
      const latest = await getJob(targetJobId);
      const canVideo = latest.status === "DONE" || !!latest.detailJson;
      if(!canVideo){
        setVideoButtonState(false, "먼저 풀이 만들기를 완료해 주세요.");
        setVideoStatus("영상 생성은 풀이 완료 후에만 가능합니다.");
        return;
      }
    }catch(_e){
      setVideoStatus("작업 상태 확인에 실패했습니다. 잠시 후 다시 시도해 주세요.");
      return;
    }

    setVideoStatus("영상 생성 요청 중...");
    try{
      await requestVideo(targetJobId);
      setVideoStatus("영상 생성이 시작되었습니다.", true);
      startPolling(targetJobId);
    }catch(e){
      setVideoStatus("영상 생성 요청 실패: " + (e?.message||""));
    }
  });

  const qJob = getQueryJobId();
  if(qJob){
    currentJobId = qJob;
    setSolveStatus("기록 불러오는 중...");
    try{
      const job = await getJob(qJob);
      await renderJob(job);
      if(job.status !== "DONE" && job.status !== "FAIL") startPolling(qJob);
      const videoStatus = job.videoStatus || "NONE";
      if(videoStatus === "PENDING" || videoStatus === "RUNNING") startPolling(qJob);
    }catch(e){
      setSolveStatus("불러오기 실패: " + (e?.message||""));
      setVideoStatus("불러오기 실패: " + (e?.message||""));
    }
  }
}
boot();
