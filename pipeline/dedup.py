from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from pipeline.utils import load_json_file, save_json_file, runs_path

_embedder = SentenceTransformer("all-MiniLM-L6-v2")


def duplicate_detector(test_cases, fixture_id, threshold=0.90):
    if len(test_cases) < 2:
        return test_cases, []

    texts = [
        f"{tc['title']} {' '.join(tc.get('steps', []))} {tc.get('expected_result', '')}"
        for tc in test_cases
    ]
    embeddings = _embedder.encode(texts)
    sim_matrix = cosine_similarity(embeddings)

    to_remove = set()
    duplicates_removed = []
    n = len(test_cases)

    for i in range(n):
        if i in to_remove:
            continue
        for j in range(i + 1, n):
            if j in to_remove:
                continue
            similarity = sim_matrix[i][j]
            if similarity >= threshold:
                to_remove.add(j)
                duplicates_removed.append({
                    "fixture_id": fixture_id,
                    "kept": test_cases[i]["test_id"],
                    "removed": test_cases[j]["test_id"],
                    "similarity": round(float(similarity), 3),
                })

    deduped = [tc for idx, tc in enumerate(test_cases) if idx not in to_remove]
    return deduped, duplicates_removed


def run_duplicate_detector_on_file(test_cases_path=None):
    test_cases_path = test_cases_path or runs_path("test_cases.json")   # fixed default
    data = load_json_file(
        test_cases_path, required=True,
        hint="Run the pipeline (run_pipeline.py or graph.py) first to generate test_cases.json."
    )

    all_dupes_log = []
    for fixture in data:
        deduped, dupes_log = duplicate_detector(fixture["test_cases"], fixture["id"])
        fixture["test_cases"] = deduped
        all_dupes_log.extend(dupes_log)

    save_json_file(test_cases_path, data)   # write back to the SAME path it read from

    existing = load_json_file(runs_path("duplicates_removed.json"), required=False, default=[])
    existing.extend(all_dupes_log)
    save_json_file(runs_path("duplicates_removed.json"), existing)

    return data, all_dupes_log


if __name__ == "__main__":
    run_duplicate_detector_on_file()