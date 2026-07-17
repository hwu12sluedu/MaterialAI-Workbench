from __future__ import annotations

import json
from pathlib import Path

from material_ai_workbench.case_intelligence import build_case_grounding_context
from material_ai_workbench.case_library import CaseSummary, find_similar_cases


def _case(
    tmp_path: Path,
    case_id: str,
    *,
    material: str,
    hole_radius: float,
    elements: int,
    tags: list[str],
) -> CaseSummary:
    case_dir = tmp_path / case_id
    case_dir.mkdir()
    return CaseSummary(
        case_id=case_id,
        title=f"{material} plate hole {case_id}",
        description="3D 带孔板拉伸验证",
        tags=tags,
        status="success",
        source_folder=str(tmp_path / "sensitive" / case_id),
        created_at="2026-07-17T10:00:00",
        updated_at="2026-07-17T10:00:00",
        case_dir=str(case_dir),
        file_counts={"model": 1, "result": 2},
        inp_features={
            "summary": {
                "materials": [material],
                "element_types": ["C3D8R"],
                "load_keywords": ["cload"],
                "estimated_node_count": elements * 2,
                "estimated_element_count": elements,
            }
        },
        parameters={
            "material_type": material,
            "youngs_modulus": 210000.0,
            "poisson_ratio": 0.3,
            "yield_strength": 355.0,
        },
        material_type=material,
        geometry={"length": 120.0, "width": 40.0, "hole_radius": hole_radius},
        loading={"load_type": "tension", "applied_strain": 0.01},
        mesh_stats={"node_count": elements * 2, "element_count": elements},
        abaqus_results={"max_mises": 410.0},
        units={
            "system": "mm-N-s-MPa",
            "length": "mm",
            "force": "N",
            "stress": "MPa",
            "time": "s",
            "temperature": "degC",
            "declared": True,
        },
        source_fingerprint="a" * 64,
        quality={
            "score": 95,
            "execution_state": "postprocessed",
            "training_eligible": True,
        },
    )


def test_similarity_result_explains_engineering_components(tmp_path) -> None:
    query = _case(
        tmp_path,
        "query",
        material="hill",
        hole_radius=5.0,
        elements=1000,
        tags=["plate", "hole", "tension"],
    )
    close = _case(
        tmp_path,
        "close",
        material="hill",
        hole_radius=5.2,
        elements=1100,
        tags=["plate", "hole", "tension"],
    )
    far = _case(
        tmp_path,
        "far",
        material="composite_ud",
        hole_radius=20.0,
        elements=10000,
        tags=["rve", "compression"],
    )

    rows = find_similar_cases(query, cases=[query, far, close], top_k=2)

    assert [row["case_id"] for row in rows] == ["close", "far"]
    assert set(rows[0]["component_scores"]) >= {
        "text",
        "material",
        "geometry",
        "loading",
        "mesh",
        "results",
        "units",
    }
    assert rows[0]["matched_features"]
    assert rows[0]["explanations"]
    assert rows[0]["relevance_score"] > rows[1]["relevance_score"]


def test_grounding_context_is_compact_and_does_not_send_local_paths(tmp_path) -> None:
    case = _case(
        tmp_path,
        "hill_plate",
        material="hill",
        hole_radius=5.0,
        elements=1000,
        tags=["plate", "hole", "tension"],
    )

    context = build_case_grounding_context(
        "参考 Hill plate hole 拉伸案例修改孔径", cases=[case]
    )
    serialized = json.dumps(context, ensure_ascii=False)

    assert context["retrieved_case_ids"] == ["hill_plate"]
    assert context["read_only"] is True
    assert context["requires_user_confirmation"] is True
    assert "source_folder" not in serialized
    assert str(tmp_path) not in serialized
