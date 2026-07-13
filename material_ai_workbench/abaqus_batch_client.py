"""Batch Abaqus Python helpers for ODB post-processing."""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from material_ai_workbench.config import ABAQUS_SMAPYTHON as DEFAULT_SMAPYTHON


class AbaqusBatchError(RuntimeError):
    """Raised when an Abaqus batch post-processing command fails."""


@dataclass
class AbaqusBatchConfig:
    abaqus_python: Path | str = DEFAULT_SMAPYTHON
    timeout_seconds: float = 300.0


def extract_odb_field_summary_batch(
    odb_path: Path | str,
    *,
    fields: list[str] | tuple[str, ...] | None = None,
    max_values_per_field: int = 500_000,
    max_history_outputs: int = 200,
    output_dir: Path | str | None = None,
    config: AbaqusBatchConfig | None = None,
) -> dict[str, Any]:
    """Extract final-frame ODB field statistics with Abaqus SMAPython."""

    cfg = config or AbaqusBatchConfig()
    abaqus_python = Path(cfg.abaqus_python).expanduser().resolve()
    odb = Path(odb_path).expanduser().resolve()
    if not odb.exists():
        raise FileNotFoundError(f"ODB file does not exist: {odb}")
    if not abaqus_python.exists():
        raise FileNotFoundError(f"SMAPython.exe does not exist: {abaqus_python}")

    work_dir = Path(output_dir or odb.parent / "odb_batch_extract").expanduser().resolve()
    work_dir.mkdir(parents=True, exist_ok=True)
    script_path = work_dir / "extract_odb_fields.py"
    result_path = work_dir / "extract_odb_fields_result.json"
    script_path.write_text(
        _batch_extract_script(
            odb,
            result_path,
            [str(item).strip().upper() for item in (fields or ("S", "PEEQ", "U", "RF", "CPRESS", "COPEN")) if str(item).strip()],
            max(1, int(max_values_per_field)),
            max(0, int(max_history_outputs)),
        ),
        encoding="utf-8",
    )

    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    completed = subprocess.run(
        [str(abaqus_python), str(script_path)],
        cwd=str(work_dir),
        env=env,
        capture_output=True,
        text=True,
        timeout=float(cfg.timeout_seconds),
    )
    if not result_path.exists():
        raise AbaqusBatchError(
            "Abaqus batch ODB extraction did not produce a result file.\n"
            f"stdout:\n{completed.stdout}\n\nstderr:\n{completed.stderr}"
        )

    payload = json.loads(result_path.read_text(encoding="utf-8"))
    if completed.returncode != 0 or not payload.get("ok", False):
        error = payload.get("error") or f"return code {completed.returncode}"
        traceback_text = payload.get("traceback") or completed.stderr
        raise AbaqusBatchError(f"{error}\n{traceback_text}".strip())
    result = payload.get("result")
    if not isinstance(result, dict):
        raise AbaqusBatchError("Abaqus batch ODB extraction returned an invalid payload.")
    result.setdefault("batch_stdout", completed.stdout[-4000:])
    result.setdefault("batch_stderr", completed.stderr[-4000:])
    return result


def extract_odb_frame_series_batch(
    odb_path: Path | str,
    *,
    fields: list[str] | tuple[str, ...] | None = None,
    region_names: list[str] | tuple[str, ...] | None = None,
    max_values_per_field: int = 200_000,
    max_frames_per_step: int = 500,
    output_dir: Path | str | None = None,
    config: AbaqusBatchConfig | None = None,
) -> dict[str, Any]:
    """Extract per-frame aggregate curves from an ODB with Abaqus SMAPython."""

    cfg = config or AbaqusBatchConfig()
    abaqus_python = Path(cfg.abaqus_python).expanduser().resolve()
    odb = Path(odb_path).expanduser().resolve()
    if not odb.exists():
        raise FileNotFoundError(f"ODB file does not exist: {odb}")
    if not abaqus_python.exists():
        raise FileNotFoundError(f"SMAPython.exe does not exist: {abaqus_python}")

    work_dir = Path(output_dir or odb.parent / "odb_frame_series").expanduser().resolve()
    work_dir.mkdir(parents=True, exist_ok=True)
    script_path = work_dir / "extract_odb_frame_series.py"
    result_path = work_dir / "extract_odb_frame_series_result.json"
    script_path.write_text(
        _batch_frame_series_script(
            odb,
            result_path,
            [str(item).strip().upper() for item in (fields or ("S", "PEEQ", "U", "RF")) if str(item).strip()],
            [str(item).strip() for item in (region_names or ()) if str(item).strip()],
            max(1, int(max_values_per_field)),
            max(1, int(max_frames_per_step)),
        ),
        encoding="utf-8",
    )

    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    completed = subprocess.run(
        [str(abaqus_python), str(script_path)],
        cwd=str(work_dir),
        env=env,
        capture_output=True,
        text=True,
        timeout=float(cfg.timeout_seconds),
    )
    if not result_path.exists():
        raise AbaqusBatchError(
            "Abaqus batch ODB frame-series extraction did not produce a result file.\n"
            f"stdout:\n{completed.stdout}\n\nstderr:\n{completed.stderr}"
        )

    payload = json.loads(result_path.read_text(encoding="utf-8"))
    if completed.returncode != 0 or not payload.get("ok", False):
        error = payload.get("error") or f"return code {completed.returncode}"
        traceback_text = payload.get("traceback") or completed.stderr
        raise AbaqusBatchError(f"{error}\n{traceback_text}".strip())
    result = payload.get("result")
    if not isinstance(result, dict):
        raise AbaqusBatchError("Abaqus batch ODB frame-series extraction returned an invalid payload.")
    result.setdefault("batch_stdout", completed.stdout[-4000:])
    result.setdefault("batch_stderr", completed.stderr[-4000:])
    return result


