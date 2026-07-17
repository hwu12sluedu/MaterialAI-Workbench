"""Explainable retrieval and LLM grounding for local simulation cases."""

from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any, Iterable

DEFAULT_SIMILARITY_WEIGHTS: dict[str, float] = {
    "text": 0.15,
    "material": 0.22,
    "geometry": 0.18,
    "loading": 0.16,
    "mesh": 0.12,
    "results": 0.07,
    "units": 0.10,
}

CATEGORY_LABELS = {
    "text": "文本与标签",
    "material": "材料",
    "geometry": "几何",
    "loading": "载荷与边界",
    "mesh": "网格",
    "results": "结果",
    "units": "单位制",
}

_GEOMETRY_TERMS = {
    "plate",
    "hole",
    "rve",
    "coupon",
    "beam",
    "shell",
    "solid",
    "cylinder",
    "带孔板",
    "板",
    "孔",
    "梁",
    "壳",
    "实体",
    "微观",
}


def rank_similar_cases(
    query_case: Any,
    candidates: Iterable[Any],
    *,
    top_k: int = 5,
    weights: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    """Rank cases with transparent material, geometry, load and mesh evidence."""

    normalized_weights = _normalized_weights(weights)
    query_profile = _case_profile(query_case)
    rows: list[dict[str, Any]] = []
    for candidate in candidates:
        profile = _case_profile(candidate)
        components: dict[str, dict[str, Any]] = {}
        matched: list[str] = []
        differing: list[str] = []
        weighted_score = 0.0
        used_weight = 0.0
        for category, weight in normalized_weights.items():
            comparison = _compare_category(
                category, query_profile[category], profile[category]
            )
            if comparison is None:
                continue
            score, evidence_count, category_matches, category_differences = comparison
            components[category] = {
                "label": CATEGORY_LABELS[category],
                "score": round(score, 6),
                "weight": round(weight, 6),
                "evidence_count": evidence_count,
            }
            weighted_score += score * weight
            used_weight += weight
            matched.extend(category_matches)
            differing.extend(category_differences)

        relevance = weighted_score / used_weight if used_weight else 0.0
        quality = dict(getattr(candidate, "quality", {}) or {})
        quality_score = _bounded_float(quality.get("score"), default=50.0) / 100.0
        trust_factor = 0.90 + 0.10 * quality_score
        similarity = max(0.0, min(1.0, relevance * trust_factor))
        explanations = [
            f"{item['label']} {item['score'] * 100:.0f}%"
            for item in sorted(
                components.values(), key=lambda value: value["score"], reverse=True
            )[:4]
        ]
        explanations.append(f"案例质量 {quality_score * 100:.0f}%")
        rows.append(
            {
                "case_id": str(getattr(candidate, "case_id", "")),
                "title": str(getattr(candidate, "title", "")),
                "status": str(getattr(candidate, "status", "")),
                "tags": ", ".join(getattr(candidate, "tags", []) or []),
                "distance": round(1.0 - similarity, 8),
                "similarity": round(similarity, 8),
                "relevance_score": round(relevance, 8),
                "trust_factor": round(trust_factor, 8),
                "component_scores": components,
                "matched_features": _unique(matched)[:8],
                "differing_features": _unique(differing)[:8],
                "explanations": explanations,
                "execution_state": quality.get("execution_state", "unknown"),
                "training_eligible": bool(quality.get("training_eligible", False)),
                "case_dir": str(getattr(candidate, "case_dir", "")),
            }
        )
    return sorted(
        rows,
        key=lambda item: (
            -float(item["similarity"]),
            -float(item["relevance_score"]),
            str(item["case_id"]),
        ),
    )[: max(1, int(top_k))]


def search_cases_by_text(
    query: str,
    *,
    cases: Iterable[Any] | None = None,
    cases_root: Any = None,
    top_k: int = 5,
    training_eligible_only: bool = False,
) -> list[dict[str, Any]]:
    """Retrieve local cases for a free-text engineering request."""

    if cases is None:
        from material_ai_workbench.case_library import CASES_ROOT, list_cases

        cases = list_cases(cases_root or CASES_ROOT)
    query_terms = _tokenize(query)
    if not query_terms:
        return []

    rows: list[dict[str, Any]] = []
    for case in cases:
        quality = dict(getattr(case, "quality", {}) or {})
        if training_eligible_only and not quality.get("training_eligible", False):
            continue
        profile = _case_profile(case)
        candidate_terms = set(profile["text"]["terms"])
        for category in ("material", "geometry", "loading", "mesh", "units"):
            candidate_terms.update(profile[category]["terms"])
        common = sorted(query_terms & candidate_terms)
        coverage = len(common) / max(1, len(query_terms))
        precision = len(common) / max(1, len(candidate_terms))
        lexical_score = 0.85 * coverage + 0.15 * precision
        quality_score = _bounded_float(quality.get("score"), default=50.0) / 100.0
        score = lexical_score * (0.9 + 0.1 * quality_score)
        if score <= 0:
            continue
        rows.append(
            {
                "case_id": str(getattr(case, "case_id", "")),
                "title": str(getattr(case, "title", "")),
                "score": round(score, 8),
                "matched_terms": common[:12],
                "execution_state": quality.get("execution_state", "unknown"),
                "training_eligible": bool(quality.get("training_eligible", False)),
                "case": case,
            }
        )
    return sorted(rows, key=lambda item: (-float(item["score"]), item["case_id"]))[
        : max(1, int(top_k))
    ]


def build_case_grounding_context(
    prompt: str,
    *,
    cases: Iterable[Any] | None = None,
    cases_root: Any = None,
    top_k: int = 3,
) -> dict[str, Any]:
    """Build a compact, path-free context block for an external LLM planner."""

    matches = search_cases_by_text(
        prompt, cases=cases, cases_root=cases_root, top_k=top_k
    )
    case_rows = []
    for match in matches:
        case = match.pop("case")
        profile = _case_profile(case)
        quality = dict(getattr(case, "quality", {}) or {})
        case_rows.append(
            {
                "case_id": str(getattr(case, "case_id", "")),
                "title": str(getattr(case, "title", "")),
                "retrieval_score": match["score"],
                "matched_terms": match["matched_terms"],
                "execution_state": quality.get("execution_state", "unknown"),
                "training_eligible": bool(quality.get("training_eligible", False)),
                "quality_score": quality.get("score", 0),
                "units": dict(getattr(case, "units", {}) or {}),
                "material_type": str(getattr(case, "material_type", "")),
                "material_parameters": profile["material"]["numeric"],
                "geometry": dict(getattr(case, "geometry", {}) or {}),
                "loading": dict(getattr(case, "loading", {}) or {}),
                "mesh": dict(getattr(case, "mesh_stats", {}) or {}),
                "result_labels": _result_labels(case),
                "source_fingerprint": str(
                    getattr(case, "source_fingerprint", "") or ""
                ),
            }
        )
    context_id = hashlib.sha256(
        json.dumps(
            {"prompt": prompt, "case_ids": [row["case_id"] for row in case_rows]},
            sort_keys=True,
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()[:16]
    return {
        "schema_version": "1.0",
        "grounding_id": context_id,
        "retrieval_method": "local_case_keyword_v1",
        "read_only": True,
        "requires_user_confirmation": True,
        "query": prompt,
        "retrieved_case_ids": [row["case_id"] for row in case_rows],
        "cases": case_rows,
    }


def grounding_provenance(context: dict[str, Any]) -> dict[str, Any]:
    """Return the immutable provenance subset attached to an LLM plan."""

    return {
        "schema_version": str(context.get("schema_version", "1.0")),
        "grounding_id": str(context.get("grounding_id", "")),
        "retrieval_method": str(context.get("retrieval_method", "")),
        "retrieved_case_ids": list(context.get("retrieved_case_ids", []) or []),
        "read_only": True,
        "requires_user_confirmation": True,
    }


def _case_profile(case: Any) -> dict[str, dict[str, Any]]:
    params = dict(getattr(case, "parameters", {}) or {})
    geometry = dict(getattr(case, "geometry", {}) or {})
    loading = dict(getattr(case, "loading", {}) or {})
    mesh = dict(getattr(case, "mesh_stats", {}) or {})
    inp = _summary(getattr(case, "inp_features", {}) or {})
    units = dict(getattr(case, "units", {}) or {})
    text = " ".join(
        [
            str(getattr(case, "title", "")),
            str(getattr(case, "description", "")),
            " ".join(getattr(case, "tags", []) or []),
            str(getattr(case, "material_type", "")),
            " ".join(str(item) for item in inp.get("materials", []) or []),
            " ".join(str(item) for item in inp.get("element_types", []) or []),
            " ".join(str(item) for item in inp.get("load_keywords", []) or []),
        ]
    )
    material_type = str(
        getattr(case, "material_type", "") or params.get("material_type", "")
    ).strip()
    material_terms = _clean_terms([material_type, *(inp.get("materials", []) or [])])
    material_numeric = _numeric_values(
        params,
        (
            "youngs_modulus",
            "poisson_ratio",
            "yield_strength",
            "fiber_volume_fraction",
            "fiber_e",
            "fiber_nu",
            "matrix_e",
            "matrix_nu",
            "interface_efficiency",
        ),
    )
    geometry_numeric = _merged_numeric_values(
        geometry,
        params,
        (
            "length",
            "width",
            "thickness",
            "hole_radius",
            "fiber_volume_fraction",
        ),
    )
    loading_numeric = _merged_numeric_values(
        loading,
        params,
        ("applied_strain", "applied_stress", "pressure", "force", "displacement"),
    )
    loading_terms = _clean_terms(
        [loading.get("load_type", ""), *(inp.get("load_keywords", []) or [])]
    )
    mesh_numeric = _merged_numeric_values(
        mesh,
        inp,
        (
            "node_count",
            "element_count",
            "estimated_node_count",
            "estimated_element_count",
        ),
    )
    unit_terms = _clean_terms(
        [
            units.get("system", ""),
            units.get("length", ""),
            units.get("force", ""),
            units.get("stress", ""),
        ]
    )
    text_terms = _tokenize(text)
    return {
        "text": {"numeric": {}, "terms": text_terms},
        "material": {"numeric": material_numeric, "terms": material_terms},
        "geometry": {
            "numeric": geometry_numeric,
            "terms": {term for term in text_terms if term in _GEOMETRY_TERMS},
        },
        "loading": {"numeric": loading_numeric, "terms": loading_terms},
        "mesh": {
            "numeric": mesh_numeric,
            "terms": _clean_terms(inp.get("element_types", []) or []),
        },
        "results": {"numeric": _result_labels(case), "terms": set()},
        "units": {"numeric": {}, "terms": unit_terms},
    }


def _compare_category(
    category: str,
    left: dict[str, Any],
    right: dict[str, Any],
) -> tuple[float, int, list[str], list[str]] | None:
    scores: list[float] = []
    matches: list[str] = []
    differences: list[str] = []
    left_numeric = dict(left.get("numeric", {}) or {})
    right_numeric = dict(right.get("numeric", {}) or {})
    for key in sorted(set(left_numeric) & set(right_numeric)):
        lvalue = float(left_numeric[key])
        rvalue = float(right_numeric[key])
        score = _numeric_similarity(lvalue, rvalue)
        scores.append(score)
        detail = (
            f"{CATEGORY_LABELS[category]}.{key}: "
            f"{_format_number(lvalue)} vs {_format_number(rvalue)}"
        )
        (matches if score >= 0.8 else differences).append(detail)

    left_terms = set(left.get("terms", set()) or set())
    right_terms = set(right.get("terms", set()) or set())
    if left_terms and right_terms:
        common = sorted(left_terms & right_terms)
        union = left_terms | right_terms
        term_score = len(common) / max(1, len(union))
        scores.append(term_score)
        if common:
            matches.append(
                f"{CATEGORY_LABELS[category]}共同项: {', '.join(common[:6])}"
            )
        unique_left = sorted(left_terms - right_terms)
        unique_right = sorted(right_terms - left_terms)
        if unique_left or unique_right:
            differences.append(
                f"{CATEGORY_LABELS[category]}差异: "
                f"查询[{', '.join(unique_left[:4])}] / 候选[{', '.join(unique_right[:4])}]"
            )
    if not scores:
        return None
    return sum(scores) / len(scores), len(scores), matches, differences


def _numeric_similarity(left: float, right: float) -> float:
    if left == right:
        return 1.0
    if left > 0 and right > 0:
        ratio_score = math.exp(-abs(math.log(left / right)))
    else:
        ratio_score = 0.0
    symmetric_score = 1.0 - abs(left - right) / max(abs(left) + abs(right), 1e-12)
    return max(0.0, min(1.0, max(ratio_score, symmetric_score)))


def _normalized_weights(weights: dict[str, float] | None) -> dict[str, float]:
    merged = dict(DEFAULT_SIMILARITY_WEIGHTS)
    if weights:
        for key, value in weights.items():
            if key in merged and isinstance(value, (int, float)) and value >= 0:
                merged[key] = float(value)
    total = sum(merged.values())
    if total <= 0:
        return dict(DEFAULT_SIMILARITY_WEIGHTS)
    return {key: value / total for key, value in merged.items()}


def _tokenize(value: Any) -> set[str]:
    text = str(value or "").strip().lower()
    terms = set(re.findall(r"[a-z0-9][a-z0-9_.+-]*", text))
    for run in re.findall(r"[\u4e00-\u9fff]+", text):
        terms.add(run)
        if len(run) > 1:
            terms.update(run[index : index + 2] for index in range(len(run) - 1))
    return {term for term in terms if term}


def _clean_terms(values: Iterable[Any]) -> set[str]:
    terms: set[str] = set()
    for value in values:
        text = str(value or "").strip().lower()
        if text and text not in {"unknown", "none", "n/a"}:
            terms.add(text)
            terms.update(_tokenize(text))
    return terms


def _numeric_values(payload: dict[str, Any], keys: Iterable[str]) -> dict[str, float]:
    values: dict[str, float] = {}
    for key in keys:
        value = payload.get(key)
        if isinstance(value, (int, float)) and math.isfinite(float(value)):
            values[key] = float(value)
    return values


def _merged_numeric_values(
    primary: dict[str, Any], fallback: dict[str, Any], keys: Iterable[str]
) -> dict[str, float]:
    merged = dict(fallback)
    merged.update(primary)
    return _numeric_values(merged, keys)


def _result_labels(case: Any) -> dict[str, float]:
    sources = [
        dict(getattr(case, "abaqus_results", {}) or {}),
        _summary(getattr(case, "result_features", {}) or {}),
    ]
    extractions = list(getattr(case, "odb_extractions", []) or [])
    if extractions and isinstance(extractions[-1], dict):
        sources.insert(0, dict(extractions[-1].get("aggregate", {}) or {}))
    labels: dict[str, float] = {}
    for key in ("max_mises", "max_peeq", "max_displacement", "max_reaction_force"):
        for source in sources:
            value = source.get(key)
            if isinstance(value, (int, float)) and math.isfinite(float(value)):
                labels[key] = float(value)
                break
    return labels


def _summary(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    nested = payload.get("summary")
    return nested if isinstance(nested, dict) else payload


def _bounded_float(value: Any, *, default: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = default
    return max(0.0, min(100.0, number))


def _format_number(value: float) -> str:
    return f"{value:.6g}"


def _unique(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
