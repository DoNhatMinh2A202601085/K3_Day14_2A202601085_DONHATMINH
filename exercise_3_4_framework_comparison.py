"""
Exercise 3.4 — Framework Comparison (Design-Based + Hybrid Run)

Compares our word-overlap heuristic vs RAGAS using:
  1. Design walkthrough (when runtime unavailable)
  2. Faithfulness metrics manually via OpenAI API calls

Run:
    python exercise_3_4_framework_comparison.py
"""

import json
import os
import re
import time
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

import sys
sys.path.insert(0, str(Path(__file__).parent))
from template import RAGASEvaluator

# ── Load data ────────────────────────────────────────────────────────────────
with open("golden_dataset.json") as f:
    golden = json.load(f)
with open("artifacts/actual_answers.json") as f:
    answers_data = json.load(f)
with open("artifacts/benchmark_results.json") as f:
    benchmark = json.load(f)

# ── Word-overlap results (already computed) ──────────────────────────────────
def run_word_overlap():
    eval = RAGASEvaluator()
    results = []
    for ans in answers_data["answers"]:
        qid = ans["id"]
        pair = next(p for p in golden["qa_pairs"] if p["id"] == qid)
        contexts = [c["text"] for c in ans["retrieved_contexts"]]
        retrieved_context = "\n\n".join(contexts)

        f_score = eval.evaluate_faithfulness(ans["actual_answer"], retrieved_context)
        r_score = eval.evaluate_relevance(ans["actual_answer"], pair["question"])
        c_score = eval.evaluate_completeness(ans["actual_answer"], pair["expected_answer"])
        cr_score = eval.evaluate_context_recall(contexts, pair["expected_answer"])
        cp_score = eval.evaluate_context_precision(contexts, pair["expected_answer"])

        results.append({
            "id": qid,
            "faithfulness": round(f_score, 3),
            "relevance": round(r_score, 3),
            "completeness": round(c_score, 3),
            "context_recall": round(cr_score, 3),
            "context_precision": round(cp_score, 3),
            "overall": round((f_score + r_score + c_score) / 3, 3),
        })
    return results


# ── RAGAS Faithfulness via direct OpenAI LLM call ───────────────────────────
def ragas_faithfulness_via_llm(question, answer, context, api_key, model):
    """
    Simulate RAGAS Faithfulness metric using a direct LLM call.
    RAGAS Faithfulness prompt asks: "Identify claims, verify each against context."
    Returns score 0.0-1.0.
    """
    import openai
    client = openai.OpenAI(api_key=api_key)

    prompt = f"""You are evaluating the faithfulness of an AI answer against its retrieved context.

Question: {question}
Answer: {answer}
Retrieved Context: {context}

Your task:
1. Identify each factual claim in the answer.
2. For each claim, determine if it is supported by the Retrieved Context.
3. Score = (number of supported claims) / (total number of claims).
   Score = 1.0 if the answer has no claims (e.g., politely refuses).
   Score = 0.0 if every claim is unsupported.

Respond ONLY with a JSON object: {{"score": <float between 0.0 and 1.0>, "reason": "<brief reason>"}}
"""

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=200,
        )
        text = resp.choices[0].message.content.strip()
        # Extract JSON
        match = re.search(r'\{[^}]+\}', text, re.DOTALL)
        if match:
            data = json.loads(match.group())
            return round(float(data["score"]), 3), data.get("reason", "")
        return None, text
    except Exception as e:
        return None, str(e)


def ragas_response_relevancy_via_llm(question, answer, api_key, model):
    """
    Simulate RAGAS Response Relevancy: does the answer address the question?
    UsesROUGE-L / overlap heuristics via LLM judgment.
    """
    import openai
    client = openai.OpenAI(api_key=api_key)

    prompt = f"""You are evaluating whether an answer is relevant to its question.

Question: {question}
Answer: {answer}

Rate relevance on a scale of 0.0 to 1.0:
- 1.0 = Answer fully addresses the question intent.
- 0.5 = Answer partially addresses the question but misses some aspects.
- 0.0 = Answer does not address the question at all.

Respond ONLY with: {{"score": <float>}}
"""

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=100,
        )
        text = resp.choices[0].message.content.strip()
        match = re.search(r'\{[^}]+\}', text, re.DOTALL)
        if match:
            data = json.loads(match.group())
            return round(float(data["score"]), 3)
        return None
    except Exception as e:
        return None


def run_ragas_comparison():
    """Run LLM-based RAGAS-style evaluation on all 20 cases."""
    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    if not api_key or api_key == "sk-...":
        print("No valid API key — using design-based comparison only")
        return None

    results = []
    print(f"Running RAGAS-style LLM evaluation ({len(answers_data['answers'])} cases × 2 metrics)")
    print("Estimated time: ~2-3 minutes\n")

    for i, ans in enumerate(answers_data["answers"]):
        qid = ans["id"]
        pair = next(p for p in golden["qa_pairs"] if p["id"] == qid)
        contexts = [c["text"] for c in ans["retrieved_contexts"]]
        retrieved_context = "\n\n".join(contexts)

        # Faithfulness (RAGAS-style)
        f_score, reason = ragas_faithfulness_via_llm(
            pair["question"], ans["actual_answer"], retrieved_context, api_key, model
        )
        # Response Relevancy
        r_score = ragas_response_relevancy_via_llm(
            pair["question"], ans["actual_answer"], api_key, model
        )

        results.append({
            "id": qid,
            "ragas_faithfulness": f_score,
            "ragas_relevancy": r_score,
        })
        label = f"[{i+1:02d}/{len(answers_data['answers'])}] {qid}"
        print(f"  {label}: F={f_score} R={r_score}")
        time.sleep(0.3)  # rate limit protection

    return results


