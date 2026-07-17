from __future__ import annotations

import json
from pathlib import Path

from material_ai_workbench.case_based_workflow import prepare_case_based_plan
from material_ai_workbench.case_library import scan_case_folder

SAMPLE_INP = """*Heading
*Node
1, 0., 0., 0.
2, 1., 0., 0.
*Element, type=T3D2
1, 1,2
*Material, name=Steel
*Elastic
210000., 0.3
*Step, name=Load
*Static
*End Step
"""


def test_case_based_plan_copies_inputs_without_results_or_submission(tmp_path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    inp_path = source / "model.inp"
    inp_path.write_text(SAMPLE_INP, encoding="utf-8")
    (source / "job.odb").write_bytes(b"must not be copied")
    cases_root = tmp_path / "cases"
    summary = scan_case_folder(
        source,
        title="reference plate",
        units="mm-N-s-MPa",
        cases_root=cases_root,
    )
    payload = {
        "task_type": "case_based_simulation",
        "case_plan": {
            "objective": "change hole radius",
            "reference_case_ids": [summary.case_id],
            "changes": [
                {"parameter": "hole_radius", "from": 5.0, "to": 6.0, "unit": "mm"}
            ],
            "unit_system": "mm-N-s-MPa",
            "submit_job": True,
        },
        "grounding": {
            "retrieved_case_ids": [summary.case_id],
            "requires_user_confirmation": True,
        },
    }

    result = prepare_case_based_plan(
        payload,
        cases_root=cases_root,
        output_root=tmp_path / "plans",
    )
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))

    assert result.status == "prepared_unmodified"
    assert any(path.suffix == ".inp" for path in result.copied_inputs)
    assert not any(path.suffix == ".odb" for path in result.copied_inputs)
    assert manifest["task"]["case_plan"]["submit_job"] is False
    assert manifest["safety"]["abaqus_submitted"] is False
    assert inp_path.read_text(encoding="utf-8") == SAMPLE_INP
    assert Path(result.review_path).exists()
