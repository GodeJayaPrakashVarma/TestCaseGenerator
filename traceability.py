from utils import load_json_file, save_json_file


def build_traceability_matrix(structured_requirements, test_cases_by_id):
    reports = {}
    for entry in structured_requirements:
        req_id = entry["id"]
        rules = entry["structured_requirement"].get("business_rules", [])
        cases = next((tc["test_cases"] for tc in test_cases_by_id if tc["id"] == req_id), [])

        matrix = {rule["rule_id"]: [] for rule in rules}
        for case in cases:
            for rule_id in case.get("linked_rule_ids", []):
                if rule_id in matrix:
                    matrix[rule_id].append(case["test_id"])

        uncovered = [rid for rid, tids in matrix.items() if not tids]
        coverage_pct = 1 - (len(uncovered) / len(matrix)) if matrix else 1.0

        reports[req_id] = {
            "traceability_matrix": matrix,
            "uncovered_rules": uncovered,
            "coverage_percentage": round(coverage_pct, 2),
        }
    return reports


if __name__ == "__main__":
    structured_requirements = load_json_file(
        "structured_requirements.json", required=True,
        hint="Run requirement_analyzer.py first."
    )
    test_cases_by_id = load_json_file(
        "test_cases.json", required=True,
        hint="Run the pipeline (run_pipeline.py or graph.py) first."
    )

    traceability_report = build_traceability_matrix(structured_requirements, test_cases_by_id)
    save_json_file("traceability_report.json", traceability_report)