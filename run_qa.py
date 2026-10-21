"""题目生成入口。

原料只加载一次，再按题型顺序调用各生成器。
新增题型时只往 GENERATORS 里登记，不改主循环。
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Sequence

from .llm_client import LLMClient
from .src.qa_gen.base import Hop, QuestionGenerator
from .src.qa_gen.materials import load_person_materials
from .src.qa_gen.models import QACandidate, QuestionRecord
from .src.qa_gen.step1_0_gen_basic_qa import BasicQAGenerator
from .src.qa_gen.step1_1_gen_open_qa import OpenQAGenerator
from .src.qa_gen.step1_2_gen_temporal_qa import TemporalQAGenerator
from .src.qa_gen.step1_3_gen_reject_qa import RejectQAGenerator
from .src.qa_gen.step1_4_gen_knowledge_update_qa import (
    KnowledgeUpdateQAGenerator,
)

GENERATORS: dict[str, type[QuestionGenerator]] = {
    "information_extraction": BasicQAGenerator,
    "open_domain": OpenQAGenerator,
    "temporal": TemporalQAGenerator,
    "reject": RejectQAGenerator,
    "knowledge_update": KnowledgeUpdateQAGenerator,
}


def run_qa(
    llm_client: LLMClient,
    *,
    person_id: str,
    output_dir: str | Path,
    save_dir: str | Path,
    planning_round: str,
    query_time: str,
    hop: Hop = "single",
    abilities: Sequence[str] | None = None,
    limit: int | None = None,
    workers: int = 4,
) -> list[QuestionRecord]:
    """生成一个人的题目，每完成一条就追加到 save_dir。

    output_dir 是 planning、sessions、extracts 的读取目录。
    abilities 为空时按注册顺序跑全部题型。
    limit 限制每个题型最多尝试多少个候选，不适合的候选不计入结果。
    workers 是生成问题的线程数。候选之间互不影响，取数仍在主线程完成。
    """
    if workers < 1:
        raise ValueError("workers 必须大于 0")

    selected = _select_generators(abilities)
    materials = load_person_materials(
        person_id,
        output_dir=output_dir,
        planning_round=planning_round,
    )
    save_path = _question_file(save_dir, person_id, hop)

    jobs: list[tuple[QuestionGenerator, QACandidate]] = []
    for generator_cls in selected:
        generator = generator_cls(llm_client)
        candidates = generator.build_candidates(materials, query_time, hop)
        if limit is not None:
            candidates = candidates[:limit]
        jobs.extend((generator, candidate) for candidate in candidates)

    records: list[QuestionRecord] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [
            pool.submit(generator.run_candidate, candidate)
            for generator, candidate in jobs
        ]
        total = len(futures)
        saved = skipped = failed = 0
        for future in as_completed(futures):
            try:
                record = future.result()
            except Exception as error:
                failed += 1
                print(f"failed {failed}/{total}: {error}", flush=True)
                continue
            if record is None:
                skipped += 1
                print(
                    f"skip saved={saved} skip={skipped} "
                    f"failed={failed} / {total}",
                    flush=True,
                )
                continue
            records.append(record)
            _append_question(save_path, record)
            saved += 1
            print(
                f"saved {saved}/{total} {record.question_id} "
                f"skip={skipped} failed={failed}",
                flush=True,
            )
    return records


def _select_generators(
    abilities: Sequence[str] | None,
) -> list[type[QuestionGenerator]]:
    if abilities is None:
        return list(GENERATORS.values())

    unknown = [name for name in abilities if name not in GENERATORS]
    if unknown:
        raise ValueError(f"未知题型：{', '.join(unknown)}")
    return [GENERATORS[name] for name in abilities]


def _question_file(save_dir: str | Path, person_id: str, hop: str) -> Path:
    directory = Path(save_dir)
    if directory.suffix:
        raise ValueError("save_dir 必须是保存文件夹，不是文件路径")
    return directory / f"{person_id}_{hop}_questions.jsonl"


def _append_question(path: Path, record: QuestionRecord) -> None:
    """完成一条后立即追加。同一个 question_id 只保留最新一行。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record.model_dump(mode="json"), ensure_ascii=False)
    kept: list[str] = []
    replaced = False
    if path.exists():
        for raw in path.read_text(encoding="utf-8").splitlines():
            if not raw.strip():
                continue
            item = json.loads(raw)
            if item.get("question_id") == record.question_id:
                kept.append(line)
                replaced = True
            else:
                kept.append(raw)
    if not replaced:
        kept.append(line)
    path.write_text("\n".join(kept) + "\n", encoding="utf-8")
