"""Resumable Abaqus acceptance workflow for a 3D plate with a circular hole."""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from material_ai_workbench.abaqus_diagnostics import (
    AbaqusDiagnosticConfig,
    run_abaqus_diagnostics,
)
from material_ai_workbench.abaqus_mcp_client import (
    AbaqusMcpConfig,
    execute_kernel_code,
    ping_bridge,
)
from material_ai_workbench.case_library import scan_case_folder
from material_ai_workbench.config import (
    ABAQUS_BAT,
    ABAQUS_MCP_HOST,
    ABAQUS_MCP_PORT,
    ABAQUS_SMAPYTHON,
    ACCEPTANCE_ROOT,
    CASES_ROOT,
    WORKSPACE_ROOT,
)

OVERALL_STATUSES = {
    "prepared",
    "blocked",
    "built",
    "solved",
    "postprocessed",
    "validated",
    "archived",
    "failed",
}
STAGE_STATUSES = {"pending", "pass", "warn", "fail", "skipped", "blocked"}


@dataclass
class PlateHoleAcceptanceConfig:
    name: str = "plate_hole_acceptance"
    output_root: Path | str = ACCEPTANCE_ROOT
    cases_root: Path | str = CASES_ROOT
    length: float = 100.0
    width: float = 50.0
    thickness: float = 5.0
    hole_radius: float = 5.0
    youngs_modulus: float = 210_000.0
    poisson_ratio: float = 0.30
    yield_strength: float = 250.0
    tangent_modulus: float = 1_000.0
    plastic_strain_limit: float = 0.05
    displacement: float = 0.35
    mesh_size: float = 2.5
    cpus: int = 4
    backend: str = "batch"
    submit_job: bool = False
    archive_case: bool = False
    timeout_seconds: float = 3_600.0
    abaqus_bat: Path | str = ABAQUS_BAT
    smapython: Path | str = ABAQUS_SMAPYTHON
    mcp_host: str = ABAQUS_MCP_HOST
    mcp_port: int = ABAQUS_MCP_PORT
    mcp_timeout_seconds: float = 3_600.0


@dataclass
class PlateHoleAcceptanceResult:
    run_dir: Path
    status: str
    manifest_path: Path
    report_path: Path
    config_path: Path
    build_script_path: Path
    postprocess_script_path: Path
    run_script_path: Path
    manifest: dict[str, Any]


