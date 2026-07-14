"""Direct client for the Abaqus MCP socket bridge.

The desktop app and other MCP clients can talk to the same Abaqus GUI-side
bridge. This module implements the small JSON-over-TCP protocol so the app can
show connection status and run guarded inspection and job-management actions.
"""

from __future__ import annotations

import base64
import json
import os
import socket
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_HOST = os.environ.get("ABAQUS_MCP_HOST", "127.0.0.1")
DEFAULT_PORT = int(os.environ.get("ABAQUS_MCP_PORT", "48152"))
DEFAULT_TIMEOUT = float(os.environ.get("ABAQUS_MCP_TIMEOUT", "10"))
MCP_SESSIONS_ROOT = Path(__file__).resolve().parent / "mcp_sessions"


class AbaqusMcpError(RuntimeError):
    """Raised when the Abaqus MCP bridge cannot complete a request."""


class AbaqusMcpConnectionError(AbaqusMcpError):
    """Raised when the Abaqus MCP bridge endpoint is unreachable."""


@dataclass
class AbaqusMcpConfig:
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    timeout_seconds: float = DEFAULT_TIMEOUT


@dataclass
class AbaqusMcpStatus:
    connected: bool
    endpoint: str
    checked_at: str
    message: str
    telemetry: dict[str, Any] | None = None
    error: str | None = None


@dataclass
class AbaqusMcpSnapshot:
    snapshot_dir: Path
    summary_path: Path
    report_path: Path
    viewport_path: Path | None
    summary: dict[str, Any]


def request_bridge(
    method: str,
    params: dict[str, Any] | None = None,
    config: AbaqusMcpConfig | None = None,
) -> dict[str, Any]:
    """Send one request to the Abaqus GUI socket bridge."""

    cfg = config or AbaqusMcpConfig()
    timeout = float(cfg.timeout_seconds)
    payload = {
        "id": str(uuid.uuid4()),
        "method": method,
        "params": {**(params or {}), "timeout": timeout},
    }

    try:
        with socket.create_connection((cfg.host, cfg.port), timeout=timeout) as sock:
            sock.settimeout(timeout)
            _send_json(sock, payload)
            response = _read_json(sock)
    except (ConnectionRefusedError, TimeoutError, socket.timeout, OSError) as exc:
        raise AbaqusMcpConnectionError(
            "Cannot connect to Abaqus MCP bridge at "
            f"{cfg.host}:{cfg.port}. Start Abaqus/CAE and run "
            "Plug-ins > Abaqus MCP > Start Socket Bridge."
        ) from exc

    if response.get("id") != payload["id"]:
        raise AbaqusMcpError("Abaqus MCP bridge returned a mismatched response id.")
    if not response.get("ok", False):
        error = response.get("error") or {}
        if isinstance(error, dict):
            message = error.get("message") or json.dumps(error, ensure_ascii=False)
        else:
            message = str(error)
        raise AbaqusMcpError(message)

    result = response.get("result")
    if not isinstance(result, dict):
        raise AbaqusMcpError("Abaqus MCP bridge returned an invalid result envelope.")
    return result


def ping_bridge(config: AbaqusMcpConfig | None = None) -> AbaqusMcpStatus:
    """Return a user-facing connection status."""

    cfg = config or AbaqusMcpConfig()
    endpoint = f"{cfg.host}:{cfg.port}"
    checked_at = datetime.now().isoformat(timespec="seconds")
    try:
        telemetry = request_bridge("ping", config=cfg)
    except AbaqusMcpConnectionError as exc:
        return AbaqusMcpStatus(
            connected=False,
            endpoint=endpoint,
            checked_at=checked_at,
            message="Abaqus MCP bridge is not connected.",
            error=str(exc),
        )
    except AbaqusMcpError as exc:
        return AbaqusMcpStatus(
            connected=False,
            endpoint=endpoint,
            checked_at=checked_at,
            message="Abaqus MCP bridge responded, but Abaqus kernel execution failed.",
            error=str(exc),
        )
    except Exception as exc:
        return AbaqusMcpStatus(
            connected=False,
            endpoint=endpoint,
            checked_at=checked_at,
            message="Abaqus MCP status check failed.",
            error=str(exc),
        )

    version = telemetry.get("abaqus_version") or "unknown"
    models = telemetry.get("models") or []
    viewports = telemetry.get("viewports") or []
    return AbaqusMcpStatus(
        connected=True,
        endpoint=endpoint,
        checked_at=checked_at,
        message=f"Connected to Abaqus {version}. Models: {models}. Viewports: {viewports}.",
        telemetry=telemetry,
    )


