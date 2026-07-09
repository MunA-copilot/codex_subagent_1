# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import json
import re
import subprocess
import sys
import textwrap
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = Path(__file__).resolve().parent
TOOLS_DIR = ROOT / "2026-07-08-video-build-tools" / "python-packages"
ASSET_DIR = OUT_DIR / "2026-07-08-render-assets"

if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from PIL import Image, ImageDraw, ImageFont
import edge_tts
import imageio_ffmpeg


WIDTH = 1920
HEIGHT = 1080
VOICE = "ko-KR-HyunsuMultilingualNeural"
VOICE_RATE = "-8%"

VIDEO_FILE = OUT_DIR / "2026-07-08-codex-subagent-구현데모.mp4"
NARRATION_FILE = OUT_DIR / "2026-07-08-codex-subagent-구현데모-내레이션.mp3"
SUBTITLE_FILE = OUT_DIR / "2026-07-08-codex-subagent-구현데모-자막.srt"
MANIFEST_FILE = OUT_DIR / "2026-07-08-codex-subagent-구현데모-제작정보.json"


@dataclass(frozen=True)
class Scene:
    title: str
    label: str
    narration: str
    caption: str
    bullets: tuple[str, ...]
    visual: str


SCENES = [
    Scene(
        title="Codex Subagent 구현 데모",
        label="문제 정의",
        narration=(
            "복잡한 작업을 Codex에게 한 번에 맡기면, 기획, 구현, 검토, 디자인 판단이 "
            "한 대화 안에 섞이기 쉽습니다. 오늘 데모에서는 이 일을 다섯 개의 역할로 나눕니다. "
            "기획자는 아이디어를 넓히고, 평가자는 냉정하게 걸러내고, 개발자는 산출물을 만들고, "
            "보조 개발자는 위험을 점검하고, 디자이너는 화면 전달력을 다듬습니다."
        ),
        caption="복잡한 요청을 역할별 서브에이전트로 나누면 판단과 실행이 분리됩니다.",
        bullets=(
            "한 대화에 모든 결정을 몰아넣지 않습니다.",
            "역할마다 다른 기준으로 산출물을 만듭니다.",
            "사용자는 메인 스레드에서 최종 방향을 잡습니다.",
        ),
        visual="problem",
    ),
    Scene(
        title="역할별 스레드 분리",
        label="실행 구조",
        narration=(
            "사용자는 메인 스레드에서 전체 요청을 내립니다. 그 다음 역할별 서브에이전트가 "
            "별도 스레드로 나뉘어 자기 일만 처리합니다. 중요한 점은, 서브에이전트가 최종 판단을 "
            "빼앗아 가는 구조가 아니라는 것입니다. 메인 스레드는 결과를 모으고, 비교하고, "
            "최종 방향을 정합니다."
        ),
        caption="역할별 스레드는 따로 움직이고, 메인 스레드는 결과를 통합합니다.",
        bullets=(
            "기획자 서브에이전트",
            "평가자 서브에이전트",
            "개발자 서브에이전트",
            "보조 개발자 서브에이전트",
            "디자이너 서브에이전트",
        ),
        visual="threads",
    ),
    Scene(
        title="기획자와 평가자의 분업",
        label="아이디어 검증",
        narration=(
            "먼저 기획자 서브에이전트는 구현 데모 아이디어를 여러 개 제안합니다. "
            "여기서 바로 만들지 않는 이유는, 영상에서 잘 보이는 아이디어와 실제로 구현하기 쉬운 "
            "아이디어가 다를 수 있기 때문입니다. 평가자 서브에이전트는 그 제안을 냉정하게 봅니다. "
            "화면에서 바로 이해되는지, 시간이 너무 길지 않은지, 과장 없이 설명할 수 있는지를 "
            "기준으로 걸러냅니다."
        ),
        caption="기획자는 넓게 제안하고, 평가자는 영상성과 구현성을 따져 걸러냅니다.",
        bullets=(
            "기획자: 데모 후보를 넓게 제안",
            "평가자: 구현 난이도와 영상 전달력 평가",
            "메인 스레드: 채택할 데모 방향 결정",
        ),
        visual="planner_evaluator",
    ),
    Scene(
        title="개발, 점검, 디자인을 병렬화",
        label="동시 작업",
        narration=(
            "그 다음 세 역할은 병렬로 움직입니다. 개발자는 템플릿과 파일 구조, 저장 방식, "
            "Git 작업 흐름을 정리합니다. 보조 개발자는 테스트가 부족한 부분, 공개 저장소에 올리면 "
            "위험한 내용, 보안상 주의해야 할 지점을 확인합니다. 디자이너는 영상에서 한눈에 들어오는 "
            "레이아웃과 색상, 버튼 상태, 정보 우선순위를 다듬습니다."
        ),
        caption="개발, 위험 점검, 디자인을 분리하면 같은 시간에 다른 관점의 결과가 나옵니다.",
        bullets=(
            "개발자: 템플릿, 저장, Git 흐름",
            "보조 개발자: 테스트 부족, 보안 취약점, 공개 위험",
            "디자이너: UI 전달력, 색상, 촬영 가독성",
        ),
        visual="parallel",
    ),
    Scene(
        title="메인 스레드의 통합 판단",
        label="결과 통합",
        narration=(
            "서브에이전트의 핵심은 여러 결과를 그냥 쌓는 것이 아닙니다. 메인 스레드가 서로 다른 "
            "의견을 비교하고, 어떤 아이디어를 채택할지 판단한 뒤, 하나의 실행 계획으로 정리합니다. "
            "이 데모에서는 작업 관리 대시보드를 실제 산출물로 만들고, 동시에 다음 프로젝트에서도 "
            "재사용할 수 있는 템플릿과 가이드를 남깁니다."
        ),
        caption="메인 스레드는 여러 산출물을 하나의 실행 계획으로 통합합니다.",
        bullets=(
            "역할별 결과를 비교",
            "채택할 구현 데모 결정",
            "템플릿, 가이드, 테스트 결과까지 저장",
        ),
        visual="integration",
    ),
    Scene(
        title="실제 구현 데모",
        label="동작 확인",
        narration=(
            "이제 결과물이 실제로 동작하는 장면입니다. 대시보드에서 위험 상태였던 작업을 완료로 "
            "바꾸면, 완료율이 올라가고 활성 위험 수가 줄어듭니다. 이렇게 화면에서 바로 변화를 "
            "확인할 수 있어야 구현 데모 영상으로 설득력이 생깁니다. 단순히 파일을 만들었다고 "
            "끝나는 것이 아니라, 사용자가 보는 결과까지 확인합니다."
        ),
        caption="상태 변경이 KPI, 위험 수, 상세 패널에 즉시 반영되는 장면을 보여줍니다.",
        bullets=(
            "위험 상태 작업을 완료로 변경",
            "완료율 상승",
            "활성 위험 수 감소",
        ),
        visual="dashboard",
    ),
    Scene(
        title="최종 산출물과 재사용",
        label="템플릿화",
        narration=(
            "마지막으로 남는 것은 하나의 데모만이 아닙니다. 역할별 프롬프트, 실행 가이드, "
            "촬영 체크리스트, 테스트 결과, 그리고 GitHub에 올릴 수 있는 프로젝트 구조가 함께 남습니다. "
            "다음에 다른 앱이나 자동화 도구를 만들 때도, 같은 방식으로 역할을 바꿔서 다시 사용할 수 있습니다."
        ),
        caption="최종 결과는 한 번짜리 화면이 아니라, 다시 쓸 수 있는 서브에이전트 작업 템플릿입니다.",
        bullets=(
            ".codex/agents 역할 정의",
            "영상 구성안과 촬영 체크리스트",
            "동작하는 HTML 데모와 테스트",
            "GitHub에 푸시 가능한 구조",
        ),
        visual="outputs",
    ),
    Scene(
        title="정리",
        label="핵심 요약",
        narration=(
            "정리하면, Codex subagent의 장점은 속도만이 아닙니다. 역할을 나누면 아이디어, 검토, "
            "구현, 위험 점검, 디자인이 서로 다른 관점으로 정리됩니다. 사용자는 메인 스레드에서 "
            "방향을 잡고, 필요한 순간에 각 역할의 결과를 확인하면 됩니다. 이 구조를 쓰면 복잡한 요청도 "
            "더 설명 가능하고, 더 재사용 가능한 작업 흐름으로 만들 수 있습니다."
        ),
        caption="서브에이전트는 복잡한 작업을 설명 가능한 AI 팀 워크플로로 바꿉니다.",
        bullets=(
            "역할 분리",
            "병렬 검토",
            "메인 스레드 통합",
            "재사용 가능한 템플릿",
        ),
        visual="summary",
    ),
]


