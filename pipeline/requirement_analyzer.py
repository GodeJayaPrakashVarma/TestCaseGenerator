import os, yaml
from langchain.chat_models import init_chat_model
from dotenv import load_dotenv
from pipeline.utils import parse_llm_json, save_json_file, runs_path

load_dotenv()
model = init_chat_model("google_genai:gemini-3.5-flash-lite", api_key=os.getenv("GOOGLE_API_KEY"))

SYSTEM_PROMPT = """You are a requirement analyzer for a QA test-case generation pipeline. Given ONE raw software requirement, extract it into structured JSON. Do not invent details, constraints, or fields not stated or clearly implied by the text.

Output valid JSON only — no markdown, no code fences, no preamble — matching exactly this schema:
{
  "feature_name": string,
  "actor": string,
  "preconditions": [string],
  "main_flow_steps": [string],
  "inputs": [{"field": string, "type": string, "constraints": string}],
  "expected_outcomes": [string],
  "business_rules": [{"rule_id": string, "description": string, "type": "validation" | "authorization" | "calculation" | "state_transition", "source_text": string}],
  "acceptance_criteria": [string],
  "ambiguities": [string]
}

Rules:
- feature_name: 3-6 words, noun-phrase summary.
- actor: the role performing the action, not a person's name. Keep any qualifier stated in the text (e.g. plan tier, account type).
- preconditions: what must be true before the flow starts. Empty list if none stated.
- main_flow_steps: ordered, imperative steps describing what happens.
- inputs: ONLY values the actor actively provides or submits. Do not add generic constraints the text doesn't state. Do not put business rules or system behavior here. Omit the key entirely if no explicit input values exist.
- expected_outcomes: observable system behavior after the flow completes.
- business_rules: explicit constraints/logic stated in the text (limits, permissions, calculations, state transitions). rule_id sequential: "BR-1", "BR-2", etc. source_text: the exact phrase the rule was drawn from.
- acceptance_criteria: concise, testable pass/fail statements a QA engineer would check off.
- ambiguities: only text explicitly marked as undecided (TBD, 'not finalized', 'not specified', etc.). A statement of what does NOT happen is a specification, not an ambiguity. Empty list if none."""


def run_requirement_analyzer(yaml_path="fixtures/requirements.yaml"):
    if not os.path.exists(yaml_path):
        raise FileNotFoundError(
            f"Required file not found: {yaml_path}\n"
            f"  -> Create requirements.yaml with your raw requirement fixtures first."
        )
    with open(yaml_path, "r", encoding="utf-8") as f:
        fixtures = yaml.safe_load(f).get("requirements", [])

    results = []
    for fixture in fixtures:
        raw_requirement = fixture.get("raw_requirement", "")
        if not raw_requirement:
            continue
        response = model.invoke([("system", SYSTEM_PROMPT), ("user", raw_requirement)])
        structured = parse_llm_json(response, context=f"Requirement Analyzer ({fixture.get('id')})")
        results.append({"id": fixture.get("id"), "structured_requirement": structured})
    return results


if __name__ == "__main__":
    results = run_requirement_analyzer()
    save_json_file(runs_path("structured_requirements.json"), results)