def _batch_extract_script(
    odb_path: Path,
    result_path: Path,
    fields: list[str],
    max_values_per_field: int,
    max_history_outputs: int,
) -> str:
    return r'''
# -*- coding: utf-8 -*-
import json
import math
import traceback

from odbAccess import openOdb
try:
    from abaqusConstants import MISES, MAGNITUDE
except Exception:
    MISES = None
    MAGNITUDE = None

odb_path = __ODB_PATH__
result_path = __RESULT_PATH__
requested_fields = __FIELDS__
max_values_per_field = __MAX_VALUES__
max_history_outputs = __MAX_HISTORY__


def to_float(value):
    try:
        return float(value)
    except Exception:
        return None


def raw_magnitude(data):
    if isinstance(data, (list, tuple)):
        total = 0.0
        found = False
        for item in data:
            number = to_float(item)
            if number is not None:
                total += number * number
                found = True
        return math.sqrt(total) if found else None
    return to_float(data)


def json_data(value):
    if isinstance(value, (list, tuple)):
        return [to_float(item) for item in value]
    return to_float(value)


def keys(obj):
    try:
        return [str(item) for item in obj.keys()]
    except Exception:
        return []


def value_location(value):
    loc = {}
    try:
        loc["position"] = str(getattr(value, "position", ""))
    except Exception:
        pass
    try:
        instance = getattr(value, "instance", None)
        if instance is not None:
            loc["instance"] = str(getattr(instance, "name", ""))
    except Exception:
        pass
    for attr, key in (("nodeLabel", "node_label"), ("elementLabel", "element_label"), ("integrationPoint", "integration_point"), ("sectionPoint", "section_point")):
        try:
            item = getattr(value, attr, None)
            if item is not None:
                loc[key] = str(item)
        except Exception:
            pass
    return loc


def scalar_field_for(field_name, field):
    if field_name == "S" and MISES is not None:
        try:
            return field.getScalarField(invariant=MISES), "MISES"
        except Exception:
            pass
    if field_name in ("U", "RF", "V", "A") and MAGNITUDE is not None:
        try:
            return field.getScalarField(invariant=MAGNITUDE), "MAGNITUDE"
        except Exception:
            pass
    return field, "RAW_OR_MAGNITUDE"


def summarize_field(field_name, field):
    scalar_field, metric = scalar_field_for(field_name, field)
    values = getattr(scalar_field, "values", [])
    total_count = len(values)
    scanned_count = 0
    min_value = None
    max_value = None
    sum_value = 0.0
    max_abs = None
    min_location = {}
    max_location = {}
    max_abs_location = {}
    try:
        component_labels = [str(item) for item in (getattr(field, "componentLabels", []) or [])]
    except Exception:
        component_labels = []
    try:
        valid_invariants = [str(item) for item in (getattr(field, "validInvariants", []) or [])]
    except Exception:
        valid_invariants = []

    for idx, value in enumerate(values):
        if idx >= max_values_per_field:
            break
        data = json_data(getattr(value, "data", None))
        number = data if isinstance(data, float) else raw_magnitude(data)
        if number is None:
            continue
        scanned_count += 1
        sum_value += number
        abs_value = abs(number)
        if min_value is None or number < min_value:
            min_value = number
            min_location = value_location(value)
        if max_value is None or number > max_value:
            max_value = number
            max_location = value_location(value)
        if max_abs is None or abs_value > max_abs:
            max_abs = abs_value
            max_abs_location = value_location(value)

    return {
        "field": field_name,
        "metric": metric,
        "component_labels": component_labels,
        "valid_invariants": valid_invariants,
        "total_count": total_count,
        "scanned_count": scanned_count,
        "truncated": total_count > max_values_per_field,
        "min": min_value,
        "max": max_value,
        "mean": (sum_value / scanned_count) if scanned_count else None,
        "max_abs": max_abs,
        "min_location": min_location,
        "max_location": max_location,
        "max_abs_location": max_abs_location,
    }


def summarize_history(step):
    rows = []
    truncated = False
    for region_name in step.historyRegions.keys():
        region = step.historyRegions[region_name]
        for output_name in region.historyOutputs.keys():
            if len(rows) >= max_history_outputs:
                truncated = True
                return rows, truncated
            output = region.historyOutputs[output_name]
            values = []
            for _, y_value in (getattr(output, "data", []) or []):
                number = to_float(y_value)
                if number is not None:
                    values.append(number)
            if not values:
                continue
            rows.append({
                "region": str(region_name),
                "output": str(output_name),
                "count": len(values),
                "first": values[0],
                "last": values[-1],
                "min": min(values),
                "max": max(values),
                "max_abs": max(abs(item) for item in values),
            })
    return rows, truncated


odb = None
payload = {"ok": False}
try:
    odb = openOdb(path=odb_path, readOnly=True)
    steps = []
    global_field_stats = []
    history_outputs = []
    history_truncated = False
    for step_name in odb.steps.keys():
        step = odb.steps[step_name]
        frame_count = len(step.frames)
        frame_summary = None
        field_stats = []
        missing_fields = []
        if frame_count:
            frame_index = frame_count - 1
            frame = step.frames[frame_index]
            frame_summary = {
                "index": frame_index,
                "frameId": getattr(frame, "frameId", None),
                "frameValue": getattr(frame, "frameValue", None),
                "description": str(getattr(frame, "description", "")),
                "available_fields": keys(frame.fieldOutputs),
            }
            for field_name in requested_fields:
                if field_name not in frame.fieldOutputs:
                    missing_fields.append(field_name)
                    continue
                stat = summarize_field(field_name, frame.fieldOutputs[field_name])
                stat["step"] = str(step_name)
                stat["frame_index"] = frame_index
                field_stats.append(stat)
                global_field_stats.append(stat)

        history_rows, truncated = summarize_history(step)
        history_outputs.extend(history_rows)
        history_truncated = history_truncated or truncated
        steps.append({
            "name": str(step_name),
            "procedure": str(getattr(step, "procedure", "")),
            "totalTime": getattr(step, "totalTime", 0.0),
            "frame_count": frame_count,
            "final_frame": frame_summary,
            "field_stats": field_stats,
            "missing_fields": missing_fields,
            "history_region_count": len(step.historyRegions.keys()),
        })

    instances = []
    try:
        for instance_name in odb.rootAssembly.instances.keys():
            inst = odb.rootAssembly.instances[instance_name]
            instances.append({
                "name": str(instance_name),
                "nodes": len(getattr(inst, "nodes", [])),
                "elements": len(getattr(inst, "elements", [])),
                "node_sets": keys(getattr(inst, "nodeSets", {})),
                "element_sets": keys(getattr(inst, "elementSets", {})),
            })
    except Exception:
        pass

    payload = {
        "ok": True,
        "result": {
            "path": odb_path,
            "title": str(getattr(odb, "title", "")),
            "description": str(getattr(odb, "description", "")),
            "instances": instances,
            "node_sets": keys(getattr(odb.rootAssembly, "nodeSets", {})) if hasattr(odb, "rootAssembly") else [],
            "element_sets": keys(getattr(odb.rootAssembly, "elementSets", {})) if hasattr(odb, "rootAssembly") else [],
            "steps": steps,
            "field_stats": global_field_stats,
            "history_outputs": history_outputs,
            "history_truncated": history_truncated,
            "fields_requested": requested_fields,
            "frame_mode": "last_frame_per_step",
            "limits": {
                "max_values_per_field": max_values_per_field,
                "max_history_outputs": max_history_outputs,
            },
        },
    }
except Exception as exc:
    payload = {"ok": False, "error": str(exc), "traceback": traceback.format_exc()}
finally:
    if odb is not None:
        try:
            odb.close()
        except Exception as close_exc:
            try:
                payload.setdefault("warnings", []).append("ODB close failed: " + str(close_exc))
            except Exception:
                pass
    with open(result_path, "w") as handle:
        json.dump(payload, handle, ensure_ascii=True)
'''.replace("__ODB_PATH__", json.dumps(str(odb_path))).replace("__RESULT_PATH__", json.dumps(str(result_path))).replace("__FIELDS__", json.dumps(fields)).replace("__MAX_VALUES__", str(max_values_per_field)).replace("__MAX_HISTORY__", str(max_history_outputs))


