"""Bonus Exercise 3.4 — score the SAME 20 QA with RAGAS and DeepEval.

Both frameworks read the artifacts the lab already produced, so all three
scoring systems (lab heuristic core, RAGAS, DeepEval) see identical inputs:

    question            <- artifacts/actual_answers.json
    actual answer       <- artifacts/actual_answers.json
    retrieved contexts  <- artifacts/actual_answers.json  (same chunks, same order)
    reference answer    <- golden_dataset.json

Extra dependencies, NOT part of requirements.txt:

    pip install ragas deepeval "langchain-community<0.4"

Needs OPENAI_API_KEY in .env. Writes artifacts/framework_comparison.json.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "YES")

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

JUDGE_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
OUTPUT_PATH = ROOT / "artifacts" / "framework_comparison.json"


def load_cases() -> list[dict[str, Any]]:
    answers = json.loads((ROOT / "artifacts" / "actual_answers.json").read_text())["answers"]
    gold = {
        pair["id"]: pair
        for pair in json.loads((ROOT / "golden_dataset.json").read_text())["qa_pairs"]
    }
    return [
        {
            "id": record["id"],
            "question": record["question"],
            "answer": record["actual_answer"],
            "contexts": [chunk["text"] for chunk in record["retrieved_contexts"]],
            "expected": gold[record["id"]]["expected_answer"],
        }
        for record in answers
    ]


def run_ragas(cases: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings
    from ragas import EvaluationDataset, SingleTurnSample, evaluate
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from ragas.llms import LangchainLLMWrapper
    from ragas.metrics import (
        Faithfulness,
        LLMContextPrecisionWithReference,
        LLMContextRecall,
        ResponseRelevancy,
    )

    llm = LangchainLLMWrapper(ChatOpenAI(model=JUDGE_MODEL, temperature=0))
    embeddings = LangchainEmbeddingsWrapper(OpenAIEmbeddings(model="text-embedding-3-small"))

    dataset = EvaluationDataset(
        samples=[
            SingleTurnSample(
                user_input=case["question"],
                response=case["answer"],
                retrieved_contexts=case["contexts"],
                reference=case["expected"],
            )
            for case in cases
        ]
    )
    result = evaluate(
        dataset=dataset,
        metrics=[
            Faithfulness(),
            ResponseRelevancy(),
            LLMContextRecall(),
            LLMContextPrecisionWithReference(),
        ],
        llm=llm,
        embeddings=embeddings,
    )
    frame = result.to_pandas()
    key = {
        "faithfulness": "faithfulness",
        "answer_relevancy": "relevance",
        "context_recall": "context_recall",
        "llm_context_precision_with_reference": "context_precision",
    }
    scores: dict[str, dict[str, float]] = {}
    for position, case in enumerate(cases):
        row = frame.iloc[position]
        scores[case["id"]] = {
            short: (None if row[column] != row[column] else float(row[column]))
            for column, short in key.items()
            if column in frame.columns
        }
    return scores


def run_deepeval(cases: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    from deepeval.metrics import (
        AnswerRelevancyMetric,
        ContextualPrecisionMetric,
        ContextualRecallMetric,
        FaithfulnessMetric,
    )
    from deepeval.test_case import LLMTestCase

    metrics = {
        "faithfulness": FaithfulnessMetric(model=JUDGE_MODEL),
        "relevance": AnswerRelevancyMetric(model=JUDGE_MODEL),
        "context_recall": ContextualRecallMetric(model=JUDGE_MODEL),
        "context_precision": ContextualPrecisionMetric(model=JUDGE_MODEL),
    }

    scores: dict[str, dict[str, float]] = {}
    for case in cases:
        test_case = LLMTestCase(
            input=case["question"],
            actual_output=case["answer"],
            expected_output=case["expected"],
            retrieval_context=case["contexts"],
        )
        row: dict[str, float] = {}
        for name, metric in metrics.items():
            try:
                metric.measure(test_case)
                row[name] = float(metric.score)
            except Exception as exc:  # a single metric failure must not kill the run
                print(f"  ! {case['id']} {name}: {type(exc).__name__}: {exc}")
                row[name] = None
        scores[case["id"]] = row
        print(f"  {case['id']} done: {row}")
    return scores


def main() -> int:
    cases = load_cases()
    heuristic = {
        row["id"]: {
            "faithfulness": row["faithfulness"],
            "relevance": row["relevance"],
            "context_recall": row["context_recall"],
            "context_precision": row["context_precision"],
        }
        for row in json.loads(
            (ROOT / "artifacts" / "benchmark_results.json").read_text()
        )["results"]
    }

    print(f"Running DeepEval on {len(cases)} cases (judge={JUDGE_MODEL})...")
    deepeval_scores = run_deepeval(cases)
    print(f"Running RAGAS on {len(cases)} cases (judge={JUDGE_MODEL})...")
    ragas_scores = run_ragas(cases)

    payload = {
        "judge_model": JUDGE_MODEL,
        "cases": [
            {
                "id": case["id"],
                "lab_heuristic": heuristic.get(case["id"], {}),
                "ragas": ragas_scores.get(case["id"], {}),
                "deepeval": deepeval_scores.get(case["id"], {}),
            }
            for case in cases
        ],
    }

    def average(system: str, metric: str) -> float | None:
        values = [
            entry[system][metric]
            for entry in payload["cases"]
            if entry[system].get(metric) is not None
        ]
        return sum(values) / len(values) if values else None

    payload["averages"] = {
        system: {
            metric: average(system, metric)
            for metric in ("faithfulness", "relevance", "context_recall", "context_precision")
        }
        for system in ("lab_heuristic", "ragas", "deepeval")
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\nSaved: {OUTPUT_PATH}")
    for system, row in payload["averages"].items():
        formatted = ", ".join(
            f"{k}={'n/a' if v is None else format(v, '.3f')}" for k, v in row.items()
        )
        print(f"  {system:14} {formatted}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
