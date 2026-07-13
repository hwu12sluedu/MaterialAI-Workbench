"""Rule-based natural-language task parser for MaterialAI Workbench v0."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from material_ai_workbench.pipeline import WorkbenchConfig


DEFAULT_HILL_RATIOS = (1.2, 1.0, 0.8, 1.0, 1.0, 1.0)
DEFAULT_BARLAT_ALPHAS = (1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0)


@dataclass
class MaterialTaskSpec:
    material_type: str = "j2"
    name: str = "nl_material_task"
    youngs_modulus: float = 200_000.0
    poisson_ratio: float = 0.3
    yield_strength: float = 60.0
    hill_ratios: tuple[float, float, float, float, float, float] = DEFAULT_HILL_RATIOS
    barlat_alphas: tuple[float, float, float, float, float, float, float, float] = DEFAULT_BARLAT_ALPHAS
    barlat_exponent: float = 8.0


@dataclass
class MLTaskSpec:
    model: str = "svc"
    c_value: float = 1.0
    gamma: float = 1.0
    n_load_cases: int = 40
    n_sequence: int = 4
    test_size: int = 80
    plot_mesh: int = 50
    calculate_curves: bool = False


@dataclass
class AbaqusTaskSpec:
    run_check: bool = False
    max_load_cases: int = 1
    timeout_seconds: int = 1200


@dataclass
class ParsedSimulationTask:
    task_type: str
    source_text: str
    material: MaterialTaskSpec
    ml: MLTaskSpec
    abaqus: AbaqusTaskSpec
    missing: list[str]
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["material"]["hill_ratios"] = list(self.material.hill_ratios)
        payload["material"]["barlat_alphas"] = list(self.material.barlat_alphas)
        return payload

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)


def parse_natural_language_task(text: str) -> ParsedSimulationTask:
    clean_text = " ".join(text.strip().split())
    lowered = clean_text.lower()
    warnings: list[str] = []
    missing: list[str] = []

    if "barlat" in lowered or "yld2000" in lowered:
        material_type = "barlat"
    elif "hill" in lowered or "各向异性" in clean_text:
        material_type = "hill"
    else:
        material_type = "j2"
    if "j2" not in lowered and "hill" not in lowered and "barlat" not in lowered and "yld2000" not in lowered and "各向异性" not in clean_text:
        warnings.append("未明确材料类型，默认使用 J2。")

    youngs_modulus = _find_float(clean_text, [r"\bE\s*=\s*({num})", r"弹性模量\s*[:=为]?\s*({num})"], 200_000.0)
    poisson_ratio = _find_float(clean_text, [r"\bnu\s*=\s*({num})", r"泊松比\s*[:=为]?\s*({num})"], 0.3)
    yield_strength = _find_float(
        clean_text,
        [r"\bsy\s*=\s*({num})", r"屈服(?:强度)?\s*[:=为]?\s*({num})", r"yield\s*(?:strength)?\s*[:=]?\s*({num})"],
        60.0,
    )
    c_value = _find_float(clean_text, [r"\bC\s*=\s*({num})", r"SVC\s*C\s*[:=]?\s*({num})"], 1.0)
    gamma = _find_float(clean_text, [r"\bgamma\s*=\s*({num})", r"SVC\s*gamma\s*[:=]?\s*({num})"], 1.0)
    n_load_cases = int(_find_float(clean_text, [r"载荷方向(?:数)?\s*[:=为]?\s*({num})", r"load\s*cases\s*[:=]?\s*({num})"], 40))
    n_sequence = int(_find_float(clean_text, [r"采样序列\s*[:=为]?\s*({num})", r"sequence\s*[:=]?\s*({num})"], 4))
    test_size = int(_find_float(clean_text, [r"测试点(?:数)?\s*[:=为]?\s*({num})", r"test\s*size\s*[:=]?\s*({num})"], 80))
    max_load_cases = int(
        _find_float(
            clean_text,
            [
                r"Abaqus.*?(\d+)\s*个?载荷",
                r"Abaqus.*?(\d+)\s*(?:load\s*)?cases?",
                r"(?<![\d.])(\d+)\s*个?\s*Abaqus",
                r"(?<![\d.])(\d+)\s*(?:load\s*)?cases?.*?Abaqus",
            ],
            1,
        )
    )

    has_explicit_hill_ratios = _has_explicit_hill_ratios(clean_text)
    hill_ratios = _find_hill_ratios(clean_text)
    if material_type == "hill" and not has_explicit_hill_ratios:
        warnings.append("未识别到 Hill r1-r6，使用默认各向异性比例。")

    run_abaqus = any(word in lowered for word in ("abaqus", "umat")) or "验算" in clean_text
    calculate_curves = "曲线" in clean_text or "stress-strain" in lowered

    # Detect composite / batch / surrogate / ODB / report keywords
    is_composite = any(w in lowered for w in ("复合材料", "composite", "rve", "板孔", "plate", "带孔板"))
    is_batch = any(w in lowered for w in ("批量", "batch", "sweep", "扫描", "参数扫描"))
    is_surrogate = any(w in lowered for w in ("代理模型", "surrogate", "预测模型", "训练代理"))
    is_odb = any(w in lowered for w in ("odb", "提取", "extract", "后处理"))
    is_report = any(w in lowered for w in ("闭环报告", "closed loop", "验证报告"))

    if is_composite:
        task_type = "composite_plate_hole"
    elif is_batch:
        task_type = "batch_parameter_sweep"
    elif is_surrogate:
        task_type = "surrogate_training"
    elif is_odb:
        task_type = "odb_extraction"
    elif is_report:
        task_type = "closed_loop_report"
    else:
        task_type = "material_training_with_abaqus_check" if run_abaqus else "material_training"

    name = _find_name(clean_text, material_type)

    return ParsedSimulationTask(
        task_type=task_type,
        source_text=text.strip(),
        material=MaterialTaskSpec(
            material_type=material_type,
            name=name,
            youngs_modulus=float(youngs_modulus),
            poisson_ratio=float(poisson_ratio),
            yield_strength=float(yield_strength),
            hill_ratios=hill_ratios,
            barlat_alphas=DEFAULT_BARLAT_ALPHAS,
            barlat_exponent=8.0,
        ),
        ml=MLTaskSpec(
            c_value=float(c_value),
            gamma=float(gamma),
            n_load_cases=max(8, int(n_load_cases)),
            n_sequence=max(2, int(n_sequence)),
            test_size=max(20, int(test_size)),
            calculate_curves=calculate_curves,
        ),
        abaqus=AbaqusTaskSpec(
            run_check=run_abaqus,
            max_load_cases=max(0, int(max_load_cases)),
        ),
        missing=missing,
        warnings=warnings,
    )


def task_from_dict(payload: dict[str, Any], source_text: str = "") -> ParsedSimulationTask:
    """Convert a structured task JSON into the internal task dataclasses."""

    fallback = parse_natural_language_task(source_text)
    material_payload = payload.get("material") if isinstance(payload.get("material"), dict) else {}
    ml_payload = payload.get("ml") if isinstance(payload.get("ml"), dict) else {}
    abaqus_payload = payload.get("abaqus") if isinstance(payload.get("abaqus"), dict) else {}

    material_type = str(material_payload.get("material_type", fallback.material.material_type)).lower()
    if material_type not in {"j2", "hill", "barlat"}:
        material_type = fallback.material.material_type

    hill_values = material_payload.get("hill_ratios", fallback.material.hill_ratios)
    hill_ratios = _coerce_hill_ratios(hill_values, fallback.material.hill_ratios)
    barlat_values = material_payload.get("barlat_alphas", fallback.material.barlat_alphas)
    barlat_alphas = _coerce_barlat_alphas(barlat_values, fallback.material.barlat_alphas)
    warnings = list(payload.get("warnings", [])) if isinstance(payload.get("warnings"), list) else []
    missing = list(payload.get("missing", [])) if isinstance(payload.get("missing"), list) else []

    return ParsedSimulationTask(
        task_type=str(payload.get("task_type", fallback.task_type)),
        source_text=source_text or str(payload.get("source_text", "")),
        material=MaterialTaskSpec(
            material_type=material_type,
            name=str(material_payload.get("name", fallback.material.name)),
            youngs_modulus=_positive_float(material_payload.get("youngs_modulus"), fallback.material.youngs_modulus),
            poisson_ratio=_bounded_float(material_payload.get("poisson_ratio"), fallback.material.poisson_ratio, 0.0, 0.49),
            yield_strength=_positive_float(material_payload.get("yield_strength"), fallback.material.yield_strength),
            hill_ratios=hill_ratios,
            barlat_alphas=barlat_alphas,
            barlat_exponent=_positive_float(material_payload.get("barlat_exponent"), fallback.material.barlat_exponent),
        ),
        ml=MLTaskSpec(
            model=str(ml_payload.get("model", fallback.ml.model)),
            c_value=_positive_float(ml_payload.get("c_value"), fallback.ml.c_value),
            gamma=_positive_float(ml_payload.get("gamma"), fallback.ml.gamma),
            n_load_cases=max(8, int(_positive_float(ml_payload.get("n_load_cases"), fallback.ml.n_load_cases))),
            n_sequence=max(2, int(_positive_float(ml_payload.get("n_sequence"), fallback.ml.n_sequence))),
            test_size=max(20, int(_positive_float(ml_payload.get("test_size"), fallback.ml.test_size))),
            plot_mesh=max(20, int(_positive_float(ml_payload.get("plot_mesh"), fallback.ml.plot_mesh))),
            calculate_curves=bool(ml_payload.get("calculate_curves", fallback.ml.calculate_curves)),
        ),
        abaqus=AbaqusTaskSpec(
            run_check=bool(abaqus_payload.get("run_check", fallback.abaqus.run_check)),
            max_load_cases=max(0, int(_positive_float(abaqus_payload.get("max_load_cases"), fallback.abaqus.max_load_cases))),
            timeout_seconds=max(60, int(_positive_float(abaqus_payload.get("timeout_seconds"), fallback.abaqus.timeout_seconds))),
        ),
        missing=missing,
        warnings=warnings,
    )


def task_to_workbench_config(task: ParsedSimulationTask, output_dir: Path) -> WorkbenchConfig:
    return WorkbenchConfig(
        material_type=task.material.material_type,
        name=task.material.name,
        output_dir=output_dir,
        youngs_modulus=task.material.youngs_modulus,
        poisson_ratio=task.material.poisson_ratio,
        yield_strength=task.material.yield_strength,
        hill_ratios=task.material.hill_ratios,
        barlat_alphas=task.material.barlat_alphas,
        barlat_exponent=task.material.barlat_exponent,
        c_value=task.ml.c_value,
        gamma=task.ml.gamma,
        n_load_cases=task.ml.n_load_cases,
        n_sequence=task.ml.n_sequence,
        calculate_curves=task.ml.calculate_curves,
        test_size=task.ml.test_size,
        plot_mesh=task.ml.plot_mesh,
    )


def _find_float(text: str, patterns: list[str], default: float) -> float:
    number = r"[-+]?\d+(?:\.\d+)?"
    for pattern in patterns:
        resolved = pattern.format(num=number)
        match = re.search(resolved, text, flags=re.IGNORECASE)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                continue
    return default


def _find_hill_ratios(text: str) -> tuple[float, float, float, float, float, float]:
    values: list[float] = []
    for idx in range(1, 7):
        match = re.search(rf"r{idx}\s*=\s*([-+]?\d+(?:\.\d+)?)", text, flags=re.IGNORECASE)
        if match:
            values.append(float(match.group(1)))
    if len(values) == 6 and all(value > 0 for value in values):
        return tuple(values)  # type: ignore[return-value]

    match = re.search(r"Hill.*?\[([^\]]+)\]", text, flags=re.IGNORECASE)
    if match:
        parsed = [float(item) for item in re.findall(r"[-+]?\d+(?:\.\d+)?", match.group(1))]
        if len(parsed) >= 6 and all(value > 0 for value in parsed[:6]):
            return tuple(parsed[:6])  # type: ignore[return-value]

    return DEFAULT_HILL_RATIOS


def _has_explicit_hill_ratios(text: str) -> bool:
    individual = all(
        re.search(rf"r{idx}\s*=\s*[-+]?\d+(?:\.\d+)?", text, flags=re.IGNORECASE)
        for idx in range(1, 7)
    )
    bracketed = re.search(r"Hill.*?\[([^\]]+)\]", text, flags=re.IGNORECASE)
    return bool(individual or bracketed)


def _find_name(text: str, material_type: str) -> str:
    match = re.search(r"(?:名称|模型名|name)\s*[:=为]\s*([A-Za-z0-9_\-]+)", text, flags=re.IGNORECASE)
    if match:
        return match.group(1)
    return f"nl_{material_type}_task"


def _coerce_hill_ratios(value: Any, default: tuple[float, float, float, float, float, float]) -> tuple[float, float, float, float, float, float]:
    if isinstance(value, (list, tuple)) and len(value) >= 6:
        try:
            parsed = tuple(float(item) for item in value[:6])
        except (TypeError, ValueError):
            return default
        if all(item > 0 for item in parsed):
            return parsed  # type: ignore[return-value]
    return default


def _coerce_barlat_alphas(
    value: Any,
    default: tuple[float, float, float, float, float, float, float, float],
) -> tuple[float, float, float, float, float, float, float, float]:
    if isinstance(value, (list, tuple)) and len(value) >= 8:
        try:
            parsed = tuple(float(item) for item in value[:8])
        except (TypeError, ValueError):
            return default
        if all(item > 0 for item in parsed):
            return parsed  # type: ignore[return-value]
    return default


def _positive_float(value: Any, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return float(default)
    return parsed if parsed > 0 else float(default)


def _bounded_float(value: Any, default: float, lower: float, upper: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return float(default)
    return parsed if lower <= parsed <= upper else float(default)
