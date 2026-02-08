import os
import json
import redis
import base64
import re
import shutil
import subprocess
from pathlib import Path
from io import BytesIO

from sqlalchemy import create_engine, text
from openai import OpenAI
from PIL import Image, ImageDraw, ImageFont, ImageFilter

QUEUE_KEY = "queue:jobs"
VIDEO_QUEUE_KEY = "queue:video_jobs"

# ===== global video settings =====
FPS = 30
W, H = 1080, 1920

TOP_RATIO = 0.62
TOP_H = int(H * TOP_RATIO)

TARGET_TOTAL_SEC = 60.0

FORMULA_MAX_LINES = 4
EXPL_MAX_LINES = 2

# ----- optional: LaTeX render via matplotlib (best) -----
# If matplotlib isn't available in your runtime image, we fallback to plain-text rendering.
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    MATPLOTLIB_OK = True
except Exception:
    MATPLOTLIB_OK = False

# small in-memory cache for rendered math images
_MATH_IMG_CACHE: dict[tuple[str, int], Image.Image] = {}


# =======================
# DB helpers
# =======================
def mysql_url():
    host = os.getenv("MYSQL_HOST", "mysql")
    port = os.getenv("MYSQL_PORT", "3306")
    db = os.getenv("MYSQL_DB", "mathshort")
    user = os.getenv("MYSQL_USER", "mathshort")
    pw = os.getenv("MYSQL_PASSWORD", "mathshort")
    return f"mysql+pymysql://{user}:{pw}@{host}:{port}/{db}?charset=utf8mb4"

def update_running(engine, job_id: str):
    sql = text("UPDATE jobs SET status='RUNNING', updated_at=NOW(), error_message=NULL WHERE id=UUID_TO_BIN(:id)")
    with engine.begin() as conn:
        conn.execute(sql, {"id": job_id})

def update_fail(engine, job_id: str, msg: str):
    sql = text("UPDATE jobs SET status='FAIL', updated_at=NOW(), error_message=:msg WHERE id=UUID_TO_BIN(:id)")
    with engine.begin() as conn:
        conn.execute(sql, {"id": job_id, "msg": msg[:8000]})

def update_done(engine, job_id: str, detail_json: str):
    sql = text("""
        UPDATE jobs
        SET status='DONE',
            updated_at=NOW(),
            detail_json=:json
        WHERE id=UUID_TO_BIN(:id)
    """)
    with engine.begin() as conn:
        conn.execute(sql, {"id": job_id, "json": detail_json})

def update_video_pending(engine, job_id: str):
    sql = text("""
        UPDATE jobs
        SET video_status='PENDING', updated_at=NOW(), video_error_message=NULL
        WHERE id=UUID_TO_BIN(:id)
    """)
    with engine.begin() as conn:
        conn.execute(sql, {"id": job_id})

def update_video_running(engine, job_id: str):
    sql = text("""
        UPDATE jobs
        SET video_status='RUNNING', updated_at=NOW(), video_error_message=NULL
        WHERE id=UUID_TO_BIN(:id)
    """)
    with engine.begin() as conn:
        conn.execute(sql, {"id": job_id})

def update_video_done(engine, job_id: str, mp4_path: str):
    sql = text("""
        UPDATE jobs
        SET output_mp4_path=:p,
            video_status='DONE',
            updated_at=NOW(),
            video_error_message=NULL
        WHERE id=UUID_TO_BIN(:id)
    """)
    with engine.begin() as conn:
        conn.execute(sql, {"id": job_id, "p": mp4_path})

def update_video_fail(engine, job_id: str, msg: str):
    sql = text("""
        UPDATE jobs
        SET video_status='FAIL',
            updated_at=NOW(),
            video_error_message=:msg
        WHERE id=UUID_TO_BIN(:id)
    """)
    with engine.begin() as conn:
        conn.execute(sql, {"id": job_id, "msg": msg[:8000]})

def update_video_path(engine, job_id: str, mp4_path: str):
    sql = text("""
        UPDATE jobs
        SET output_mp4_path=:p, updated_at=NOW()
        WHERE id=UUID_TO_BIN(:id)
    """)
    with engine.begin() as conn:
        conn.execute(sql, {"id": job_id, "p": mp4_path})

def get_detail_json(engine, job_id: str) -> str:
    sql = text("SELECT detail_json FROM jobs WHERE id=UUID_TO_BIN(:id)")
    with engine.begin() as conn:
        row = conn.execute(sql, {"id": job_id}).mappings().first()
        if not row:
            raise RuntimeError("job not found")
        return row.get("detail_json") or ""

def get_input_png(engine, job_id: str) -> str:
    sql = text("SELECT input_png_path FROM jobs WHERE id=UUID_TO_BIN(:id)")
    with engine.begin() as conn:
        row = conn.execute(sql, {"id": job_id}).mappings().first()
        if not row:
            raise RuntimeError("job not found")
        return row["input_png_path"]


