"""生成状态驱动的长期交互记忆 Benchmark 架构图与人物数据卡片。"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from collections import Counter
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
OUTPUT = ROOT / "data" / "output"
QA_DIR = ROOT / "data" / "qa"
FIGURE_SKILL = Path(
    r"D:\youyan\笔记\汇报及作图及结果图工具\nature-skills\skills\nature-figure"
)
sys.path.insert(0, str(FIGURE_SKILL / "scripts"))
from audit_panel_alignment import require_matplotlib_panel_alignment  # noqa: E402


mpl.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": [
            "Microsoft YaHei",
            "SimHei",
            "Arial",
            "DejaVu Sans",
            "sans-serif",
        ],
        "font.size": 7,
        "axes.linewidth": 0.8,
        "svg.fonttype": "none",
        "pdf.fonttype": 42,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
    }
)


INK = "#202124"
MUTED = "#687078"
LINE = "#B8C0C8"
BLUE = "#3775BA"
BLUE_DARK = "#174F86"
BLUE_PALE = "#EAF2FA"
VIOLET = "#7656A8"
VIOLET_PALE = "#F0EAF7"
TEAL = "#348C86"
TEAL_PALE = "#E4F3F1"
ORANGE = "#C66A2B"
ORANGE_PALE = "#FBEDE3"
GREEN = "#4A8B57"
GREEN_PALE = "#E8F3E9"
RED = "#B55252"
RED_PALE = "#F8E9E8"
GREY_PALE = "#F3F5F7"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def setup_axis(ax, panel: str | None = None):
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    if panel:
        ax.text(
            -0.02,
            1.015,
            panel,
            transform=ax.transAxes,
            fontsize=9,
            fontweight="bold",
            color=INK,
            ha="left",
            va="bottom",
        )


def box(
    ax,
    xy,
    wh,
    title,
    body="",
    *,
    fill=BLUE_PALE,
    edge=BLUE,
    title_color=INK,
    body_color=MUTED,
    lw=1.0,
    radius=0.03,
    title_size=7.2,
    body_size=5.8,
    align="center",
    zorder=2,
):
    x, y = xy
    w, h = wh
    patch = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle=f"round,pad=0.008,rounding_size={radius}",
        facecolor=fill,
        edgecolor=edge,
        linewidth=lw,
        zorder=zorder,
    )
    ax.add_patch(patch)
    tx = x + w / 2 if align == "center" else x + 0.018
    ha = "center" if align == "center" else "left"
    ax.text(
        tx,
        y + h * (0.63 if body else 0.5),
        title,
        ha=ha,
        va="center",
        fontsize=title_size,
        fontweight="bold",
        color=title_color,
        linespacing=1.15,
        zorder=zorder + 1,
    )
    if body:
        ax.text(
            tx,
            y + h * 0.30,
            body,
            ha=ha,
            va="center",
            fontsize=body_size,
            color=body_color,
            linespacing=1.25,
            zorder=zorder + 1,
        )
    return patch


def arrow(
    ax,
    start,
    end,
    *,
    color=LINE,
    lw=1.2,
    rad=0.0,
    style="-|>",
    zorder=1,
):
    item = FancyArrowPatch(
        start,
        end,
        arrowstyle=style,
        mutation_scale=8,
        linewidth=lw,
        color=color,
        connectionstyle=f"arc3,rad={rad}",
        shrinkA=0,
        shrinkB=0,
        zorder=zorder,
    )
    ax.add_patch(item)
    return item


def capsule(ax, x, y, text, fill, edge, width=0.11, height=0.055, size=5.5):
    box(
        ax,
        (x, y),
        (width, height),
        text,
        fill=fill,
        edge=edge,
        radius=0.025,
        title_size=size,
        lw=0.8,
    )


def metric(ax, x, y, value, label, *, color=BLUE_DARK, width=0.14):
    ax.text(
        x,
        y,
        str(value),
        fontsize=15,
        fontweight="bold",
        color=color,
        ha="center",
        va="center",
    )
    ax.text(
        x,
        y - 0.07,
        label,
        fontsize=5.8,
        color=MUTED,
        ha="center",
        va="top",
        linespacing=1.15,
    )
    ax.plot(
        [x - width / 2, x + width / 2],
        [y - 0.105, y - 0.105],
        color=LINE,
        linewidth=0.7,
    )


def save_figure(fig, basename: str, *, dpi=600, alignment_kwargs=None):
    target = DOCS / basename
    kwargs = alignment_kwargs or {}
    with tempfile.TemporaryDirectory(prefix=f"{basename}-qa-") as temp_dir:
        qa_dir = os.environ.get("FIGURE_QA_DIR")
        qa_root = Path(qa_dir) / basename if qa_dir else Path(temp_dir) / basename
        qa_root.parent.mkdir(parents=True, exist_ok=True)
        require_matplotlib_panel_alignment(
            fig,
            json_out=str(qa_root.with_suffix(".alignment.json")),
            overlay_svg=str(qa_root.with_suffix(".alignment.svg")),
            tolerance_pt=1.5,
            gutter_tolerance_pt=1.5,
            strict=True,
            **kwargs,
        )
        fig.savefig(target.with_suffix(".svg"), bbox_inches="tight")
        fig.savefig(qa_root.with_suffix(".pdf"), bbox_inches="tight")
        preview_dir = os.environ.get("FIGURE_PREVIEW_DIR")
        preview_path = (
            Path(preview_dir) / f"{basename}.png"
            if preview_dir
            else qa_root.with_suffix(".png")
        )
        if preview_dir:
            preview_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(preview_path, dpi=dpi, bbox_inches="tight")
        fig.savefig(qa_root.with_suffix(".tiff"), dpi=dpi, bbox_inches="tight")
    plt.close(fig)


def architecture_figure():
    fig = plt.figure(figsize=(7.2, 5.65), constrained_layout=False)
    grid = fig.add_gridspec(
        2,
        2,
        height_ratios=[1.15, 1.0],
        left=0.035,
        right=0.985,
        top=0.895,
        bottom=0.055,
        hspace=0.20,
        wspace=0.12,
    )
    ax_a = fig.add_subplot(grid[0, :])
    ax_b = fig.add_subplot(grid[1, 0])
    ax_c = fig.add_subplot(grid[1, 1])
    for ax, label in zip([ax_a, ax_b, ax_c], ["a", "b", "c"]):
        setup_axis(ax, label)

    fig.text(
        0.035,
        0.962,
        "状态驱动的长期交互记忆 Benchmark",
        fontsize=13,
        fontweight="bold",
        color=INK,
        ha="left",
        va="top",
    )
    fig.text(
        0.035,
        0.925,
        "人物状态先被规划，再由事件实现并通过自然对话暴露；会话持续增长，任意冻结版本都可独立出题。",
        fontsize=7,
        color=MUTED,
        ha="left",
        va="top",
    )

    # a — worldline growth
    ax_a.text(
        0.015,
        0.96,
        "世界线生长：人工/参数控制方向，模型实现合理路径",
        fontsize=8,
        fontweight="bold",
        color=INK,
        va="top",
    )
    steps = [
        (
            0.015,
            "人物种子",
            "结构化事实\n＋人物摘要",
            GREY_PALE,
            MUTED,
        ),
        (
            0.180,
            "领域规划",
            "16 个领域中选取\n1 主线＋4 副线",
            VIOLET_PALE,
            VIOLET,
        ),
        (
            0.345,
            "章末状态差",
            "10 条 create / update\n规定 What",
            BLUE_PALE,
            BLUE,
        ),
        (
            0.510,
            "时间事件图",
            "把变化变成因果事件\n规定 When / Why",
            ORANGE_PALE,
            ORANGE,
        ),
        (
            0.675,
            "双角色对话",
            "User 自然披露\nAssistant 正常回应",
            TEAL_PALE,
            TEAL,
        ),
        (
            0.840,
            "证据提交",
            "事实·事件·turn 证据\n覆盖后才落盘",
            GREEN_PALE,
            GREEN,
        ),
    ]
    for x, title, body, fill, edge in steps:
        box(
            ax_a,
            (x, 0.51),
            (0.14, 0.27),
            title,
            body,
            fill=fill,
            edge=edge,
            title_size=7.0,
            body_size=5.5,
        )
    for left, right in zip(steps[:-1], steps[1:]):
        arrow(ax_a, (left[0] + 0.142, 0.645), (right[0] - 0.004, 0.645), color=LINE)

    # Cumulative chain
    ax_a.text(
        0.015,
        0.405,
        "累计状态链",
        fontsize=6.2,
        fontweight="bold",
        color=BLUE_DARK,
        va="center",
    )
    for i, (x, label, sub) in enumerate(
        [
            (0.145, "v0", "初始画像"),
            (0.285, "v1", "一个月"),
            (0.425, "v2", "继续生长"),
            (0.565, "…", "旧事实保留"),
            (0.705, "v13", "冻结快照"),
            (0.845, "vN", "仍可续长"),
        ]
    ):
        fill = GREEN_PALE if label in {"v0", "v13"} else BLUE_PALE
        edge = GREEN if label in {"v0", "v13"} else BLUE
        box(
            ax_a,
            (x, 0.30),
            (0.105, 0.18),
            label,
            sub,
            fill=fill,
            edge=edge,
            title_size=7.0,
            body_size=5.0,
        )
        if i:
            arrow(ax_a, (x - 0.035, 0.39), (x - 0.006, 0.39), color=BLUE)
    ax_a.text(
        0.145,
        0.20,
        "每轮写回当前画像，下一轮从该画像继续；sessions / extracts / summaries 对同一人物只追加、不重写。",
        fontsize=5.8,
        color=MUTED,
        ha="left",
        va="center",
    )
    ax_a.text(
        0.897,
        0.235,
        "反馈 → 下一轮输入",
        fontsize=5.4,
        color=VIOLET,
        ha="center",
    )

    # b — dual role dialogue engine
    ax_b.text(
        0.02,
        0.96,
        "对话引擎：信息不对称的双角色生成",
        fontsize=8,
        fontweight="bold",
        color=INK,
        va="top",
    )
    box(
        ax_b,
        (0.02, 0.68),
        (0.34, 0.20),
        "",
        "",
        fill=TEAL_PALE,
        edge=TEAL,
        title_size=7.5,
        body_size=5.5,
    )
    ax_b.text(
        0.19,
        0.815,
        "User Agent",
        fontsize=7.5,
        fontweight="bold",
        color=INK,
        ha="center",
        va="center",
    )
    ax_b.text(
        0.19,
        0.735,
        "扮演人物 · 主动开口\n逐轮自然透露目标状态",
        fontsize=5.5,
        color=MUTED,
        ha="center",
        va="center",
        linespacing=1.25,
    )
    box(
        ax_b,
        (0.64, 0.68),
        (0.34, 0.20),
        "",
        "",
        fill=BLUE_PALE,
        edge=BLUE,
        title_size=7.5,
        body_size=5.5,
    )
    ax_b.text(
        0.81,
        0.815,
        "Assistant Agent",
        fontsize=7.5,
        fontweight="bold",
        color=INK,
        ha="center",
        va="center",
    )
    ax_b.text(
        0.81,
        0.735,
        "友好 AI 助手\n只按对话内容正常回应",
        fontsize=5.5,
        color=MUTED,
        ha="center",
        va="center",
        linespacing=1.25,
    )
    arrow(ax_b, (0.37, 0.82), (0.63, 0.82), color=TEAL, lw=1.4)
    arrow(ax_b, (0.63, 0.73), (0.37, 0.73), color=BLUE, lw=1.4)
    ax_b.text(
        0.50,
        0.88,
        "12 turns",
        fontsize=5.5,
        color=MUTED,
        ha="center",
        va="center",
    )
    box(
        ax_b,
        (0.02, 0.16),
        (0.44, 0.41),
        "User 可见上下文",
        "人物摘要\n此前已发生事件\n本次事件＋状态变更\n最近 10 条滚动摘要",
        fill=GREY_PALE,
        edge=TEAL,
        align="left",
        title_size=6.8,
        body_size=5.5,
    )
    box(
        ax_b,
        (0.54, 0.16),
        (0.44, 0.41),
        "Assistant 可见上下文",
        "当前日期\n本段已经发生的对话\n\n看不到事件图和目标状态",
        fill=GREY_PALE,
        edge=BLUE,
        align="left",
        title_size=6.8,
        body_size=5.5,
    )
    arrow(ax_b, (0.24, 0.58), (0.19, 0.67), color=TEAL)
    arrow(ax_b, (0.76, 0.58), (0.81, 0.67), color=BLUE)
    ax_b.text(
        0.50,
        0.06,
        "滚动摘要既维持连续性，也避免把全部历史对话塞回上下文。",
        fontsize=5.5,
        color=MUTED,
        ha="center",
    )

    # c — grounding and benchmark
    ax_c.text(
        0.02,
        0.96,
        "验证与产物：从一句话追溯到最终画像",
        fontsize=8,
        fontweight="bold",
        color=INK,
        va="top",
    )
    y = 0.70
    items = [
        (0.02, "生成会话", "用户/助手交替", TEAL_PALE, TEAL),
        (0.265, "抽取", "fact · event", ORANGE_PALE, ORANGE),
        (0.510, "证据对齐", "turn → state", VIOLET_PALE, VIOLET),
        (0.755, "覆盖检查", "失败重试 ≤3", RED_PALE, RED),
    ]
    for x, title, body, fill, edge in items:
        box(
            ax_c,
            (x, y),
            (0.205, 0.17),
            title,
            body,
            fill=fill,
            edge=edge,
            title_size=6.3,
            body_size=5.1,
        )
    for left, right in zip(items[:-1], items[1:]):
        arrow(ax_c, (left[0] + 0.207, y + 0.085), (right[0] - 0.004, y + 0.085))

    ax_c.text(
        0.02,
        0.59,
        "提交后形成三类可追溯材料",
        fontsize=6.4,
        fontweight="bold",
        color=INK,
    )
    capsule(ax_c, 0.02, 0.47, "状态链", BLUE_PALE, BLUE, width=0.18)
    capsule(ax_c, 0.22, 0.47, "完整会话", TEAL_PALE, TEAL, width=0.18)
    capsule(ax_c, 0.42, 0.47, "turn 证据", VIOLET_PALE, VIOLET, width=0.18)
    capsule(ax_c, 0.62, 0.47, "滚动摘要", ORANGE_PALE, ORANGE, width=0.18)
    capsule(ax_c, 0.82, 0.47, "当前画像", GREEN_PALE, GREEN, width=0.16)

    box(
        ax_c,
        (0.02, 0.16),
        (0.96, 0.22),
        "冻结快照 → 独立 QA 流水线",
        "信息抽取 IE  ·  开放域 OD  ·  时间推理 TR  ·  拒答 RJ  ·  知识更新 KU\n单跳读取一个状态；多跳读取同一 subject 的历史版本链。之后仍可继续生成 vN。",
        fill=GREY_PALE,
        edge=INK,
        align="left",
        title_size=7.0,
        body_size=5.5,
    )
    ax_c.text(
        0.02,
        0.06,
        "核心解耦：生成阶段创造可验证记忆；出题阶段只消费已冻结的状态与证据。",
        fontsize=5.5,
        color=MUTED,
    )

    save_figure(
        fig,
        "architecture",
        alignment_kwargs={
            "panel_ids": {ax_b: "b", ax_c: "c"},
            "row_groups": [["b", "c"]],
            "exclude_axes": [ax_a],
        },
    )


def profile_card_figure():
    initial = load_json(ROOT / "data" / "persons" / "P001_v0_profile_data.json")
    profile = load_json(OUTPUT / "P001_v13_profile_data.json")
    planning = load_json(OUTPUT / "P001_v13_planning_state.json")
    events = load_json(OUTPUT / "P001_v13_time_event_graph.json")["events"]
    sessions = load_json(OUTPUT / "P001_dialogue_sessions.json")["sessions"]
    extracts = load_jsonl(OUTPUT / "P001_dialogue_extracts.jsonl")
    summaries = load_jsonl(OUTPUT / "P001_dialogue_summaries.jsonl")
    qa_single = load_jsonl(QA_DIR / "P001_single_questions.jsonl")
    qa_multi = load_jsonl(QA_DIR / "P001_multi_questions.jsonl")

    versions = [version for chain in planning["states"] for version in chain["versions"]]
    evidence_count = sum(len(row.get("evidence", [])) for row in extracts)
    turns = sum(len(session["turns"]) for session in sessions)
    domain_counts = Counter(state["domain"] for state in profile["states"])

    chains = {chain["subject"]: chain for chain in planning["states"]}

    def values(subject):
        return [" / ".join(v["value"]) for v in chains[subject]["versions"]]

    def state_value(subject):
        state = next(item for item in profile["states"] if item["subject"] == subject)
        return " / ".join(state["value"])

    initial_values = {
        state["subject"]: " / ".join(state["value"]) for state in initial["states"]
    }

    fig, ax = plt.subplots(figsize=(7.2, 5.7))
    setup_axis(ax)
    fig.subplots_adjust(left=0.025, right=0.985, top=0.975, bottom=0.035)

    # Header
    ax.add_patch(
        FancyBboxPatch(
            (0.0, 0.86),
            1.0,
            0.14,
            boxstyle="round,pad=0.0,rounding_size=0.02",
            facecolor=BLUE_DARK,
            edgecolor=BLUE_DARK,
            linewidth=0,
        )
    )
    ax.text(
        0.035,
        0.952,
        "P001 · 林晓",
        fontsize=15,
        fontweight="bold",
        color="white",
        ha="left",
        va="center",
    )
    ax.text(
        0.035,
        0.902,
        "从 9 条初始事实出发，经过 13 轮可控生长形成的可追溯人物快照",
        fontsize=7,
        color="#DCE9F5",
        ha="left",
        va="center",
    )
    ax.text(
        0.965,
        0.947,
        "v13",
        fontsize=14,
        fontweight="bold",
        color="white",
        ha="right",
        va="center",
    )
    ax.text(
        0.965,
        0.898,
        f"{sessions[0]['session_time']} — {sessions[-1]['session_time']}",
        fontsize=6,
        color="#DCE9F5",
        ha="right",
        va="center",
    )

    # Metrics
    metrics = [
        (len(profile["states"]), "当前状态"),
        (len(domain_counts), "覆盖领域"),
        (len(versions), "状态版本"),
        (len(events), "时间事件"),
        (len(sessions), "对话会话"),
        (turns, "对话 turns"),
        (evidence_count, "证据片段"),
        (len(qa_single) + len(qa_multi), "已生成问题"),
    ]
    for index, (value, label) in enumerate(metrics):
        metric(ax, 0.065 + index * 0.1245, 0.805, value, label, width=0.095)

    # v0 portrait
    box(
        ax,
        (0.0, 0.47),
        (0.285, 0.24),
        "",
        "",
        fill=GREY_PALE,
        edge=LINE,
        align="left",
        title_size=8,
    )
    ax.text(
        0.025,
        0.680,
        "v0 · 初始人物画像",
        fontsize=8,
        fontweight="bold",
        color=INK,
        ha="left",
        va="center",
    )
    initial_portrait = [
        ("姓名", initial_values["法定姓名"]),
        ("居住", initial_values["现居地"]),
        ("父母", initial_values["父母居住地"]),
        ("学校", initial_values["本科毕业院校"]),
        ("专业", initial_values["本科主修专业"]),
        ("房租", initial_values["每月房租"]),
        ("通勤", initial_values["日常通勤"]),
        ("住房", initial_values["住房类型"]),
        ("手机", "iPhone 14 Pro Max / iPhone 13"),
    ]
    for idx, (name, value) in enumerate(initial_portrait):
        y = 0.645 - idx * 0.021
        ax.text(0.025, y, name, fontsize=5.0, color=MUTED, fontweight="bold", va="center")
        ax.text(0.075, y, value, fontsize=5.0, color=INK, va="center")
    ax.text(
        0.255,
        0.680,
        "9 states",
        fontsize=5.3,
        color=MUTED,
        ha="right",
        va="center",
    )

    # Growth bridge
    arrow(ax, (0.300, 0.585), (0.425, 0.585), color=VIOLET, lw=2.0)
    ax.text(
        0.362,
        0.655,
        "13 轮生长",
        fontsize=7.2,
        fontweight="bold",
        color=VIOLET,
        ha="center",
    )
    ax.text(0.362, 0.620, "+70 create", fontsize=5.4, color=MUTED, ha="center")
    ax.text(0.362, 0.548, "+60 update", fontsize=5.4, color=MUTED, ha="center")
    ax.text(
        0.362,
        0.505,
        "事件驱动\n证据约束",
        fontsize=5.1,
        color=VIOLET,
        ha="center",
        va="center",
        linespacing=1.25,
    )

    # v13 portrait
    box(
        ax,
        (0.44, 0.47),
        (0.56, 0.24),
        "",
        "",
        fill=GREEN_PALE,
        edge=GREEN,
        align="left",
        title_size=8,
    )
    ax.text(
        0.465,
        0.680,
        "v13 · 最终人物画像",
        fontsize=8,
        fontweight="bold",
        color=INK,
        ha="left",
        va="center",
    )
    ax.text(
        0.970,
        0.680,
        "79 states · 16 domains",
        fontsize=5.3,
        color=MUTED,
        ha="right",
        va="center",
    )
    final_portrait = [
        ("居住", "苏州高新区"),
        ("住房", "租住一室一厅"),
        ("职业", "资深后端开发工程师"),
        ("薪资", "税后 21500 元"),
        ("宠物", "橘猫一只"),
        ("感情", "单身"),
        ("手机", "iPhone 15 Pro"),
        ("工具", "Notion / 飞书"),
        ("储蓄", "每月 3000 元"),
        ("运动", "每周游泳两次"),
        ("阅读", "《芯片战争》"),
        ("价值", "健康与稳定优先"),
    ]
    for idx, (name, value) in enumerate(final_portrait):
        col = idx // 6
        row = idx % 6
        x = 0.465 + col * 0.265
        y = 0.642 - row * 0.030
        ax.text(x, y, name, fontsize=5.0, color=GREEN, fontweight="bold", va="center")
        ax.text(x + 0.052, y, value, fontsize=5.0, color=INK, va="center")

    # State-chain examples
    box(
        ax,
        (0.0, 0.245),
        (0.68, 0.18),
        "",
        "",
        fill=BLUE_PALE,
        edge=BLUE,
        align="left",
        title_size=8,
    )
    ax.text(
        0.025,
        0.395,
        "状态变更链",
        fontsize=7.5,
        fontweight="bold",
        color=INK,
        ha="left",
        va="center",
    )
    examples = [
        ("房租", values("每月房租"), "v0 → v1 → v2 → v8"),
        ("手机", values("持有手机"), "v0 → v1 → v5 → v7 → v12"),
        ("薪资", values("税后月薪"), "v2 → v6 → v10 → v12"),
        ("联系", values("主要联系渠道"), "v1 → v9 → v10 → v13"),
    ]
    for idx, (name, vals, rounds) in enumerate(examples):
        y = 0.355 - idx * 0.035
        shown = " → ".join(vals)
        if len(shown) > 62:
            shown = shown[:60] + "…"
        ax.text(0.025, y, name, fontsize=5.2, color=BLUE_DARK, fontweight="bold", va="center")
        ax.text(0.078, y, shown, fontsize=5.0, color=INK, va="center")
        ax.text(0.655, y, rounds, fontsize=5.0, color=MUTED, ha="right", va="center")

    # Traceability
    box(
        ax,
        (0.70, 0.245),
        (0.30, 0.18),
        "",
        "",
        fill=VIOLET_PALE,
        edge=VIOLET,
        align="left",
        title_size=7.4,
    )
    ax.text(
        0.725,
        0.395,
        "一条记忆如何被追溯",
        fontsize=7.5,
        fontweight="bold",
        color=INK,
        ha="left",
        va="center",
    )
    trace = [
        ("状态", "持有银行卡"),
        ("事件", "补办招商储蓄卡"),
        ("会话", "v1-S001"),
        ("证据", "v1-EV001-T003"),
        ("原话", "“多了一张招商银行的储蓄卡”"),
    ]
    for idx, (key, value) in enumerate(trace):
        y = 0.355 - idx * 0.028
        ax.text(0.725, y, key, fontsize=5.0, color=VIOLET, fontweight="bold", va="center")
        ax.text(0.785, y, value, fontsize=5.0, color=INK, va="center")

    # Domain distribution
    ax.text(
        0.0,
        0.195,
        "领域覆盖",
        fontsize=7,
        fontweight="bold",
        color=INK,
        ha="left",
        va="center",
    )
    ordered = sorted(domain_counts.items(), key=lambda item: (-item[1], item[0]))
    max_count = max(domain_counts.values())
    cols = 8
    for idx, (domain, count) in enumerate(ordered):
        row, col = divmod(idx, cols)
        x = col * 0.125
        y = 0.125 - row * 0.070
        width = 0.105
        ax.add_patch(
            FancyBboxPatch(
                (x, y),
                width,
                0.052,
                boxstyle="round,pad=0.005,rounding_size=0.012",
                facecolor=BLUE_PALE,
                edgecolor=LINE,
                linewidth=0.6,
            )
        )
        ax.add_patch(
            FancyBboxPatch(
                (x, y),
                width * count / max_count,
                0.052,
                boxstyle="round,pad=0.005,rounding_size=0.012",
                facecolor=BLUE,
                edgecolor=BLUE,
                linewidth=0,
                alpha=0.24,
            )
        )
        short = domain.replace("与", "·")
        ax.text(x + 0.008, y + 0.031, short, fontsize=5.0, color=INK, va="center")
        ax.text(
            x + width - 0.006,
            y + 0.031,
            str(count),
            fontsize=5.0,
            color=BLUE_DARK,
            fontweight="bold",
            ha="right",
            va="center",
        )

    ax.text(
        0.0,
        0.012,
        f"状态操作：9 initial + {sum(v['op'] == 'create' for v in versions)} create + "
        f"{sum(v['op'] == 'update' for v in versions)} update    ·    "
        f"对话材料：{len(extracts)} extracts + {len(summaries)} rolling summaries    ·    "
        f"问题集：{len(qa_single)} single-hop + {len(qa_multi)} multi-hop",
        fontsize=5.3,
        color=MUTED,
        ha="left",
        va="center",
    )

    save_figure(fig, "person_data_card")


def profile_card_timeline_figure():
    """横向时间轴版本：突出人物从种子到最终画像的生长过程。"""
    initial = load_json(ROOT / "data" / "persons" / "P001_v0_profile_data.json")
    profile = load_json(OUTPUT / "P001_v13_profile_data.json")
    planning = load_json(OUTPUT / "P001_v13_planning_state.json")
    events = load_json(OUTPUT / "P001_v13_time_event_graph.json")["events"]
    sessions = load_json(OUTPUT / "P001_dialogue_sessions.json")["sessions"]
    extracts = load_jsonl(OUTPUT / "P001_dialogue_extracts.jsonl")
    qa_single = load_jsonl(QA_DIR / "P001_single_questions.jsonl")
    qa_multi = load_jsonl(QA_DIR / "P001_multi_questions.jsonl")

    chains = {chain["subject"]: chain for chain in planning["states"]}
    versions = [version for chain in planning["states"] for version in chain["versions"]]

    def round_number(round_id):
        return int(round_id.removeprefix("v"))

    def state_count_at(round_index):
        return sum(
            min(round_number(v["round_id"]) for v in chain["versions"]) <= round_index
            for chain in planning["states"]
        )

    def chain_text(subject, limit=62):
        text = " → ".join(" / ".join(v["value"]) for v in chains[subject]["versions"])
        return text if len(text) <= limit else text[: limit - 1] + "…"

    fig, ax = plt.subplots(figsize=(10.2, 4.9))
    setup_axis(ax)
    fig.subplots_adjust(left=0.018, right=0.988, top=0.975, bottom=0.045)

    ax.text(
        0.01,
        0.965,
        "P001 人物成长时间轴",
        fontsize=15,
        fontweight="bold",
        color=INK,
        ha="left",
        va="top",
    )
    ax.text(
        0.01,
        0.915,
        "从 9 条人物种子出发，每一轮通过状态规划、事件实现和对话证据向前生长",
        fontsize=7,
        color=MUTED,
        ha="left",
        va="top",
    )
    ax.text(
        0.99,
        0.955,
        "2023-01-05 — 2024-01-31",
        fontsize=6.5,
        color=MUTED,
        ha="right",
        va="top",
    )

    # Timeline
    ax.plot([0.07, 0.93], [0.735, 0.735], color=LINE, linewidth=2.0, zorder=1)
    milestones = [
        (0.07, "v0", "9", "初始人物画像", GREY_PALE, MUTED),
        (0.285, "v3", str(state_count_at(3)), "迁居高新区", BLUE_PALE, BLUE),
        (0.50, "v6", str(state_count_at(6)), "职业与价值观成长", VIOLET_PALE, VIOLET),
        (0.715, "v10", str(state_count_at(10)), "生活网络扩展", ORANGE_PALE, ORANGE),
        (0.93, "v13", "79", "最终人物画像", GREEN_PALE, GREEN),
    ]
    for x, version, count, label, fill, edge in milestones:
        ax.scatter([x], [0.735], s=55, color=fill, edgecolor=edge, linewidth=1.5, zorder=3)
        ax.text(x, 0.795, version, fontsize=6, fontweight="bold", color=edge, ha="center", va="center", zorder=4)
        ax.text(x, 0.685, f"{count} states", fontsize=7, fontweight="bold", color=INK, ha="center")
        ax.text(x, 0.645, label, fontsize=5.5, color=MUTED, ha="center")
    for left, right in zip(milestones[:-1], milestones[1:]):
        ax.text(
            (left[0] + right[0]) / 2,
            0.765,
            "目标状态 → 事件 → 对话 → 证据",
            fontsize=5.0,
            color=VIOLET,
            ha="center",
        )

    # Initial card
    box(ax, (0.01, 0.245), (0.22, 0.32), "", "", fill=GREY_PALE, edge=LINE)
    ax.text(0.03, 0.53, "v0 · 初始人物画像", fontsize=8, fontweight="bold", color=INK)
    seed_items = [
        ("姓名", "林晓"),
        ("居住", "苏州工业园区"),
        ("学历", "青岛大学 · 计算机"),
        ("房租", "3500 元"),
        ("通勤", "地铁"),
        ("住房", "租住两室一厅"),
        ("手机", "iPhone 14 Pro Max / 13"),
    ]
    for idx, (key, value) in enumerate(seed_items):
        y = 0.485 - idx * 0.033
        ax.text(0.03, y, key, fontsize=5.2, color=MUTED, fontweight="bold")
        ax.text(0.078, y, value, fontsize=5.2, color=INK)

    # Growth ledger
    box(ax, (0.25, 0.245), (0.46, 0.32), "", "", fill=BLUE_PALE, edge=BLUE)
    ax.text(0.27, 0.53, "增长账本 · 13 轮 / 139 个状态版本", fontsize=8, fontweight="bold", color=INK)
    ledger = [
        ("房租", chain_text("每月房租"), "4 versions"),
        ("手机", chain_text("持有手机"), "5 versions"),
        ("薪资", chain_text("税后月薪"), "4 versions"),
        ("住房", chain_text("住房类型"), "4 versions"),
        ("联系", chain_text("主要联系渠道"), "4 versions"),
    ]
    for idx, (key, text, count) in enumerate(ledger):
        y = 0.478 - idx * 0.050
        ax.text(0.27, y, key, fontsize=5.3, color=BLUE_DARK, fontweight="bold")
        ax.text(0.315, y, text, fontsize=5.1, color=INK)
        ax.text(0.69, y, count, fontsize=5.0, color=MUTED, ha="right")

    # Final portrait
    box(ax, (0.73, 0.245), (0.26, 0.32), "", "", fill=GREEN_PALE, edge=GREEN)
    ax.text(0.75, 0.53, "v13 · 最终人物画像", fontsize=8, fontweight="bold", color=INK)
    final_items = [
        ("居住", "苏州高新区"),
        ("职业", "资深后端开发工程师"),
        ("薪资", "税后 21500 元"),
        ("住房", "租住一室一厅"),
        ("宠物", "橘猫一只"),
        ("生活", "游泳 · 骑行 · 阅读"),
        ("价值", "健康与稳定优先"),
    ]
    for idx, (key, value) in enumerate(final_items):
        y = 0.485 - idx * 0.033
        ax.text(0.75, y, key, fontsize=5.2, color=GREEN, fontweight="bold")
        ax.text(0.80, y, value, fontsize=5.2, color=INK)

    # Bottom evidence strip
    ax.text(0.01, 0.185, "可追溯产物", fontsize=6.5, fontweight="bold", color=INK)
    products = [
        (f"{len(events)}", "时间事件", ORANGE_PALE, ORANGE),
        (f"{len(sessions)}", "对话会话", TEAL_PALE, TEAL),
        (f"{sum(len(x.get('evidence', [])) for x in extracts)}", "turn 证据", VIOLET_PALE, VIOLET),
        (f"{sum(v['op'] == 'create' for v in versions)}", "create", BLUE_PALE, BLUE),
        (f"{sum(v['op'] == 'update' for v in versions)}", "update", BLUE_PALE, BLUE),
        (f"{len(qa_single) + len(qa_multi)}", "Benchmark 问题", GREEN_PALE, GREEN),
    ]
    for idx, (value, label, fill, edge) in enumerate(products):
        x = 0.12 + idx * 0.145
        box(ax, (x, 0.115), (0.125, 0.085), value, label, fill=fill, edge=edge, title_size=8, body_size=5.0)
    ax.text(
        0.01,
        0.045,
        "状态 → 事件 → 会话 → turn 原话构成一条闭合证据链；任意冻结版本都能独立生成问题。",
        fontsize=5.5,
        color=MUTED,
    )

    save_figure(fig, "person_data_card_timeline")


def profile_card_atlas_figure():
    """领域档案版本：突出最终画像的广度和可核查结构。"""
    initial = load_json(ROOT / "data" / "persons" / "P001_v0_profile_data.json")
    profile = load_json(OUTPUT / "P001_v13_profile_data.json")
    planning = load_json(OUTPUT / "P001_v13_planning_state.json")
    events = load_json(OUTPUT / "P001_v13_time_event_graph.json")["events"]
    sessions = load_json(OUTPUT / "P001_dialogue_sessions.json")["sessions"]
    extracts = load_jsonl(OUTPUT / "P001_dialogue_extracts.jsonl")
    qa_single = load_jsonl(QA_DIR / "P001_single_questions.jsonl")
    qa_multi = load_jsonl(QA_DIR / "P001_multi_questions.jsonl")
    versions = [version for chain in planning["states"] for version in chain["versions"]]
    domain_counts = Counter(state["domain"] for state in profile["states"])

    fig, ax = plt.subplots(figsize=(7.2, 6.65))
    setup_axis(ax)
    fig.subplots_adjust(left=0.025, right=0.985, top=0.98, bottom=0.035)

    # Header
    ax.add_patch(
        FancyBboxPatch(
            (0, 0.885),
            1,
            0.115,
            boxstyle="round,pad=0.0,rounding_size=0.02",
            facecolor="#24364B",
            edgecolor="#24364B",
            linewidth=0,
        )
    )
    ax.text(0.035, 0.958, "PERSON MEMORY DOSSIER", fontsize=6.5, color="#AFC5D8", fontweight="bold")
    ax.text(0.035, 0.915, "P001 · 林晓 · 最终人物画像", fontsize=15, color="white", fontweight="bold")
    ax.text(0.965, 0.945, "v0  →  v13", fontsize=11, color="white", fontweight="bold", ha="right")
    ax.text(0.965, 0.910, "13 rounds · 2023—2024", fontsize=5.5, color="#AFC5D8", ha="right")

    # Growth statement
    box(ax, (0.0, 0.765), (1.0, 0.085), "", "", fill=GREY_PALE, edge=LINE, radius=0.015)
    ax.text(0.035, 0.805, "9", fontsize=17, fontweight="bold", color=MUTED, va="center")
    ax.text(0.075, 0.805, "初始事实", fontsize=6, color=MUTED, va="center")
    arrow(ax, (0.145, 0.805), (0.225, 0.805), color=VIOLET, lw=2.0)
    ax.text(0.27, 0.805, "13 轮受控生长", fontsize=8, fontweight="bold", color=VIOLET, va="center")
    ax.text(0.43, 0.805, "+70 create  ·  +60 update", fontsize=6, color=MUTED, va="center")
    arrow(ax, (0.63, 0.805), (0.71, 0.805), color=VIOLET, lw=2.0)
    ax.text(0.755, 0.805, "79", fontsize=17, fontweight="bold", color=GREEN, va="center")
    ax.text(0.805, 0.805, "最终状态 / 16 个领域", fontsize=6, color=INK, va="center")

    # Final identity dossier
    box(ax, (0.0, 0.405), (0.36, 0.32), "", "", fill=GREEN_PALE, edge=GREEN)
    ax.text(0.025, 0.695, "最终人物画像", fontsize=9, fontweight="bold", color=INK)
    profile_rows = [
        ("身份", "林晓 · INTJ · 山东青岛"),
        ("居住", "苏州高新区 · 一室一厅"),
        ("职业", "互联网公司资深后端开发工程师"),
        ("收入", "税后月薪 21500 元"),
        ("家庭", "父母在青岛 · 每周视频两次"),
        ("关系", "单身 · 苏州有校友和同事朋友"),
        ("宠物", "橘猫 · 已接种疫苗和驱虫"),
        ("生活", "7:00 起床 · 游泳 · 周末骑行"),
        ("学习", "CS50 Python · 机器学习课程"),
        ("价值", "健康与稳定优先于晋升速度"),
    ]
    for idx, (key, value) in enumerate(profile_rows):
        y = 0.653 - idx * 0.025
        ax.text(0.025, y, key, fontsize=5.1, color=GREEN, fontweight="bold")
        ax.text(0.082, y, value, fontsize=5.1, color=INK)

    # Domain atlas
    box(ax, (0.38, 0.405), (0.62, 0.32), "", "", fill=BLUE_PALE, edge=BLUE)
    ax.text(0.405, 0.695, "16 领域画像图谱", fontsize=9, fontweight="bold", color=INK)
    ordered = sorted(domain_counts.items(), key=lambda item: (-item[1], item[0]))
    max_count = max(domain_counts.values())
    for idx, (domain, count) in enumerate(ordered):
        row, col = divmod(idx, 4)
        x = 0.405 + col * 0.145
        y = 0.615 - row * 0.060
        width = 0.123
        ax.add_patch(
            FancyBboxPatch(
                (x, y),
                width,
                0.043,
                boxstyle="round,pad=0.004,rounding_size=0.010",
                facecolor="white",
                edgecolor=LINE,
                linewidth=0.6,
            )
        )
        ax.add_patch(
            FancyBboxPatch(
                (x, y),
                width * count / max_count,
                0.043,
                boxstyle="round,pad=0.004,rounding_size=0.010",
                facecolor=BLUE,
                edgecolor="none",
                alpha=0.22,
            )
        )
        ax.text(x + 0.006, y + 0.024, domain.replace("与", "·"), fontsize=5.0, color=INK, va="center")
        ax.text(x + width - 0.006, y + 0.024, str(count), fontsize=5.0, color=BLUE_DARK, fontweight="bold", ha="right", va="center")

    # Before-after table
    box(ax, (0.0, 0.165), (0.61, 0.20), "", "", fill=GREY_PALE, edge=LINE)
    ax.text(0.025, 0.335, "关键变化 · v0 与 v13", fontsize=8, fontweight="bold", color=INK)
    ax.text(0.175, 0.305, "v0", fontsize=5.3, color=MUTED, fontweight="bold")
    ax.text(0.405, 0.305, "v13", fontsize=5.3, color=GREEN, fontweight="bold")
    comparisons = [
        ("居住", "苏州工业园区", "苏州高新区"),
        ("住房", "租住两室一厅", "租住一室一厅"),
        ("手机", "iPhone 14 Pro Max / 13", "iPhone 15 Pro"),
        ("职业", "未记录", "资深后端开发工程师"),
        ("宠物", "未记录", "橘猫一只"),
    ]
    for idx, (key, before, after) in enumerate(comparisons):
        y = 0.275 - idx * 0.027
        ax.text(0.025, y, key, fontsize=5.1, color=MUTED, fontweight="bold")
        ax.text(0.095, y, before, fontsize=5.1, color=INK)
        arrow(ax, (0.345, y + 0.004), (0.375, y + 0.004), color=VIOLET, lw=1.0)
        ax.text(0.405, y, after, fontsize=5.1, color=INK)

    # Provenance dossier
    box(ax, (0.63, 0.165), (0.37, 0.20), "", "", fill=VIOLET_PALE, edge=VIOLET)
    ax.text(0.655, 0.335, "记忆证据档案", fontsize=8, fontweight="bold", color=INK)
    evidence_rows = [
        ("状态版本", str(len(versions))),
        ("时间事件", str(len(events))),
        ("对话会话", str(len(sessions))),
        ("turn 证据", str(sum(len(x.get("evidence", [])) for x in extracts))),
        ("问题", f"{len(qa_single)} single + {len(qa_multi)} multi"),
    ]
    for idx, (key, value) in enumerate(evidence_rows):
        y = 0.292 - idx * 0.028
        ax.text(0.655, y, key, fontsize=5.2, color=VIOLET, fontweight="bold")
        ax.text(0.775, y, value, fontsize=5.2, color=INK)
    ax.text(
        0.0,
        0.095,
        "人物画像是指定版本上的结构化状态快照；状态变化、世界事件和对话证据彼此对齐。",
        fontsize=6.2,
        fontweight="bold",
        color=INK,
    )
    ax.text(
        0.0,
        0.055,
        "它既可以回答“这个人现在是什么样”，也可以回答“过去如何变化、何时变化、依据是哪一句话”。",
        fontsize=5.5,
        color=MUTED,
    )

    save_figure(fig, "person_data_card_atlas")


if __name__ == "__main__":
    DOCS.mkdir(parents=True, exist_ok=True)
    architecture_figure()
    profile_card_figure()
    profile_card_timeline_figure()
    profile_card_atlas_figure()
