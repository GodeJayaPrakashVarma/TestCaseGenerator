import json, os


RUNS_DIR = "runs"

def runs_path(filename):
    """Path to a generated pipeline output file, kept out of the repo root."""
    return os.path.join(RUNS_DIR, filename)


def extract_text(response):
    """
    Normalizes an LLM response into plain text regardless of provider.
    Groq returns response.content as a plain string. Gemini (and some
    others) can return a list of content parts instead. This handles both,
    so swapping providers in any stage doesn't require touching parsing code.
    """
    content = response.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and "text" in item:
                parts.append(item["text"])
        return "".join(parts)
    return str(content)


def parse_llm_json(response, context=""):
    """
    extract_text() + defensive cleanup + json.loads(), with a clear error
    (including the raw text) if parsing fails. Strips accidental markdown
    code fences some models add despite being told not to — another
    any-model robustness point, not just a Groq/Gemini fix.
    """
    raw_text = extract_text(response).strip()

    if raw_text.startswith("```"):
        raw_text = raw_text.strip("`")
        if raw_text.lower().startswith("json"):
            raw_text = raw_text[4:]
        raw_text = raw_text.strip()

    try:
        return json.loads(raw_text)
    except json.JSONDecodeError as e:
        raise ValueError(f"{context} returned bad JSON: {e}\nRaw response: {raw_text}")


def load_json_file(path, required=True, default=None, hint=None):
    """
    Loads a JSON file. If missing and required=True, raises a clear error
    explaining what's missing and how to fix it, instead of a bare
    FileNotFoundError with no context. If required=False, returns default.
    """
    if not os.path.exists(path):
        if required:
            message = f"Required file not found: {path}"
            if hint:
                message += f"\n  -> {hint}"
            raise FileNotFoundError(message)
        return default

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json_file(path, data):
    directory = os.path.dirname(path)
    if directory and not os.path.exists(directory):
        os.makedirs(directory)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)