COLORS = {
    "bg": "#F7F4EE",
    "ink": "#20242A",
    "muted": "#5D6673",
    "panel": "#FFFFFF",
    "line": "#D8D2C8",
    "blue": "#276EF1",
    "green": "#1E8A5A",
    "red": "#C74343",
    "yellow": "#D99B2B",
    "teal": "#167C80",
    "navy": "#1F2B46",
}


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    font_dirs = [
        Path.home() / "AppData/Local/Microsoft/Windows/Fonts",
        Path("C:/Windows/Fonts"),
    ]
    candidates = {
        "regular": ["NanumSquareNeo-bRg.ttf", "NanumSquareNeoOTF-Rg.otf"],
        "bold": ["NanumSquareNeo-cBd.ttf", "NanumSquareNeoOTF-Bd.otf"],
        "extra_bold": ["NanumSquareNeo-dEb.ttf", "NanumSquareNeoOTF-Eb.otf"],
    }[name]
    for candidate in candidates:
        for fonts_dir in font_dirs:
            path = fonts_dir / candidate
            if path.exists():
                return ImageFont.truetype(str(path), size)
    raise FileNotFoundError(f"NanumSquare Neo font not found for {name}: {candidates}")


FONT_H1 = font("extra_bold", 58)
FONT_H2 = font("extra_bold", 38)
FONT_BODY = font("regular", 30)
FONT_BODY_BOLD = font("bold", 30)
FONT_SMALL = font("regular", 23)
FONT_SMALL_BOLD = font("bold", 24)
FONT_CAPTION = font("bold", 29)


def text_size(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.ImageFont) -> tuple[int, int]:
    box = draw.textbbox((0, 0), text, font=fnt)
    return box[2] - box[0], box[3] - box[1]


def wrap_text(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.ImageFont, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        trial = word if not current else f"{current} {word}"
        if text_size(draw, trial, fnt)[0] <= max_width:
            current = trial
            continue
        if current:
            lines.append(current)
        current = word
        while text_size(draw, current, fnt)[0] > max_width and len(current) > 1:
            cut = len(current) - 1
            while cut > 1 and text_size(draw, current[:cut], fnt)[0] > max_width:
                cut -= 1
            lines.append(current[:cut])
            current = current[cut:]
    if current:
        lines.append(current)
    return lines


def draw_wrapped(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    fnt: ImageFont.ImageFont,
    fill: str,
    max_width: int,
    line_gap: int = 10,
) -> int:
    x, y = xy
    for line in wrap_text(draw, text, fnt, max_width):
        draw.text((x, y), line, font=fnt, fill=fill)
        y += text_size(draw, line, fnt)[1] + line_gap
    return y


def rounded(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], fill: str, outline: str | None = None, width: int = 2, radius: int = 18) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def draw_header(draw: ImageDraw.ImageDraw, scene: Scene, index: int) -> None:
    draw.text((88, 62), scene.title, font=FONT_H1, fill=COLORS["ink"])
    draw.text((92, 132), f"{index:02d} / {len(SCENES):02d}  {scene.label}", font=FONT_SMALL_BOLD, fill=COLORS["blue"])
    draw.line((88, 176, 1832, 176), fill=COLORS["line"], width=2)


def draw_caption(draw: ImageDraw.ImageDraw, caption: str) -> None:
    rounded(draw, (88, 820, 1832, 910), COLORS["navy"], radius=18)
    draw_wrapped(draw, (128, 846), caption, FONT_CAPTION, "#FFFFFF", 1660, line_gap=8)


def draw_bullets(draw: ImageDraw.ImageDraw, bullets: tuple[str, ...], x: int, y: int, max_width: int) -> None:
    for bullet in bullets:
        rounded(draw, (x, y + 2, x + 18, y + 20), COLORS["blue"], radius=6)
        y = draw_wrapped(draw, (x + 38, y - 6), bullet, FONT_BODY, COLORS["ink"], max_width, line_gap=8) + 20