# =======================
# OpenAI helpers
# =======================
def extract_problem_text(client: OpenAI, png_path: str) -> str:
    with open(png_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode("utf-8")

    resp = client.responses.create(
        model=os.getenv("OPENAI_VISION_MODEL", "gpt-5.2"),
        input=[{
            "role": "user",
            "content": [
                {"type": "input_text",
                 "text": "다음 이미지의 수학 문제를 텍스트로 정확히 추출해줘. 불필요한 설명 없이 문제 텍스트만 출력."},
                {"type": "input_image",
                 "image_url": f"data:image/png;base64,{img_b64}"}
            ]
        }],
    )
    return resp.output_text.strip()

def solve_math_to_json(client: OpenAI, problem_text: str) -> dict:
    prompt = f"""
너는 수학 풀이 튜터다.
아래 문제를 보고, 웹/영상에서 쓰기 좋은 JSON만 출력해라.
규칙:
- 반드시 JSON만 출력(코드블록 금지)
- steps는 최소 4단계 이상
- 각 step에는 title, explanation(텍스트), formula(없으면 null), check(검산/검증 또는 한줄 점검) 포함
- formula 필드는 반드시 LaTeX 수식만 작성(자연어 금지)
- formula에는 \\int, \\frac{a}{b}, x^{2}, a_{n}, \\Rightarrow 등 LaTeX 명령어를 사용
- 백슬래시는 반드시 \\ 사용(₩ 금지)
- 가능한 한 지수/첨자는 ^{{}}, _{{}} 형태의 표준 LaTeX로 출력
- explanation/check/tts/title에는 LaTeX 문법(\\, ^, _, {{}}) 사용 금지
- explanation/check/tts/title은 일반 텍스트만 사용하고, 필요 시 기호는 ×, ÷, →, ≤, ≥처럼 일반 유니코드 문자로 표기
- 추가로 steps[i].tts 를 반드시 작성:
  - 선생님이 말로 설명하듯 1~2문장
  - 화면 문장을 그대로 읽지 말기
  - 문장 시작을 매번 "이 단계에서는..."으로 반복 금지
  - 길이 너무 길면 잘릴 수 있으니 20~60자 정도 권장
- introHook도 반드시 작성:
  - "핵심은 ~" 형태로 1문장(20자 이하)
- finalAnswer는 마지막에 한 번만

출력 스키마:
{{
  "problemText": "...",
  "concept": "문제 유형 요약(짧게,20자 이하)",
  "introHook": "이 유형의 핵심 한 문장(20자 이하)",
  "steps": [
    {{
      "idx": 1,
      "title": "...",
      "explanation": "...",
      "formula": "..." or null,
      "check": "...",
      "tts": "..."
    }}
  ],
  "finalAnswer": "...",
  "notes": ["실수 포인트", "팁"]
}}

문제:
{problem_text}
""".strip()


    resp = client.responses.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4.1"),
        input=prompt,
        reasoning={"effort": os.getenv("OPENAI_REASONING_EFFORT", "medium")},
    )
    text_out = (resp.output_text or "").strip()

    parsed = _parse_json_lenient(text_out)
    if parsed is not None:
        parsed.setdefault("problemText", problem_text)
        parsed.setdefault("concept", "")
        parsed.setdefault("steps", [])
        parsed.setdefault("finalAnswer", "")
        parsed.setdefault("notes", [])
        return parsed

    return {
        "problemText": problem_text,
        "concept": "parse-failed",
        "steps": [],
        "finalAnswer": "",
        "notes": [],
        "raw": text_out
    }


def _parse_json_lenient(text_out: str) -> dict | None:
    """
    모델 출력이 코드블록/설명문을 섞어도 JSON 본문만 최대한 복구해서 파싱한다.
    """
    if not text_out:
        return None

    # 1) 원문 그대로 시도
    try:
        obj = json.loads(text_out)
        return obj if isinstance(obj, dict) else None
    except Exception:
        pass

    # 2) ```json ... ``` 코드블록 제거 후 시도
    cleaned = re.sub(r"^```(?:json)?\s*", "", text_out.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned.strip())
    try:
        obj = json.loads(cleaned)
        return obj if isinstance(obj, dict) else None
    except Exception:
        pass

    # 3) 첫 '{' ~ 마지막 '}' 구간만 추출해 시도
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = cleaned[start:end + 1]
        try:
            obj = json.loads(candidate)
            return obj if isinstance(obj, dict) else None
        except Exception:
            return None

    return None


def solve_math_from_png_to_json(client: OpenAI, png_path: str) -> dict:
    with open(png_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode("utf-8")

    prompt = """
너는 수학 풀이 튜터다.
이미지의 문제를 읽고, 아래 스키마의 JSON만 출력해라.
규칙:
- 반드시 JSON만 출력(코드블록 금지)
- steps는 최소 4단계 이상
- 각 step에는 title, explanation(텍스트), formula(없으면 null), check(검산/검증 또는 한줄 점검), tts 포함
- formula 필드는 반드시 LaTeX 수식만 작성(자연어 금지)
- formula에는 \\int, \\frac{a}{b}, x^{2}, a_{n}, \\Rightarrow 등 LaTeX 명령어를 사용
- 백슬래시는 반드시 \\ 사용(₩ 금지)
- 가능한 한 지수/첨자는 ^{}, _{} 형태의 표준 LaTeX로 출력
- explanation/check/tts/title에는 LaTeX 문법(\\, ^, _, {{}}) 사용 금지
- explanation/check/tts/title은 일반 텍스트만 사용하고, 필요 시 기호는 ×, ÷, →, ≤, ≥처럼 일반 유니코드 문자로 표기
- introHook 포함 ("핵심은 ~" 1문장)
- finalAnswer는 마지막에 한 번만

출력 스키마:
{
  "problemText": "...",
  "concept": "문제 유형 요약(20자 이하)",
  "introHook": "핵심 한 문장(20자 이하)",
  "steps": [
    {
      "idx": 1,
      "title": "...",
      "explanation": "...",
      "formula": "..." or null,
      "check": "...",
      "tts": "..."
    }
  ],
  "finalAnswer": "...",
  "notes": ["...", "..."]
}
""".strip()

    resp = client.responses.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4.1"),
        input=[{
            "role": "user",
            "content": [
                {"type": "input_text", "text": prompt},
                {"type": "input_image", "image_url": f"data:image/png;base64,{img_b64}"}
            ]
        }],
        reasoning={"effort": os.getenv("OPENAI_REASONING_EFFORT", "medium")},
    )

    text_out = (resp.output_text or "").strip()
    parsed = _parse_json_lenient(text_out)
    if parsed is not None:
        parsed.setdefault("problemText", "")
        parsed.setdefault("concept", "")
        parsed.setdefault("steps", [])
        parsed.setdefault("finalAnswer", "")
        parsed.setdefault("notes", [])
        return parsed

    return {
        "problemText": "",
        "concept": "parse-failed",
        "steps": [],
        "finalAnswer": "",
        "notes": [],
        "raw": text_out,
    }


