from material_ai_workbench.run_metal_closed_loop import _parse_strengths


def test_parse_strengths_accepts_commas_and_semicolons():
    assert _parse_strengths("50, 60;70") == [50.0, 60.0, 70.0]