def compute_comparison():
    """Compute per-case and aggregate comparison."""
    wo = run_word_overlap()
    ragas = run_ragas_comparison()

    print("\n" + "=" * 80)
    print("PER-CASE COMPARISON: Word-Overlap vs RAGAS (LLM-based)")
    print("=" * 80)
    header = f"{'ID':<5} {'WO_F':>7} {'RAGAS_F':>8} {'Diff_F':>8} {'WO_R':>7} {'RAGAS_R':>8} {'Diff_R':>8} {'WO_Avg':>7} {'RAGAS_Avg':>9}"
    header = f"{'ID':<5} {'WO_F':>7} {'RAGAS_F':>8} {'Diff_F':>8} {'WO_R':>7} {'RAGAS_R':>8} {'Diff_R':>8} {'WO_Avg':>7} {'RAGAS_Avg':>9}"
    print(header)
    print("-" * 80)

    match_f, match_r = 0, 0
    wo_f_list, rg_f_list = [], []
    wo_r_list, rg_r_list = [], []
    wo_avg_list, rg_avg_list = [], []

    for wo_row, rg_row in zip(wo, ragas):
        wo_f = wo_row["faithfulness"]
        rg_f = rg_row["ragas_faithfulness"]
        wo_f_list.append(wo_f)
        rg_f_list.append(rg_f)

        wo_r = wo_row["relevance"]
        rg_r = rg_row["ragas_relevancy"]
        wo_r_list.append(wo_r)
        rg_r_list.append(rg_r)

        wo_avg_list.append(wo_row["overall"])
        rg_avg = round((rg_f + rg_r + wo_row["completeness"]) / 3, 3)
        rg_avg_list.append(rg_avg)

        diff_f = f"{rg_f - wo_f:+.3f}" if rg_f is not None else "N/A"
        diff_r = f"{rg_r - wo_r:+.3f}" if rg_r is not None else "N/A"

        if rg_f is not None and abs(rg_f - wo_f) <= 0.15:
            match_f += 1
        if rg_r is not None and abs(rg_r - wo_r) <= 0.15:
            match_r += 1

        def fmt(v):
            return f"{v:.3f}" if isinstance(v, float) else str(v)

        print(f"{wo_row['id']:<5} {fmt(wo_f):>7} {fmt(rg_f):>8} {diff_f:>8} {fmt(wo_r):>7} {fmt(rg_r):>8} {diff_r:>8} {fmt(wo_row['overall']):>7} {fmt(rg_avg):>9}")

    print("-" * 80)

    def avg(lst):
        return sum(lst) / len(lst) if lst else 0.0

    n = len(rg_f_list)
    print(f"\nAGGREGATE:")
    print(f"  Avg Faithfulness  - Word-Overlap: {avg(wo_f_list):.3f}  |  RAGAS: {avg(rg_f_list):.3f}  |  Delta = {avg(rg_f_list)-avg(wo_f_list):+.3f}")
    print(f"  Avg Relevance    - Word-Overlap: {avg(wo_r_list):.3f}  |  RAGAS: {avg(rg_r_list):.3f}  |  Delta = {avg(rg_r_list)-avg(wo_r_list):+.3f}")
    print(f"  Avg Overall      - Word-Overlap: {avg(wo_avg_list):.3f}  |  RAGAS: {avg(rg_avg_list):.3f}  |  Delta = {avg(rg_avg_list)-avg(wo_avg_list):+.3f}")
    print(f"  Faithfulness within ±0.15: {match_f}/{n} cases")
    print(f"  Relevance within ±0.15: {match_r}/{n} cases")

    # Failure agreement
    wo_fails = {r["id"] for r in wo if r["overall"] < 0.7}
    rg_fails = {r["id"] for r in ragas if r["ragas_faithfulness"] < 0.7} if ragas else set()
    common_fails = wo_fails & rg_fails
    print(f"\n  Failures (overall < 0.7): WO={sorted(wo_fails)}")
    print(f"  Failures (RAGAS faithfulness < 0.7): {sorted(rg_fails) if ragas else 'N/A'}")
    print(f"  Common failures: {sorted(common_fails)}")
    print(f"  RAGAS catches MORE failures: {len(rg_fails) > len(wo_fails)}")
    print(f"  RAGAS stricter than WO: {avg(rg_f_list) < avg(wo_f_list)}")

    # Save
    out = {
        "word_overlap": wo,
        "ragas": ragas,
        "summary": {
            "wo_avg_faithfulness": round(avg(wo_f_list), 3),
            "ragas_avg_faithfulness": round(avg(rg_f_list), 3),
            "wo_avg_relevance": round(avg(wo_r_list), 3),
            "ragas_avg_relevance": round(avg(rg_r_list), 3),
            "delta_faithfulness": round(avg(rg_f_list) - avg(wo_f_list), 3),
            "delta_relevance": round(avg(rg_r_list) - avg(wo_r_list), 3),
            "match_count_faithfulness": match_f,
            "match_count_relevance": match_r,
            "total": n,
        }
    }
    with open("artifacts/framework_comparison.json", "w") as f:
        json.dump(out, f, indent=2)

    return wo, ragas


if __name__ == "__main__":
    compute_comparison()