# =======================
# Media helpers
# =======================
def safe_mkdir(p: Path):
    p.mkdir(parents=True, exist_ok=True)

def probe_duration_sec(path: Path) -> float:
    out = subprocess.check_output([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=nw=1:nk=1",
        str(path)
    ]).decode().strip()
    return float(out)

def tts_to_mp3(client: OpenAI, model: str, voice: str, text_in: str, out_path: Path):
    with client.audio.speech.with_streaming_response.create(
        model=model,
        voice=voice,
        input=text_in
    ) as resp:
        resp.stream_to_file(str(out_path))

def normalize_mp3(in_path: Path, out_path: Path):
    subprocess.run([
        "ffmpeg", "-y",
        "-i", str(in_path),
        "-ar", "44100", "-ac", "2",
        "-c:a", "libmp3lame", "-b:a", "192k",
        str(out_path)
    ], check=True)

def make_segment_mp4(frames_dir: Path, audio_mp3: Path, out_mp4: Path, fps: int = FPS):
    subprocess.run([
        "ffmpeg", "-y",
        "-framerate", str(fps),
        "-i", str(frames_dir / "%05d.png"),
        "-i", str(audio_mp3),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        "-map", "0:v:0", "-map", "1:a:0",
        str(out_mp4)
    ], check=True)

def concat_mp4(segments: list[Path], out_mp4: Path):
    tmp = out_mp4.parent / "concat_list.txt"
    tmp.write_text("\n".join([f"file '{p.as_posix()}'" for p in segments]), encoding="utf-8")
    subprocess.run([
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(tmp),
        "-c", "copy",
        str(out_mp4)
    ], check=True)

def pad_or_trim_to_60s(in_mp4: Path, out_mp4: Path):
    """
    입력이 60초보다 짧으면 마지막 프레임을 복제해서 video를 늘리고,
    audio는 silence로 apad한 뒤 60초로 atrim.
    """
    subprocess.run([
        "ffmpeg", "-y",
        "-i", str(in_mp4),
        "-filter_complex",
        f"[0:v]tpad=stop_mode=clone:stop_duration=120,trim=0:{TARGET_TOTAL_SEC},setpts=PTS-STARTPTS[v];"
        f"[0:a]apad=pad_dur=120,atrim=0:{TARGET_TOTAL_SEC},asetpts=PTS-STARTPTS[a]",
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        str(out_mp4)
    ], check=True)


# =======================
# Text helpers
# =======================
def estimate_tts_seconds(text: str) -> float:
    return max(0.0, len(re.sub(r"\s+", " ", text).strip()) / 7.0)

def shrink_to_target(text_in: str, target_sec: float) -> str:
    s = re.sub(r"\s+", " ", (text_in or "")).strip()
    if not s:
        return s
    sents = re.split(r"(?<=[.!?。])\s+", s)
    for k in range(len(sents), 0, -1):
        cand = " ".join(sents[:k]).strip()
        if estimate_tts_seconds(cand) <= target_sec:
            return cand
    max_chars = max(35, int(target_sec * 7))
    return s[:max_chars].rstrip() + "."


def normalize_formula(s: str) -> str:
    """
    수식 문자열에서 깨진 백슬래시를 복구.
    - ₩  -> \
    - Wsin, Wcos, Wtheta, Wsqrt, Wfrac ... 처럼 수식 토큰 앞의 W -> \
    ※ 일반 문장에는 적용하면 안 되고, formula(수식)에서만 사용.
    """
    if not s:
        return ""
    s = s.strip()

    # 1) Windows 원화기호 -> 백슬래시
    s = s.replace("₩", "\\")

    # 1.5) 백슬래시 없이 나온 LaTeX 토큰 복구
    # 예: Rightarrow -> \Rightarrow, rightarrow -> \rightarrow, left/right -> \left/\right
    # 이미 '\\'가 있는 경우는 건드리지 않음
    s = re.sub(r"(?<!\\)\bRightarrow\b", r"\\Rightarrow", s)
    s = re.sub(r"(?<!\\)\brightarrow\b", r"\\rightarrow", s)
    s = re.sub(r"(?<!\\)\bleft\b", r"\\left", s)
    s = re.sub(r"(?<!\\)\bright\b", r"\\right", s)
    s = re.sub(r"(?<!\\)\bint\b", r"\\int", s)
    # int_0^1 같은 케이스를 우선 복구 (백슬래시 없는 적분)
    s = re.sub(r"(?<!\\)\bint(?=\s*_)", r"\\int", s)

    # 2) 수식 토큰 앞의 'W'를 백슬래시로 복구 (Wsin -> \sin)
    s = re.sub(
        r"W(?=(sin|cos|tan|theta|pi|sqrt|frac|cdot|times|pm|quad|left|right|Rightarrow|to|ge|le|neq)\b)",
        r"\\",
        s,
    )

    # 3) 구분자 자체가 깨진 경우: W( ... W) / W[ ... W]
    s = re.sub(r"^W(?=[\(\[])", r"\\", s)
    s = re.sub(r"W(?=[\)\]])$", r"\\", s)

    return s