def execute_kernel_code(code: str, config: AbaqusMcpConfig | None = None) -> dict[str, Any]:
    """Execute a small Python chunk inside the live Abaqus/CAE kernel."""

    if not code.strip():
        raise ValueError("code must not be empty")
    result = request_bridge("execute", {"code": code}, config=config)
    if not result.get("ok", False):
        raise AbaqusMcpError(_format_kernel_error(result))
    return result


def stop_bridge(config: AbaqusMcpConfig | None = None) -> dict[str, Any]:
    """Request the Abaqus MCP socket bridge to stop.

    This does not close Abaqus/CAE and does not touch the current model. It is
    useful when a stale bridge is still listening on the socket port.
    """

    return request_bridge("stop", config=config)


def set_workdir(path: Path | str, config: AbaqusMcpConfig | None = None) -> dict[str, Any]:
    target = str(Path(path).resolve())
    code = r"""
import os
target = __TARGET__
old_dir = os.getcwd()
if not os.path.isdir(target):
    raise OSError("Directory does not exist: " + target)
os.chdir(target)
result = {"success": True, "previous": old_dir, "current": os.getcwd()}
""".replace("__TARGET__", json.dumps(target))
    return _return_value(execute_kernel_code(code, config=config))


def get_model_info(config: AbaqusMcpConfig | None = None) -> dict[str, Any]:
    code = r"""
from abaqus import mdb, session

def keys(obj):
    try:
        return list(obj.keys())
    except Exception:
        return []

models = {}
for model_name in mdb.models.keys():
    model = mdb.models[model_name]
    part_details = {}
    for part_name in model.parts.keys():
        part = model.parts[part_name]
        part_details[part_name] = {
            "cells": len(getattr(part, "cells", [])),
            "faces": len(getattr(part, "faces", [])),
            "edges": len(getattr(part, "edges", [])),
            "vertices": len(getattr(part, "vertices", [])),
            "sets": keys(part.sets),
            "surfaces": keys(part.surfaces),
        }
    models[model_name] = {
        "parts": keys(model.parts),
        "materials": keys(model.materials),
        "sections": keys(model.sections),
        "steps": keys(model.steps),
        "loads": keys(model.loads),
        "boundary_conditions": keys(model.boundaryConditions),
        "interactions": keys(model.interactions),
        "constraints": keys(model.constraints),
        "assembly_instances": keys(model.rootAssembly.instances),
        "sets": keys(model.rootAssembly.sets),
        "surfaces": keys(model.rootAssembly.surfaces),
        "part_details": part_details,
    }

jobs = []
for job_name in mdb.jobs.keys():
    job = mdb.jobs[job_name]
    item = {"name": job_name}
    for attr in ("status", "type", "model", "description", "numCpus", "numDomains", "memory"):
        try:
            value = getattr(job, attr, None)
            if value is not None:
                item[attr] = str(value)
        except Exception:
            pass
    jobs.append(item)

result = {
    "models": models,
    "jobs": jobs,
    "current_viewport": getattr(session, "currentViewportName", None),
    "viewports": list(session.viewports.keys()) if hasattr(session, "viewports") else [],
}
"""
    return _return_value(execute_kernel_code(code, config=config))


def list_jobs(config: AbaqusMcpConfig | None = None) -> list[dict[str, Any]]:
    code = r"""
from abaqus import mdb
jobs = []
for name in mdb.jobs.keys():
    job = mdb.jobs[name]
    item = {"name": name}
    for attr in ("status", "type", "model", "description", "numCpus", "numDomains", "memory", "explicitPrecision"):
        try:
            value = getattr(job, attr, None)
            if value is not None:
                item[attr] = str(value)
        except Exception:
            pass
    jobs.append(item)
result = {"jobs": jobs}
"""
    return _return_value(execute_kernel_code(code, config=config)).get("jobs", [])


