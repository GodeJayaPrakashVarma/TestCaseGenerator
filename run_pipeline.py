import json
from requirement_analyzer import run_requirement_analyzer
from graph import run_full_pipeline, write_pipeline_outputs
from export import export_to_gherkin, export_to_csv

if __name__ == "__main__":
    print("Step 1/3: Requirement Analyzer")
    structured_requirements = run_requirement_analyzer()
    with open("structured_requirements.json", "w", encoding="utf-8") as f:
        json.dump(structured_requirements, f, indent=2)

    print("Step 2/3: Generate -> Dedup -> Matrix -> Verify -> Review (LangGraph)")
    all_results = run_full_pipeline(structured_requirements)
    run_id = write_pipeline_outputs(all_results)

    print("Step 3/3: Export")
    with open("test_cases.json", "r", encoding="utf-8") as f:
        test_cases_by_id = json.load(f)
    with open("review_results.json", "r", encoding="utf-8") as f:
        review_results = json.load(f)

    approved_fixtures = [f for f in test_cases_by_id if review_results.get(f["id"], {}).get("approved")]
    pending_fixtures = [f for f in test_cases_by_id if not review_results.get(f["id"], {}).get("approved")]

    if approved_fixtures:
        approved_structured = [e for e in structured_requirements if e["id"] in {f["id"] for f in approved_fixtures}]
        export_to_gherkin(approved_structured, approved_fixtures)
        export_to_csv(approved_fixtures)

    if pending_fixtures:
        with open("pending_human_review.json", "w", encoding="utf-8") as f:
            json.dump({f["id"]: review_results[f["id"]] for f in pending_fixtures}, f, indent=2)

    print(f"\nDone. Run {run_id}.")
    print(f"  Exported: {[f['id'] for f in approved_fixtures]}")
    print(f"  Held for review: {[f['id'] for f in pending_fixtures]}")