def sanitize_plain_text(text_in: str) -> str:
    """
    explanation/check/tts 같은 일반 텍스트 필드에서
    깨진 LaTeX 토큰(Wcdot 등)과 LaTeX 명령을 일반 문자로 정리한다.
    """
    if text_in is None:
        return ""
    s = str(text_in)

    # 깨진 백슬래시 토큰/W토큰 보정
    s = s.replace("₩", "\\")
    s = re.sub(r"W(?=(cdot|times|pm|rightarrow|Rightarrow|le|ge|neq)\b)", r"\\", s)

    # 대표 토큰을 일반 문자로 치환
    repl = {
        r"\cdot": "×",
        r"\times": "×",
        r"\pm": "±",
        r"\Rightarrow": "→",
        r"\rightarrow": "→",
        r"\le": "≤",
        r"\ge": "≥",
        r"\neq": "≠",
        r"\quad": " ",
        r"\,": " ",
    }
    for k, v in repl.items():
        s = s.replace(k, v)

    # 남아있는 LaTeX 명령어는 백슬래시만 제거해 일반 텍스트화
    s = re.sub(r"\\([A-Za-z]+)", r"\1", s)
    # LaTeX 잔여 기호 최소 정리
    s = s.replace("{", "").replace("}", "")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def sanitize_detail_payload(detail: dict) -> dict:
    """
    DB 저장 전 detail 전체를 정리:
    - formula는 LaTeX 복구(normalize_formula)
    - explanation/check/tts/title 등 일반 텍스트는 LaTeX 제거
    - notes도 동일 정리
    """
    if not isinstance(detail, dict):
        return detail

    out = dict(detail)

    steps = out.get("steps")
    if isinstance(steps, list):
        fixed_steps = []
        for st in steps:
            if not isinstance(st, dict):
                continue
            row = dict(st)
            row["formula"] = normalize_formula(row.get("formula") or "") if row.get("formula") is not None else None
            for k in ("title", "explanation", "check", "tts"):
                if k in row and row.get(k) is not None:
                    row[k] = sanitize_plain_text(row.get(k))
            fixed_steps.append(row)
        out["steps"] = fixed_steps

    for k in ("concept", "introHook", "problemText"):
        if k in out and out.get(k) is not None:
            out[k] = sanitize_plain_text(out.get(k))

    if isinstance(out.get("notes"), list):
        out["notes"] = [sanitize_plain_text(x) for x in out.get("notes")]

    # 전체 문자열 안전망: Wcdot/Wtimes 등 잔여 토큰 제거
    dumped = json.dumps(out, ensure_ascii=False)
    dumped = dumped.replace("Wcdot", "×").replace("Wtimes", "×").replace("WRightarrow", "→").replace("Wrightarrow", "→")
    try:
        return json.loads(dumped)
    except Exception:
        return out

def fit_image_to_box(im: Image.Image, max_w: int, max_h: int, min_scale: float = 0.85, max_scale: float = 1.35) -> Image.Image:
    """
    Scale RGBA image to fit inside (max_w, max_h).
    - If too big: scale down.
    - If too small: scale up a bit (capped by max_scale).
    """
    if im is None:
        return im

    # downscale to fit
    scale_down = min(max_w / max(1, im.width), max_h / max(1, im.height), 1.0)
    # optional upscale if it's too small
    scale_up = min(max_scale, max(min_scale, 1.0))
    # 실제로는 "너무 작을 때만" 약간 키움: (가로가 max_w의 60% 미만이면 키우기)
    if im.width < max_w * 0.60 and im.height < max_h * 0.60:
        scale_up = max_scale
    else:
        scale_up = 1.0

    scale = min(scale_up, scale_down)
    if abs(scale - 1.0) < 1e-3:
        return im

    new_w = max(1, int(im.width * scale))
    new_h = max(1, int(im.height * scale))
    out = im.resize((new_w, new_h), Image.LANCZOS)

    # 확대/축소 후 약간 선명하게
    try:
        out = sharpen_after_resize(out)
    except Exception:
        pass
    return out

# =======================
# LaTeX / Math rendering helpers
# =======================
def _strip_math_delimiters(s: str) -> str:
    """Remove common math delimiters like \( \), \[ \], $$ $$."""
    if not s:
        return ""
    s = s.strip()
    # Windows oddity: won sign instead of backslash
    s = s.replace("₩", "\\")
    # remove $$...$$
    if s.startswith("$$") and s.endswith("$$") and len(s) >= 4:
        s = s[2:-2].strip()
    # remove \( ... \)
    if s.startswith(r"\(") and s.endswith(r"\)") and len(s) >= 4:
        s = s[2:-2].strip()
    # remove \[ ... \]
    if s.startswith(r"\[") and s.endswith(r"\]") and len(s) >= 4:
        s = s[2:-2].strip()
    return s

