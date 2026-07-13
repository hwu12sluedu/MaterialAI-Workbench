"""Schema validation and dry-run preview for MaterialAI task plans."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


# -- Schema definitions for each task type --

REQUIRED_TASK_FIELDS: dict[str, dict[str, Any]] = {
    "material_training": {
        "material": ["material_type", "name", "youngs_modulus", "poisson_ratio", "yield_strength"],
        "ml": ["c_value", "gamma", "n_load_cases", "n_sequence", "test_size"],
        "abaqus": [],
    },
    "material_training_with_abaqus_check": {
        "material": ["material_type", "name", "youngs_modulus", "poisson_ratio", "yield_strength"],
        "ml": ["c_value", "gamma", "n_load_cases", "n_sequence", "test_size"],
        "abaqus": ["run_check", "max_load_cases", "timeout_seconds"],
    },
    "composite_plate_hole": {
        "composite": ["name", "fiber_volume_fraction", "fiber_e", "fiber_nu",
                      "matrix_e", "matrix_nu", "interface_efficiency", "hole_radius",
                      "length", "width", "thickness"],
        "abaqus": [],
    },
    "batch_parameter_sweep": {
        "batch": ["name", "material_type", "yield_strengths"],
    },
    "case_library_query": {
        "query": ["filters"],
    },
    "surrogate_training": {
        "surrogate": ["dataset_dir", "target_column", "models"],
    },
    "odb_extraction": {
        "odb": ["odb_path", "fields"],
    },
    "closed_loop_report": {},
}

STEP_LABELS: dict[str, str] = {
    "train_material": "Train ML constitutive model",
    "abaqus_check": "Run Abaqus UMAT unit-element verification",
    "generate_rve": "Generate micro RVE geometry and phase map",
    "run_pbc": "Run PBC homogenization (6 load cases)",
    "solve_plate": "Solve 3D plate-with-hole Abaqus model",
    "odb_extract": "Extract ODB field statistics",
    "create_sweep": "Create parameter sweep plan",
    "run_samples": "Run batch samples",
    "export_dataset": "Export training dataset",
    "train_models": "Train surrogate models (RF/MLP/GBR)",
    "compare": "Compare model performance",
    "search_cases": "Search case library",
    "generate_report": "Generate closed-loop validation report",
}

DEFAULT_STEPS_BY_TASK_TYPE: dict[str, list[str]] = {
    "material_training": ["train_material"],
    "material_training_with_abaqus_check": ["train_material", "abaqus_check"],
    "composite_plate_hole": ["generate_rve", "run_pbc", "solve_plate"],
    "batch_parameter_sweep": ["create_sweep", "run_samples", "export_dataset"],
    "case_library_query": ["search_cases"],
    "surrogate_training": ["train_models", "compare"],
    "odb_extraction": ["odb_extract"],
    "closed_loop_report": ["generate_report"],
}

ABAQUS_ACTIONS = {"abaqus_check", "run_pbc", "solve_plate", "odb_extract"}


@dataclass
class SchemaResult:
    valid: bool
    task_type: str
    missing_sections: list[str] = field(default_factory=list)
    missing_fields: dict[str, list[str]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


@dataclass
class ExecutableStep:
    index: int
    action: str
    label: str
    requires_abaqus: bool = False
    status: str = "pending"
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutablePlan:
    payload: dict[str, Any]
    schema: SchemaResult
    steps: list[ExecutableStep]

    @property
    def can_execute(self) -> bool:
        return self.schema.valid


def validate_task_payload(payload: dict[str, Any]) -> SchemaResult:
    """Validate a task JSON payload against the schema for its task_type."""
    task_type = str(payload.get("task_type", "")).strip()
    schema = REQUIRED_TASK_FIELDS.get(task_type)

    if schema is None:
        return SchemaResult(
            valid=False,
            task_type=task_type or "unknown",
            warnings=[f"Unknown task_type '{task_type}'. Supported: {', '.join(REQUIRED_TASK_FIELDS)}"],
        )

    missing_sections: list[str] = []
    missing_fields: dict[str, list[str]] = {}
    warnings: list[str] = []

    for section, required_fields in schema.items():
        if required_fields and section not in payload:
            missing_sections.append(section)
            missing_fields[section] = list(required_fields)
        elif section in payload:
            section_data = payload[section]
            if not isinstance(section_data, dict):
                warnings.append(f"Section '{section}' should be a JSON object.")
                missing_fields[section] = list(required_fields)
            else:
                mf = [f for f in required_fields if f not in section_data or section_data[f] is None]
                if mf:
                    missing_fields[section] = mf

    if task_type == "material_training_with_abaqus_check":
        abaqus = payload.get("abaqus", {})
        if isinstance(abaqus, dict) and not abaqus.get("run_check", False):
            warnings.append("Abaqus check is configured but run_check is False — Abaqus will NOT be called.")

    if task_type == "composite_plate_hole":
        composite = payload.get("composite", {})
        if isinstance(composite, dict):
            run_abaqus = composite.get("run_abaqus", False)
            submit_job = composite.get("submit_job", False)
            if not run_abaqus:
                warnings.append("run_abaqus=False — model files will be generated but Abaqus will NOT be called.")
            if run_abaqus and not submit_job:
                warnings.append("run_abaqus=True but submit_job=False — Abaqus CAE will build geometry but NOT solve.")

    valid = len(missing_sections) == 0 and all(len(v) == 0 for v in missing_fields.values())
    return SchemaResult(
        valid=valid,
        task_type=task_type,
        missing_sections=missing_sections,
        missing_fields=missing_fields,
        warnings=warnings,
    )


def infer_steps(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Return explicit or inferred execution steps for a task payload."""

    explicit_steps = payload.get("steps")
    if isinstance(explicit_steps, list) and explicit_steps:
        normalized: list[dict[str, Any]] = []
        for item in explicit_steps:
            if isinstance(item, dict):
                action = str(item.get("action", "")).strip()
                if action:
                    normalized.append(dict(item))
            elif str(item).strip():
                normalized.append({"action": str(item).strip()})
        if normalized:
            return normalized

    task_type = str(payload.get("task_type", "material_training")).strip()
    actions = list(DEFAULT_STEPS_BY_TASK_TYPE.get(task_type, ["train_material"]))
    text = str(payload.get("source_text", "")).lower()
    if task_type == "composite_plate_hole":
        if any(word in text for word in ("代理模型", "surrogate", "预测模型", "train surrogate")) or "surrogate" in payload:
            actions.extend(["odb_extract", "export_dataset", "train_models", "compare"])
        if any(word in text for word in ("报告", "report", "闭环")):
            actions.append("generate_report")
    return [{"action": action} for action in actions]