def draw_problem(draw: ImageDraw.ImageDraw, scene: Scene) -> None:
    rounded(draw, (92, 230, 760, 742), COLORS["panel"], COLORS["line"], radius=18)
    draw.text((140, 278), "한 대화에 섞이는 일", font=FONT_H2, fill=COLORS["ink"])
    for i, item in enumerate(["아이디어", "평가", "구현", "테스트", "디자인"]):
        y = 360 + i * 72
        rounded(draw, (140, y, 660, y + 48), "#F1EFE9", radius=12)
        draw.text((166, y + 7), item, font=FONT_SMALL_BOLD, fill=COLORS["muted"])
    draw.text((842, 494), "->", font=FONT_H1, fill=COLORS["blue"])
    rounded(draw, (1010, 230, 1830, 742), COLORS["panel"], COLORS["line"], radius=18)
    draw.text((1060, 278), "역할별로 나누기", font=FONT_H2, fill=COLORS["ink"])
    roles = [("기획자", COLORS["blue"]), ("평가자", COLORS["red"]), ("개발자", COLORS["green"]), ("보조 개발자", COLORS["yellow"]), ("디자이너", COLORS["teal"])]
    for i, (role, color) in enumerate(roles):
        x = 1060 + (i % 2) * 345
        y = 374 + (i // 2) * 120
        rounded(draw, (x, y, x + 300, y + 82), "#F8FAFC", color, width=3, radius=16)
        draw.text((x + 26, y + 22), role, font=FONT_BODY_BOLD, fill=COLORS["ink"])
    summary = " / ".join(["판단 분리", "역할 기준", "메인 통합"])
    rounded(draw, (285, 770, 1635, 804), "#EAF2FF", COLORS["blue"], radius=14)
    draw.text((546, 775), summary, font=FONT_SMALL_BOLD, fill=COLORS["blue"])


def draw_threads(draw: ImageDraw.ImageDraw, scene: Scene) -> None:
    rounded(draw, (92, 230, 520, 820), "#ECEFF3", "#D1D7E0", radius=22)
    draw.text((132, 272), "Threads", font=FONT_H2, fill=COLORS["ink"])
    threads = ["메인 스레드", *scene.bullets]
    for i, label in enumerate(threads):
        y = 350 + i * 68
        fill = "#FFFFFF" if i else COLORS["navy"]
        color = "#FFFFFF" if i == 0 else COLORS["ink"]
        rounded(draw, (132, y, 480, y + 48), fill, "#CDD5E0", radius=14)
        draw.text((156, y + 8), label, font=FONT_SMALL_BOLD, fill=color)
    rounded(draw, (610, 250, 1830, 802), COLORS["panel"], COLORS["line"], radius=20)
    draw.text((660, 300), "메인 스레드", font=FONT_H2, fill=COLORS["ink"])
    draw_wrapped(
        draw,
        (660, 368),
        "모든 역할의 결과를 모아 최종 데모 실행 계획으로 정리합니다.",
        FONT_BODY,
        COLORS["muted"],
        1040,
    )
    x0 = 690
    for i, role in enumerate(["기획", "평가", "개발", "위험 점검", "디자인"]):
        x = x0 + i * 205
        rounded(draw, (x, 535, x + 160, 610), "#F8FAFC", COLORS["blue"], radius=16)
        draw.text((x + 32, 556), role, font=FONT_SMALL_BOLD, fill=COLORS["ink"])
        if i < 4:
            draw.text((x + 171, 552), "+", font=FONT_BODY_BOLD, fill=COLORS["blue"])
    rounded(draw, (805, 690, 1635, 748), "#EAF2FF", COLORS["blue"], radius=16)
    draw.text((858, 704), "통합 요약과 최종 산출물은 메인 스레드에서 확인", font=FONT_SMALL_BOLD, fill=COLORS["blue"])


def draw_planner_evaluator(draw: ImageDraw.ImageDraw, scene: Scene) -> None:
    headers = [("기획자", COLORS["blue"]), ("평가자", COLORS["red"]), ("메인 스레드", COLORS["green"])]
    for i, (head, color) in enumerate(headers):
        x = 110 + i * 590
        rounded(draw, (x, 250, x + 520, 760), COLORS["panel"], color, width=3, radius=20)
        draw.text((x + 38, 292), head, font=FONT_H2, fill=COLORS["ink"])
    draw_bullets(draw, ("후보 아이디어 5개", "화면 변화가 보이는 데모", "재사용 가능한 구조"), 150, 380, 430)
    draw_bullets(draw, ("구현 난이도", "영상 전달력", "과장 위험"), 740, 380, 430)
    draw_bullets(draw, ("작업 관리 대시보드 선택", "역할 결과를 하나로 정리", "실제 동작 확인"), 1330, 380, 430)
    rounded(draw, (692, 748, 1228, 800), "#FFF7E6", COLORS["yellow"], radius=16)
    draw.text((728, 761), "넓게 제안 -> 냉정하게 평가 -> 하나로 결정", font=FONT_SMALL_BOLD, fill=COLORS["ink"])


def draw_parallel(draw: ImageDraw.ImageDraw, scene: Scene) -> None:
    cards = [
        ("개발자", "파일 구조, 템플릿, Git 흐름", COLORS["green"]),
        ("보조 개발자", "테스트 부족, 보안 취약점, 공개 위험", COLORS["yellow"]),
        ("디자이너", "UI 전달력, 촬영 가독성, 정보 우선순위", COLORS["teal"]),
    ]
    for i, (role, desc, color) in enumerate(cards):
        x = 130 + i * 585
        rounded(draw, (x, 260, x + 500, 735), COLORS["panel"], color, width=3, radius=20)
        draw.text((x + 42, 315), role, font=FONT_H2, fill=COLORS["ink"])
        draw_wrapped(draw, (x + 42, 390), desc, FONT_BODY, COLORS["muted"], 410)
        rounded(draw, (x + 42, 560, x + 458, 622), "#F8FAFC", "#DDE3EA", radius=14)
        draw.text((x + 74, 576), "자기 역할 결과만 작성", font=FONT_SMALL_BOLD, fill=COLORS["ink"])
    draw.text((830, 765), "동시에 다른 관점 확보", font=FONT_H2, fill=COLORS["blue"])


def draw_integration(draw: ImageDraw.ImageDraw, scene: Scene) -> None:
    steps = ["역할별 결과", "비교", "채택", "실행 계획", "산출물 저장"]
    for i, step in enumerate(steps):
        x = 130 + i * 340
        rounded(draw, (x, 330, x + 250, 430), "#FFFFFF", COLORS["blue"], radius=18)
        draw.text((x + 40, 360), step, font=FONT_SMALL_BOLD, fill=COLORS["ink"])
        if i < len(steps) - 1:
            draw.text((x + 265, 350), "->", font=FONT_BODY_BOLD, fill=COLORS["blue"])
    rounded(draw, (250, 560, 1670, 790), COLORS["panel"], COLORS["line"], radius=20)
    draw.text((300, 610), "저장되는 템플릿", font=FONT_H2, fill=COLORS["ink"])
    draw_bullets(draw, scene.bullets, 320, 674, 1250)


def draw_dashboard(draw: ImageDraw.ImageDraw, scene: Scene) -> None:
    rounded(draw, (110, 238, 1810, 790), "#FFFFFF", "#D7DDE5", radius=22)
    draw.text((160, 286), "작업 관리 대시보드", font=FONT_H2, fill=COLORS["ink"])
    stats = [("완료율", "17% -> 33%", COLORS["blue"]), ("활성 위험", "1 -> 0", COLORS["red"]), ("상태 변경", "위험 -> 완료", COLORS["green"])]
    for i, (label, value, color) in enumerate(stats):
        x = 160 + i * 535
        rounded(draw, (x, 365, x + 470, 510), "#F8FAFC", "#DDE3EA", radius=16)
        draw.text((x + 30, 392), label, font=FONT_SMALL_BOLD, fill=COLORS["muted"])
        draw.text((x + 30, 430), value, font=FONT_H2, fill=color)
    rounded(draw, (160, 585, 1100, 665), "#F2F5F9", radius=14)
    rounded(draw, (160, 585, 475, 665), COLORS["blue"], radius=14)
    draw.text((190, 604), "완료율 증가", font=FONT_SMALL_BOLD, fill="#FFFFFF")
    rounded(draw, (1210, 570, 1660, 692), "#EAF8F1", COLORS["green"], radius=18)
    draw.text((1248, 608), "공개 저장소 보안 점검: 완료", font=FONT_SMALL_BOLD, fill=COLORS["green"])
    draw_bullets(draw, scene.bullets, 190, 704, 1200)


def draw_outputs(draw: ImageDraw.ImageDraw, scene: Scene) -> None:
    rounded(draw, (150, 255, 1770, 790), COLORS["panel"], COLORS["line"], radius=22)
    draw.text((210, 305), "재사용 가능한 폴더 구조", font=FONT_H2, fill=COLORS["ink"])
    rows = [
        (".codex/agents", "역할별 서브에이전트 설정"),
        ("codex-subagent-demo-kit", "프롬프트, 실행 가이드, 촬영 체크리스트"),
        ("task-dashboard-demo", "동작하는 구현 데모와 테스트"),
        ("video-production", "MP4, 내레이션, 자막, 제작정보"),
    ]
    for i, (folder, desc) in enumerate(rows):
        y = 394 + i * 78
        rounded(draw, (220, y, 1680, y + 56), "#F8FAFC", "#E0E6ED", radius=14)
        draw.text((250, y + 12), folder, font=FONT_SMALL_BOLD, fill=COLORS["blue"])
        draw.text((690, y + 12), desc, font=FONT_SMALL, fill=COLORS["ink"])


def draw_summary(draw: ImageDraw.ImageDraw, scene: Scene) -> None:
    items = [
        ("1", "역할 분리", COLORS["blue"]),
        ("2", "병렬 검토", COLORS["green"]),
        ("3", "통합 판단", COLORS["yellow"]),
        ("4", "재사용 템플릿", COLORS["teal"]),
    ]
    for i, (num, title, color) in enumerate(items):
        x = 180 + i * 420
        rounded(draw, (x, 300, x + 330, 655), COLORS["panel"], color, width=4, radius=22)
        rounded(draw, (x + 110, 350, x + 220, 460), color, radius=55)
        w, h = text_size(draw, num, FONT_H1)
        draw.text((x + 165 - w / 2, 405 - h / 2), num, font=FONT_H1, fill="#FFFFFF")
        draw.text((x + 72, 540), title, font=FONT_BODY_BOLD, fill=COLORS["ink"])
    draw_wrapped(
        draw,
        (330, 716),
        "복잡한 작업을 더 설명 가능하고, 더 검토 가능하고, 다음 프로젝트에 다시 쓸 수 있는 방식으로 바꿉니다.",
        FONT_BODY,
        COLORS["muted"],
        1260,
    )


VISUALS = {
    "problem": draw_problem,
    "threads": draw_threads,
    "planner_evaluator": draw_planner_evaluator,
    "parallel": draw_parallel,
    "integration": draw_integration,
    "dashboard": draw_dashboard,
    "outputs": draw_outputs,
    "summary": draw_summary,
}


THEME = {
    "page": "#EEF2F7",
    "window": "#FDFEFF",
    "surface": "#FFFFFF",
    "surface_alt": "#F5F8FC",
    "sidebar": "#111827",
    "sidebar_soft": "#1F2937",
    "ink": "#101828",
    "muted": "#667085",
    "subtle": "#98A2B3",
    "line": "#D9E2EC",
    "blue": "#2563EB",
    "blue_soft": "#EAF2FF",
    "green": "#059669",
    "green_soft": "#EAF8F1",
    "amber": "#D97706",
    "amber_soft": "#FFF7E6",
    "red": "#DC2626",
    "red_soft": "#FEF2F2",
    "teal": "#0E7490",
    "teal_soft": "#E6F7FA",
    "purple": "#7C3AED",
    "purple_soft": "#F3E8FF",
    "caption": "#0F172A",
}

FONT_DISPLAY = font("extra_bold", 54)
FONT_SCENE_TITLE = font("extra_bold", 38)
FONT_PANEL_TITLE = font("extra_bold", 28)
FONT_UI = font("bold", 23)
FONT_UI_REGULAR = font("regular", 22)
FONT_META = font("bold", 18)
FONT_TINY = font("regular", 17)
FONT_CAPTION_NEW = font("bold", 28)

ROLE_COLORS = {
    "기획자": THEME["blue"],
    "평가자": THEME["red"],
    "개발자": THEME["green"],
    "보조 개발자": THEME["amber"],
    "디자이너": THEME["teal"],
}


def draw_card(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    fill: str = THEME["surface"],
    outline: str = THEME["line"],
    width: int = 2,
    radius: int = 20,
    shadow: bool = True,
) -> None:
    if shadow:
        sx1, sy1, sx2, sy2 = box
        draw.rounded_rectangle((sx1 + 6, sy1 + 8, sx2 + 6, sy2 + 8), radius=radius, fill="#DDE5EF")
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def draw_pill(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    text: str,
    fill: str,
    text_fill: str,
    outline: str | None = None,
    fnt: ImageFont.ImageFont = FONT_META,
    radius: int = 18,
) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=2 if outline else 1)
    tw, th = text_size(draw, text, fnt)
    x1, y1, x2, y2 = box
    draw.text((x1 + (x2 - x1 - tw) / 2, y1 + (y2 - y1 - th) / 2 - 1), text, font=fnt, fill=text_fill)


