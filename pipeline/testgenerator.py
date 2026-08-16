import json, os
from langchain.chat_models import init_chat_model
from dotenv import load_dotenv
from pipeline.utils import parse_llm_json

load_dotenv()
model = init_chat_model("google_genai:gemini-3.5-flash-lite", api_key=os.getenv("GOOGLE_API_KEY"))

SYSTEM_PROMPT = """You are a test case generator for a QA test-case generation pipeline. Given a structured requirement with its business rules and acceptance criteria, generate concrete test cases. Only test what's provided — do not invent rules, fields, or behavior not present in the input.

First decide which test categories apply (functional, negative, boundary, edge_case) — not every requirement needs all four. Then generate cases for each category that applies.

Output valid JSON only — no markdown, no code fences, no preamble — matching exactly this schema:
{
  "test_cases": [
    {
      "test_id": string,
      "title": string,
      "category": "functional" | "negative" | "boundary" | "edge_case",
      "linked_rule_ids": [string],
      "preconditions": [string],
      "steps": [string],
      "test_data": {"field_name": "value"},
      "expected_result": string
    }
  ]
}

Rules:
- linked_rule_ids: only reference rule_id values that exist in the provided business_rules. Never invent one. Empty list if not tied to a specific rule.
- steps: imperative, ordered actions the actor performs.
- preconditions: setup state required before steps run.
- expected_result: one observable outcome, grounded in acceptance_criteria where one applies.
- test_data: concrete values pulled from inputs/business_rules — real numbers, not placeholders.
- If existing_test_case_titles is provided, do not regenerate cases covering the same scenario.
- If gap_context is provided, generate ONLY test cases addressing those specific gaps."""


def generate_test_cases(sr, gap_context=None, existing_titles=None):
    payload = {
        "requirement": {k: v for k, v in sr.items() if k not in ("business_rules", "acceptance_criteria")},
        "business_rules": sr.get("business_rules", []),
        "acceptance_criteria": sr.get("acceptance_criteria", []),
    }
    if gap_context:
        payload["gap_context"] = gap_context
    if existing_titles:
        payload["existing_test_case_titles"] = existing_titles

    response = model.invoke([("system", SYSTEM_PROMPT), ("user", json.dumps(payload))])
    generated = parse_llm_json(response, context="Test Generator")
    return generated.get("test_cases", [])