def build_executable_plan(payload: dict[str, Any]) -> ExecutablePlan:
    """Merge defaults, validate schema, and build a UI-friendly execution plan."""

    merged = merge_with_defaults(payload)
    steps: list[ExecutableStep] = []
    for index, step in enumerate(infer_steps(merged), start=1):
        action = str(step.get("action", "unknown"))
        params = step.get("parameters", {})
        steps.append(
            ExecutableStep(
                index=index,
                action=action,
                label=STEP_LABELS.get(action, action),
                requires_abaqus=action in ABAQUS_ACTIONS,
                parameters=params if isinstance(params, dict) else {},
            )
        )
    merged["steps"] = [step.__dict__ for step in steps]
    schema_result = validate_task_payload(merged)
    return ExecutablePlan(payload=merged, schema=schema_result, steps=steps)


def dry_run_summary(payload: dict[str, Any], schema_result: SchemaResult) -> str:
    """Generate a human-readable dry-run summary of what would happen."""
    task_type = schema_result.task_type
    steps = infer_steps(payload)

    lines = [f"## Dry-Run: {task_type}", ""]

    if not schema_result.valid:
        lines.append("### Schema Issues (will use defaults)")
        for section in schema_result.missing_sections:
            fields = ", ".join(schema_result.missing_fields.get(section, []))
            lines.append(f"- Missing section `{section}` (fields: {fields})")
        lines.append("")

    if schema_result.warnings:
        lines.append("### Warnings")
        for w in schema_result.warnings:
            lines.append(f"- {w}")
        lines.append("")

    if steps:
        lines.append("### Execution Plan")
        for i, step in enumerate(steps, 1):
            action = step.get("action", "unknown") if isinstance(step, dict) else str(step)
            label = STEP_LABELS.get(action, action)
            suffix = " (Abaqus)" if action in ABAQUS_ACTIONS else ""
            lines.append(f"{i}. **{label}**{suffix}")
    else:
        lines.append("(No explicit steps array — plan will be inferred from task_type)")

    lines.append("")
    lines.append("### Key Parameters")
    for section in ["material", "composite", "batch", "surrogate"]:
        if section in payload and isinstance(payload[section], dict):
            for k, v in payload[section].items():
                if k not in ("hill_ratios", "barlat_alphas", "barlat_coeffs", "yield_strengths"):
                    lines.append(f"- `{section}.{k}` = {v}")
                elif isinstance(v, list):
                    lines.append(f"- `{section}.{k}` = [{len(v)} values]")

    return "\n".join(lines)


def merge_with_defaults(payload: dict[str, Any]) -> dict[str, Any]:
    """Fill missing fields with sensible defaults so the plan can still execute."""
    import copy
    result = copy.deepcopy(payload)
    task_type = result.get("task_type", "material_training")

    if "material" in REQUIRED_TASK_FIELDS.get(task_type, {}):
        mat = result.setdefault("material", {})
        mat.setdefault("material_type", "j2")
        mat.setdefault("name", "nl_task")
        mat.setdefault("youngs_modulus", 200000)
        mat.setdefault("poisson_ratio", 0.3)
        mat.setdefault("yield_strength", 60)

    if "ml" in REQUIRED_TASK_FIELDS.get(task_type, {}):
        ml = result.setdefault("ml", {})
        ml.setdefault("c_value", 1.0)
        ml.setdefault("gamma", 1.0)
        ml.setdefault("n_load_cases", 40)
        ml.setdefault("n_sequence", 4)
        ml.setdefault("test_size", 80)
        ml.setdefault("calculate_curves", False)

    if "abaqus" in REQUIRED_TASK_FIELDS.get(task_type, {}):
        abq = result.setdefault("abaqus", {})
        abq.setdefault("run_check", False)
        abq.setdefault("max_load_cases", 1)
        abq.setdefault("timeout_seconds", 1200)

    if task_type == "composite_plate_hole":
        comp = result.setdefault("composite", {})
        comp.setdefault("name", "nl_composite")
        comp.setdefault("fiber_volume_fraction", 0.55)
        comp.setdefault("fiber_e", 230000)
        comp.setdefault("fiber_nu", 0.2)
        comp.setdefault("matrix_e", 3500)
        comp.setdefault("matrix_nu", 0.35)
        comp.setdefault("interface_efficiency", 0.92)
        comp.setdefault("hole_radius", 5.0)
        comp.setdefault("length", 120)
        comp.setdefault("width", 40)
        comp.setdefault("thickness", 2)
        comp.setdefault("run_abaqus", False)
        comp.setdefault("submit_job", False)

    result["missing"] = []
    result.setdefault("warnings", [])
    return result
