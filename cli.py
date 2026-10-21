"""长期记忆 Benchmark 命令行：对话生成与问答生成。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .src.dialogue_gen.dialogue_prompt.target_state_plan.step2_domain_taxonomy_v3 import (
    DOMAIN_DEFINITIONS,
)
from .src.dialogue_gen.dialogue_prompt.target_state_plan.step_1_0_target_state import (
    SELECTED_DOMAIN_COUNT,
)

DEFAULT_MODEL = "gpt-4.1"

PACKAGE_ROOT = Path(__file__).resolve().parent
DEFAULT_PROFILE = PACKAGE_ROOT / "data" / "persons" / "P001_v0_profile_data.json"
DEFAULT_SAVE_DIR = PACKAGE_ROOT / "data" / "output"
DEFAULT_QA_SAVE_DIR = PACKAGE_ROOT / "data" / "qa"
DEFAULT_TIME_START = "2023-01-01"
DEFAULT_QUERY_TIME = "2024-12-01"
QA_ABILITIES = (
    "information_extraction",
    "open_domain",
    "temporal",
    "reject",
    "knowledge_update",
)
MULTI_HOP_ABILITIES = ("information_extraction", "knowledge_update")


def _domain_names() -> list[str]:
    return [item["name"] for item in DOMAIN_DEFINITIONS.values()]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="longterm_memory_benchmark",
        description="长期记忆 Benchmark 命令行入口",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    list_domains = sub.add_parser("list-domains", help="列出可选 domain 中文名")
    list_domains.set_defaults(func=_cmd_list_domains)

    dialogue = sub.add_parser(
        "dialogue",
        help="从人物画像迭代生成规划 / 事件图 / 对话",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    dialogue.add_argument(
        "--profile",
        type=Path,
        default=DEFAULT_PROFILE,
        help="入口人物画像，例如 P001_v0_profile_data.json",
    )
    dialogue.add_argument(
        "--save-dir",
        type=Path,
        default=DEFAULT_SAVE_DIR,
        help="产物输出目录",
    )
    dialogue.add_argument(
        "--to-round",
        type=int,
        required=True,
        help="迭代到的版本整数。传入 3 时执行 v0→v1→v2→v3",
    )
    dialogue.add_argument(
        "--time-start",
        default=DEFAULT_TIME_START,
        help="世界时间线起始日期 YYYY-MM-DD",
    )
    dialogue.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help="规划 / 事件图等共用模型",
    )
    dialogue.add_argument(
        "--dialogue-model",
        default=None,
        help="对话生成模型；默认与 --model 相同",
    )
    dialogue.add_argument(
        "--base-url",
        default=None,
        help="OpenAI 兼容接口 base_url；默认读环境或内置 Azure",
    )
    dialogue.add_argument(
        "--api-key",
        default=None,
        help="API Key；默认读环境或 Azure token provider",
    )
    dialogue.add_argument(
        "--domains",
        nargs="+",
        metavar="DOMAIN",
        default=None,
        help=(
            f"本轮规划使用的 {SELECTED_DOMAIN_COUNT} 个 domain 中文名；"
            "第一个为主线，其余为副线。与 --fixed-side-domains 互斥。"
            "可用 list-domains 查看全部名称。"
        ),
    )
    dialogue.add_argument(
        "--fixed-side-domains",
        nargs="+",
        metavar="DOMAIN",
        default=None,
        help=(
            "指定副线（不当主线）。其余主线与副线仍从剩下的域随机补齐。"
            f"最多 {SELECTED_DOMAIN_COUNT - 1} 个。与 --domains 互斥。"
        ),
    )
    dialogue.set_defaults(func=_cmd_dialogue)

    qa = sub.add_parser(
        "qa",
        help="从已有对话材料生成问答",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    qa.add_argument("--person-id", default="P001", help="人物编号")
    qa.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_SAVE_DIR,
        help="planning、sessions、extracts 的读取目录",
    )
    qa.add_argument(
        "--save-dir",
        type=Path,
        default=DEFAULT_QA_SAVE_DIR,
        help="题目 jsonl 保存目录",
    )
    qa.add_argument(
        "--planning-round",
        required=True,
        help="材料版本，例如 v13；传入整数时自动补成 v13",
    )
    qa.add_argument(
        "--query-time",
        default=DEFAULT_QUERY_TIME,
        help="提问日期 YYYY-MM-DD",
    )
    qa.add_argument(
        "--hop",
        choices=["single", "multi"],
        default="single",
        help="单跳或多跳。多跳未指定题型时，只跑信息抽取和知识更新",
    )
    qa.add_argument(
        "--abilities",
        nargs="+",
        metavar="ABILITY",
        default=None,
        help="要生成的题型：" + "、".join(QA_ABILITIES),
    )
    qa.add_argument(
        "--limit",
        type=int,
        default=None,
        help="每个题型最多尝试多少个候选",
    )
    qa.add_argument("--workers", type=int, default=4, help="生成问题的线程数")
    qa.add_argument("--model", default=DEFAULT_MODEL, help="生成问答使用的模型")
    qa.add_argument(
        "--base-url",
        default=None,
        help="OpenAI 兼容接口 base_url；默认读环境或内置 Azure",
    )
    qa.add_argument(
        "--api-key",
        default=None,
        help="API Key；默认读环境或 Azure token provider",
    )
    qa.set_defaults(func=_cmd_qa)
    return parser


def _cmd_list_domains(_: argparse.Namespace) -> int:
    for name in _domain_names():
        print(name)
    print(
        f"\n规划默认需要正好 {SELECTED_DOMAIN_COUNT} 个："
        "1 个主线 + "
        f"{SELECTED_DOMAIN_COUNT - 1} 个副线。"
        "也可用 --fixed-side-domains 只钉住部分副线。",
        flush=True,
    )
    return 0


def _parse_domains(names: list[str] | None):
    from .src.api import DomainSelection

    if names is None:
        return None
    if len(names) != SELECTED_DOMAIN_COUNT:
        raise ValueError(
            f"--domains 需要正好 {SELECTED_DOMAIN_COUNT} 个，当前 {len(names)} 个"
        )
    known = set(_domain_names())
    unknown = [name for name in names if name not in known]
    if unknown:
        raise ValueError(
            "未知 domain："
            + "、".join(unknown)
            + "。请先运行 list-domains 查看可选名称。"
        )
    if len(set(names)) != len(names):
        raise ValueError("--domains 不能重复")
    return DomainSelection(main_domain=names[0], side_domains=names[1:])


def _parse_fixed_side_domains(names: list[str] | None) -> list[str] | None:
    if names is None:
        return None
    side_slots = SELECTED_DOMAIN_COUNT - 1
    if len(names) > side_slots:
        raise ValueError(
            f"--fixed-side-domains 最多 {side_slots} 个，当前 {len(names)} 个"
        )
    if len(set(names)) != len(names):
        raise ValueError("--fixed-side-domains 不能重复")
    known = set(_domain_names())
    unknown = [name for name in names if name not in known]
    if unknown:
        raise ValueError(
            "未知指定副线："
            + "、".join(unknown)
            + "。请先运行 list-domains 查看可选名称。"
        )
    return list(names)


def _cmd_dialogue(args: argparse.Namespace) -> int:
    from .llm_client import LLMClient
    from .run_dialogue import run_dialogue

    if args.to_round < 0:
        raise ValueError("--to-round 必须是非负整数")
    if args.domains and args.fixed_side_domains:
        raise ValueError("--domains 与 --fixed-side-domains 不能同时使用")
    domains = _parse_domains(args.domains)
    fixed_side_domains = _parse_fixed_side_domains(args.fixed_side_domains)
    llm_client = LLMClient(
        base_url=args.base_url,
        model=args.model,
        api_key=args.api_key,
    )
    dialogue_model = args.dialogue_model or args.model
    if dialogue_model == args.model:
        dialogue_client = llm_client
    else:
        dialogue_client = LLMClient(
            base_url=args.base_url,
            model=dialogue_model,
            api_key=args.api_key,
        )

    if domains is not None:
        print(
            "domains: 主线="
            + domains.main_domain
            + "；副线="
            + "、".join(domains.side_domains),
            flush=True,
        )
    elif fixed_side_domains:
        print(
            "fixed_side_domains="
            + "、".join(fixed_side_domains)
            + "；其余主线/副线随机",
            flush=True,
        )
    else:
        print("domains: 随机选择", flush=True)
    print(f"model={args.model} dialogue_model={dialogue_model}", flush=True)
    print(f"profile={args.profile}", flush=True)
    print(f"save_dir={args.save_dir}", flush=True)
    print(f"to_round=v{args.to_round} time_start={args.time_start}", flush=True)

    sessions = run_dialogue(
        profile_path=args.profile,
        llm_client=llm_client,
        save_dir=args.save_dir,
        round_id=args.to_round,
        time_start=args.time_start,
        dialogue_client=dialogue_client,
        domains=domains,
        fixed_side_domains=fixed_side_domains,
    )
    print(f"完成：共 {len(sessions.sessions)} 段对话", flush=True)
    return 0


def _planning_round(value: str) -> str:
    text = value.strip()
    if not text:
        raise ValueError("--planning-round 不能为空")
    if text.isdigit():
        return f"v{int(text)}"
    return text


def _qa_abilities(hop: str, names: list[str] | None) -> list[str] | None:
    if names is None:
        if hop == "multi":
            return list(MULTI_HOP_ABILITIES)
        return None
    unknown = [name for name in names if name not in QA_ABILITIES]
    if unknown:
        raise ValueError("未知题型：" + "、".join(unknown))
    if len(set(names)) != len(names):
        raise ValueError("--abilities 不能重复")
    return list(names)


def _cmd_qa(args: argparse.Namespace) -> int:
    from collections import Counter

    from .llm_client import LLMClient
    from .run_qa import run_qa

    if args.limit is not None and args.limit < 1:
        raise ValueError("--limit 必须大于 0")
    planning_round = _planning_round(args.planning_round)
    abilities = _qa_abilities(args.hop, args.abilities)
    llm_client = LLMClient(
        base_url=args.base_url,
        model=args.model,
        api_key=args.api_key,
    )
    print(f"model={args.model}", flush=True)
    print(f"person_id={args.person_id} planning_round={planning_round}", flush=True)
    print(f"hop={args.hop} query_time={args.query_time}", flush=True)
    print(
        "abilities=" + ("全部已注册题型" if abilities is None else "、".join(abilities)),
        flush=True,
    )
    print(f"output_dir={args.output_dir}", flush=True)
    print(f"save_dir={args.save_dir}", flush=True)
    if args.limit is not None:
        print(f"limit={args.limit}", flush=True)
    print(f"workers={args.workers}", flush=True)

    records = run_qa(
        llm_client,
        person_id=args.person_id,
        output_dir=args.output_dir,
        save_dir=args.save_dir,
        planning_round=planning_round,
        query_time=args.query_time,
        hop=args.hop,
        abilities=abilities,
        limit=args.limit,
        workers=args.workers,
    )
    counts = dict(Counter(record.template for record in records))
    print(f"完成：共 {len(records)} 题 {counts}", flush=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception as error:  # noqa: BLE001 - CLI 入口统一报错
        print(f"错误：{error}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