def _looks_like_latex(s: str) -> bool:
    if not s:
        return False
    s = s.strip()
    return ("\\" in s) or ("^" in s) or ("_" in s) or (r"\(" in s) or ("$$" in s)

def pretty_formula_fallback(s: str) -> str:
    """
    Fallback when math rendering isn't available.
    (Not perfect, but avoids \theta / ₩ issues.)
    """
    if not s:
        return ""
    s = s.replace("₩", "\\")
    # remove delimiters
    s = s.replace(r"\(", "").replace(r"\)", "").replace(r"\[", "").replace(r"\]", "").replace("$$", "")
    # minimal replacements
    repl = {
        r"\theta": "θ",
        r"\pi": "π",
        r"\sin": "sin",
        r"\cos": "cos",
        r"\tan": "tan",
        r"\cdot": "×",
        r"\times": "×",
        r"\pm": "±",
        r"\Rightarrow": "⇒",
        r"\to": "→",
        r"\ge": "≥",
        r"\le": "≤",
        r"\neq": "≠",
        r"\quad": " ",
        r"\,": " ",
        r"\left": "",
        r"\right": "",
    }
    for k, v in repl.items():
        s = s.replace(k, v)

    # 백슬래시 없는 토큰도 최소 복구
    s = re.sub(r"\bRightarrow\b", "⇒", s)
    s = re.sub(r"\brightarrow\b", "→", s)
    s = re.sub(r"\bcdot\b", "×", s)
    s = re.sub(r"\btimes\b", "×", s)
    s = re.sub(r"\bint\b", "∫", s)

    # int_0^1 -> ∫_0^1 (문자열 노출 완화)
    s = re.sub(r"\bint(?=\s*_)", "∫", s)

     # \sqrt2, \sqrt x 처리
    s = re.sub(r"\\sqrt\s*([A-Za-z0-9])", r"\\sqrt{\1}", s)

    # simple sqrt / frac
    s = re.sub(r"\\sqrt\s*\{([^}]*)\}", r"√(\1)", s)
    s = re.sub(r"\\frac\s*\{([^}]*)\}\s*\{([^}]*)\}", r"(\1/\2)", s)
    s = s.replace("{", "").replace("}", "")
    s = s.replace("^2", "²").replace("^3", "³")
    # remove leftover backslashes
    s = s.replace("\\", "")
    s = re.sub(r"\s+", " ", s).strip()
    return s

def render_latex_to_pil(latex: str, font_size: int = 38) -> Image.Image | None:
    """
    Render LaTeX math to a transparent RGBA PIL image using matplotlib's mathtext.
    Returns None if matplotlib isn't available or rendering fails.
    """
    if not MATPLOTLIB_OK:
        return None
    latex = _strip_math_delimiters(latex)
    if not latex:
        return None

    key = (latex, font_size)
    if key in _MATH_IMG_CACHE:
        return _MATH_IMG_CACHE[key].copy()

    # Use mathtext: wrap in $...$ for inline math rendering
    text = f"${latex}$"

    try:
        fig = plt.figure(figsize=(0.01, 0.01), dpi=300)
        fig.patch.set_alpha(0.0)
        ax = fig.add_axes([0, 0, 1, 1])
        ax.axis("off")

        t = ax.text(0, 0, text, fontsize=font_size, color="black", va="bottom", ha="left")
        fig.canvas.draw()

        bbox = t.get_window_extent(renderer=fig.canvas.get_renderer())
        # Expand a bit for safe padding
        pad = 6
        w_px = int(bbox.width) + pad * 2
        h_px = int(bbox.height) + pad * 2

        plt.close(fig)

        # Re-render at correct size
        fig2 = plt.figure(figsize=(w_px / 300, h_px / 300), dpi=300)
        fig2.patch.set_alpha(0.0)
        ax2 = fig2.add_axes([0, 0, 1, 1])
        ax2.axis("off")
        ax2.text(pad / 300, pad / 300, text, fontsize=font_size, color="black", va="bottom", ha="left")

        buf = BytesIO()
        fig2.savefig(buf, format="png", transparent=True, bbox_inches="tight", pad_inches=0.0)
        plt.close(fig2)
        buf.seek(0)

        im = Image.open(buf).convert("RGBA")
        im = crop_transparent(im)
        _MATH_IMG_CACHE[key] = im.copy()
        return im
    except Exception:
        try:
            plt.close("all")
        except Exception:
            pass
        return None

def crop_transparent(im: Image.Image) -> Image.Image:
    """Crop fully transparent borders from an RGBA image."""
    if im.mode != "RGBA":
        im = im.convert("RGBA")
    alpha = im.split()[-1]
    bbox = alpha.getbbox()
    if bbox:
        return im.crop(bbox)
    return im

def paste_rgba(base_rgb: Image.Image, overlay_rgba: Image.Image, xy: tuple[int, int]):
    """Alpha-paste RGBA onto RGB image."""
    if base_rgb.mode != "RGB":
        base_rgb = base_rgb.convert("RGB")
    if overlay_rgba.mode != "RGBA":
        overlay_rgba = overlay_rgba.convert("RGBA")
    base_rgb.paste(overlay_rgba, xy, overlay_rgba)

def fit_image_to_width(im: Image.Image, max_w: int) -> Image.Image:
    """Scale down RGBA image to fit max_w (keep aspect)."""
    if im.width <= max_w:
        return im
    scale = max_w / max(1, im.width)
    new_w = max(1, int(im.width * scale))
    new_h = max(1, int(im.height * scale))
    return im.resize((new_w, new_h), Image.LANCZOS)