def monitor_job_status(job_name: str = "", config: AbaqusMcpConfig | None = None) -> dict[str, Any]:
    code = r"""
import os
import re
from abaqus import mdb

job_name = __JOB_NAME__

def tail_lines(path, count):
    try:
        with open(path, "r") as handle:
            return handle.read().splitlines()[-count:]
    except Exception:
        return []

def grep_tail(path, patterns, limit):
    try:
        rx = re.compile("|".join(patterns))
        matches = []
        with open(path, "r") as handle:
            for line in handle:
                if rx.search(line):
                    matches.append(line.rstrip())
        return matches[-limit:]
    except Exception:
        return []

if not job_name:
    jobs = []
    for name in mdb.jobs.keys():
        job = mdb.jobs[name]
        item = {"name": name}
        for attr in ("status", "type", "model", "description", "numCpus", "numDomains", "memory"):
            try:
                value = getattr(job, attr, None)
                if value is not None:
                    item[attr] = str(value)
            except Exception:
                pass
        jobs.append(item)
    result = {"jobs": jobs, "workdir": os.getcwd()}
else:
    sta_path = os.path.join(os.getcwd(), job_name + ".sta")
    msg_path = os.path.join(os.getcwd(), job_name + ".msg")
    result = {
        "job_name": job_name,
        "workdir": os.getcwd(),
        "sta_path": sta_path,
        "msg_path": msg_path,
        "progress_tail": tail_lines(sta_path, 8),
        "diagnostics_tail": grep_tail(msg_path, [r"^\*\*\*ERROR", r"^\*\*\*WARNING"], 12),
    }
""".replace("__JOB_NAME__", json.dumps(job_name.strip()))
    return _return_value(execute_kernel_code(code, config=config))


def submit_job(job_name: str, config: AbaqusMcpConfig | None = None) -> dict[str, Any]:
    if not job_name.strip():
        raise ValueError("job_name must not be empty")
    code = r"""
from abaqus import mdb
job_name = __JOB_NAME__
if job_name not in mdb.jobs:
    raise KeyError("Job not found: " + job_name)
job = mdb.jobs[job_name]
job.submit(consistencyChecking=False)
job.waitForCompletion()
result = {"success": True, "job": job_name, "status": str(getattr(job, "status", "UNKNOWN"))}
""".replace("__JOB_NAME__", json.dumps(job_name.strip()))
    return _return_value(execute_kernel_code(code, config=config))


def inspect_odb(odb_path: Path | str, config: AbaqusMcpConfig | None = None) -> dict[str, Any]:
    path = str(Path(odb_path).resolve())
    code = r"""
from odbAccess import openOdb

odb_path = __ODB_PATH__
odb = None
try:
    odb = openOdb(path=odb_path, readOnly=True)
    steps = []
    for step_name in odb.steps.keys():
        step = odb.steps[step_name]
        frame_count = len(step.frames)
        sample_idxs = []
        if frame_count <= 5:
            sample_idxs = list(range(frame_count))
        elif frame_count:
            sample_idxs = [0, int(round((frame_count - 1) * 0.25)), int(round((frame_count - 1) * 0.5)), int(round((frame_count - 1) * 0.75)), frame_count - 1]
            sample_idxs = sorted(set(sample_idxs))

        frames = []
        for idx in sample_idxs:
            frame = step.frames[idx]
            frames.append({
                "index": idx,
                "frameId": frame.frameId,
                "frameValue": frame.frameValue,
                "description": str(getattr(frame, "description", "")),
            })

        field_outputs = []
        if step.frames:
            for key in step.frames[-1].fieldOutputs.keys():
                field = step.frames[-1].fieldOutputs[key]
                field_outputs.append({
                    "name": key,
                    "components": list(getattr(field, "componentLabels", []) or []),
                    "validInvariants": [str(x) for x in (getattr(field, "validInvariants", []) or [])],
                })

        steps.append({
            "name": step_name,
            "procedure": str(getattr(step, "procedure", "")),
            "totalTime": getattr(step, "totalTime", 0.0),
            "frame_count": frame_count,
            "frames": frames,
            "fieldOutputs": field_outputs,
            "historyRegions": list(step.historyRegions.keys()),
        })

    result = {
        "path": odb_path,
        "title": str(getattr(odb, "title", "")),
        "description": str(getattr(odb, "description", "")),
        "parts": list(odb.parts.keys()) if hasattr(odb, "parts") else [],
        "instances": list(odb.rootAssembly.instances.keys()) if hasattr(odb, "rootAssembly") else [],
        "steps": steps,
    }
finally:
    if odb is not None:
        odb.close()
""".replace("__ODB_PATH__", json.dumps(path))
    return _return_value(execute_kernel_code(code, config=config))


