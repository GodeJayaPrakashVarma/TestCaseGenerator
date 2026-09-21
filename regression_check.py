from pipeline.graph import run_full_pipeline
from pipeline.utils import load_json_file

ISSUE_COUNT_TOLERANCE = 1

def check_regression():
    golden_requirements = load_json_file(
        "golden/structured_requirements.json", required=True,
        hint="Run create_baseline.py first to create the golden baseline."
    )
    golden_summary = load_json_file(
        "golden/golden_summary.json", required=True,
        hint="Run create_baseline.py first to create the golden baseline."
    )

    print("Running pipeline against golden requirements...")
    results = run_full_pipeline(golden_requirements)

    problems = []

    for state in results:
        req_id = state["id"]
        baseline = golden_summary.get(req_id, {})

        for tc in state["test_cases"]:
            for field in ["test_id", "title", "category", "steps", "expected_result"]:
                if field not in tc:
                    problems.append(f"{req_id}/{tc.get('test_id')}: missing '{field}'")

        ids = [tc["test_id"] for tc in state["test_cases"]]
        if len(ids) != len(set(ids)):
            problems.append(f"{req_id}: duplicate test_id values found")

        valid_rule_ids = set(br["rule_id"] for br in state["structured_requirement"].get("business_rules", []))
        for tc in state["test_cases"]:
            for rid in tc.get("linked_rule_ids", []):
                if rid not in valid_rule_ids:
                    problems.append(f"{req_id}/{tc['test_id']}: invented rule_id '{rid}'")

        current_coverage = state["matrix_report"]["coverage_percentage"]
        baseline_coverage = baseline.get("final_coverage", 0)
        if current_coverage < baseline_coverage:
            problems.append(f"{req_id}: coverage dropped ({current_coverage} < baseline {baseline_coverage})")

        current_issues = len(state["review_result"]["issues_found"])
        baseline_issues = baseline.get("review_issue_count", 0)
        if current_issues > baseline_issues + ISSUE_COUNT_TOLERANCE:
            problems.append(f"{req_id}: review issues increased ({current_issues} > baseline {baseline_issues})")

    print()
    if problems:
        print(f"FAILED — {len(problems)} problem(s) found:")
        for p in problems:
            print(" -", p)
        return False
    else:
        print("PASSED — no regressions found.")
        return True

if __name__ == "__main__":
    passed = check_regression()
    if not passed:
        exit(1)
