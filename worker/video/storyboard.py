from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Any

@dataclass
class Scene:
    idx: int
    badge: str
    title: str
    desc: str
    formula_latex: str
    side_note: str
    svg_overlay: str
    tts_text: str
    duration_hint: float  # seconds (rough)

def build_storyboard(detail: Dict[str, Any]) -> List[Scene]:
    # 0~3초: 유형 요약(무음)
    concept = detail.get("concept", "문제 풀이")
    problem_text = detail.get("problemText", "")
    steps = detail.get("steps", [])
    final_answer = detail.get("finalAnswer", "")

    scenes: List[Scene] = []
    scenes.append(Scene(
        idx=1,
        badge="문제 요약 (0~3s)",
        title="문제 유형 요약",
        desc=f"{concept}\n\n(풀이를 바로 시작합니다)",
        formula_latex="",
        side_note="처음 3초 안에 유형을 알려주고 풀이로 넘어갑니다.",
        svg_overlay="",  # MVP: 추후 밑줄/동그라미 좌표 넣기
        tts_text="",     # 무음
        duration_hint=3.0
    ))

    # 풀이 scenes: 최대 4개 정도로 압축(너무 길면 쇼츠 초과)
    # 핵심: step 설명은 짧게, 공식/검산 체크포인트는 side_note에
    max_steps = 4
    chosen = steps[:max_steps] if isinstance(steps, list) else []

    for i, s in enumerate(chosen, start=2):
        title = s.get("title", f"풀이 {i-1}")
        expl = s.get("explanation", "")
        formula = s.get("formula", "")
        check = s.get("check", "")
        # formula는 MathJax가 먹게 \( ... \) 형태로 감싸기
        formula_latex = f"\\({formula}\\)" if formula else ""
        # tts는 길이 제한을 위해 짧게
        tts = f"{title}. {expl}"
        # 너무 길면 뒤를 자르지 말고, 처음 문장만 남김(룰 기반)
        tts = tts.split(".")[0].strip() + "." if "." in tts else tts

        scenes.append(Scene(
            idx=i,
            badge=f"풀이 {i-1}",
            title=title,
            desc=expl,
            formula_latex=formula_latex,
            side_note=check or "핵심 전개가 맞는지 확인합니다.",
            svg_overlay="",  # MVP: 추후
            tts_text=tts,
            duration_hint=10.0
        ))

    # 마지막: 정답(마지막 3~5초만 정답 언급)
    scenes.append(Scene(
        idx=len(scenes)+1,
        badge="정답 (마지막 3~5s)",
        title="정답",
        desc="마무리 검산 후 정답을 말합니다.",
        formula_latex="",
        side_note="정답은 마지막 구간에서만 언급합니다.",
        svg_overlay="",
        tts_text=f"정답은 {final_answer} 입니다.",
        duration_hint=4.0
    ))
    return scenes