def reveal_crop(im: Image.Image, progress: float) -> Image.Image:
    """Reveal image left->right according to progress [0..1]."""
    progress = max(0.0, min(1.0, progress))
    w = max(1, int(im.width * progress))
    return im.crop((0, 0, w, im.height))


# =======================
# Image helpers
# =======================
def crop_whitespace(im: Image.Image, threshold=245) -> Image.Image:
    g = im.convert("L")
    bw = g.point(lambda p: 0 if p > threshold else 255, mode="1")
    bbox = bw.getbbox()
    if bbox:
        return im.crop(bbox)
    return im

def sharpen_after_resize(im: Image.Image) -> Image.Image:
    # 과도하지 않게 선명도만 살짝
    return im.filter(ImageFilter.UnsharpMask(radius=2, percent=150, threshold=3))

def load_fonts():
    candidates = [
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/usr/share/fonts/truetype/nanum/NanumBarunGothic.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for fp in candidates:
        try:
            big = ImageFont.truetype(fp, 50)
            mid = ImageFont.truetype(fp, 38)
            small = ImageFont.truetype(fp, 30)
            mono = ImageFont.truetype(fp, 36)
            return big, mid, small, mono
        except Exception:
            continue
    d = ImageFont.load_default()
    return d, d, d, d

def wrap_text(draw: ImageDraw.ImageDraw, text_in: str, font, max_width: int) -> list[str]:
    text_in = re.sub(r"\s+", " ", (text_in or "")).strip()
    if not text_in:
        return [""]
    words = text_in.split(" ")
    lines = []
    cur = ""
    for w in words:
        test = (cur + " " + w).strip()
        bw = draw.textbbox((0, 0), test, font=font)[2]
        if bw <= max_width:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines

def draw_typewriter(draw: ImageDraw.ImageDraw, x: int, y: int, full_text: str, font, progress: float):
    s = full_text or ""
    n = max(0, min(len(s), int(len(s) * progress)))
    draw.text((x, y), s[:n], fill="black", font=font)


# =======================
# Rendering (duration-driven by segment mp3)
# =======================
def render_segment_frames(
    png_path: str,
    frames_dir: Path,
    duration_sec: float,
    mode: str,
    payload: dict,
    fps: int = FPS,
):
    safe_mkdir(frames_dir)
    big, mid, small, mono = load_fonts()

    raw = Image.open(png_path).convert("RGB")
    raw = crop_whitespace(raw)

    total_frames = max(1, int(duration_sec * fps))
    board_y = TOP_H + 10

    for fi in range(total_frames):
        t = fi / max(1, total_frames - 1)  # 0..1
        img = Image.new("RGB", (W, H), "white")
        draw = ImageDraw.Draw(img)

        # ---- top: keep aspect ratio, fill width, no ugly stretch ----
        # 목표 박스: (W-40) x (TOP_H-30)
        box_w, box_h = (W - 40), (TOP_H - 30)
        prob = raw.copy()

        # 비율 유지 확대(필요시) + 선명화
        prob.thumbnail((box_w, box_h), Image.LANCZOS)
        # 만약 원본이 너무 작아서 내용이 작으면, width 기준으로 적당히 upscale(비율 유지)
        if prob.width < box_w * 0.92:
            scale = (box_w * 0.92) / max(1, prob.width)
            new_w = int(prob.width * scale)
            new_h = int(prob.height * scale)
            prob = prob.resize((new_w, new_h), Image.LANCZOS)
            prob = sharpen_after_resize(prob)

        px = 20 + (box_w - prob.width) // 2
        py = 10 + (box_h - prob.height) // 2
        img.paste(prob, (px, py))

        # ---- bottom: whiteboard ----
        draw.rectangle([20, board_y, W - 20, H - 20], outline="black", width=3)

        x = 45
        y = board_y + 26
        max_w = W - 90

        if mode == "intro":
            concept = (payload.get("concept") or "문제").strip()
            core_raw = (payload.get("core") or "").strip()
            core_text = core_raw
            if core_raw.startswith("핵심은"):
                core_text = core_raw[len("핵심은"):].strip()

            line1 = f"유형: {concept}"
            line2 = core_text
            START_DELAY = 0.2
            # 인트로 타이핑은 오디오 길이와 무관하게 1초 안에 끝내기
            TYPE1_SEC   = 1.0      # 유형은 1초 안에 완성
            GAP_SEC     = 0.2      # 유형 끝난 뒤 0.2초 쉬고
            TYPE2_SEC   = 1.0      # 핵심도 1초 안에 완성(원하면 1.2 등으로)
            sec = fi / fps
            p1 = max(0.0, min(1.0, (sec - START_DELAY) / TYPE1_SEC))
            draw_typewriter(draw, x, y + 60, line1, mid, p1)

            # 2) 핵심 타이핑은 "유형이 끝난 뒤 + 0.2초"부터 시작
            core_start = START_DELAY + TYPE1_SEC + GAP_SEC
            p2 = max(0.0, min(1.0, (sec - core_start) / TYPE2_SEC))
            draw_typewriter(draw, x, y + 120, line2, mid, p2)

        elif mode == "step":
            idx = payload.get("idx", 1)
            title = (payload.get("title") or "").strip()

            raw_formula = normalize_formula(payload.get("formula") or "")
            inner_formula = _strip_math_delimiters(raw_formula)

            # split into lines if author inserted newlines
            raw_lines = [ln.strip() for ln in (inner_formula.split("\n") if inner_formula else []) if ln.strip()]
            raw_lines = raw_lines[:FORMULA_MAX_LINES]

            # explanation
            expl = re.sub(r"\s+", " ", (payload.get("explanation") or "")).strip()
            expl_sents = re.split(r"(?<=[.!?。])\s+", expl)
            expl_short = " ".join(expl_sents[:1]).strip()
            expl_lines = wrap_text(draw, expl_short, small, max_w)[:EXPL_MAX_LINES]

            draw.text((x, y), f"{idx}단계  {title}", fill="black", font=mid)

            f_start, f_end = 0.15, 0.85
            ty = y + 78

            if t >= f_start:
                prog = min(1.0, max(0.0, (t - f_start) / max(1e-6, (f_end - f_start))))

                # Render formula lines:
                # If matplotlib available -> render LaTeX to image, else fallback to safe text.
                rendered_any = False
                for li, latex_line in enumerate(raw_lines):
                    phase = li * 0.12
                    line_prog = min(1.0, max(0.0, (prog - phase) / max(1e-6, 1.0 - phase)))

                    # Try render math
                    math_img = None
                    if _looks_like_latex(latex_line):
                        safe_line = sanitize_for_mathtext(latex_line)
                        math_img = render_latex_to_pil(safe_line, font_size=40)

                    if math_img is not None:
                        rendered_any = True
                        LINE_H = 56
                        FORMULA_BOX_W = max_w - 30
                        FORMULA_BOX_H = LINE_H - 10  # 위아래 여백

                        math_img = fit_image_to_box(math_img, FORMULA_BOX_W, FORMULA_BOX_H, max_scale=1.35)

                        reveal = reveal_crop(math_img, line_prog)

                        # 세로 중앙정렬(수식 높이가 줄어도 줄 안에서 가운데로)
                        yy = ty + li * LINE_H + (LINE_H - math_img.height) // 2
                        paste_rgba(img, reveal, (x, yy))

                    else:
                        # fallback: safe plain text (won sign / theta etc.)
                        fallback_text = pretty_formula_fallback(latex_line)
                        draw_typewriter(draw, x, ty + li * 56, fallback_text, mono, line_prog)

                # If there were no formula lines but we still got something, show nothing (ok)
                # explanation area (below formula)
                ey = ty + FORMULA_MAX_LINES * 56 + 12
                for i2, ln in enumerate(expl_lines):
                    draw.text((x, ey + i2 * 42), ln, fill="black", font=small)

                # highlight box (after formula typed)
                if t >= 0.85:
                    box_h = (max(1, min(FORMULA_MAX_LINES, len(raw_lines))) * 56) + 16
                    draw.rectangle([x - 10, ty - 10, W - 45, ty - 10 + box_h], outline="black", width=4)

        elif mode == "outro":
            ans = (payload.get("finalAnswer") or "").strip()
            draw.text((x, y), "정답", fill="black", font=big)

            # If answer looks like LaTeX -> render as math, else draw plain text
            ans_norm = normalize_formula(ans)
            ans_inner = _strip_math_delimiters(ans_norm)

            if _looks_like_latex(ans_inner):
                safe_ans = sanitize_for_mathtext(ans_inner)
                math_img = render_latex_to_pil(safe_ans, font_size=64)
                if math_img is not None:
                    math_img = fit_image_to_box(math_img, W - 180, 110, max_scale=1.25)  # 정답 박스 높이 맞춤
                    paste_rgba(img, math_img, (x, y + 92))
                else:
                    draw.text((x, y + 100), pretty_formula_fallback(ans_inner) or "정답", fill="black", font=big)
            else:
                draw.text((x, y + 100), ans if ans else "정답", fill="black", font=big)

            draw.rectangle([x - 10, y + 85, W - 45, y + 175], outline="black", width=5)

        img.save(frames_dir / f"{fi:05d}.png")

def sanitize_for_mathtext(s: str) -> str:
    """matplotlib mathtext가 잘 먹도록 LaTeX를 최소 변환."""
    if not s:
        return ""
    s = normalize_formula(s)          # (너가 만든 정규화)
    s = _strip_math_delimiters(s)

    # 백슬래시 없는 적분 표기 보정
    s = re.sub(r"\bint(?=\s*_)", r"\\int", s)

    # mathtext가 약한/불안정한 토큰들 정리
    s = s.replace(r"\quad", " ")
    s = s.replace(r"\,", " ")
    s = s.replace(r"\:", " ")
    s = s.replace(r"\;", " ")

    # 화살표류: mathtext에서 실패하면 그냥 -> 로
    s = s.replace(r"\Rightarrow", r"\to")
    s = s.replace(r"\Longrightarrow", r"\to")

    # left/right 제거 (mathtext에서 불안정할 때가 있음)
    s = s.replace(r"\left", "")
    s = s.replace(r"\right", "")

    # \sqrt2, \sqrt x  ->  \sqrt{2}, \sqrt{x} 로 보정 (mathtext 성공률↑)
    s = re.sub(r"\\sqrt\s*([A-Za-z0-9])", r"\\sqrt{\1}", s)
    s = re.sub(r"\\sqrt\s*\(([^)]+)\)", r"\\sqrt{\1}", s)

    # 중괄호는 유지해야 frac/sqrt가 살아있음 (제거 금지)
    return s.strip()

# =======================
# Main video builder (order fixed + 60s fixed)
# =======================
def build_video(job_id: str, png_path: str, detail: dict) -> str:
    base = Path(os.getenv("STORAGE_BASE", "/data"))
    out_dir = base / "outputs"
    safe_mkdir(out_dir)

    tmp_dir = out_dir / f"tmp_{job_id}"
    safe_mkdir(tmp_dir)

    final_mp4 = out_dir / f"{job_id}.mp4"

    concept = (detail.get("concept") or "문제 유형").strip()
    steps = detail.get("steps") or []
    if not isinstance(steps, list) or not steps:
        steps = [{"idx": 1, "title": "풀이", "explanation": "문제를 단계별로 풀어봅니다.", "formula": "", "check": ""}]
    final_answer = (detail.get("finalAnswer") or "").strip()

    # ---- TTS ----
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    voice = os.getenv("OPENAI_TTS_VOICE", "alloy")
    tts_model = os.getenv("OPENAI_TTS_MODEL", "gpt-4o-mini-tts")

    def make_seg(name: str, text_in: str, mode: str, payload: dict) -> tuple[Path, float]:
        raw = tmp_dir / f"{name}_raw.mp3"
        mp3 = tmp_dir / f"{name}.mp3"
        tts_to_mp3(client, tts_model, voice, text_in, raw)
        normalize_mp3(raw, mp3)
        dur = probe_duration_sec(mp3)

        fdir = tmp_dir / f"frames_{name}"
        render_segment_frames(png_path, fdir, dur, mode, payload, fps=FPS)

        mp4 = tmp_dir / f"{name}.mp4"
        make_segment_mp4(fdir, mp3, mp4, fps=FPS)
        return mp4, dur

    concept = (detail.get("concept") or "문제 유형").strip()
    hook = (detail.get("introHook") or "").strip()


    if hook:
        intro_audio = f"이 유형은 {concept}입니다. {hook} 그 점을 염두에 두고 풀이 시작하겠습니다."
    else:
        intro_audio = f"이 유형은 {concept}입니다. 핵심 아이디어를 잡고 풀이 시작하겠습니다."
        
    outro_audio = f"정답은 {final_answer} 입니다." if final_answer else "정답을 확인합니다."

    intro_mp4, intro_dur = make_seg("intro", intro_audio, "intro", {"concept": concept,"core": hook})
    outro_mp4, outro_dur = make_seg("outro", outro_audio, "outro", {"finalAnswer": final_answer})

    # 60초 안에 '정답'이 들어오게 step 길이 제한
    remain = max(10.0, TARGET_TOTAL_SEC - intro_dur - outro_dur)
    per_step = max(3.5, remain / max(1, len(steps)))

    step_mp4s: list[Path] = []
    for i, st in enumerate(steps, start=1):
        tts_text = (st.get("tts") or "").strip()
        if not tts_text:
            # 혹시 예전 데이터(호환)
            tts_text = re.sub(r"\s+", " ", (st.get("explanation") or "")).strip()

        narration = shrink_to_target(tts_text, per_step)
        mp4, _dur = make_seg(
            f"step{i}",
            narration,
            "step",
            {
                "idx": st.get("idx", i),
                "title": st.get("title", ""),
                "formula": st.get("formula") or "",
                "explanation": st.get("explanation") or "",
            }
        )
        step_mp4s.append(mp4)

    # ✅ concat 순서 고정: intro -> steps -> outro
    stitched = tmp_dir / "stitched.mp4"
    concat_mp4([intro_mp4] + step_mp4s + [outro_mp4], stitched)

    # ✅ 60초 강제(짧으면 패딩, 길면 컷)
    fixed = tmp_dir / "final60.mp4"
    pad_or_trim_to_60s(stitched, fixed)
    shutil.copyfile(fixed, final_mp4)

    try:
        shutil.rmtree(tmp_dir)
    except Exception:
        pass

    return str(final_mp4)


# =======================
# Worker loop
# =======================
def main():
    r = redis.Redis(
        host=os.getenv("REDIS_HOST", "redis"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        decode_responses=True
    )
    engine = create_engine(mysql_url(), pool_pre_ping=True)
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    print("worker up. waiting queue...")
    while True:
        item = r.brpop([QUEUE_KEY, VIDEO_QUEUE_KEY], timeout=5)
        if not item:
            continue
        key, job_id = item

        if key == QUEUE_KEY:
            try:
                update_running(engine, job_id)

                png_path = get_input_png(engine, job_id)
                detail = solve_math_from_png_to_json(client, png_path)

                # 단일 호출이 실패한 경우에만 기존 2단계 방식으로 재시도(호환)
                if detail.get("concept") == "parse-failed" or not detail.get("steps"):
                    problem_text = extract_problem_text(client, png_path)
                    detail = solve_math_to_json(client, problem_text)

                detail = sanitize_detail_payload(detail)

                update_done(engine, job_id, json.dumps(detail, ensure_ascii=False))

            except Exception as e:
                update_fail(engine, job_id, str(e))
                print("job failed:", e)

        elif key == VIDEO_QUEUE_KEY:
            try:
                update_video_running(engine, job_id)

                png_path = get_input_png(engine, job_id)
                detail_json = get_detail_json(engine, job_id)
                if not detail_json:
                    raise RuntimeError("detail_json is empty. solve job first")

                detail = json.loads(detail_json)
                mp4_path = build_video(job_id, png_path, detail)
                update_video_done(engine, job_id, mp4_path)

            except Exception as e:
                update_video_fail(engine, job_id, str(e))
                print("video job failed:", e)

        else:
            print("unknown queue key:", key)

if __name__ == "__main__":
    main()
