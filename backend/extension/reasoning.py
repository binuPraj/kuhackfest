import json
import os
from typing import Dict, List, Optional


BASE_DIR = os.path.dirname(__file__)
# Data lives at <project_root>/public/data; extension module is at backend/extension
DATA_DIR = os.path.normpath(os.path.join(BASE_DIR, "..", "..", "public", "data"))
FALLACY_PATH = os.path.join(DATA_DIR, "logicalfallacy.json")
TOULMIN_PATH = os.path.join(DATA_DIR, "Toulmin.json")

_fallacy_model: Optional[Dict] = None
_toulmin_model: Optional[Dict] = None


def _load_json(path: str) -> Optional[Dict]:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        print(f"❌ Missing data file: {path}")
    except json.JSONDecodeError as exc:
        print(f"❌ Invalid JSON in {path}: {exc}")
    return None


def initialize_models() -> bool:
    global _fallacy_model, _toulmin_model
    _fallacy_model = _load_json(FALLACY_PATH)
    _toulmin_model = _load_json(TOULMIN_PATH)

    if _fallacy_model:
        print(f"✅ Loaded {len(_fallacy_model.get('fallacies', []))} fallacy definitions")
    if _toulmin_model:
        print(f"✅ Loaded {len(_toulmin_model.get('toulmin_factors', []))} Toulmin factors")

    return bool(_fallacy_model) and bool(_toulmin_model)


def get_fallacy_definitions() -> List[Dict]:
    if not _fallacy_model:
        return []
    return _fallacy_model.get("fallacies", [])


def get_fallacy_by_id(fallacy_id: str) -> Optional[Dict]:
    return next((f for f in get_fallacy_definitions() if f.get("id") == fallacy_id), None)


def get_fallacy_list_for_prompt() -> str:
    lines: List[str] = []
    for fallacy in get_fallacy_definitions():
        examples = fallacy.get("examples", [])
        example_lines = [f'    - "{example.get("scenario", "").strip()}"' for example in examples]
        lines.append(
            f"- **{fallacy.get('name', '')}** ({fallacy.get('alias', '')}): {fallacy.get('description', '')}\n"
            f"  Examples:\n" + "\n".join(example_lines)
        )
    return "\n\n".join(lines)


def get_compact_fallacy_list() -> str:
    return "\n".join(
        [f"• {fallacy.get('name', '')} ({fallacy.get('alias', '')}): {fallacy.get('description', '')}" for fallacy in get_fallacy_definitions()]
    )


def validate_detected_fallacy(detected_name: str) -> Optional[Dict]:
    if not detected_name:
        return None

    normalized = detected_name.lower().strip()
    for fallacy in get_fallacy_definitions():
        if normalized in {
            fallacy.get("id", "").lower(),
            fallacy.get("name", "").lower(),
            fallacy.get("alias", "").lower(),
        }:
            return fallacy

    for fallacy in get_fallacy_definitions():
        name = fallacy.get("name", "").lower()
        alias = fallacy.get("alias", "").lower()
        if normalized in name or name in normalized or normalized in alias or alias in normalized:
            return fallacy

    return None


def enrich_fallacy_data(detected: Dict) -> Dict:
    match = validate_detected_fallacy(detected.get("type") or detected.get("name"))
    if not match:
        return {**detected, "isVerified": False, "modelMatch": None}

    return {
        **detected,
        "isVerified": True,
        "modelMatch": {
            "id": match.get("id"),
            "name": match.get("name"),
            "alias": match.get("alias"),
            "definition": match.get("description"),
            "examples": match.get("examples", []),
        },
    }


def get_toulmin_factors() -> List[Dict]:
    if not _toulmin_model:
        return []
    return _toulmin_model.get("toulmin_factors", [])


def get_compact_toulmin_list() -> str:
    return "\n".join([f"• {factor.get('factor')}: {factor.get('definition')}" for factor in get_toulmin_factors()])


def create_empty_toulmin_analysis() -> Dict:
    return {
        "claim": {"present": False, "score": 0, "feedback": ""},
        "data": {"present": False, "score": 0, "feedback": ""},
        "warrant": {"present": False, "score": 0, "feedback": ""},
        "backing": {"present": False, "score": 0, "feedback": ""},
        "qualifier": {"present": False, "score": 0, "feedback": ""},
        "rebuttal": {"present": False, "score": 0, "feedback": ""},
        "overallScore": 0,
        "strengths": [],
        "weaknesses": [],
    }


def _ensure_factor_entry(analysis: Dict, factor_key: str) -> Dict:
    if factor_key not in analysis or not isinstance(analysis.get(factor_key), dict):
        analysis[factor_key] = {"present": False, "score": 0, "feedback": ""}
    return analysis[factor_key]


def calculate_argument_score(analysis: Dict) -> float:
    weights = {"claim": 0.25, "data": 0.20, "warrant": 0.20, "backing": 0.15, "qualifier": 0.10, "rebuttal": 0.10}
    total = 0.0
    for factor, weight in weights.items():
        score = analysis.get(factor, {}).get("score") or 0
        total += score * weight
    return round(total, 1)


def enrich_toulmin_analysis(analysis: Dict) -> Dict:
    if not analysis:
        return analysis

    enriched = dict(analysis)
    for factor in get_toulmin_factors():
        key = factor.get("factor", "").lower()
        entry = _ensure_factor_entry(enriched, key)
        entry["modelInsights"] = {
            "definition": factor.get("definition"),
            "need": factor.get("need"),
            "fallacyRisk": factor.get("fallacy_exploitation"),
            "strongQualifier": factor.get("strong_qualifier"),
            "weakExample": factor.get("example", {}).get("weak"),
            "strongExample": factor.get("example", {}).get("strong"),
            "metrics": factor.get("measurable_metrics", {}),
        }
    enriched["overallScore"] = calculate_argument_score(enriched)
    return enriched


def generate_analysis_context() -> Dict:
    fallacy_defs = get_fallacy_definitions()
    factors = get_toulmin_factors()
    return {
        "fallacyList": get_compact_fallacy_list(),
        "toulminFactors": get_compact_toulmin_list(),
        "fallacyCount": len(fallacy_defs),
        "factorCount": len(factors),
    }


def enrich_analysis_result(ai_result: Dict) -> Dict:
    enriched = dict(ai_result or {})

    fallacies = enriched.get("fallacies") if isinstance(enriched.get("fallacies"), list) else []
    enriched["fallacies"] = [enrich_fallacy_data(f) for f in fallacies]
    enriched["verifiedFallacies"] = [f for f in enriched["fallacies"] if f.get("isVerified")]
    enriched["unverifiedFallacies"] = [f for f in enriched["fallacies"] if not f.get("isVerified")]

    toulmin_analysis = enriched.get("toulminAnalysis")
    if toulmin_analysis:
        enriched["toulminAnalysis"] = enrich_toulmin_analysis(toulmin_analysis)

    return enriched


def get_references() -> List[Dict]:
    if not _toulmin_model:
        return []
    return _toulmin_model.get("references", [])


# Initialize on import so the models are ready for requests
initialize_models()