def draw_centered(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    text: str,
    fnt: ImageFont.ImageFont,
    fill: str,
) -> None:
    tw, th = text_size(draw, text, fnt)
    x1, y1, x2, y2 = box
    draw.text((x1 + (x2 - x1 - tw) / 2, y1 + (y2 - y1 - th) / 2), text, font=fnt, fill=fill)


def draw_small_label(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, color: str) -> None:
    x, y = xy
    draw.rounded_rectangle((x, y, x + 14, y + 14), radius=5, fill=color)
    draw.text((x + 24, y - 5), text, font=FONT_TINY, fill=THEME["muted"])


def draw_thread_item(draw: ImageDraw.ImageDraw, y: int, label: str, active: bool = False) -> None:
    fill = THEME["blue"] if active else THEME["sidebar_soft"]
    text_fill = "#FFFFFF" if active else "#CBD5E1"
    draw.rounded_rectangle((112, y, 318, y + 38), radius=11, fill=fill)
    draw.text((128, y + 8), label, font=FONT_TINY, fill=text_fill)


def draw_demo_shell(draw: ImageDraw.ImageDraw, scene: Scene, index: int, active_thread: str = "메인 스레드") -> tuple[int, int, int, int]:
    draw.rectangle((0, 0, WIDTH, HEIGHT), fill=THEME["page"])
    draw_card(draw, (62, 56, 1858, 948), fill=THEME["window"], outline="#CAD5E2", radius=28, shadow=True)
    draw.rounded_rectangle((88, 88, 346, 918), radius=22, fill=THEME["sidebar"])
    draw.text((118, 124), "Codex", font=FONT_PANEL_TITLE, fill="#FFFFFF")
    draw_pill(draw, (252, 126, 312, 154), "Local", "#263244", "#DDE7F3", fnt=FONT_TINY, radius=12)

    for i, nav in enumerate(["New thread", "Automations", "Skills"]):
        y = 198 + i * 44
        draw.rounded_rectangle((112, y, 322, y + 34), radius=10, fill="#182235")
        draw.text((132, y + 7), nav, font=FONT_TINY, fill="#B9C5D4")

    draw.text((112, 360), "Threads", font=FONT_META, fill="#8EA0B8")
    thread_labels = [
        ("메인 스레드", active_thread == "메인 스레드"),
        ("기획자 서브에이전트", active_thread == "기획자"),
        ("평가자 서브에이전트", active_thread == "평가자"),
        ("개발자 서브에이전트", active_thread == "개발자"),
        ("보조 개발자", active_thread == "보조 개발자"),
        ("디자이너 서브에이전트", active_thread == "디자이너"),
    ]
    for i, (label, active) in enumerate(thread_labels):
        draw_thread_item(draw, 398 + i * 46, label, active)

    draw.rounded_rectangle((382, 88, 1818, 142), radius=16, fill=THEME["surface_alt"], outline=THEME["line"])
    draw_pill(draw, (410, 101, 492, 130), f"{index:02d}/08", THEME["blue"], "#FFFFFF", fnt=FONT_META, radius=13)
    draw.text((512, 103), scene.label, font=FONT_UI, fill=THEME["blue"])
    draw.text((1506, 103), "Subagent demo pilot", font=FONT_META, fill=THEME["muted"])

    draw.text((392, 178), scene.title, font=FONT_DISPLAY, fill=THEME["ink"])
    draw.line((392, 252, 1810, 252), fill=THEME["line"], width=2)

    draw.rounded_rectangle((392, 790, 1810, 872), radius=18, fill=THEME["caption"])
    draw_wrapped(draw, (430, 813), scene.caption, FONT_CAPTION_NEW, "#FFFFFF", 1338, line_gap=8)
    return (392, 286, 1810, 754)


