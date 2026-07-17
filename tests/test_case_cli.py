from __future__ import annotations

import json

from material_ai_workbench.case_cli import main

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
*Cload
2, 1, 1.
*End Step
"""


def test_case_cli_import_and_inspect_emit_json(tmp_path, capsys) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "model.inp").write_text(SAMPLE_INP, encoding="utf-8")
    cases_root = tmp_path / "cases"

    result = main(
        [
            "import",
            str(source),
            "--title",
            "CLI case",
            "--units",
            "mm-N-s-MPa",
            "--cases-root",
            str(cases_root),
        ]
    )
    imported = json.loads(capsys.readouterr().out)
    case_id = imported["case_package"]["case_id"]

    inspect_result = main(["inspect", case_id, "--cases-root", str(cases_root)])
    inspected = json.loads(capsys.readouterr().out)

    assert result == 0
    assert inspect_result == 0
    assert imported["ok"] is True
    assert inspected["case_package"]["schema_version"] == "2.0"
    assert inspected["case_package"]["quality"]["execution_state"] == "prepared"
