import os
from datetime import datetime, timezone
from typing import TypedDict, Optional
from langgraph.graph import StateGraph, END
from testgenerator import generate_test_cases
from dedup import duplicate_detector
from traceability import build_traceability_matrix
from coverage_verifier import coverage_verifier
from reviewer import review_test_suite
from utils import load_json_file, save_json_file


class RequirementState(TypedDict):
    id: str
    structured_requirement: dict
    test_cases: list
    covered_rule_ids: set
    gap_context: Optional[dict]
    retry_count: int
    matrix_report: dict
    dupes_log: list
    review_result: dict


def generate_node(state):
    existing_titles = [tc["title"] for tc in state["test_cases"]]
    new_cases = generate_test_cases(state["structured_requirement"],
                                     gap_context=state.get("gap_context"),
                                     existing_titles=existing_titles)
    for i, tc in enumerate(new_cases, start=len(state["test_cases"]) + 1):
        tc["test_id"] = f"{state['id']}-TC-{i}"
    return {"test_cases": state["test_cases"] + new_cases}


def dedup_node(state):
    deduped, log = duplicate_detector(state["test_cases"], state["id"])
    return {"test_cases": deduped, "dupes_log": state["dupes_log"] + log}


def matrix_node(state):
    entry = {"id": state["id"], "structured_requirement": state["structured_requirement"]}
    report = build_traceability_matrix([entry], [{"id": state["id"], "test_cases": state["test_cases"]}])
    return {"matrix_report": report[state["id"]]}


def verify_node(state):
    entry = {"id": state["id"], "structured_requirement": state["structured_requirement"]}
    results = coverage_verifier([entry], [{"id": state["id"], "test_cases": state["test_cases"]}],
                                 {state["id"]: state["matrix_report"]},
                                 covered_rule_ids_by_fixture={state["id"]: state["covered_rule_ids"]})
    judgments = next((r["adequacy_judgments"] for r in results if r["id"] == state["id"]), [])
    covered = state["covered_rule_ids"] | {j["rule_id"] for j in judgments if j["adequate"]}
    inadequate = [j for j in judgments if not j["adequate"]]
    gap_context = {"uncovered_rules": state["matrix_report"]["uncovered_rules"], "inadequate_rules": inadequate}
    return {"covered_rule_ids": covered, "gap_context": gap_context, "retry_count": state["retry_count"] + 1}


def review_node(state):
    coverage_summary = {"coverage_percentage": state["matrix_report"]["coverage_percentage"],
                         "uncovered_rules": state["matrix_report"]["uncovered_rules"]}
    result = review_test_suite(state["structured_requirement"], state["test_cases"], coverage_summary)
    return {"review_result": result}


def should_retry(state):
    has_gaps = bool(state["gap_context"]["uncovered_rules"]) or bool(state["gap_context"]["inadequate_rules"])
    if has_gaps and state["retry_count"] < 3:
        return "retry"
    return "review"


graph = StateGraph(RequirementState)
graph.add_node("generate", generate_node)
graph.add_node("dedup", dedup_node)
graph.add_node("matrix", matrix_node)
graph.add_node("verify", verify_node)
graph.add_node("review", review_node)

graph.set_entry_point("generate")
graph.add_edge("generate", "dedup")
graph.add_edge("dedup", "matrix")
graph.add_edge("matrix", "verify")
graph.add_conditional_edges("verify", should_retry, {"retry": "generate", "review": "review"})
graph.add_edge("review", END)

compiled_graph = graph.compile()


def run_full_pipeline(structured_requirements):
    all_results = []
    for entry in structured_requirements:
        initial_state = {
            "id": entry["id"], "structured_requirement": entry["structured_requirement"],
            "test_cases": [], "covered_rule_ids": set(), "gap_context": None,
            "retry_count": 0, "matrix_report": {}, "dupes_log": [], "review_result": {},
        }
        final_state = compiled_graph.invoke(initial_state)
        all_results.append(final_state)
    return all_results


def write_pipeline_outputs(all_results):
    save_json_file("test_cases.json", [{"id": r["id"], "test_cases": r["test_cases"]} for r in all_results])
    save_json_file("review_results.json", {r["id"]: r["review_result"] for r in all_results})

    run_id = datetime.now(timezone.utc).isoformat(timespec="seconds")
    record = {
        "run_id": run_id,
        "requirements": [
            {
                "id": r["id"],
                "final_coverage": r["matrix_report"]["coverage_percentage"],
                "retries_used": r["retry_count"],
                "test_case_count": len(r["test_cases"]),
                "duplicates_removed_count": len(r["dupes_log"]),
                "review_approved": r["review_result"]["approved"],
                "review_issue_count": len(r["review_result"]["issues_found"]),
            }
            for r in all_results
        ],
    }
    runs = load_json_file("pipeline_runs.json", required=False, default=[])
    runs.append(record)
    save_json_file("pipeline_runs.json", runs)

    new_dupes = [{**entry, "run_id": run_id} for r in all_results for entry in r["dupes_log"]]
    existing_dupes = load_json_file("duplicates_removed.json", required=False, default=[])
    existing_dupes.extend(new_dupes)
    save_json_file("duplicates_removed.json", existing_dupes)

    return run_id


if __name__ == "__main__":
    structured_requirements = load_json_file(
        "structured_requirements.json", required=True,
        hint="Run requirement_analyzer.py first."
    )

    all_results = run_full_pipeline(structured_requirements)
    run_id = write_pipeline_outputs(all_results)

    print(f"Run {run_id} complete.")
    for r in all_results:
        print(f"  {r['id']}: coverage={r['matrix_report']['coverage_percentage']}, "
              f"review_approved={r['review_result']['approved']}, retries={r['retry_count']}")