def _batch_frame_series_script(
    odb_path: Path,
    result_path: Path,
    fields: list[str],
    region_names: list[str],
    max_values_per_field: int,
    max_frames_per_step: int,
) -> str:
    return r'''
# -*- coding: utf-8 -*-
import json
import math
import traceback

from odbAccess import openOdb
try:
    from abaqusConstants import MISES, MAGNITUDE
except Exception:
    MISES = None
    MAGNITUDE = None

odb_path = __ODB_PATH__
result_path = __RESULT_PATH__
requested_fields = __FIELDS__
requested_regions = __REGIONS__
max_values_per_field = __MAX_VALUES__
max_frames_per_step = __MAX_FRAMES__


def to_float(value):
    try:
        return float(value)
    except Exception:
        return None


def raw_magnitude(data):
    if isinstance(data, (list, tuple)):
        total = 0.0
        found = False
        for item in data:
            number = to_float(item)
            if number is not None:
                total += number * number
                found = True
        return math.sqrt(total) if found else None
    return to_float(data)


def json_data(value):
    if isinstance(value, (list, tuple)):
        return [to_float(item) for item in value]
    return to_float(value)


def keys(obj):
    try:
        return [str(item) for item in obj.keys()]
    except Exception:
        return []


def value_location(value):
    loc = {}
    try:
        loc["position"] = str(getattr(value, "position", ""))
    except Exception:
        pass
    try:
        instance = getattr(value, "instance", None)
        if instance is not None:
            loc["instance"] = str(getattr(instance, "name", ""))
    except Exception:
        pass
    for attr, key in (("nodeLabel", "node_label"), ("elementLabel", "element_label"), ("integrationPoint", "integration_point"), ("sectionPoint", "section_point")):
        try:
            item = getattr(value, attr, None)
            if item is not None:
                loc[key] = str(item)
        except Exception:
            pass
    return loc


def scalar_field_for(field_name, field):
    if field_name == "S" and MISES is not None:
        try:
            return field.getScalarField(invariant=MISES), "MISES"
        except Exception:
            pass
    if field_name in ("U", "RF", "V", "A") and MAGNITUDE is not None:
        try:
            return field.getScalarField(invariant=MAGNITUDE), "MAGNITUDE"
        except Exception:
            pass
    return field, "RAW_OR_MAGNITUDE"


def find_regions(odb, names):
    regions = []
    seen = set()
    if not names:
        return regions

    def add_region(name, kind, scope, region):
        key = (name.upper(), kind, scope)
        if key not in seen:
            seen.add(key)
            regions.append({"name": name, "kind": kind, "scope": scope, "region": region})

    def lookup(container, requested_upper):
        try:
            for key in container.keys():
                if str(key).upper() == requested_upper:
                    return str(key), container[key]
        except Exception:
            pass
        return None, None

    assembly = getattr(odb, "rootAssembly", None)
    if assembly is None:
        return regions
    for name in names:
        upper = name.upper()
        for container_name, kind in (("nodeSets", "node_set"), ("elementSets", "element_set")):
            container = getattr(assembly, container_name, {})
            matched_name, region = lookup(container, upper)
            if region is not None:
                add_region(matched_name, kind, "assembly", region)
        try:
            instances = assembly.instances
        except Exception:
            instances = {}
        for instance_name in instances.keys():
            instance = instances[instance_name]
            for container_name, kind in (("nodeSets", "node_set"), ("elementSets", "element_set")):
                container = getattr(instance, container_name, {})
                matched_name, region = lookup(container, upper)
                if region is not None:
                    add_region(matched_name, kind, "instance:" + str(instance_name), region)
    return regions


def summarize_field(field_name, field, region_info=None):
    region_name = "GLOBAL"
    region_kind = "global"
    region_scope = "odb"
    if region_info is not None:
        region_name = region_info.get("name", "")
        region_kind = region_info.get("kind", "")
        region_scope = region_info.get("scope", "")
        try:
            field = field.getSubset(region=region_info["region"])
        except Exception as exc:
            return {
                "field": field_name,
                "metric": "REGION_SUBSET_FAILED",
                "region_name": region_name,
                "region_kind": region_kind,
                "region_scope": region_scope,
                "total_count": 0,
                "scanned_count": 0,
                "truncated": False,
                "min": None,
                "max": None,
                "mean": None,
                "max_abs": None,
                "max_abs_location": {},
                "region_error": str(exc),
            }

    scalar_field, metric = scalar_field_for(field_name, field)
    values = getattr(scalar_field, "values", [])
    total_count = len(values)
    scanned_count = 0
    min_value = None
    max_value = None
    sum_value = 0.0
    max_abs = None
    max_abs_location = {}
    for idx, value in enumerate(values):
        if idx >= max_values_per_field:
            break
        data = json_data(getattr(value, "data", None))
        number = data if isinstance(data, float) else raw_magnitude(data)
        if number is None:
            continue
        scanned_count += 1
        sum_value += number
        abs_value = abs(number)
        if min_value is None or number < min_value:
            min_value = number
        if max_value is None or number > max_value:
            max_value = number
        if max_abs is None or abs_value > max_abs:
            max_abs = abs_value
            max_abs_location = value_location(value)
    return {
        "field": field_name,
        "metric": metric,
        "region_name": region_name,
        "region_kind": region_kind,
        "region_scope": region_scope,
        "total_count": total_count,
        "scanned_count": scanned_count,
        "truncated": total_count > max_values_per_field,
        "min": min_value,
        "max": max_value,
        "mean": (sum_value / scanned_count) if scanned_count else None,
        "max_abs": max_abs,
        "max_abs_location": max_abs_location,
    }


odb = None
payload = {"ok": False}
try:
    odb = openOdb(path=odb_path, readOnly=True)
    rows = []
    steps = []
    regions = find_regions(odb, requested_regions)
    region_requests = [None] + regions
    for step_name in odb.steps.keys():
        step = odb.steps[step_name]
        frame_count = len(step.frames)
        sampled_count = min(frame_count, max_frames_per_step)
        steps.append({
            "name": str(step_name),
            "frame_count": frame_count,
            "sampled_frame_count": sampled_count,
            "procedure": str(getattr(step, "procedure", "")),
            "totalTime": getattr(step, "totalTime", 0.0),
        })
        for frame_index in range(sampled_count):
            frame = step.frames[frame_index]
            available_fields = keys(frame.fieldOutputs)
            for field_name in requested_fields:
                if field_name not in frame.fieldOutputs:
                    continue
                for region_info in region_requests:
                    stat = summarize_field(field_name, frame.fieldOutputs[field_name], region_info)
                    stat.update({
                        "step": str(step_name),
                        "frame_index": frame_index,
                        "frame_id": getattr(frame, "frameId", None),
                        "frame_value": getattr(frame, "frameValue", None),
                        "available_fields": available_fields,
                    })
                    rows.append(stat)
    payload = {
        "ok": True,
        "result": {
            "path": odb_path,
            "title": str(getattr(odb, "title", "")),
            "description": str(getattr(odb, "description", "")),
            "fields_requested": requested_fields,
            "regions_requested": requested_regions,
            "regions_found": [{"name": item["name"], "kind": item["kind"], "scope": item["scope"]} for item in regions],
            "steps": steps,
            "rows": rows,
            "frame_mode": "all_frames_per_step_limited",
            "limits": {
                "max_values_per_field": max_values_per_field,
                "max_frames_per_step": max_frames_per_step,
            },
        },
    }
except Exception as exc:
    payload = {"ok": False, "error": str(exc), "traceback": traceback.format_exc()}
finally:
    if odb is not None:
        try:
            odb.close()
        except Exception as close_exc:
            try:
                payload.setdefault("warnings", []).append("ODB close failed: " + str(close_exc))
            except Exception:
                pass
    with open(result_path, "w") as handle:
        json.dump(payload, handle, ensure_ascii=True)
'''.replace("__ODB_PATH__", json.dumps(str(odb_path))).replace("__RESULT_PATH__", json.dumps(str(result_path))).replace("__FIELDS__", json.dumps(fields)).replace("__REGIONS__", json.dumps(region_names)).replace("__MAX_VALUES__", str(max_values_per_field)).replace("__MAX_FRAMES__", str(max_frames_per_step))
