import json
import time
import os
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.graph.workflow import run_workflow
from app.observability import new_run_id
from dotenv import load_dotenv
import argparse

load_dotenv()

RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)


def load_questions(path: str = None) -> list[dict]:
    questions_path = path or Path(__file__).parent / "questions.json"
    with open(questions_path, "r", encoding="utf-8") as f:
        return json.load(f)


def check_sql_uses_expected_tables(generated_sql: str, expected_tables: list[str]) -> bool:
    if not generated_sql:
        return False
    sql_lower = generated_sql.lower()
    return all(table.lower() in sql_lower for table in expected_tables)


def check_answer_contains_facts(answer: str, expected_facts: list[str]) -> float:
    if not answer or not expected_facts:
        return 0.0
    answer_lower = answer.lower()
    matched = sum(1 for fact in expected_facts if any(word.lower() in answer_lower for word in fact.split()))
    return matched / len(expected_facts) if expected_facts else 0.0


def evaluate(
    db_config: dict,
    groq_api_key: str,
    question_ids: list[int] | None = None,
    questions_path: str | None = None,
    groq_model: str | None = None,
) -> dict:
    questions = load_questions(questions_path)

    if question_ids:
        questions = [q for q in questions if q["id"] in question_ids]

    results = []
    total = len(questions)
    sql_successes = 0
    table_correct = 0
    answer_fact_scores = []
    retry_counts = []
    latencies = []
    failures = 0

    print(f"\n{'='*60}")
    print(f"  Agentic Data Analyst — Evaluation")
    print(f"  Questions: {total}")
    print(f"{'='*60}\n")

    for i, q in enumerate(questions):
        print(f"[{i+1}/{total}] {q['question'][:70]}...")
        run_id = new_run_id()
        start = time.monotonic()

        try:
            result = run_workflow(
                question=q["question"],
                db_config=db_config,
                groq_api_key=groq_api_key,
                run_id=run_id,
                groq_model=groq_model,
            )
            elapsed = (time.monotonic() - start) * 1000

            import pandas as pd
            df = result.get("query_result")
            sql_success = df is not None and isinstance(df, pd.DataFrame) and not df.empty

            if sql_success:
                sql_successes += 1
                print(f"  ✓ SQL success | rows: {len(df)} | {elapsed:.0f}ms")
            else:
                print(f"  ✗ SQL failed or empty | {elapsed:.0f}ms")
                if result.get("execution_error"):
                    print(f"    Error: {result['execution_error'][:100]}")

            generated_sql = result.get("generated_sql") or ""
            tables_ok = check_sql_uses_expected_tables(generated_sql, q["expected_tables"])
            if tables_ok:
                table_correct += 1

            answer = result.get("final_answer") or ""
            fact_score = check_answer_contains_facts(answer, q["expected_answer_facts"])
            answer_fact_scores.append(fact_score)

            retries = result.get("iteration_count", 0)
            retry_counts.append(retries)
            latencies.append(elapsed)

            results.append({
                "id": q["id"],
                "question": q["question"],
                "sql_success": sql_success,
                "tables_correct": tables_ok,
                "fact_score": fact_score,
                "retries": retries,
                "latency_ms": round(elapsed, 2),
                "generated_sql": generated_sql[:500],
                "error": result.get("execution_error"),
            })

        except Exception as e:
            elapsed = (time.monotonic() - start) * 1000
            failures += 1
            latencies.append(elapsed)
            retry_counts.append(0)
            answer_fact_scores.append(0.0)
            print(f"  ✗ Exception: {str(e)[:100]}")
            results.append({
                "id": q["id"],
                "question": q["question"],
                "sql_success": False,
                "tables_correct": False,
                "fact_score": 0.0,
                "retries": 0,
                "latency_ms": round(elapsed, 2),
                "generated_sql": None,
                "error": str(e),
            })

    report = {
        "timestamp": datetime.now().isoformat(),
        "total_questions": total,
        "sql_execution_success_rate": round(sql_successes / total * 100, 1),
        "schema_adherence_rate": round(table_correct / total * 100, 1),
        "avg_fact_score": round(sum(answer_fact_scores) / len(answer_fact_scores) * 100, 1) if answer_fact_scores else 0.0,
        "avg_retries": round(sum(retry_counts) / len(retry_counts), 2) if retry_counts else 0.0,
        "avg_latency_ms": round(sum(latencies) / len(latencies), 1) if latencies else 0.0,
        "failure_count": failures,
        "results": results,
    }

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = RESULTS_DIR / f"eval_{timestamp}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"\n{'='*60}")
    print(f"  EVALUATION RESULTS")
    print(f"{'='*60}")
    print(f"  Total questions:       {total}")
    print(f"  SQL success rate:      {report['sql_execution_success_rate']}%")
    print(f"  Schema adherence:      {report['schema_adherence_rate']}%")
    print(f"  Avg answer fact score: {report['avg_fact_score']}%")
    print(f"  Avg SQL retries:       {report['avg_retries']}")
    print(f"  Avg latency:           {report['avg_latency_ms']} ms")
    print(f"  Failures:              {failures}")
    print(f"\n  Full report saved to: {out_path}")
    print(f"{'='*60}\n")

    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate Agentic Data Analyst")
    parser.add_argument("--host", required=True, help="MySQL host")
    parser.add_argument("--port", type=int, default=3306, help="MySQL port")
    parser.add_argument("--user", required=True, help="MySQL user")
    parser.add_argument("--password", required=True, help="MySQL password")
    parser.add_argument("--database", required=True, help="MySQL database")
    parser.add_argument("--groq-key", required=True, help="Groq API key")
    parser.add_argument("--model", default=None, help="Groq model name")
    parser.add_argument("--ids", nargs="*", type=int, help="Specific question IDs to evaluate")
    args = parser.parse_args()

    db_config = {
        "host": args.host,
        "port": args.port,
        "user": args.user,
        "password": args.password,
        "database": args.database,
    }

    evaluate(db_config=db_config, groq_api_key=args.groq_key, question_ids=args.ids, groq_model=args.model)