def run_plate_hole_acceptance(
    config: PlateHoleAcceptanceConfig | None = None,
    *,
    execute: bool = False,
    run_dir: Path | str | None = None,
) -> PlateHoleAcceptanceResult:
    """Prepare or execute the plate-hole workflow and persist every state change."""

    cfg = config or PlateHoleAcceptanceConfig()
    _validate_config(cfg)
    target_dir = _resolve_run_dir(cfg, run_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    paths = _artifact_paths(target_dir, cfg)
    manifest = _load_or_create_manifest(paths["manifest"], cfg, target_dir)
    manifest["config"] = _serialize_config(cfg)
    _write_config(paths["config"], cfg)
    _write_build_script(paths["build_script"], cfg, target_dir)
    _write_postprocess_script(paths["postprocess_script"], cfg, target_dir)
    _write_run_script(paths["run_script"], cfg, paths)
    _set_stage(
        manifest,
        "prepare",
        "pass",
        "已生成确定性的 Abaqus 建模脚本、后处理脚本和启动文件。",
        evidence={
            "config": str(paths["config"]),
            "build_script": str(paths["build_script"]),
            "postprocess_script": str(paths["postprocess_script"]),
            "run_script": str(paths["run_script"]),
        },
    )

    diagnostic = run_abaqus_diagnostics(
        AbaqusDiagnosticConfig(
            abaqus_bat=cfg.abaqus_bat,
            smapython=cfg.smapython,
            workspace_root=WORKSPACE_ROOT,
            output_root=target_dir / "diagnostics",
            mcp=AbaqusMcpConfig(
                host=cfg.mcp_host,
                port=int(cfg.mcp_port),
                timeout_seconds=min(float(cfg.mcp_timeout_seconds), 20.0),
            ),
            probe_commands=False,
            include_live_context=False,
        )
    )
    _set_stage(
        manifest,
        "diagnostics",
        "pass" if diagnostic.batch_ready else "warn",
        f"Abaqus 环境诊断状态：{diagnostic.overall_status}。",
        evidence={
            "batch_ready": diagnostic.batch_ready,
            "mcp_ready": diagnostic.mcp_ready,
            "json": str(diagnostic.json_path),
            "markdown": str(diagnostic.markdown_path),
        },
    )

    _sync_artifacts(manifest, paths)
    if not execute:
        manifest["status"] = "prepared"
        manifest["next_actions"] = [
            "检查 acceptance_config.json 和 build_plate_hole.py。",
            "确认后使用 materialai-plate-hole --resume <run_dir> --execute --submit-job 继续。",
        ]
        _persist(manifest, paths)
        return _result(target_dir, paths, manifest)

    if cfg.backend == "batch" and not Path(cfg.abaqus_bat).expanduser().is_file():
        return _blocked(
            target_dir,
            paths,
            manifest,
            "已请求 Abaqus 批处理，但未找到 abaqus.bat。",
        )
    if cfg.backend == "mcp" and not ping_bridge(_mcp_config(cfg)).connected:
        return _blocked(
            target_dir,
            paths,
            manifest,
            "已请求 Abaqus MCP 执行，但 Socket Bridge 未连接。",
        )

    existing_odb = paths["odb"].is_file()
    if existing_odb:
        _set_stage(
            manifest,
            "build",
            "pass",
            "检测到已有 ODB，本次未重复建模。",
            evidence={"odb": str(paths["odb"])},
        )
        _set_stage(
            manifest,
            "solve",
            "pass",
            "已有 ODB 作为该运行目录的求解器证据。",
            evidence={
                "odb": str(paths["odb"]),
                "size_bytes": paths["odb"].stat().st_size,
            },
        )
        manifest["status"] = "solved"
    else:
        build = _execute_build(cfg, paths, target_dir)
        manifest["execution_evidence"]["build"] = build
        if build["returncode"] != 0:
            _set_stage(
                manifest, "build", "fail", "Abaqus 模型构建失败。", evidence=build
            )
            manifest["status"] = "failed"
            manifest["next_actions"] = [
                "检查 build_stdout.log、build_stderr.log 和 abaqus_build_summary.json。"
            ]
            _persist(manifest, paths)
            return _result(target_dir, paths, manifest)

        built = paths["inp"].is_file() and paths["cae"].is_file()
        _set_stage(
            manifest,
            "build",
            "pass" if built else "fail",
            (
                "已生成 Abaqus CAE 和 INP。"
                if built
                else "Abaqus 进程已返回，但 CAE/INP 工件不完整。"
            ),
            evidence=_file_evidence(paths["cae"], paths["inp"], paths["build_summary"]),
        )
        if not built:
            manifest["status"] = "failed"
            manifest["next_actions"] = ["检查 Abaqus 建模日志与脚本版本兼容性。"]
            _persist(manifest, paths)
            return _result(target_dir, paths, manifest)
        manifest["status"] = "built"

        if cfg.submit_job:
            solved = paths["odb"].is_file() and paths["odb"].stat().st_size > 0
            _set_stage(
                manifest,
                "solve",
                "pass" if solved else "fail",
                "已生成真实 Abaqus ODB。" if solved else "Job 提交后未生成 ODB。",
                evidence=_solver_evidence(paths),
            )
            if not solved:
                manifest["status"] = "failed"
                manifest["next_actions"] = ["重试前检查 .sta、.msg、.dat 和建模日志。"]
                _persist(manifest, paths)
                return _result(target_dir, paths, manifest)
            manifest["status"] = "solved"
        else:
            _set_stage(
                manifest,
                "solve",
                "skipped",
                "本次未请求提交 Job，因此不声明已求解。",
            )
            manifest["next_actions"] = ["使用 --submit-job 恢复该运行并生成真实 ODB。"]
            _persist(manifest, paths)
            return _result(target_dir, paths, manifest)

    post = _execute_postprocess(cfg, paths, target_dir)
    manifest["execution_evidence"]["postprocess"] = post
    summary = _load_json(paths["result_json"])
    post_ok = post["returncode"] == 0 and bool(summary.get("ok"))
    _set_stage(
        manifest,
        "postprocess",
        "pass" if post_ok else "fail",
        "已从 ODB 提取工程特征。" if post_ok else "ODB 后处理失败。",
        evidence={
            **post,
            "result_json": str(paths["result_json"]),
            "result_csv": str(paths["result_csv"]),
        },
    )
    if not post_ok:
        manifest["status"] = "failed"
        manifest["next_actions"] = [
            "检查 postprocess_stdout.log、postprocess_stderr.log 和 plate_hole_results.json。"
        ]
        _persist(manifest, paths)
        return _result(target_dir, paths, manifest)

    manifest["results"] = summary.get("results", {})
    manifest["status"] = "postprocessed"
    validation = _engineering_validation(cfg, manifest["results"])
    _set_stage(
        manifest,
        "engineering_validation",
        validation["status"],
        validation["message"],
        evidence=validation,
    )
    if validation["status"] == "pass":
        manifest["status"] = "validated"

    _write_feature_row(paths["feature_csv"], cfg, manifest["results"], validation)
    if cfg.archive_case:
        existing_case_id = manifest.get("case_id")
        existing_archive = (manifest.get("stages") or {}).get("archive") or {}
        if existing_case_id and existing_archive.get("status") == "pass":
            _set_stage(
                manifest,
                "archive",
                "pass",
                "该验收运行已在案例库中，无需重复索引。",
                evidence=existing_archive.get("evidence")
                or {"case_id": existing_case_id},
            )
            if validation["status"] == "pass":
                manifest["status"] = "archived"
        else:
            try:
                case = scan_case_folder(
                    target_dir,
                    title=f"{cfg.name} 三维带孔板验收",
                    tags=["abaqus", "plate-hole", "3d", "j2", "acceptance"],
                    description="含可追溯 ODB 特征的 Abaqus 三维带孔板拉伸验收算例。",
                    status="success" if validation["status"] == "pass" else "review",
                    parameters={
                        **_engineering_config(cfg),
                        **manifest["results"],
                    },
                    cases_root=Path(cfg.cases_root).expanduser().resolve(),
                )
            except Exception as exc:
                _set_stage(
                    manifest,
                    "archive",
                    "warn",
                    "求解结果仍然有效，但案例库索引失败。",
                    evidence={"error": str(exc)},
                )
            else:
                _set_stage(
                    manifest,
                    "archive",
                    "pass",
                    "验收运行已加入案例库索引。",
                    evidence={"case_id": case.case_id, "case_dir": case.case_dir},
                )
                manifest["case_id"] = case.case_id
                if validation["status"] == "pass":
                    manifest["status"] = "archived"
    else:
        _set_stage(manifest, "archive", "skipped", "本次未请求加入案例库。")

    manifest["next_actions"] = (
        ["验收已通过，可将 plate_hole_features.csv 作为已验证数据行。"]
        if validation["status"] == "pass"
        else ["将结果用于训练前，先处理工程合理性检查中的警告。"]
    )
    _persist(manifest, paths)
    return _result(target_dir, paths, manifest)


def resume_plate_hole_acceptance(
    run_dir: Path | str,
    *,
    execute: bool = True,
    submit_job: bool | None = None,
    archive_case: bool | None = None,
    backend: str | None = None,
) -> PlateHoleAcceptanceResult:
    """Resume a prepared or interrupted run from its persisted configuration."""

    target = Path(run_dir).expanduser().resolve()
    config_path = target / "acceptance_config.json"
    if not config_path.is_file():
        raise FileNotFoundError(f"验收配置不存在：{config_path}")
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    cfg = PlateHoleAcceptanceConfig(**payload)
    cfg.output_root = target.parent
    if submit_job is not None:
        cfg.submit_job = bool(submit_job)
    if archive_case is not None:
        cfg.archive_case = bool(archive_case)
    if backend is not None:
        cfg.backend = backend
    return run_plate_hole_acceptance(cfg, execute=execute, run_dir=target)


def _execute_build(
    config: PlateHoleAcceptanceConfig,
    paths: dict[str, Path],
    run_dir: Path,
) -> dict[str, Any]:
    started = datetime.now().isoformat(timespec="seconds")
    if config.backend == "mcp":
        namespace_code = (
            "script_path = " + repr(str(paths["build_script"])) + "\n"
            "namespace = {'__name__': '__main__'}\n"
            "execfile(script_path, namespace, namespace)\n"
            "result = namespace.get('result', {})\n"
        )
        try:
            response = execute_kernel_code(namespace_code, config=_mcp_config(config))
        except Exception as exc:
            return {
                "backend": "mcp",
                "started_at": started,
                "finished_at": datetime.now().isoformat(timespec="seconds"),
                "returncode": 1,
                "error": str(exc),
            }
        paths["build_stdout"].write_text(
            json.dumps(response, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return {
            "backend": "mcp",
            "started_at": started,
            "finished_at": datetime.now().isoformat(timespec="seconds"),
            "returncode": 0,
            "response_path": str(paths["build_stdout"]),
        }

    env = os.environ.copy()
    env["MATERIALAI_SUBMIT_JOB"] = "1" if config.submit_job else "0"
    env.setdefault("PYTHONIOENCODING", "utf-8")
    command = [
        str(Path(config.abaqus_bat).expanduser().resolve()),
        "cae",
        f"noGUI={paths['build_script']}",
    ]
    try:
        completed = subprocess.run(
            command,
            cwd=str(run_dir),
            env=env,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=max(1.0, float(config.timeout_seconds)),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        paths["build_stderr"].write_text(str(exc), encoding="utf-8")
        return {
            "backend": "batch",
            "command": command,
            "started_at": started,
            "finished_at": datetime.now().isoformat(timespec="seconds"),
            "returncode": 1,
            "error": str(exc),
        }

    paths["build_stdout"].write_text(
        completed.stdout or "", encoding="utf-8", errors="replace"
    )
    paths["build_stderr"].write_text(
        completed.stderr or "", encoding="utf-8", errors="replace"
    )
    build_summary = _load_json(paths["build_summary"])
    effective_returncode = completed.returncode
    if build_summary and not build_summary.get("ok", False):
        effective_returncode = effective_returncode or 1
    return {
        "backend": "batch",
        "command": command,
        "started_at": started,
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "returncode": effective_returncode,
        "stdout": str(paths["build_stdout"]),
        "stderr": str(paths["build_stderr"]),
    }


def _execute_postprocess(
    config: PlateHoleAcceptanceConfig,
    paths: dict[str, Path],
    run_dir: Path,
) -> dict[str, Any]:
    command = [
        str(Path(config.smapython).expanduser().resolve()),
        str(paths["postprocess_script"]),
    ]
    started = datetime.now().isoformat(timespec="seconds")
    if not Path(config.smapython).expanduser().is_file():
        return {
            "command": command,
            "started_at": started,
            "finished_at": datetime.now().isoformat(timespec="seconds"),
            "returncode": 1,
            "error": "SMAPython executable does not exist.",
        }
    try:
        completed = subprocess.run(
            command,
            cwd=str(run_dir),
            capture_output=True,
            text=True,
            errors="replace",
            timeout=max(1.0, min(float(config.timeout_seconds), 900.0)),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        paths["post_stderr"].write_text(str(exc), encoding="utf-8")
        return {
            "command": command,
            "started_at": started,
            "finished_at": datetime.now().isoformat(timespec="seconds"),
            "returncode": 1,
            "error": str(exc),
        }
    paths["post_stdout"].write_text(
        completed.stdout or "", encoding="utf-8", errors="replace"
    )
    paths["post_stderr"].write_text(
        completed.stderr or "", encoding="utf-8", errors="replace"
    )
    return {
        "command": command,
        "started_at": started,
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "returncode": completed.returncode,
        "stdout": str(paths["post_stdout"]),
        "stderr": str(paths["post_stderr"]),
    }


def _write_build_script(
    path: Path, config: PlateHoleAcceptanceConfig, run_dir: Path
) -> None:
    model_name = _safe_name(config.name)[:60]
    job_name = f"{model_name}_job"[:79]
    script = r"""# -*- coding: utf-8 -*-
from __future__ import print_function

import json
import os
import traceback
from datetime import datetime

from abaqus import *
from abaqusConstants import *
from caeModules import *
import mesh

WORKDIR = __WORKDIR__
MODEL_NAME = __MODEL_NAME__
JOB_NAME = __JOB_NAME__
LENGTH = __LENGTH__
WIDTH = __WIDTH__
THICKNESS = __THICKNESS__
HOLE_RADIUS = __HOLE_RADIUS__
YOUNGS_MODULUS = __YOUNGS_MODULUS__
POISSON_RATIO = __POISSON_RATIO__
YIELD_STRENGTH = __YIELD_STRENGTH__
TANGENT_MODULUS = __TANGENT_MODULUS__
PLASTIC_STRAIN_LIMIT = __PLASTIC_STRAIN_LIMIT__
DISPLACEMENT = __DISPLACEMENT__
MESH_SIZE = __MESH_SIZE__
CPUS = __CPUS__
SUBMIT_DEFAULT = __SUBMIT_DEFAULT__
SUBMIT_JOB = os.environ.get('MATERIALAI_SUBMIT_JOB', '1' if SUBMIT_DEFAULT else '0').strip() == '1'
SUMMARY_PATH = os.path.join(WORKDIR, 'abaqus_build_summary.json')


def safe_exception_text(value):
    try:
        return unicode(value)
    except Exception:
        raw = str(value)
        for encoding in ('utf-8', 'gbk', 'mbcs', 'latin-1'):
            try:
                return raw.decode(encoding)
            except Exception:
                pass
        return repr(raw)


def safe_traceback_text():
    raw = traceback.format_exc()
    try:
        if isinstance(raw, unicode):
            return raw
        for encoding in ('utf-8', 'gbk', 'mbcs', 'latin-1'):
            try:
                return raw.decode(encoding)
            except Exception:
                pass
        return repr(raw)
    except Exception:
        return repr(raw)


def build_and_run():
    if not os.path.isdir(WORKDIR):
        os.makedirs(WORKDIR)
    os.chdir(WORKDIR)
    if JOB_NAME in mdb.jobs:
        del mdb.jobs[JOB_NAME]
    if MODEL_NAME in mdb.models:
        del mdb.models[MODEL_NAME]

    model = mdb.Model(name=MODEL_NAME)
    half_l = LENGTH / 2.0
    half_w = WIDTH / 2.0
    sketch = model.ConstrainedSketch(name='plate_profile', sheetSize=max(LENGTH, WIDTH) * 2.5)
    sketch.rectangle(point1=(-half_l, -half_w), point2=(half_l, half_w))
    sketch.CircleByCenterPerimeter(center=(0.0, 0.0), point1=(HOLE_RADIUS, 0.0))
    part = model.Part(name='PLATE', dimensionality=THREE_D, type=DEFORMABLE_BODY)
    part.BaseSolidExtrude(sketch=sketch, depth=THICKNESS)
    del model.sketches['plate_profile']

    material = model.Material(name='J2_BILINEAR_MATERIAL')
    material.Elastic(table=((YOUNGS_MODULUS, POISSON_RATIO),))
    plastic_stress = YIELD_STRENGTH + TANGENT_MODULUS * PLASTIC_STRAIN_LIMIT
    material.Plastic(table=((YIELD_STRENGTH, 0.0), (plastic_stress, PLASTIC_STRAIN_LIMIT)))
    model.HomogeneousSolidSection(name='PLATE_SECTION', material=material.name, thickness=None)
    part.Set(name='ALL_CELLS', cells=part.cells)
    part.SectionAssignment(region=part.sets['ALL_CELLS'], sectionName='PLATE_SECTION')

    part.seedPart(size=MESH_SIZE, deviationFactor=0.1, minSizeFactor=0.1)
    part.setMeshControls(regions=part.cells, elemShape=TET, technique=FREE)
    element_type = mesh.ElemType(elemCode=C3D10, elemLibrary=STANDARD)
    part.setElementType(regions=(part.cells,), elemTypes=(element_type,))
    part.generateMesh()

    assembly = model.rootAssembly
    assembly.DatumCsysByDefault(CARTESIAN)
    instance = assembly.Instance(name='PLATE-1', part=part, dependent=ON)
    assembly.regenerate()
    tol = max(LENGTH, WIDTH, THICKNESS) * 1.0e-5
    left_faces = instance.faces.getByBoundingBox(
        xMin=-half_l-tol, xMax=-half_l+tol,
        yMin=-half_w-tol, yMax=half_w+tol,
        zMin=-tol, zMax=THICKNESS+tol)
    right_faces = instance.faces.getByBoundingBox(
        xMin=half_l-tol, xMax=half_l+tol,
        yMin=-half_w-tol, yMax=half_w+tol,
        zMin=-tol, zMax=THICKNESS+tol)
    right_nodes = instance.nodes.getByBoundingBox(
        xMin=half_l-tol, xMax=half_l+tol,
        yMin=-half_w-tol, yMax=half_w+tol,
        zMin=-tol, zMax=THICKNESS+tol)
    roi_elements = instance.elements.getByBoundingBox(
        xMin=-2.0*HOLE_RADIUS, xMax=2.0*HOLE_RADIUS,
        yMin=-2.0*HOLE_RADIUS, yMax=2.0*HOLE_RADIUS,
        zMin=-tol, zMax=THICKNESS+tol)
    if len(left_faces) == 0 or len(right_faces) == 0 or len(right_nodes) == 0:
        raise RuntimeError('Failed to identify grip faces or load-face nodes.')
    if len(roi_elements) == 0:
        roi_elements = instance.elements

    assembly.Set(name='FIXED_FACE', faces=left_faces)
    assembly.Set(name='LOAD_FACE', faces=right_faces)
    assembly.Set(name='LOAD_FACE_NODES', nodes=right_nodes)
    assembly.Set(name='HOLE_ROI', elements=roi_elements)
    assembly.Set(name='ALL_ELEMENTS', elements=instance.elements)

    model.StaticStep(
        name='TENSION', previous='Initial', nlgeom=OFF,
        initialInc=0.02, minInc=1.0e-8, maxInc=0.05, maxNumInc=500)
    model.EncastreBC(name='FIXED_GRIP', createStepName='Initial', region=assembly.sets['FIXED_FACE'])
    model.DisplacementBC(
        name='APPLIED_DISPLACEMENT', createStepName='TENSION',
        region=assembly.sets['LOAD_FACE'], u1=DISPLACEMENT,
        u2=UNSET, u3=UNSET, ur1=UNSET, ur2=UNSET, ur3=UNSET)
    model.fieldOutputRequests['F-Output-1'].setValues(
        variables=('S', 'PE', 'PEEQ', 'U', 'RF'), frequency=1)

    cae_path = os.path.join(WORKDIR, MODEL_NAME + '.cae')
    job = mdb.Job(
        name=JOB_NAME, model=MODEL_NAME,
        description='MaterialAI 3D plate-hole acceptance',
        numCpus=CPUS, numDomains=CPUS, multiprocessingMode=DEFAULT)
    mdb.saveAs(pathName=cae_path)
    job.writeInput(consistencyChecking=OFF)
    if SUBMIT_JOB:
        job.submit(consistencyChecking=OFF)
        job.waitForCompletion()

    return {
        'ok': True,
        'created_at': datetime.now().isoformat(),
        'model_name': MODEL_NAME,
        'job_name': JOB_NAME,
        'submit_requested': SUBMIT_JOB,
        'job_status': str(getattr(job, 'status', 'NOT_SUBMITTED')),
        'cae_path': cae_path,
        'inp_path': os.path.join(WORKDIR, JOB_NAME + '.inp'),
        'odb_path': os.path.join(WORKDIR, JOB_NAME + '.odb'),
        'node_count': len(instance.nodes),
        'element_count': len(instance.elements),
        'load_face_node_count': len(right_nodes),
        'hole_roi_element_count': len(roi_elements),
        'sets': list(assembly.sets.keys()),
    }


try:
    result = build_and_run()
except Exception as exc:
    result = {
        'ok': False,
        'created_at': datetime.now().isoformat(),
        'error_type': type(exc).__name__,
        'error': safe_exception_text(exc),
        'traceback': safe_traceback_text(),
    }
    with open(SUMMARY_PATH, 'w') as handle:
        json.dump(result, handle, indent=2, sort_keys=True, ensure_ascii=True)
    raise
else:
    with open(SUMMARY_PATH, 'w') as handle:
        json.dump(result, handle, indent=2, sort_keys=True, ensure_ascii=True)
    print(json.dumps(result, indent=2, sort_keys=True))
"""
    replacements = {
        "__WORKDIR__": repr(str(run_dir)),
        "__MODEL_NAME__": repr(model_name),
        "__JOB_NAME__": repr(job_name),
        "__LENGTH__": repr(float(config.length)),
        "__WIDTH__": repr(float(config.width)),
        "__THICKNESS__": repr(float(config.thickness)),
        "__HOLE_RADIUS__": repr(float(config.hole_radius)),
        "__YOUNGS_MODULUS__": repr(float(config.youngs_modulus)),
        "__POISSON_RATIO__": repr(float(config.poisson_ratio)),
        "__YIELD_STRENGTH__": repr(float(config.yield_strength)),
        "__TANGENT_MODULUS__": repr(float(config.tangent_modulus)),
        "__PLASTIC_STRAIN_LIMIT__": repr(float(config.plastic_strain_limit)),
        "__DISPLACEMENT__": repr(float(config.displacement)),
        "__MESH_SIZE__": repr(float(config.mesh_size)),
        "__CPUS__": repr(int(config.cpus)),
        "__SUBMIT_DEFAULT__": repr(bool(config.submit_job)),
    }
    for token, value in replacements.items():
        script = script.replace(token, value)
    path.write_text(script, encoding="utf-8")


def _write_postprocess_script(
    path: Path, config: PlateHoleAcceptanceConfig, run_dir: Path
) -> None:
    job_name = f"{_safe_name(config.name)[:60]}_job"[:79]
    script = r"""# -*- coding: utf-8 -*-
from __future__ import print_function

import csv
import json
import math
import os
import traceback
from datetime import datetime

from abaqusConstants import MAGNITUDE, MISES
from odbAccess import openOdb

WORKDIR = __WORKDIR__
JOB_NAME = __JOB_NAME__
WIDTH = __WIDTH__
THICKNESS = __THICKNESS__
DISPLACEMENT = __DISPLACEMENT__
LENGTH = __LENGTH__
ODB_PATH = os.path.join(WORKDIR, JOB_NAME + '.odb')
RESULT_PATH = os.path.join(WORKDIR, 'plate_hole_results.json')
CSV_PATH = os.path.join(WORKDIR, 'plate_hole_results.csv')


def safe_exception_text(value):
    try:
        return unicode(value)
    except Exception:
        raw = str(value)
        for encoding in ('utf-8', 'gbk', 'mbcs', 'latin-1'):
            try:
                return raw.decode(encoding)
            except Exception:
                pass
        return repr(raw)


def safe_traceback_text():
    raw = traceback.format_exc()
    try:
        if isinstance(raw, unicode):
            return raw
        for encoding in ('utf-8', 'gbk', 'mbcs', 'latin-1'):
            try:
                return raw.decode(encoding)
            except Exception:
                pass
        return repr(raw)
    except Exception:
        return repr(raw)


def maximum(field, invariant=None):
    scalar = field.getScalarField(invariant=invariant) if invariant is not None else field
    best = None
    best_location = {}
    for value in scalar.values:
        try:
            number = float(value.data)
        except Exception:
            continue
        if best is None or number > best:
            best = number
            best_location = {
                'instance': str(getattr(getattr(value, 'instance', None), 'name', '')),
                'node_label': getattr(value, 'nodeLabel', None),
                'element_label': getattr(value, 'elementLabel', None),
                'integration_point': getattr(value, 'integrationPoint', None),
            }
    return best, best_location


def process():
    if not os.path.isfile(ODB_PATH):
        raise IOError('ODB does not exist: ' + ODB_PATH)
    odb = openOdb(path=ODB_PATH, readOnly=True)
    try:
        step_name = list(odb.steps.keys())[-1]
        step = odb.steps[step_name]
        frame = step.frames[-1]
        fields = frame.fieldOutputs
        root = odb.rootAssembly
        roi = root.elementSets['HOLE_ROI']
        load_nodes = root.nodeSets['LOAD_FACE_NODES']

        stress = fields['S'].getSubset(region=roi)
        max_mises, max_mises_location = maximum(stress, MISES)
        max_u, max_u_location = maximum(fields['U'], MAGNITUDE)
        peeq = fields['PEEQ'].getSubset(region=roi)
        max_peeq, max_peeq_location = maximum(peeq)
        plastic_values = []
        for value in peeq.values:
            try:
                plastic_values.append(float(value.data))
            except Exception:
                pass
        plastic_fraction = (
            float(sum(1 for value in plastic_values if value > 1.0e-10)) / len(plastic_values)
            if plastic_values else 0.0)

        rf = fields['RF'].getSubset(region=load_nodes)
        sum_rf1 = 0.0
        for value in rf.values:
            try:
                sum_rf1 += float(value.data[0])
            except Exception:
                pass
        reaction_force = abs(sum_rf1)
        gross_area = WIDTH * THICKNESS
        nominal_stress = reaction_force / gross_area if gross_area > 0.0 else None
        stress_concentration = (
            max_mises / nominal_stress
            if max_mises is not None and nominal_stress not in (None, 0.0)
            else None)
        results = {
            'odb_path': ODB_PATH,
            'step': step_name,
            'frame_index': len(step.frames) - 1,
            'frame_value': float(frame.frameValue),
            'max_mises_mpa': max_mises,
            'max_mises_location': max_mises_location,
            'max_displacement_mm': max_u,
            'max_displacement_location': max_u_location,
            'max_peeq': max_peeq,
            'max_peeq_location': max_peeq_location,
            'plastic_zone_fraction_roi': plastic_fraction,
            'sum_rf1_n': sum_rf1,
            'reaction_force_n': reaction_force,
            'gross_nominal_stress_mpa': nominal_stress,
            'stress_concentration_ratio': stress_concentration,
            'nominal_strain': DISPLACEMENT / LENGTH,
            'node_sets': list(root.nodeSets.keys()),
            'element_sets': list(root.elementSets.keys()),
        }
        payload = {
            'ok': True,
            'created_at': datetime.now().isoformat(),
            'results': results,
        }
    except Exception:
        try:
            odb.close()
        except Exception:
            pass
        raise
    try:
        odb.close()
    except Exception as exc:
        payload['odb_close_warning'] = safe_exception_text(exc)
    return payload


try:
    result = process()
except Exception as exc:
    result = {
        'ok': False,
        'created_at': datetime.now().isoformat(),
        'error_type': type(exc).__name__,
        'error': safe_exception_text(exc),
        'traceback': safe_traceback_text(),
    }
    with open(RESULT_PATH, 'w') as handle:
        json.dump(result, handle, indent=2, sort_keys=True, ensure_ascii=True)
    raise
else:
    with open(RESULT_PATH, 'w') as handle:
        json.dump(result, handle, indent=2, sort_keys=True, ensure_ascii=True)
    values = result['results'].copy()
    for key in list(values.keys()):
        if isinstance(values[key], (dict, list, tuple)):
            values[key] = json.dumps(values[key], sort_keys=True)
    with open(CSV_PATH, 'wb') as handle:
        writer = csv.DictWriter(handle, fieldnames=sorted(values.keys()))
        writer.writeheader()
        writer.writerow(values)
    print(json.dumps(result, indent=2, sort_keys=True))
"""
    replacements = {
        "__WORKDIR__": repr(str(run_dir)),
        "__JOB_NAME__": repr(job_name),
        "__WIDTH__": repr(float(config.width)),
        "__THICKNESS__": repr(float(config.thickness)),
        "__DISPLACEMENT__": repr(float(config.displacement)),
        "__LENGTH__": repr(float(config.length)),
    }
    for token, value in replacements.items():
        script = script.replace(token, value)
    path.write_text(script, encoding="utf-8")


def _write_run_script(
    path: Path, config: PlateHoleAcceptanceConfig, paths: dict[str, Path]
) -> None:
    content = f"""param([switch]$SubmitJob)
$ErrorActionPreference = 'Stop'
$env:MATERIALAI_SUBMIT_JOB = if ($SubmitJob) {{ '1' }} else {{ '0' }}
Set-Location -LiteralPath '{_ps_quote(paths['run_dir'])}'
& '{_ps_quote(Path(config.abaqus_bat))}' cae 'noGUI={_ps_quote(paths['build_script'])}'
if ($LASTEXITCODE -ne 0) {{ exit $LASTEXITCODE }}
if (Test-Path -LiteralPath '{_ps_quote(paths['odb'])}') {{
    & '{_ps_quote(Path(config.smapython))}' '{_ps_quote(paths['postprocess_script'])}'
    exit $LASTEXITCODE
}}
Write-Host 'Model prepared. Re-run with -SubmitJob to request a real Abaqus solve.'
"""
    path.write_text(content, encoding="utf-8")


def _validate_config(config: PlateHoleAcceptanceConfig) -> None:
    if not _safe_name(config.name):
        raise ValueError("算例名称至少包含一个字母或数字")
    for key in (
        "length",
        "width",
        "thickness",
        "hole_radius",
        "youngs_modulus",
        "yield_strength",
        "plastic_strain_limit",
        "displacement",
        "mesh_size",
    ):
        if float(getattr(config, key)) <= 0.0:
            raise ValueError(f"{key} 必须为正数")
    if not -1.0 < float(config.poisson_ratio) < 0.5:
        raise ValueError("poisson_ratio 必须位于 -1 与 0.5 之间")
    if float(config.tangent_modulus) < 0.0:
        raise ValueError("tangent_modulus 不能为负数")
    if float(config.hole_radius) * 2.2 >= float(config.width):
        raise ValueError("孔径过大，板宽方向未保留足够韧带")
    if float(config.mesh_size) > float(config.hole_radius):
        raise ValueError("验收模型的 mesh_size 不能大于 hole_radius")
    if int(config.cpus) < 1:
        raise ValueError("cpus 至少为 1")
    if config.backend not in {"batch", "mcp"}:
        raise ValueError("backend 只能是 batch 或 mcp")


def _engineering_validation(
    config: PlateHoleAcceptanceConfig, results: dict[str, Any]
) -> dict[str, Any]:
    checks = []
    max_mises = _number(results.get("max_mises_mpa"))
    max_u = _number(results.get("max_displacement_mm"))
    reaction = _number(results.get("reaction_force_n"))
    kt = _number(results.get("stress_concentration_ratio"))
    max_peeq = _number(results.get("max_peeq"))

    checks.append(
        _metric_check(
            "max_mises_positive", max_mises is not None and max_mises > 0.0, max_mises
        )
    )
    checks.append(
        _metric_check(
            "reaction_force_positive", reaction is not None and reaction > 0.0, reaction
        )
    )
    displacement_ok = (
        max_u is not None
        and config.displacement * 0.9 <= max_u <= config.displacement * 1.25
    )
    checks.append(_metric_check("displacement_matches_bc", displacement_ok, max_u))
    kt_ok = kt is not None and 1.0 <= kt <= 10.0
    checks.append(_metric_check("stress_concentration_sane", kt_ok, kt))
    checks.append(
        _metric_check(
            "peeq_nonnegative", max_peeq is not None and max_peeq >= 0.0, max_peeq
        )
    )
    failed = [item for item in checks if not item["passed"]]
    return {
        "status": "pass" if not failed else "warn",
        "message": (
            "工程合理性检查通过。"
            if not failed
            else f"有 {len(failed)} 项工程合理性检查需要复核。"
        ),
        "checks": checks,
    }


def _metric_check(key: str, passed: bool, value: float | None) -> dict[str, Any]:
    return {"key": key, "passed": bool(passed), "value": value}


def _artifact_paths(
    run_dir: Path, config: PlateHoleAcceptanceConfig
) -> dict[str, Path]:
    model_name = _safe_name(config.name)[:60]
    job_name = f"{model_name}_job"[:79]
    return {
        "run_dir": run_dir,
        "manifest": run_dir / "acceptance_manifest.json",
        "report": run_dir / "acceptance_report.md",
        "config": run_dir / "acceptance_config.json",
        "build_script": run_dir / "build_plate_hole.py",
        "postprocess_script": run_dir / "extract_plate_hole.py",
        "run_script": run_dir / "run_plate_hole.ps1",
        "cae": run_dir / f"{model_name}.cae",
        "inp": run_dir / f"{job_name}.inp",
        "odb": run_dir / f"{job_name}.odb",
        "sta": run_dir / f"{job_name}.sta",
        "msg": run_dir / f"{job_name}.msg",
        "dat": run_dir / f"{job_name}.dat",
        "job_log": run_dir / f"{job_name}.log",
        "build_summary": run_dir / "abaqus_build_summary.json",
        "result_json": run_dir / "plate_hole_results.json",
        "result_csv": run_dir / "plate_hole_results.csv",
        "feature_csv": run_dir / "plate_hole_features.csv",
        "build_stdout": run_dir / "build_stdout.log",
        "build_stderr": run_dir / "build_stderr.log",
        "post_stdout": run_dir / "postprocess_stdout.log",
        "post_stderr": run_dir / "postprocess_stderr.log",
    }


def _load_or_create_manifest(
    path: Path, config: PlateHoleAcceptanceConfig, run_dir: Path
) -> dict[str, Any]:
    if path.is_file():
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("schema_version") != "1.0":
            raise ValueError("Unsupported acceptance manifest schema_version")
        return payload
    now = datetime.now().isoformat(timespec="seconds")
    return {
        "schema_version": "1.0",
        "run_id": run_dir.name,
        "case_type": "abaqus_3d_plate_with_hole_tension",
        "created_at": now,
        "updated_at": now,
        "status": "prepared",
        "config": _serialize_config(config),
        "stages": {
            key: {
                "status": "pending",
                "message": "",
                "updated_at": None,
                "evidence": {},
            }
            for key in (
                "prepare",
                "diagnostics",
                "build",
                "solve",
                "postprocess",
                "engineering_validation",
                "archive",
            )
        },
        "artifacts": {},
        "execution_evidence": {},
        "results": {},
        "next_actions": [],
    }


def _set_stage(
    manifest: dict[str, Any],
    key: str,
    status: str,
    message: str,
    *,
    evidence: dict[str, Any] | None = None,
) -> None:
    if status not in STAGE_STATUSES:
        raise ValueError(f"Unsupported stage status: {status}")
    manifest.setdefault("stages", {})[key] = {
        "status": status,
        "message": message,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "evidence": evidence or {},
    }


def _sync_artifacts(manifest: dict[str, Any], paths: dict[str, Path]) -> None:
    manifest["artifacts"] = {
        key: str(path) for key, path in paths.items() if key not in {"run_dir"}
    }


def _persist(manifest: dict[str, Any], paths: dict[str, Path]) -> None:
    if manifest.get("status") not in OVERALL_STATUSES:
        raise ValueError(f"Unsupported overall status: {manifest.get('status')}")
    manifest["updated_at"] = datetime.now().isoformat(timespec="seconds")
    _sync_artifacts(manifest, paths)
    paths["manifest"].write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    paths["report"].write_text(_acceptance_report(manifest), encoding="utf-8")


def _acceptance_report(manifest: dict[str, Any]) -> str:
    stage_rows = []
    for key, stage in manifest.get("stages", {}).items():
        stage_rows.append(
            f"| `{key}` | `{stage.get('status')}` | {stage.get('message', '')} |"
        )
    results = manifest.get("results") or {}
    result_lines = (
        "\n".join(
            f"- `{key}`: `{value}`"
            for key, value in results.items()
            if not isinstance(value, (dict, list))
        )
        or "- 尚无真实 ODB 结果。"
    )
    actions = (
        "\n".join(
            f"{index}. {item}"
            for index, item in enumerate(manifest.get("next_actions") or [], 1)
        )
        or "1. 无。"
    )
    return f"""# 三维带孔板 Abaqus 验收报告

- Run ID：`{manifest.get('run_id')}`
- 总体状态：`{manifest.get('status')}`
- 更新时间：`{manifest.get('updated_at')}`
- 算例类型：`{manifest.get('case_type')}`

## 阶段状态

| 阶段 | 状态 | 结论 |
|---|---|---|
{chr(10).join(stage_rows)}

## 真实结果

{result_lines}

## 下一步

{actions}

## 证据边界

`prepared` 或 `built` 只代表文件或模型已生成；只有 `solve=pass` 且 ODB 文件存在才代表 Abaqus 已真实求解。
`engineering_validation=pass` 表示自动合理性检查通过，不替代网格收敛、材料标定和正式工程评审。
"""


def _write_feature_row(
    path: Path,
    config: PlateHoleAcceptanceConfig,
    results: dict[str, Any],
    validation: dict[str, Any],
) -> None:
    row = {
        **_engineering_config(config),
        **{
            key: value
            for key, value in results.items()
            if not isinstance(value, (dict, list))
        },
        "validation_status": validation["status"],
    }
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row.keys()))
        writer.writeheader()
        writer.writerow(row)


def _engineering_config(config: PlateHoleAcceptanceConfig) -> dict[str, Any]:
    return {
        "length_mm": float(config.length),
        "width_mm": float(config.width),
        "thickness_mm": float(config.thickness),
        "hole_radius_mm": float(config.hole_radius),
        "youngs_modulus_mpa": float(config.youngs_modulus),
        "poisson_ratio": float(config.poisson_ratio),
        "yield_strength_mpa": float(config.yield_strength),
        "tangent_modulus_mpa": float(config.tangent_modulus),
        "displacement_mm": float(config.displacement),
        "mesh_size_mm": float(config.mesh_size),
    }


def _solver_evidence(paths: dict[str, Path]) -> dict[str, Any]:
    return _file_evidence(
        paths["odb"], paths["sta"], paths["msg"], paths["dat"], paths["job_log"]
    )


def _file_evidence(*paths: Path) -> dict[str, Any]:
    return {
        path.name: {
            "path": str(path),
            "exists": path.is_file(),
            "size_bytes": path.stat().st_size if path.is_file() else 0,
        }
        for path in paths
    }


def _blocked(
    run_dir: Path,
    paths: dict[str, Path],
    manifest: dict[str, Any],
    message: str,
) -> PlateHoleAcceptanceResult:
    _set_stage(manifest, "build", "blocked", message)
    manifest["status"] = "blocked"
    manifest["next_actions"] = [message]
    _persist(manifest, paths)
    return _result(run_dir, paths, manifest)


def _result(
    run_dir: Path, paths: dict[str, Path], manifest: dict[str, Any]
) -> PlateHoleAcceptanceResult:
    return PlateHoleAcceptanceResult(
        run_dir=run_dir,
        status=manifest["status"],
        manifest_path=paths["manifest"],
        report_path=paths["report"],
        config_path=paths["config"],
        build_script_path=paths["build_script"],
        postprocess_script_path=paths["postprocess_script"],
        run_script_path=paths["run_script"],
        manifest=manifest,
    )


def _resolve_run_dir(
    config: PlateHoleAcceptanceConfig, run_dir: Path | str | None
) -> Path:
    if run_dir is not None:
        return Path(run_dir).expanduser().resolve()
    root = Path(config.output_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    stem = (
        datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3] + "_" + _safe_name(config.name)
    )
    candidate = root / stem
    index = 2
    while candidate.exists():
        candidate = root / f"{stem}_{index}"
        index += 1
    return candidate


def _write_config(path: Path, config: PlateHoleAcceptanceConfig) -> None:
    path.write_text(
        json.dumps(_serialize_config(config), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _serialize_config(config: PlateHoleAcceptanceConfig) -> dict[str, Any]:
    return {
        key: str(value) if isinstance(value, Path) else value
        for key, value in asdict(config).items()
    }


def _mcp_config(config: PlateHoleAcceptanceConfig) -> AbaqusMcpConfig:
    return AbaqusMcpConfig(
        host=config.mcp_host,
        port=int(config.mcp_port),
        timeout_seconds=float(config.mcp_timeout_seconds),
    )


def _safe_name(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_]+", "_", str(value).strip()).strip("_")
    return safe or "plate_hole_acceptance"


def _ps_quote(path: Path) -> str:
    return str(Path(path).expanduser().resolve()).replace("'", "''")


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Prepare or run the 3D Abaqus plate-hole acceptance workflow."
    )
    parser.add_argument("--name", default="plate_hole_acceptance")
    parser.add_argument("--output-root", default=str(ACCEPTANCE_ROOT))
    parser.add_argument("--resume")
    parser.add_argument("--backend", choices=("batch", "mcp"), default="batch")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--submit-job", action="store_true")
    parser.add_argument("--archive-case", action="store_true")
    parser.add_argument("--length", type=float, default=100.0)
    parser.add_argument("--width", type=float, default=50.0)
    parser.add_argument("--thickness", type=float, default=5.0)
    parser.add_argument("--hole-radius", type=float, default=5.0)
    parser.add_argument("--youngs-modulus", type=float, default=210_000.0)
    parser.add_argument("--poisson-ratio", type=float, default=0.30)
    parser.add_argument("--yield-strength", type=float, default=250.0)
    parser.add_argument("--tangent-modulus", type=float, default=1_000.0)
    parser.add_argument("--displacement", type=float, default=0.35)
    parser.add_argument("--mesh-size", type=float, default=2.5)
    parser.add_argument("--cpus", type=int, default=4)
    parser.add_argument("--timeout", type=float, default=3_600.0)
    args = parser.parse_args(argv)

    if args.resume:
        result = resume_plate_hole_acceptance(
            args.resume,
            execute=args.execute,
            submit_job=args.submit_job if args.execute else None,
            archive_case=args.archive_case if args.execute else None,
            backend=args.backend,
        )
    else:
        result = run_plate_hole_acceptance(
            PlateHoleAcceptanceConfig(
                name=args.name,
                output_root=args.output_root,
                length=args.length,
                width=args.width,
                thickness=args.thickness,
                hole_radius=args.hole_radius,
                youngs_modulus=args.youngs_modulus,
                poisson_ratio=args.poisson_ratio,
                yield_strength=args.yield_strength,
                tangent_modulus=args.tangent_modulus,
                displacement=args.displacement,
                mesh_size=args.mesh_size,
                cpus=args.cpus,
                backend=args.backend,
                submit_job=args.submit_job,
                archive_case=args.archive_case,
                timeout_seconds=args.timeout,
            ),
            execute=args.execute,
        )
    print(
        json.dumps(
            {"status": result.status, "run_dir": str(result.run_dir)}, ensure_ascii=True
        )
    )
    return 1 if result.status in {"failed", "blocked"} else 0


if __name__ == "__main__":
    raise SystemExit(main())