def extract_odb_field_summary(
    odb_path: Path | str,
    *,
    fields: list[str] | tuple[str, ...] | None = None,
    max_values_per_field: int = 500_000,
    max_history_outputs: int = 200,
    config: AbaqusMcpConfig | None = None,
) -> dict[str, Any]:
    """Extract final-frame field statistics from an ODB through Abaqus/CAE.

    The heavy ODB access happens inside the Abaqus Python kernel. The returned
    payload is deliberately plain JSON-compatible data so Streamlit and the
    case library can persist it without Abaqus imports.
    """

    path = str(Path(odb_path).resolve())
    field_names = [str(item).strip().upper() for item in (fields or ("S", "PEEQ", "U", "RF", "CPRESS", "COPEN")) if str(item).strip()]
    max_values = max(1, int(max_values_per_field))
    max_history = max(0, int(max_history_outputs))
    code = r"""
from odbAccess import openOdb
try:
    from abaqusConstants import MISES, MAGNITUDE
except Exception:
    MISES = None
    MAGNITUDE = None

odb_path = __ODB_PATH__
requested_fields = __FIELDS__
max_values_per_field = __MAX_VALUES__
max_history_outputs = __MAX_HISTORY__

def to_float(value):
    try:
        return float(value)
    except Exception:
        return None

def json_data(value):
    if isinstance(value, (list, tuple)):
        return [to_float(item) for item in value]
    return to_float(value)

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

def raw_magnitude(data):
    if isinstance(data, (list, tuple)):
        total = 0.0
        found = False
        for item in data:
            number = to_float(item)
            if number is not None:
                total += number * number
                found = True
        return total ** 0.5 if found else None
    return to_float(data)

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
    component_labels = []
    valid_invariants = []
    try:
        component_labels = [str(item) for item in (getattr(field, "componentLabels", []) or [])]
    except Exception:
        pass
    try:
        valid_invariants = [str(item) for item in (getattr(field, "validInvariants", []) or [])]
    except Exception:
        pass

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
    for region_name in step.historyRegions.keys():
        region = step.historyRegions[region_name]
        for output_name in region.historyOutputs.keys():
            if len(rows) >= max_history_outputs:
                return rows, True
            output = region.historyOutputs[output_name]
            data = getattr(output, "data", []) or []
            values = []
            for _, y_value in data:
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
    return rows, False

odb = None
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
                "available_fields": list(frame.fieldOutputs.keys()),
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
                "node_sets": list(getattr(inst, "nodeSets", {}).keys()),
                "element_sets": list(getattr(inst, "elementSets", {}).keys()),
            })
    except Exception:
        pass

    result = {
        "path": odb_path,
        "title": str(getattr(odb, "title", "")),
        "description": str(getattr(odb, "description", "")),
        "instances": instances,
        "node_sets": list(getattr(odb.rootAssembly, "nodeSets", {}).keys()) if hasattr(odb, "rootAssembly") else [],
        "element_sets": list(getattr(odb.rootAssembly, "elementSets", {}).keys()) if hasattr(odb, "rootAssembly") else [],
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
    }
finally:
    if odb is not None:
        odb.close()
""".replace("__ODB_PATH__", json.dumps(path)).replace("__FIELDS__", json.dumps(field_names)).replace("__MAX_VALUES__", str(max_values)).replace("__MAX_HISTORY__", str(max_history))
    return _return_value(execute_kernel_code(code, config=config))