def draw_role_badge(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], role: str, subtitle: str) -> None:
    color = ROLE_COLORS.get(role, THEME["blue"])
    draw_card(draw, box, fill=THEME["surface"], outline=color, width=3, radius=20, shadow=False)
    x1, y1, x2, _ = box
    draw.rounded_rectangle((x1 + 24, y1 + 24, x1 + 68, y1 + 68), radius=14, fill=color)
    draw.text((x1 + 86, y1 + 24), role, font=FONT_PANEL_TITLE, fill=THEME["ink"])
    draw_wrapped(draw, (x1 + 86, y1 + 64), subtitle, FONT_TINY, THEME["muted"], x2 - x1 - 112, line_gap=5)


def scene_problem(draw: ImageDraw.ImageDraw, scene: Scene, index: int) -> None:
    x1, y1, x2, y2 = draw_demo_shell(draw, scene, index)
    left = (x1 + 16, y1 + 18, x1 + 610, y2 - 8)
    right = (x1 + 790, y1 + 18, x2 - 16, y2 - 8)
    draw_card(draw, left, fill=THEME["surface"], outline=THEME["line"], radius=24)
    draw_card(draw, right, fill=THEME["surface"], outline=THEME["line"], radius=24)
    draw.text((left[0] + 38, left[1] + 38), "한 스레드에 몰아넣기", font=FONT_SCENE_TITLE, fill=THEME["ink"])
    for i, item in enumerate(["기획", "평가", "구현", "테스트", "디자인"]):
        y = left[1] + 116 + i * 58
        draw.rounded_rectangle((left[0] + 42, y, left[2] - 42, y + 40), radius=12, fill=THEME["surface_alt"])
        draw.text((left[0] + 68, y + 8), item, font=FONT_UI, fill=THEME["muted"])
    draw.text((x1 + 692, y1 + 214), "->", font=FONT_DISPLAY, fill=THEME["blue"])
    draw.text((right[0] + 38, right[1] + 38), "역할별로 분리하기", font=FONT_SCENE_TITLE, fill=THEME["ink"])
    roles = [
        ("기획자", "아이디어 확장"),
        ("평가자", "냉정한 검토"),
        ("개발자", "파일과 구현"),
        ("보조 개발자", "테스트와 위험"),
        ("디자이너", "화면 전달력"),
    ]
    for i, (role, subtitle) in enumerate(roles):
        bx = right[0] + 42 + (i % 2) * 330
        by = right[1] + 116 + (i // 2) * 104
        draw_role_badge(draw, (bx, by, bx + 284, by + 78), role, subtitle)
    draw_pill(draw, (x1 + 430, y2 - 34, x2 - 430, y2), "판단 분리  /  역할 기준  /  메인 통합", THEME["blue_soft"], THEME["blue"], outline=THEME["blue"], fnt=FONT_UI, radius=16)


def scene_threads(draw: ImageDraw.ImageDraw, scene: Scene, index: int) -> None:
    x1, y1, x2, y2 = draw_demo_shell(draw, scene, index, active_thread="메인 스레드")
    draw_card(draw, (x1 + 24, y1 + 28, x1 + 560, y2 - 22), fill=THEME["surface"], outline=THEME["line"], radius=24)
    draw.text((x1 + 62, y1 + 68), "메인 스레드", font=FONT_SCENE_TITLE, fill=THEME["ink"])
    draw_wrapped(draw, (x1 + 62, y1 + 124), "큰 요청을 받고, 역할별 결과를 다시 모아 최종 판단을 내립니다.", FONT_UI_REGULAR, THEME["muted"], 430, line_gap=8)
    draw_pill(draw, (x1 + 62, y1 + 242, x1 + 492, y1 + 294), "최종 결과는 메인 스레드에서 확인", THEME["blue_soft"], THEME["blue"], outline=THEME["blue"], fnt=FONT_UI, radius=16)

    roles = ["기획자", "평가자", "개발자", "보조 개발자", "디자이너"]
    for i, role in enumerate(roles):
        bx = x1 + 676 + (i % 3) * 240
        by = y1 + 70 + (i // 3) * 170
        color = ROLE_COLORS[role]
        draw_card(draw, (bx, by, bx + 194, by + 112), fill=THEME["surface"], outline=color, width=3, radius=20)
        draw_centered(draw, (bx, by + 24, bx + 194, by + 58), role, FONT_UI, THEME["ink"])
        draw_pill(draw, (bx + 28, by + 70, bx + 166, by + 96), "별도 스레드", "#F8FAFC", color, outline=color, fnt=FONT_TINY, radius=12)
        draw.line((x1 + 560, y1 + 270, bx, by + 56), fill="#A7B5C8", width=3)
    draw_pill(draw, (x1 + 748, y2 - 72, x2 - 88, y2 - 24), "역할별 작업은 분리되고, 판단은 다시 하나로 모입니다.", THEME["surface_alt"], THEME["ink"], outline=THEME["line"], fnt=FONT_UI, radius=16)


def scene_planner_evaluator(draw: ImageDraw.ImageDraw, scene: Scene, index: int) -> None:
    x1, y1, x2, y2 = draw_demo_shell(draw, scene, index, active_thread="평가자")
    panel_w = 430
    draw_card(draw, (x1 + 24, y1 + 30, x1 + 24 + panel_w, y2 - 24), fill=THEME["surface"], outline=THEME["blue"], width=3, radius=24)
    draw_card(draw, (x1 + 496, y1 + 30, x1 + 496 + panel_w, y2 - 24), fill=THEME["surface"], outline=THEME["red"], width=3, radius=24)
    draw_card(draw, (x1 + 968, y1 + 30, x2 - 24, y2 - 24), fill=THEME["surface"], outline=THEME["green"], width=3, radius=24)
    draw.text((x1 + 62, y1 + 72), "기획자", font=FONT_SCENE_TITLE, fill=THEME["blue"])
    draw.text((x1 + 534, y1 + 72), "평가자", font=FONT_SCENE_TITLE, fill=THEME["red"])
    draw.text((x1 + 1006, y1 + 72), "채택 결과", font=FONT_SCENE_TITLE, fill=THEME["green"])
    for i, item in enumerate(["회의록 자동 분해", "버그 5개 동시 수정", "작업 관리 대시보드"]):
        y = y1 + 148 + i * 66
        fill = THEME["blue_soft"] if i == 2 else THEME["surface_alt"]
        draw.rounded_rectangle((x1 + 62, y, x1 + 392, y + 44), radius=13, fill=fill)
        draw.text((x1 + 86, y + 10), item, font=FONT_UI_REGULAR, fill=THEME["ink"])
    for i, (label, value, color) in enumerate([("영상성", "8/10", THEME["green"]), ("구현성", "9/10", THEME["green"]), ("과장 위험", "낮음", THEME["amber"])]):
        y = y1 + 150 + i * 74
        draw.text((x1 + 534, y), label, font=FONT_UI, fill=THEME["ink"])
        draw_pill(draw, (x1 + 760, y - 4, x1 + 878, y + 34), value, THEME["surface_alt"], color, outline=color, fnt=FONT_UI, radius=14)
    draw.text((x1 + 1006, y1 + 166), "작업 관리 대시보드", font=FONT_SCENE_TITLE, fill=THEME["ink"])
    draw_wrapped(draw, (x1 + 1008, y1 + 226), "상태 변경이 KPI와 위험 수에 즉시 반영되어 영상에서 결과 차이가 분명합니다.", FONT_UI_REGULAR, THEME["muted"], 340, line_gap=8)
    draw_pill(draw, (x1 + 1008, y2 - 92, x2 - 68, y2 - 42), "이 아이디어로 구현 데모 진행", THEME["green_soft"], THEME["green"], outline=THEME["green"], fnt=FONT_UI, radius=16)


def scene_parallel(draw: ImageDraw.ImageDraw, scene: Scene, index: int) -> None:
    x1, y1, x2, y2 = draw_demo_shell(draw, scene, index, active_thread="디자이너")
    lanes = [
        ("개발자", "템플릿화\n저장 구조\nGit 작업"),
        ("보조 개발자", "테스트 부족\n공개 저장소 위험\n보안 점검"),
        ("디자이너", "촬영 가독성\n정보 우선순위\n화면 정리"),
    ]
    for i, (role, body) in enumerate(lanes):
        lx = x1 + 36 + i * 460
        color = ROLE_COLORS[role]
        draw_card(draw, (lx, y1 + 40, lx + 398, y2 - 40), fill=THEME["surface"], outline=color, width=3, radius=24)
        draw_pill(draw, (lx + 34, y1 + 78, lx + 156, y1 + 114), role, color, "#FFFFFF", fnt=FONT_UI, radius=14)
        for j, line in enumerate(body.splitlines()):
            y = y1 + 168 + j * 78
            draw.rounded_rectangle((lx + 34, y, lx + 362, y + 50), radius=14, fill=THEME["surface_alt"])
            draw.text((lx + 58, y + 13), line, font=FONT_UI, fill=THEME["ink"])
        draw.line((lx + 58, y2 - 112, lx + 338, y2 - 112), fill=color, width=8)
        draw_pill(draw, (lx + 92, y2 - 92, lx + 304, y2 - 48), "역할별 산출물", "#F8FAFC", color, outline=color, fnt=FONT_UI, radius=15)
    draw_pill(draw, (x1 + 456, y2 - 24, x2 - 456, y2 + 20), "동시에 다른 관점 확보", THEME["blue_soft"], THEME["blue"], outline=THEME["blue"], fnt=FONT_UI, radius=16)


def scene_integration(draw: ImageDraw.ImageDraw, scene: Scene, index: int) -> None:
    x1, y1, x2, y2 = draw_demo_shell(draw, scene, index, active_thread="메인 스레드")
    center = (x1 + 496, y1 + 92, x1 + 920, y2 - 44)
    draw_card(draw, center, fill=THEME["surface"], outline=THEME["blue"], width=3, radius=26)
    draw.text((center[0] + 42, center[1] + 46), "통합 실행 계획", font=FONT_SCENE_TITLE, fill=THEME["ink"])
    for i, line in enumerate(["데모 아이디어 선택", "검토 기준 반영", "구현 순서 정리", "최종 산출물 저장"]):
        y = center[1] + 128 + i * 58
        draw_small_label(draw, (center[0] + 48, y + 8), line, THEME["blue"])
    sources = [
        ("기획", x1 + 54, y1 + 70, THEME["blue"]),
        ("평가", x1 + 1050, y1 + 70, THEME["red"]),
        ("개발", x1 + 54, y1 + 322, THEME["green"]),
        ("점검", x1 + 1050, y1 + 322, THEME["amber"]),
        ("디자인", x1 + 1050, y1 + 405, THEME["teal"]),
    ]
    for label, sx, sy, color in sources:
        draw_card(draw, (sx, sy, sx + 250, sy + 92), fill=THEME["surface"], outline=color, width=3, radius=20, shadow=False)
        draw_centered(draw, (sx, sy + 18, sx + 250, sy + 50), label, FONT_PANEL_TITLE, THEME["ink"])
        draw.line((sx + 250 if sx < center[0] else sx, sy + 46, center[0] if sx < center[0] else center[2], center[1] + 210), fill="#A9B7CB", width=3)
    draw_pill(draw, (center[0] + 58, center[3] - 78, center[2] - 58, center[3] - 32), "메인 스레드가 최종 판단", THEME["blue_soft"], THEME["blue"], outline=THEME["blue"], fnt=FONT_UI, radius=15)


def scene_dashboard(draw: ImageDraw.ImageDraw, scene: Scene, index: int) -> None:
    x1, y1, x2, y2 = draw_demo_shell(draw, scene, index)
    draw_card(draw, (x1 + 32, y1 + 24, x2 - 32, y2 - 18), fill=THEME["surface"], outline=THEME["line"], radius=26)
    draw.text((x1 + 72, y1 + 66), "작업 관리 대시보드", font=FONT_SCENE_TITLE, fill=THEME["ink"])
    kpis = [("완료율", "17% -> 33%", THEME["blue"]), ("활성 위험", "1 -> 0", THEME["red"]), ("상태", "위험 -> 완료", THEME["green"])]
    for i, (label, value, color) in enumerate(kpis):
        bx = x1 + 72 + i * 420
        draw.rounded_rectangle((bx, y1 + 132, bx + 354, y1 + 232), radius=18, fill=THEME["surface_alt"], outline=THEME["line"])
        draw.text((bx + 26, y1 + 154), label, font=FONT_META, fill=THEME["muted"])
        draw.text((bx + 26, y1 + 184), value, font=FONT_PANEL_TITLE, fill=color)
    draw.rounded_rectangle((x1 + 72, y1 + 260, x1 + 844, y1 + 312), radius=14, fill="#EDF2F8")
    draw.rounded_rectangle((x1 + 72, y1 + 260, x1 + 378, y1 + 312), radius=14, fill=THEME["blue"])
    draw.text((x1 + 104, y1 + 274), "완료율 상승", font=FONT_UI, fill="#FFFFFF")
    rows = [("서브에이전트 스레드 분리", "완료"), ("공개 저장소 보안 점검", "완료"), ("영상 화면 검수", "진행")]
    for i, (task, status) in enumerate(rows):
        y = y1 + 342 + i * 52
        draw.rounded_rectangle((x1 + 72, y, x1 + 1068, y + 38), radius=12, fill=THEME["surface_alt"])
        draw.text((x1 + 98, y + 8), task, font=FONT_UI_REGULAR, fill=THEME["ink"])
        color = THEME["green"] if status == "완료" else THEME["amber"]
        draw_pill(draw, (x1 + 906, y + 6, x1 + 1038, y + 32), status, "#FFFFFF", color, outline=color, fnt=FONT_TINY, radius=12)
    draw_card(draw, (x1 + 1120, y1 + 260, x2 - 72, y1 + 488), fill=THEME["green_soft"], outline=THEME["green"], width=3, radius=22, shadow=False)
    draw.text((x1 + 1160, y1 + 300), "공개 저장소 보안 점검", font=FONT_UI, fill=THEME["green"])
    draw.text((x1 + 1160, y1 + 352), "위험 -> 완료", font=FONT_SCENE_TITLE, fill=THEME["green"])
    draw_wrapped(draw, (x1 + 1160, y1 + 414), "상태 변경이 KPI와 위험 수에 즉시 반영됩니다.", FONT_TINY, THEME["muted"], 340, line_gap=5)


def scene_outputs(draw: ImageDraw.ImageDraw, scene: Scene, index: int) -> None:
    x1, y1, x2, y2 = draw_demo_shell(draw, scene, index)
    draw_card(draw, (x1 + 34, y1 + 30, x1 + 760, y2 - 28), fill=THEME["surface"], outline=THEME["line"], radius=24)
    draw.text((x1 + 72, y1 + 72), "프로젝트 산출물", font=FONT_SCENE_TITLE, fill=THEME["ink"])
    files = [
        (".codex/agents", "역할 정의"),
        ("codex-subagent-demo-kit", "프롬프트와 가이드"),
        ("task-dashboard-demo", "구현 데모"),
        ("video-production", "MP4, 내레이션, 자막"),
    ]
    for i, (name, desc) in enumerate(files):
        y = y1 + 146 + i * 66
        draw.rounded_rectangle((x1 + 72, y, x1 + 708, y + 46), radius=12, fill=THEME["surface_alt"])
        draw.text((x1 + 96, y + 11), name, font=FONT_UI, fill=THEME["blue"])
        draw.text((x1 + 430, y + 12), desc, font=FONT_TINY, fill=THEME["muted"])
    draw_card(draw, (x1 + 822, y1 + 30, x2 - 34, y2 - 28), fill=THEME["surface"], outline=THEME["line"], radius=24)
    draw.text((x1 + 862, y1 + 72), "GitHub 동기화", font=FONT_SCENE_TITLE, fill=THEME["ink"])
    steps = ["저장", "커밋", "푸시", "재사용"]
    for i, step in enumerate(steps):
        cx = x1 + 856 + i * 140
        cy = y1 + 202
        draw.ellipse((cx, cy, cx + 86, cy + 86), fill=THEME["blue"], outline=THEME["blue"])
        draw_centered(draw, (cx, cy + 22, cx + 86, cy + 54), str(i + 1), FONT_PANEL_TITLE, "#FFFFFF")
        draw.text((cx + 8, cy + 112), step, font=FONT_UI, fill=THEME["ink"])
        if i < 3:
            draw.line((cx + 92, cy + 43, cx + 132, cy + 43), fill=THEME["line"], width=5)
    draw_pill(draw, (x1 + 914, y2 - 76, x2 - 128, y2 - 32), "다음 프로젝트에 다시 사용", THEME["blue_soft"], THEME["blue"], outline=THEME["blue"], fnt=FONT_UI, radius=16)


def scene_summary(draw: ImageDraw.ImageDraw, scene: Scene, index: int) -> None:
    x1, y1, x2, y2 = draw_demo_shell(draw, scene, index)
    pillars = [
        ("역할 분리", "기획, 평가, 구현을 섞지 않음", THEME["blue"]),
        ("병렬 검토", "같은 시간에 다른 관점 확보", THEME["green"]),
        ("통합 판단", "메인 스레드에서 결정", THEME["amber"]),
        ("재사용", "템플릿과 Git 구조로 저장", THEME["teal"]),
    ]
    for i, (title, desc, color) in enumerate(pillars):
        bx = x1 + 34 + i * 344
        draw_card(draw, (bx, y1 + 70, bx + 286, y1 + 408), fill=THEME["surface"], outline=color, width=3, radius=26)
        draw.ellipse((bx + 102, y1 + 118, bx + 184, y1 + 200), fill=color)
        draw_centered(draw, (bx + 102, y1 + 140, bx + 184, y1 + 168), str(i + 1), FONT_PANEL_TITLE, "#FFFFFF")
        draw_centered(draw, (bx + 30, y1 + 240, bx + 256, y1 + 272), title, FONT_PANEL_TITLE, THEME["ink"])
        draw_wrapped(draw, (bx + 42, y1 + 298), desc, FONT_TINY, THEME["muted"], 210, line_gap=5)
    draw_pill(draw, (x1 + 310, y2 - 120, x2 - 310, y2 - 60), "서브에이전트는 복잡한 요청을 설명 가능한 AI 팀 워크플로로 바꿉니다.", THEME["surface"], THEME["ink"], outline=THEME["line"], fnt=FONT_UI, radius=18)


VISUALS = {
    "problem": scene_problem,
    "threads": scene_threads,
    "planner_evaluator": scene_planner_evaluator,
    "parallel": scene_parallel,
    "integration": scene_integration,
    "dashboard": scene_dashboard,
    "outputs": scene_outputs,
    "summary": scene_summary,
}


def render_slide(scene: Scene, index: int) -> Path:
    image = Image.new("RGB", (WIDTH, HEIGHT), THEME["page"])
    draw = ImageDraw.Draw(image)
    VISUALS[scene.visual](draw, scene, index)
    output = ASSET_DIR / f"2026-07-08-scene-{index:02d}.png"
    image.save(output, "PNG")
    return output


def format_srt_time(seconds: float) -> str:
    td = timedelta(seconds=max(seconds, 0))
    total_ms = int(td.total_seconds() * 1000)
    hours, rem = divmod(total_ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, ms = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def run_ffmpeg(args: list[str], allow_failure: bool = False) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        args,
        cwd=str(OUT_DIR),
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    if completed.returncode and not allow_failure:
        print(completed.stdout)
        print(completed.stderr)
        raise RuntimeError(f"ffmpeg failed: {' '.join(args)}")
    return completed


def media_duration(ffmpeg: str, path: Path) -> float:
    completed = run_ffmpeg([ffmpeg, "-i", str(path)], allow_failure=True)
    text = completed.stdout + completed.stderr
    match = re.search(r"Duration:\s+(\d+):(\d+):(\d+(?:\.\d+)?)", text)
    if not match:
        raise RuntimeError(f"Duration not found for {path}")
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


async def synthesize_scene_audio() -> list[Path]:
    paths: list[Path] = []
    for index, scene in enumerate(SCENES, start=1):
        output = ASSET_DIR / f"2026-07-08-scene-{index:02d}-voice.mp3"
        paths.append(output)
        if output.exists() and output.stat().st_size > 10_000:
            continue
        communicate = edge_tts.Communicate(scene.narration, voice=VOICE, rate=VOICE_RATE)
        await communicate.save(str(output))
    return paths


def write_concat_file(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_srt(durations: list[float]) -> None:
    start = 0.0
    blocks: list[str] = []
    for index, (scene, duration) in enumerate(zip(SCENES, durations), start=1):
        end = start + duration
        wrapped = "\n".join(textwrap.wrap(scene.caption, width=38))
        blocks.append(
            f"{index}\n{format_srt_time(start)} --> {format_srt_time(end)}\n{wrapped}\n"
        )
        start = end
    SUBTITLE_FILE.write_text("\n".join(blocks), encoding="utf-8")


def build_video(ffmpeg: str, slide_paths: list[Path], audio_paths: list[Path], durations: list[float]) -> None:
    audio_list = ASSET_DIR / "2026-07-08-audio-concat.txt"
    # FFmpeg resolves concat entries relative to the list file itself.
    write_concat_file(audio_list, [f"file '{path.name}'" for path in audio_paths])
    run_ffmpeg([
        ffmpeg,
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        audio_list.relative_to(OUT_DIR).as_posix(),
        "-c:a",
        "libmp3lame",
        "-b:a",
        "160k",
        NARRATION_FILE.name,
    ])
    narration_duration = media_duration(ffmpeg, NARRATION_FILE)

    image_lines: list[str] = []
    for slide, duration in zip(slide_paths, durations):
        image_lines.append(f"file '{slide.name}'")
        image_lines.append(f"duration {duration:.3f}")
    image_lines.append(f"file '{slide_paths[-1].name}'")
    image_list = ASSET_DIR / "2026-07-08-image-concat.txt"
    write_concat_file(image_list, image_lines)

    run_ffmpeg([
        ffmpeg,
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        image_list.relative_to(OUT_DIR).as_posix(),
        "-i",
        NARRATION_FILE.name,
        "-vf",
        "fps=30,format=yuv420p",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "20",
        "-c:a",
        "aac",
        "-b:a",
        "160k",
        "-t",
        f"{narration_duration:.3f}",
        "-movflags",
        "+faststart",
        VIDEO_FILE.name,
    ])


def write_manifest(ffmpeg: str, durations: list[float]) -> None:
    video_duration = media_duration(ffmpeg, VIDEO_FILE)
    narration_duration = media_duration(ffmpeg, NARRATION_FILE)
    data = {
        "title": "Codex Subagent 구현 데모",
        "voice": VOICE,
        "voice_rate": VOICE_RATE,
        "font_family": "NanumSquare Neo",
        "font_files": {
            "regular": "NanumSquareNeo-bRg.ttf",
            "bold": "NanumSquareNeo-cBd.ttf",
            "extra_bold": "NanumSquareNeo-dEb.ttf",
        },
        "visual_design": "product-demo-app-shell-v2",
        "scene_count": len(SCENES),
        "scene_durations_seconds": [round(value, 2) for value in durations],
        "video_duration_seconds": round(video_duration, 2),
        "narration_duration_seconds": round(narration_duration, 2),
        "files": {
            "video": VIDEO_FILE.name,
            "narration": NARRATION_FILE.name,
            "subtitles": SUBTITLE_FILE.name,
        },
        "file_sizes_bytes": {
            "video": VIDEO_FILE.stat().st_size,
            "narration": NARRATION_FILE.stat().st_size,
            "subtitles": SUBTITLE_FILE.stat().st_size,
        },
        "message": "서브에이전트는 역할 분리, 병렬 검토, 메인 스레드 통합을 보여주는 워크플로입니다.",
    }
    MANIFEST_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()

    slide_paths = [render_slide(scene, index) for index, scene in enumerate(SCENES, start=1)]
    audio_paths = asyncio.run(synthesize_scene_audio())
    durations = [media_duration(ffmpeg, path) for path in audio_paths]

    build_srt(durations)
    build_video(ffmpeg, slide_paths, audio_paths, durations)
    write_manifest(ffmpeg, durations)

    print(f"MP4: {VIDEO_FILE}")
    print(f"내레이션: {NARRATION_FILE}")
    print(f"자막: {SUBTITLE_FILE}")
    print(f"제작정보: {MANIFEST_FILE}")


if __name__ == "__main__":
    main()
