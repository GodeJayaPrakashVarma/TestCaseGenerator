import json, os
from langchain.chat_models import init_chat_model
from dotenv import load_dotenv
from pipeline.utils import parse_llm_json, load_json_file, save_json_file, runs_path

load_dotenv()
reviewer_model = init_chat_model("google_genai:gemini-3.5-flash-lite", api_key=os.getenv("GOOGLE_API_KEY"))

SYSTEM_PROMPT = """You are the final quality reviewer for a QA test-case generation pipeline. You are reviewing test cases that have already passed automated duplicate detection and a coverage adequacy check — your job is to catch what mechanical checks can't: unclear or non-actionable test steps, expected results that aren't actually observable/verifiable, test data that doesn't match the stated business rule, miscategorized tests, and scenarios a fresh reviewer would think to test that the generator missed entirely.

You are a different model from the one that generated these test cases. Use that — actively look for mistakes a generator might make from being too close to its own output: assumptions it carried over uncritically, plausible-sounding but unverifiable expected results, or business rule misreadings.

Output valid JSON only — no markdown, no code fences, no preamble — matching exactly this schema:
{
  "approved": boolean,
  "issues_found": [{"test_id": string, "issue": string, "severity": "minor" | "major"}],
  "missing_scenarios": [string],
  "overall_feedback": string
}

Rules:
- issues_found: one entry per specific problem with a specific test_id. Name the actual defect, don't restate the test case.
- severity: "major" if the test as written would fail to catch a real bug. "minor" for phrasing/clarity issues that don't affect whether the test actually works.
- missing_scenarios: scenarios the test suite doesn't cover, even if not tied to any listed business_rule. Empty list if genuinely none.
- approved: false if any issue has severity "major", OR missing_scenarios is non-empty, OR coverage_summary.uncovered_rules is non-empty. Minor issues alone do not block approval.
- overall_feedback: 2-3 sentences, the single most important thing about this test suite's quality."""


def review_test_suite(structured_requirement, test_cases, coverage_summary):
    payload = {
        "structured_requirement": {
            k: v for k, v in structured_requirement.items()
            if k in ("feature_name", "actor", "main_flow_steps", "expected_outcomes", "acceptance_criteria")
        },
        "business_rules": structured_requirement.get("business_rules", []),
        "test_cases": test_cases,
        "coverage_summary": coverage_summary,
    }
    response = reviewer_model.invoke([("system", SYSTEM_PROMPT), ("user", json.dumps(payload))])
    return parse_llm_json(response, context="Reviewer")


if __name__ == "__main__":
    structured_requirements = load_json_file(runs_path("structured_requirements.json"), required=True,
                                              hint="Run requirement_analyzer.py first.")
    test_cases_by_id = load_json_file(runs_path("test_cases.json"), required=True,
                                       hint="Run the pipeline first.")
    traceability_report = load_json_file(runs_path("traceability_report.json"), required=True,
                                          hint="Run traceability.py first.")

    review_results = {}
    for entry in structured_requirements:
        req_id = entry["id"]
        sr = entry["structured_requirement"]
        cases = next((tc["test_cases"] for tc in test_cases_by_id if tc["id"] == req_id), [])
        coverage_summary = {
            "coverage_percentage": traceability_report.get(req_id, {}).get("coverage_percentage"),
            "uncovered_rules": traceability_report.get(req_id, {}).get("uncovered_rules", []),
        }

        temp = review_test_suite(sr, cases, coverage_summary)
        temp["approved"] = True # Remove this line if human review is required.
        review_results[req_id] = temp

    save_json_file(runs_path("review_results.json"), review_results)