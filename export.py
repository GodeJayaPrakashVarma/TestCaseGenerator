import json, os, csv
from utils import load_json_file, save_json_file


def to_gherkin_steps(keyword, items):
    lines = []
    for i, item in enumerate(items):
        step_keyword = keyword if i == 0 else "And"
        lines.append(f"    {step_keyword} {item}")
    return lines


def export_to_gherkin(structured_requirements, test_cases_by_id, output_dir="exports/features"):
    os.makedirs(output_dir, exist_ok=True)
    feature_names = {
        entry["id"]: entry["structured_requirement"].get("feature_name", entry["id"])
        for entry in structured_requirements
    }

    for fixture in test_cases_by_id:
        req_id = fixture["id"]
        lines = [f"Feature: {feature_names.get(req_id, req_id)}", ""]

        for tc in fixture["test_cases"]:
            tags = [tc.get("category", "")] + tc.get("linked_rule_ids", [])
            tag_line = " ".join(f"@{t}" for t in tags if t)
            if tag_line:
                lines.append(f"  {tag_line}")
            lines.append(f"  Scenario: {tc['title']}")

            if tc.get("preconditions"):
                lines.extend(to_gherkin_steps("Given", tc["preconditions"]))
            if tc.get("steps"):
                lines.extend(to_gherkin_steps("When", tc["steps"]))
            if tc.get("expected_result"):
                lines.append(f"    Then {tc['expected_result']}")
            if tc.get("test_data"):
                lines.append(f"    # test_data: {json.dumps(tc['test_data'])}")
            lines.append("")

        with open(os.path.join(output_dir, f"{req_id}.feature"), "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    print(f"Gherkin features written to {output_dir}/")


def export_to_csv(test_cases_by_id, output_path="exports/test_cases.csv"):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    fieldnames = ["requirement_id", "test_id", "title", "category", "linked_rule_ids",
                  "preconditions", "steps", "test_data", "expected_result"]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for fixture in test_cases_by_id:
            for tc in fixture["test_cases"]:
                writer.writerow({
                    "requirement_id": fixture["id"],
                    "test_id": tc.get("test_id", ""),
                    "title": tc.get("title", ""),
                    "category": tc.get("category", ""),
                    "linked_rule_ids": "; ".join(tc.get("linked_rule_ids", [])),
                    "preconditions": " | ".join(tc.get("preconditions", [])),
                    "steps": " | ".join(tc.get("steps", [])),
                    "test_data": json.dumps(tc.get("test_data", {})),
                    "expected_result": tc.get("expected_result", ""),
                })

    print(f"CSV written to {output_path}")


if __name__ == "__main__":
    structured_requirements = load_json_file("structured_requirements.json", required=True,
                                              hint="Run requirement_analyzer.py first.")
    test_cases_by_id = load_json_file("test_cases.json", required=True,
                                       hint="Run the pipeline first.")
    review_results = load_json_file("review_results.json", required=True,
                                     hint="Run reviewer.py or the full pipeline first.")

    approved_fixtures = [f for f in test_cases_by_id if review_results.get(f["id"], {}).get("approved")]
    pending_fixtures = [f for f in test_cases_by_id if not review_results.get(f["id"], {}).get("approved")]

    if approved_fixtures:
        approved_structured = [e for e in structured_requirements if e["id"] in {f["id"] for f in approved_fixtures}]
        export_to_gherkin(approved_structured, approved_fixtures)
        export_to_csv(approved_fixtures)

    if pending_fixtures:
        save_json_file("pending_human_review.json",
                        {f["id"]: review_results[f["id"]] for f in pending_fixtures})
        print(f"Held for human review, not exported: {[f['id'] for f in pending_fixtures]}")