def display_odb_contour(
    odb_path: Path | str,
    *,
    field_label: str = "S",
    invariant: str = "Mises",
    output_position: str = "INTEGRATION_POINT",
    config: AbaqusMcpConfig | None = None,
) -> dict[str, Any]:
    """Display an ODB contour in the current Abaqus viewport before capture."""

    path = str(Path(odb_path).resolve())
    code = r"""
from odbAccess import openOdb
from abaqus import session
from abaqusConstants import CONTOURS_ON_DEF, INTEGRATION_POINT, NODAL, ELEMENT_NODAL, WHOLE_ELEMENT, INVARIANT, COMPONENT

odb_path = __ODB_PATH__
field_label = __FIELD_LABEL__
invariant = __INVARIANT__
output_position_name = __OUTPUT_POSITION__

position_map = {
    "INTEGRATION_POINT": INTEGRATION_POINT,
    "NODAL": NODAL,
    "ELEMENT_NODAL": ELEMENT_NODAL,
    "WHOLE_ELEMENT": WHOLE_ELEMENT,
}
output_position = position_map.get(output_position_name, INTEGRATION_POINT)

if odb_path in session.odbs:
    odb = session.odbs[odb_path]
else:
    odb = openOdb(path=odb_path, readOnly=True)

vp_name = getattr(session, "currentViewportName", None)
if not vp_name or vp_name not in session.viewports.keys():
    vp_name = list(session.viewports.keys())[0]
vp = session.viewports[vp_name]
vp.setValues(displayedObject=odb)
try:
    vp.odbDisplay.display.setValues(plotState=(CONTOURS_ON_DEF,))
except Exception:
    pass

try:
    last_step_name = list(odb.steps.keys())[-1]
    last_step = odb.steps[last_step_name]
    if len(last_step.frames):
        vp.odbDisplay.setFrame(step=last_step_name, frame=len(last_step.frames) - 1)
except Exception:
    pass

refinement_type = INVARIANT if invariant else COMPONENT
refinement_label = invariant if invariant else ""
try:
    vp.odbDisplay.setPrimaryVariable(
        variableLabel=field_label,
        outputPosition=output_position,
        refinement=(refinement_type, refinement_label),
    )
except Exception:
    vp.odbDisplay.setPrimaryVariable(variableLabel=field_label, outputPosition=output_position)

result = {
    "success": True,
    "path": odb_path,
    "viewport": vp_name,
    "field": field_label,
    "invariant": invariant,
    "output_position": output_position_name,
}
""".replace("__ODB_PATH__", json.dumps(path)).replace("__FIELD_LABEL__", json.dumps(field_label.strip() or "S")).replace("__INVARIANT__", json.dumps(invariant.strip())).replace("__OUTPUT_POSITION__", json.dumps(output_position.strip().upper() or "INTEGRATION_POINT"))
    return _return_value(execute_kernel_code(code, config=config))


def capture_viewport(
    output_dir: Path | str,
    viewport_name: str = "",
    image_format: str = "PNG",
    config: AbaqusMcpConfig | None = None,
) -> Path:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    fmt_name = (image_format or "PNG").upper()
    code = r"""
import os
import tempfile
import base64
from abaqus import session
import abaqusConstants

vp_name = __VP_NAME__
fmt_name = __FORMAT__.upper()
fmt_map = {
    "PNG": abaqusConstants.PNG,
    "TIFF": abaqusConstants.TIFF,
    "SVG": abaqusConstants.SVG,
    "EPS": abaqusConstants.EPS,
    "PS": abaqusConstants.PS,
}
fmt = fmt_map.get(fmt_name, abaqusConstants.PNG)
if not vp_name or vp_name not in session.viewports.keys():
    vp_name = session.currentViewportName
vp = session.viewports[vp_name]
suffix = "." + fmt_name.lower()
handle = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
tmp_path = handle.name
handle.close()
try:
    session.printToFile(fileName=tmp_path, format=fmt, canvasObjects=(vp,))
    with open(tmp_path, "rb") as image_file:
        image_base64 = base64.b64encode(image_file.read()).decode("ascii")
    result = {
        "success": True,
        "viewport": vp_name,
        "format": fmt_name.lower(),
        "image_base64": image_base64,
    }
finally:
    try:
        os.unlink(tmp_path)
    except Exception:
        pass
""".replace("__VP_NAME__", json.dumps(viewport_name.strip())).replace("__FORMAT__", json.dumps(fmt_name))
    data = _return_value(execute_kernel_code(code, config=config))
    suffix = "." + str(data.get("format", fmt_name.lower()))
    viewport = _safe_name(str(data.get("viewport") or "viewport"))
    path = output / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{viewport}{suffix}"
    image_bytes = base64.b64decode(str(data.get("image_base64") or ""))
    path.write_bytes(image_bytes)
    return path


