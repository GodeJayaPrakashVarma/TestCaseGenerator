from utils import load_json_file, save_json_file


def create_baseline():
    structured_requirements = load_json_file("structured_requirements.json", required=True,
                                               hint="Run requirement_analyzer.py first.")
    save_json_file("golden/structured_requirements.json", structured_requirements)

    test_cases = load_json_file("test_cases.json", required=True,
                                 hint="Run the pipeline first.")
    save_json_file("golden/test_cases.json", test_cases)

    all_runs = load_json_file("pipeline_runs.json", required=True,
                               hint="Run the pipeline first — pipeline_runs.json is written by graph.py.")
    latest_run = all_runs[-1]

    summary = {
        req["id"]: {
            "final_coverage": req["final_coverage"],
            "review_issue_count": req["review_issue_count"],
        }
        for req in latest_run["requirements"]
    }
    save_json_file("golden/golden_summary.json", summary)

    print("Golden baseline saved from run:", latest_run["run_id"])


if __name__ == "__main__":
    create_baseline()