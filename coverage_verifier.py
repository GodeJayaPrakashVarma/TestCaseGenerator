import json, os
from langchain.chat_models import init_chat_model
from dotenv import load_dotenv
from utils import parse_llm_json, load_json_file, save_json_file

load_dotenv()
model = init_chat_model("google_genai:gemini-3.5-flash-lite", api_key=os.getenv("GOOGLE_API_KEY"))

SYSTEM_PROMPT = """You are a coverage adequacy judge for a QA test-case generation pipeline. You are given business rules that already have at least one linked test case — the mechanical link has already been verified. Your job is to judge whether the linked test case(s) actually exercise the substance of each rule, not just whether a link exists.

Mark adequate=true only if at least one linked test case's steps and expected_result would genuinely catch a violation of that rule if the implementation were wrong. If the linked case checks something adjacent or generic but doesn't test the rule's specific condition, mark it inadequate.

Output valid JSON only — no markdown, no code fences, no preamble — matching exactly this schema:
{
  "adequacy_judgments": [
    {"rule_id": string, "adequate": boolean, "reasoning": string, "gap": string}
  ]
}

Rules:
- One entry per rule_id provided. Do not judge rules not given to you.
- reasoning: one sentence, specific to what the linked test case(s) do or don't verify — not generic praise.
- gap: only when adequate is false, a short concrete description of the missing scenario, written so it can be handed directly to a test generator as a target. Empty string when adequate is true."""


def coverage_verifier(structured_requirements, test_cases, traceability_report, covered_rule_ids_by_fixture=None):
    covered_rule_ids_by_fixture = covered_rule_ids_by_fixture or {}
    all_results = []

    test_case_lookup = {
        fixture["id"]: {tc["test_id"]: tc for tc in fixture.get("test_cases", [])}
        for fixture in test_cases
    }
    rules_lookup = {
        entry["id"]: {br["rule_id"]: br for br in entry["structured_requirement"].get("business_rules", [])}
        for entry in structured_requirements
    }

    for fixture_id, report in traceability_report.items():
        already_covered = covered_rule_ids_by_fixture.get(fixture_id, set())
        rules_to_judge = []
        for rule_id, linked_test_ids in report["traceability_matrix"].items():
            if not linked_test_ids or rule_id in already_covered:
                continue
            rule = rules_lookup.get(fixture_id, {}).get(rule_id)
            if not rule:
                continue
            linked_cases = [
                {
                    "test_id": tid,
                    "title": test_case_lookup[fixture_id][tid]["title"],
                    "steps": test_case_lookup[fixture_id][tid]["steps"],
                    "expected_result": test_case_lookup[fixture_id][tid]["expected_result"],
                }
                for tid in linked_test_ids
                if tid in test_case_lookup.get(fixture_id, {})
            ]
            rules_to_judge.append({
                "rule_id": rule_id,
                "description": rule.get("description", ""),
                "source_text": rule.get("source_text", ""),
                "linked_test_cases": linked_cases,
            })

        if not rules_to_judge:
            continue

        payload = {"rules_to_judge": rules_to_judge}
        response = model.invoke([("system", SYSTEM_PROMPT), ("user", json.dumps(payload))])
        parsed = parse_llm_json(response, context=f"Coverage Verifier ({fixture_id})")
        all_results.append({"id": fixture_id, **parsed})

    return all_results


if __name__ == "__main__":
    structured_requirements = load_json_file("structured_requirements.json", required=True,
                                              hint="Run requirement_analyzer.py first.")
    test_cases = load_json_file("test_cases.json", required=True,
                                 hint="Run the pipeline first.")
    traceability_report = load_json_file("traceability_report.json", required=True,
                                          hint="Run traceability.py first.")

    results = coverage_verifier(structured_requirements, test_cases, traceability_report)
    save_json_file("adequacy_judgments.json", results)