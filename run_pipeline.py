from pipeline.requirement_analyzer import run_requirement_analyzer
from pipeline.graph import run_full_pipeline, write_pipeline_outputs
from pipeline.export import export_to_gherkin, export_to_csv
from pipeline.utils import save_json_file, load_json_file, runs_path

if __name__ == "__main__":
    print("Step 1/3: Requirement Analyzer")
    structured_requirements = run_requirement_analyzer()
    save_json_file(runs_path("structured_requirements.json"), structured_requirements)

    print("Step 2/3: Generate -> Dedup -> Matrix -> Verify -> Review (LangGraph)")
    all_results = run_full_pipeline(structured_requirements)
    run_id = write_pipeline_outputs(all_results)

    print("Step 3/3: Export")
    test_cases_by_id = load_json_file(
        runs_path("test_cases.json"), required=True,
        hint="write_pipeline_outputs() should have created this in Step 2 — check graph.py."
    )
    review_results = load_json_file(
        runs_path("review_results.json"), required=True,
        hint="write_pipeline_outputs() should have created this in Step 2 — check graph.py."
    )

    approved_fixtures = [f for f in test_cases_by_id if review_results.get(f["id"], {}).get("approved")]
    pending_fixtures = [f for f in test_cases_by_id if not review_results.get(f["id"], {}).get("approved")]

    if approved_fixtures:
        approved_structured = [e for e in structured_requirements if e["id"] in {f["id"] for f in approved_fixtures}]
        export_to_gherkin(approved_structured, approved_fixtures)
        export_to_csv(approved_fixtures)

    if pending_fixtures:
        save_json_file(runs_path("pending_human_review.json"),
                        {f["id"]: review_results[f["id"]] for f in pending_fixtures})

    print(f"\nDone. Run {run_id}.")
    print(f"  Exported: {[f['id'] for f in approved_fixtures]}")
    print(f"  Held for review: {[f['id'] for f in pending_fixtures]}")