def create_session_snapshot(
    selected_run: Path | None = None,
    config: AbaqusMcpConfig | None = None,
    capture_image: bool = True,
) -> AbaqusMcpSnapshot:
    """Capture status/model/job/viewport information into a local report folder."""

    cfg = config or AbaqusMcpConfig()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    snapshot_dir = MCP_SESSIONS_ROOT / f"{stamp}_abaqus_mcp_snapshot"
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    status = ping_bridge(cfg)
    model_info: dict[str, Any] | None = None
    jobs: list[dict[str, Any]] | None = None
    viewport_path: Path | None = None
    errors: list[str] = []

    if status.connected:
        try:
            model_info = get_model_info(cfg)
        except Exception as exc:
            errors.append(f"model_info: {exc}")
        try:
            jobs = list_jobs(cfg)
        except Exception as exc:
            errors.append(f"jobs: {exc}")
        if capture_image:
            try:
                viewport_path = capture_viewport(snapshot_dir, config=cfg)
            except Exception as exc:
                errors.append(f"viewport: {exc}")

    summary = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "selected_run": str(selected_run) if selected_run else None,
        "config": asdict(cfg),
        "status": asdict(status),
        "model_info": model_info,
        "jobs": jobs,
        "viewport_image": str(viewport_path) if viewport_path else None,
        "errors": errors,
    }
    summary_path = snapshot_dir / "mcp_snapshot.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    report_path = snapshot_dir / "mcp_snapshot_report.md"
    report_path.write_text(_snapshot_report(summary), encoding="utf-8")
    return AbaqusMcpSnapshot(
        snapshot_dir=snapshot_dir,
        summary_path=summary_path,
        report_path=report_path,
        viewport_path=viewport_path,
        summary=summary,
    )


def _send_json(sock: socket.socket, payload: dict[str, Any]) -> None:
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    sock.sendall(data + b"\n")


def _read_json(sock: socket.socket, max_bytes: int = 32 * 1024 * 1024) -> dict[str, Any]:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = sock.recv(4096)
        if not chunk:
            raise AbaqusMcpError("socket closed before a complete message was received")
        newline = chunk.find(b"\n")
        if newline >= 0:
            chunks.append(chunk[:newline])
            break
        chunks.append(chunk)
        total += len(chunk)
        if total > max_bytes:
            raise AbaqusMcpError(f"message exceeded {max_bytes} bytes")

    message = json.loads(b"".join(chunks).decode("utf-8"))
    if not isinstance(message, dict):
        raise AbaqusMcpError("protocol message must be a JSON object")
    return message


def _return_value(execution_result: dict[str, Any]) -> dict[str, Any]:
    value = execution_result.get("return_value")
    return value if isinstance(value, dict) else {"value": value}


def _format_kernel_error(result: dict[str, Any]) -> str:
    error_type = str(result.get("error_type", "Error")).rsplit(".", 1)[-1]
    core_error = result.get("core_error", "Unknown error")
    error_line = result.get("error_line")
    location = f" at line {error_line}" if error_line else ""
    return f"{error_type}{location}: {core_error}"


def _safe_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in value).strip("_") or "viewport"


def _snapshot_report(summary: dict[str, Any]) -> str:
    status = summary.get("status", {})
    jobs = summary.get("jobs") or []
    model_info = summary.get("model_info") or {}
    models = list((model_info.get("models") or {}).keys()) if isinstance(model_info, dict) else []
    errors = summary.get("errors") or []
    job_lines = "\n".join(f"- `{job.get('name')}`: {job.get('status', 'unknown')}" for job in jobs) or "- 暂无 job"
    error_lines = "\n".join(f"- {item}" for item in errors) or "- 无"
    return f"""# Abaqus MCP 会话快照

## 连接状态

- 端点：`{status.get("endpoint")}`
- 状态：`{"connected" if status.get("connected") else "disconnected"}`
- 检查时间：`{status.get("checked_at")}`
- 消息：{status.get("message")}

## 当前模型

- 模型：`{models}`
- 视口截图：`{summary.get("viewport_image") or "未生成"}`

## Job

{job_lines}

## 错误与风险

{error_lines}

## 说明

本快照由 MaterialAI Workbench 通过 Abaqus MCP socket bridge 生成，用于记录 AI 客户端与 Abaqus/CAE 的实时连接状态、模型上下文、Job 状态和可视化输出。
"""
