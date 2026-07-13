"""Composite micro-to-macro workflow for a 3D Abaqus plate-with-hole case."""

from __future__ import annotations

import csv
import json
import math
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from material_ai_workbench.config import ABAQUS_BAT as DEFAULT_ABAQUS_BAT
from material_ai_workbench.config import ABAQUS_SMAPYTHON as DEFAULT_SMAPYTHON
from material_ai_workbench.config import COMPOSITE_ROOT


@dataclass
class CompositePlateConfig:
    name: str = "ud_composite_plate_hole"
    output_dir: Path = COMPOSITE_ROOT
    fiber_volume_fraction: float = 0.55
    fiber_e: float = 230_000.0
    fiber_nu: float = 0.20
    matrix_e: float = 3_500.0
    matrix_nu: float = 0.35
    interface_efficiency: float = 0.92
    interface_thickness_ratio: float = 0.18
    length: float = 120.0
    width: float = 40.0
    thickness: float = 2.0
    hole_radius: float = 5.0
    applied_strain: float = 0.003
    mesh_size: float = 2.0
    n_preview_fibers: int = 80
    micro_fiber_count: int = 16
    micro_length: float = 1.0
    micro_width: float = 1.0
    micro_height: float = 1.0
    micro_nx: int = 8
    micro_ny: int = 18
    micro_nz: int = 18
    micro_load_strain: float = 0.001
    random_seed: int = 7
    abaqus_bat: Path = DEFAULT_ABAQUS_BAT
    smapython: Path = DEFAULT_SMAPYTHON
    cpus: int = 4
    run_pbc_homogenization: bool = False
    use_abaqus_homogenization: bool = False
    run_abaqus: bool = False
    submit_job: bool = False
    # Fiber orientation & geometry (Task 1)
    fiber_orientation_theta_deg: float = 0.0
    fiber_orientation_phi_deg: float = 0.0
    fiber_orientation_spread_deg: float = 8.0
    fiber_length_normalized: float = 1.2
    fiber_length_std: float = 0.08
    fiber_diameter_normalized: float | None = None
    fiber_geometry_mode: str = "oriented_cylinders"  # "ud", "oriented_cylinders", "chopped"


@dataclass
class CompositePlateResult:
    run_dir: Path
    manifest_path: Path
    report_path: Path
    effective_properties_path: Path
    material_card_path: Path
    micro_rve_inp_path: Path
    micro_phase_map_path: Path
    micro_rve_layout_path: Path
    micro_rve_run_script_path: Path
    micro_pbc_job_dir: Path
    micro_pbc_plan_path: Path
    micro_pbc_run_script_path: Path
    micro_pbc_postprocess_script_path: Path
    abaqus_script_path: Path
    postprocess_script_path: Path
    run_script_path: Path
    microstructure_png: Path
    plate_preview_png: Path
    dataset_csv: Path
    effective_properties: dict[str, float]
    engineering_estimates: dict[str, float]
    microstructure_metrics: dict[str, float]
    abaqus_status: str


def run_composite_plate_workflow(config: CompositePlateConfig) -> CompositePlateResult:
    _validate_config(config)
    run_dir = _prepare_run_dir(config)
    estimated_props = compute_effective_ud_properties(config)
    props = dict(estimated_props)
    estimates = estimate_plate_response(config, props)
    pylabfea_summary = build_pylabfea_material_summary(config, props)

    micro_png = run_dir / "figures" / "micro_rve_preview.png"
    plate_png = run_dir / "figures" / "plate_with_hole_preview.png"
    micro_inp = run_dir / "micro_rve" / "micro_rve_voxel.inp"
    micro_phase_map = run_dir / "micro_rve" / "phase_map.csv"
    micro_layout = run_dir / "micro_rve" / "fiber_layout.json"
    micro_run_script = run_dir / "micro_rve" / "run_micro_rve.ps1"
    micro_pbc_dir = run_dir / "micro_rve" / "pbc_jobs"
    micro_pbc_plan = run_dir / "micro_rve" / "pbc_loadcase_plan.json"
    micro_pbc_run_script = run_dir / "micro_rve" / "run_pbc_jobs.ps1"
    micro_pbc_post_script = run_dir / "micro_rve" / "extract_rve_effective_stiffness.py"
    material_card = run_dir / "abaqus" / "effective_orthotropic_material.inp"
    abaqus_script = run_dir / "abaqus" / "build_plate_with_hole.py"
    post_script = run_dir / "abaqus" / "extract_plate_results.py"
    run_script = run_dir / "run_abaqus_plate.ps1"
    props_json = run_dir / "effective_properties.json"
    pylabfea_json = run_dir / "pylabfea_material_summary.json"
    dataset_csv = run_dir / "composite_plate_dataset_row.csv"
    report_path = run_dir / "composite_plate_report.md"
    manifest_path = run_dir / "manifest.json"

    for folder in (run_dir / "figures", run_dir / "abaqus", run_dir / "data", run_dir / "micro_rve", micro_pbc_dir):
        folder.mkdir(parents=True, exist_ok=True)

    layout = generate_fiber_layout(config)
    micro_metrics = write_microstructure_preview(micro_png, config, layout)
    micro_metrics.update(write_micro_rve_inp(micro_inp, micro_phase_map, config, layout))
    micro_layout.write_text(json.dumps(layout, indent=2), encoding="utf-8")
    write_micro_rve_run_script(micro_run_script, config, micro_inp, run_dir)
    pbc_jobs = write_micro_rve_pbc_jobs(micro_pbc_dir, config, layout)
    write_micro_pbc_plan(micro_pbc_plan, config, pbc_jobs)
    write_micro_pbc_run_script(micro_pbc_run_script, config, micro_pbc_dir, pbc_jobs)
    write_micro_pbc_postprocess_script(micro_pbc_post_script, config, micro_pbc_dir)
    pbc_summary: dict[str, Any] = {}
    if config.run_pbc_homogenization:
        pbc_summary = run_micro_rve_pbc_homogenization(config, micro_pbc_dir, micro_pbc_post_script, run_dir)
        pbc_props = pbc_summary.get("homogenized_properties", {}) if isinstance(pbc_summary, dict) else {}
        if config.use_abaqus_homogenization and pbc_props:
            props = _merge_homogenized_properties(props, pbc_props)
            estimates = estimate_plate_response(config, props)
            pylabfea_summary = build_pylabfea_material_summary(config, props)
    write_plate_preview(plate_png, config, estimates)
    write_material_card(material_card, props)
    write_abaqus_build_script(abaqus_script, config, props, run_dir)
    write_odb_postprocess_script(post_script, config, run_dir)
    write_run_script(run_script, config, abaqus_script, post_script, run_dir)
    props_json.write_text(json.dumps(props, indent=2), encoding="utf-8")
    pylabfea_json.write_text(json.dumps(pylabfea_summary, indent=2), encoding="utf-8")
    write_dataset_row(
        dataset_csv,
        config,
        props,
        estimates,
        micro_metrics,
        estimated_props=estimated_props,
        pbc_summary=pbc_summary,
    )

    abaqus_status = "generated"
    if config.run_abaqus:
        abaqus_status = run_abaqus_build(config, abaqus_script, post_script, run_dir)
    plate_results = _load_json_if_exists(run_dir / "plate_odb_summary.json")

    manifest = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "workflow": "composite_micro_to_macro_plate_hole",
        "config": _json_ready(asdict(config)),
        "estimated_effective_properties": estimated_props,
        "effective_properties": props,
        "pbc_homogenization": pbc_summary,
        "microstructure_metrics": micro_metrics,
        "engineering_estimates": estimates,
        "plate_results": plate_results,
        "paths": {
            "run_dir": str(run_dir),
            "report": str(report_path),
            "effective_properties": str(props_json),
            "pylabfea_material_summary": str(pylabfea_json),
            "micro_rve_inp": str(micro_inp),
            "micro_phase_map": str(micro_phase_map),
            "micro_rve_layout": str(micro_layout),
            "micro_rve_run_script": str(micro_run_script),
            "micro_pbc_job_dir": str(micro_pbc_dir),
            "micro_pbc_plan": str(micro_pbc_plan),
            "micro_pbc_run_script": str(micro_pbc_run_script),
            "micro_pbc_postprocess_script": str(micro_pbc_post_script),
            "micro_pbc_jobs": [str(path) for path in pbc_jobs.values()],
            "material_card": str(material_card),
            "abaqus_script": str(abaqus_script),
            "postprocess_script": str(post_script),
            "run_script": str(run_script),
            "microstructure_png": str(micro_png),
            "plate_preview_png": str(plate_png),
            "dataset_csv": str(dataset_csv),
            "plate_odb_summary": str(run_dir / "plate_odb_summary.json"),
            "plate_odb_summary_csv": str(run_dir / "plate_odb_summary.csv"),
            "abaqus_plate_results": str(run_dir / "abaqus" / "plate_results.json"),
            "abaqus_plate_results_csv": str(run_dir / "abaqus" / "plate_results.csv"),
        },
        "pylabfea_material_summary": pylabfea_summary,
        "abaqus_status": abaqus_status,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    report_path.write_text(_markdown_report(manifest), encoding="utf-8")

    return CompositePlateResult(
        run_dir=run_dir,
        manifest_path=manifest_path,
        report_path=report_path,
        effective_properties_path=props_json,
        material_card_path=material_card,
        micro_rve_inp_path=micro_inp,
        micro_phase_map_path=micro_phase_map,
        micro_rve_layout_path=micro_layout,
        micro_rve_run_script_path=micro_run_script,
        micro_pbc_job_dir=micro_pbc_dir,
        micro_pbc_plan_path=micro_pbc_plan,
        micro_pbc_run_script_path=micro_pbc_run_script,
        micro_pbc_postprocess_script_path=micro_pbc_post_script,
        abaqus_script_path=abaqus_script,
        postprocess_script_path=post_script,
        run_script_path=run_script,
        microstructure_png=micro_png,
        plate_preview_png=plate_png,
        dataset_csv=dataset_csv,
        effective_properties=props,
        engineering_estimates=estimates,
        microstructure_metrics=micro_metrics,
        abaqus_status=abaqus_status,
    )


def compute_effective_ud_properties(config: CompositePlateConfig) -> dict[str, float]:
    vf = config.fiber_volume_fraction
    vm = 1.0 - vf
    ef = config.fiber_e
    em = config.matrix_e
    nuf = config.fiber_nu
    num = config.matrix_nu
    eta = config.interface_efficiency

    gf = ef / (2.0 * (1.0 + nuf))
    gm = em / (2.0 * (1.0 + num))
    e1 = eta * (vf * ef + vm * em)
    e2 = eta / (vf / ef + vm / em)
    e3 = e2
    g12 = eta / (vf / gf + vm / gm)
    g13 = g12
    nu12 = min(0.49, vf * nuf + vm * num)
    nu13 = nu12
    nu23 = min(0.49, num * vm + nuf * vf * 0.75)
    g23 = e2 / (2.0 * (1.0 + nu23))

    return {
        "E1": float(e1),
        "E2": float(e2),
        "E3": float(e3),
        "nu12": float(nu12),
        "nu13": float(nu13),
        "nu23": float(nu23),
        "G12": float(g12),
        "G13": float(g13),
        "G23": float(g23),
        "fiber_volume_fraction": float(vf),
        "matrix_volume_fraction": float(vm),
        "fiber_shear_modulus": float(gf),
        "matrix_shear_modulus": float(gm),
    }


def build_pylabfea_material_summary(config: CompositePlateConfig, props: dict[str, float]) -> dict[str, Any]:
    interface_e, interface_nu = _interface_elastic_constants(config)
    phase_inputs = {
        "fiber": {"E": config.fiber_e, "nu": config.fiber_nu},
        "interface": {"E": interface_e, "nu": interface_nu},
        "matrix": {"E": config.matrix_e, "nu": config.matrix_nu},
    }
    try:
        import pylabfea as FE

        phase_materials: dict[str, dict[str, Any]] = {}
        for phase_name, values in phase_inputs.items():
            material = FE.Material(name=f"{phase_name}_phase")
            material.elasticity(E=float(values["E"]), nu=float(values["nu"]))
            phase_materials[phase_name] = {
                "name": material.name,
                "E": float(material.E),
                "nu": float(material.nu),
                "C11": float(material.C11),
                "C12": float(material.C12),
                "C44": float(material.C44),
                "stiffness_trace": float(np.trace(material.CV)),
            }
        return {
            "status": "ok",
            "source": "pylabfea.Material.elasticity",
            "purpose": "track constituent phase material definitions before ML constitutive training",
            "phase_materials": phase_materials,
            "effective_label_interface": {
                key: float(props[key])
                for key in ("E1", "E2", "E3", "nu12", "nu13", "nu23", "G12", "G13", "G23")
            },
        }
    except Exception as exc:
        return {
            "status": "unavailable",
            "source": "pylabfea.Material.elasticity",
            "error": str(exc),
            "phase_inputs": phase_inputs,
        }


def estimate_plate_response(config: CompositePlateConfig, props: dict[str, float]) -> dict[str, float]:
    diameter = 2.0 * config.hole_radius
    width_ratio = diameter / config.width
    kt = 3.0 - 3.14 * width_ratio + 3.667 * width_ratio**2 - 1.527 * width_ratio**3
    kt = max(1.0, kt)
    nominal_stress = props["E1"] * config.applied_strain
    max_stress = nominal_stress * kt
    displacement = config.applied_strain * config.length
    net_area = (config.width - diameter) * config.thickness
    gross_area = config.width * config.thickness
    net_force = nominal_stress * net_area
    gross_force = nominal_stress * gross_area
    return {
        "hole_diameter": float(diameter),
        "diameter_width_ratio": float(width_ratio),
        "stress_concentration_factor_estimate": float(kt),
        "nominal_axial_stress_mpa": float(nominal_stress),
        "max_stress_near_hole_estimate_mpa": float(max_stress),
        "right_edge_displacement": float(displacement),
        "net_section_area": float(net_area),
        "gross_section_area": float(gross_area),
        "net_section_force_n": float(net_force),
        "gross_section_force_n": float(gross_force),
    }


def list_composite_runs(root: Path = COMPOSITE_ROOT) -> list[Path]:
    if not root.exists():
        return []
    return sorted(
        [path for path in root.iterdir() if path.is_dir() and (path / "manifest.json").exists()],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )


def load_composite_manifest(run_dir: Path | str) -> dict[str, Any]:
    return json.loads((Path(run_dir) / "manifest.json").read_text(encoding="utf-8"))


def _fiber_direction(theta_deg: float, phi_deg: float) -> tuple[float, float, float]:
    """Unit vector from spherical angles (degrees). theta=0, phi=0 = global X."""
    theta = math.radians(theta_deg)
    phi = math.radians(phi_deg)
    return (math.cos(phi) * math.cos(theta), math.cos(phi) * math.sin(theta), math.sin(phi))


def _orientation_tensor(directions: list[tuple[float, float, float]]) -> dict[str, float]:
    """Compute a11, a22, a33, a12 from a list of unit direction vectors."""
    n = len(directions)
    if n == 0:
        return {"a11": 1.0, "a22": 0.0, "a33": 0.0, "a12": 0.0}
    a11 = sum(d[0]**2 for d in directions) / n
    a22 = sum(d[1]**2 for d in directions) / n
    a33 = sum(d[2]**2 for d in directions) / n
    a12 = sum(d[0] * d[1] for d in directions) / n
    return {"a11": float(a11), "a22": float(a22), "a33": float(a33), "a12": float(a12)}


def _point_to_segment_dist_sq(px: float, py: float, pz: float,
                               sx: float, sy: float, sz: float,
                               ex: float, ey: float, ez: float) -> float:
    """Squared distance from point to line segment in 3D."""
    dx, dy, dz = ex - sx, ey - sy, ez - sz
    seg_len_sq = dx*dx + dy*dy + dz*dz
    if seg_len_sq < 1e-16:
        return (px-sx)**2 + (py-sy)**2 + (pz-sz)**2
    t = max(0.0, min(1.0, ((px-sx)*dx + (py-sy)*dy + (pz-sz)*dz) / seg_len_sq))
    nx, ny, nz = sx + t*dx - px, sy + t*dy - py, sz + t*dz - pz
    return nx*nx + ny*ny + nz*nz


def distance_point_to_segment(
    point_xyz: tuple[float, float, float],
    start_xyz: tuple[float, float, float] | list[float],
    end_xyz: tuple[float, float, float] | list[float],
) -> float:
    """Return the Euclidean distance from a point to a finite 3D segment."""

    return math.sqrt(
        _point_to_segment_dist_sq(*point_xyz, *start_xyz, *end_xyz)
    )


def classify_voxel_phase(
    point_xyz: tuple[float, float, float],
    fibers: list[dict[str, Any]],
    fiber_radius: float,
    interface_radius: float,
) -> str:
    """Classify a voxel center using the same oriented fiber geometry as the UI."""

    phase_code = _classify_voxel(point_xyz, fibers, fiber_radius, interface_radius)
    return {0: "matrix", 1: "interface", 2: "fiber"}[phase_code]


def _classify_voxel(p: tuple[float,float,float],
                    fibers_data: list[dict], fiber_r: float,
                    interface_r: float) -> int:
    """0=matrix, 1=interface, 2=fiber."""
    best = float("inf")
    for f in fibers_data:
        d2 = _point_to_segment_dist_sq(*p, *f["start"], *f["end"])
        if d2 < best:
            best = d2
    if best <= fiber_r**2:
        return 2
    if best <= interface_r**2:
        return 1
    return 0


def generate_fiber_layout(config: CompositePlateConfig) -> dict[str, Any]:
    """Generate 3D oriented fiber segments with angles, orientation tensor, and Vf calibration."""
    rng = np.random.default_rng(config.random_seed)
    target_vf = float(config.fiber_volume_fraction)
    n_fibers = max(1, int(config.micro_fiber_count))
    theta_mean = float(config.fiber_orientation_theta_deg)
    phi_mean = float(config.fiber_orientation_phi_deg)
    spread = float(config.fiber_orientation_spread_deg)
    geom_mode = config.fiber_geometry_mode or "oriented_cylinders"

    # Compute fiber radius: from diameter if given, else from Vf calibration
    radius = float(config.fiber_diameter_normalized or 0) / 2.0
    if radius <= 0:
        # Estimate: Vf = n * pi * r^2 * length / volume, volume = 1.0
        fl = float(config.fiber_length_normalized)
        radius = math.sqrt(target_vf / (math.pi * n_fibers * fl))
        radius = min(radius, 0.12)
    interface_r = radius * (1.0 + float(config.interface_thickness_ratio))

    # Generate fiber segments
    fibers: list[dict[str, Any]] = []
    directions: list[tuple[float, float, float]] = []
    fl_mean = float(config.fiber_length_normalized)
    fl_std = float(config.fiber_length_std)

    for i in range(n_fibers):
        theta = rng.normal(theta_mean, spread)
        phi = rng.normal(phi_mean, max(spread * 0.3, 0.5))
        dx, dy, dz = _fiber_direction(theta, phi)
        directions.append((dx, dy, dz))
        fl = max(0.3, rng.normal(fl_mean, fl_std))
        # Place center randomly in the unit cube
        cx, cy, cz = rng.uniform(0.0, 1.0, 3)
        fibers.append({
            "id": i + 1,
            "center": [float(cx), float(cy), float(cz)],
            "start": [float(cx - 0.5*fl*dx), float(cy - 0.5*fl*dy), float(cz - 0.5*fl*dz)],
            "end":   [float(cx + 0.5*fl*dx), float(cy + 0.5*fl*dy), float(cz + 0.5*fl*dz)],
            "direction": [float(dx), float(dy), float(dz)],
            "theta_deg": float(theta), "phi_deg": float(phi),
            "length": float(fl),
            "radius": float(radius),
            "interface_radius": float(interface_r),
        })

    # Voxel calibration with iterative radius adjustment for Vf accuracy
    nx, ny, nz = int(config.micro_nx), int(config.micro_ny), int(config.micro_nz)
    max_iters = 20
    best_radius = radius
    best_vf = 0.0
    lo, hi = radius * 0.3, radius * 3.0
    for _ in range(max_iters):
        mid = (lo + hi) / 2.0
        phase = np.zeros((nx, ny, nz), dtype=np.uint8)
        for ix in range(nx):
            for iy in range(ny):
                for iz in range(nz):
                    p = ((ix+0.5)/nx, (iy+0.5)/ny, (iz+0.5)/nz)
                    phase[ix,iy,iz] = _classify_voxel(p, fibers, mid, mid * (1.0 + float(config.interface_thickness_ratio)))
        test_vf = float(np.sum(phase == 2) / phase.size)
        if abs(test_vf - target_vf) < abs(best_vf - target_vf):
            best_vf, best_radius = test_vf, mid
        if test_vf < target_vf:
            lo = mid
        else:
            hi = mid
        if abs(test_vf - target_vf) < 0.005:
            break
    radius = best_radius
    interface_r = radius * (1.0 + float(config.interface_thickness_ratio))
    # Final classification with best radius
    phase = np.zeros((nx, ny, nz), dtype=np.uint8)
    for ix in range(nx):
        for iy in range(ny):
            for iz in range(nz):
                p = ((ix+0.5)/nx, (iy+0.5)/ny, (iz+0.5)/nz)
                phase[ix,iy,iz] = _classify_voxel(p, fibers, radius, interface_r)
    actual_vf = float(np.sum(phase == 2) / phase.size)
    actual_vi = float(np.sum(phase == 1) / phase.size)
    actual_vm = float(np.sum(phase == 0) / phase.size)
    # Update fiber radius and interface radius in fiber records
    for f in fibers:
        f["radius"] = float(radius)
        f["interface_radius"] = float(interface_r)

    orientation = _orientation_tensor(directions)
    # Legacy compat
    centers_legacy = [{"y": float(f["center"][1]), "z": float(f["center"][2])} for f in fibers]

    return {
        "coordinate_system": "unit_cube_xyz",
        "fiber_geometry_mode": geom_mode,
        "fiber_radius_normalized": float(radius),
        "interface_radius_normalized": float(interface_r),
        "target_vf": target_vf,
        "actual_vf": float(actual_vf),
        "actual_vf_source": "voxel_phase_fraction_3d_segments",
        "interface_vf": float(actual_vi),
        "matrix_vf": float(actual_vm),
        "target_vf_error": float(actual_vf - target_vf),
        "preview_vf": float(actual_vf),
        "orientation_tensor": orientation,
        "fiber_count": n_fibers,
        "centers": centers_legacy,
        "fibers": fibers,
    }


def _calibrate_fiber_radius_to_voxels(
    centers: list[tuple[float, float]],
    max_radius: float,
    target_vf: float,
    config: CompositePlateConfig,
) -> tuple[float, float]:
    """Choose the radius that gives the closest voxelized fiber fraction."""

    ny = int(config.micro_ny)
    nz = int(config.micro_nz)
    if ny <= 0 or nz <= 0:
        return 0.0, 0.0
    distances: list[float] = []
    for j in range(ny):
        cy = (j + 0.5) / ny
        for k in range(nz):
            cz = (k + 0.5) / nz
            distances.append(math.sqrt(min((cy - fy) ** 2 + (cz - fz) ** 2 for fy, fz in centers)))
    candidate_radii = {0.0, float(max_radius)}
    candidate_radii.update(min(float(max_radius), value) for value in distances if value <= max_radius)

    best_radius = 0.0
    best_vf = 0.0
    best_error = float("inf")
    for radius in sorted(candidate_radii):
        vf = _fiber_voxel_fraction(centers, radius, config)
        error = abs(vf - target_vf)
        if error < best_error or (math.isclose(error, best_error) and radius < best_radius):
            best_radius = float(radius)
            best_vf = float(vf)
            best_error = float(error)
    return best_radius, best_vf


def _regular_fiber_centers(grid_n: int) -> list[tuple[float, float]]:
    spacing = 1.0 / grid_n
    return [((iy + 0.5) * spacing, (iz + 0.5) * spacing) for iy in range(grid_n) for iz in range(grid_n)]


def _fiber_voxel_fraction(centers: list[tuple[float, float]], radius: float, config: CompositePlateConfig) -> float:
    ny = int(config.micro_ny)
    nz = int(config.micro_nz)
    if ny <= 0 or nz <= 0:
        return 0.0
    radius2 = float(radius) ** 2
    count = 0
    for j in range(ny):
        cy = (j + 0.5) / ny
        for k in range(nz):
            cz = (k + 0.5) / nz
            if min((cy - fy) ** 2 + (cz - fz) ** 2 for fy, fz in centers) <= radius2:
                count += 1
    return float(count / (ny * nz))


def _preview_font() -> ImageFont.ImageFont:
    return ImageFont.load_default()


def _draw_centered_text(
    draw: ImageDraw.ImageDraw,
    center: tuple[int | float, int | float],
    text: str,
    font: ImageFont.ImageFont,
    *,
    fill: str,
) -> None:
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    draw.text((center[0] - text_width / 2, center[1] - text_height / 2), text, font=font, fill=fill)


def _draw_arrow(
    draw: ImageDraw.ImageDraw,
    start: tuple[float, float],
    end: tuple[float, float],
    fill: str,
    *,
    width: int = 8,
) -> None:
    draw.line((*start, *end), fill=fill, width=width)
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length = math.hypot(dx, dy)
    if length <= 1e-9:
        return
    ux = dx / length
    uy = dy / length
    px = -uy
    py = ux
    head_length = 24.0
    head_width = 18.0
    base_x = end[0] - ux * head_length
    base_y = end[1] - uy * head_length
    points = [
        end,
        (base_x + px * head_width / 2.0, base_y + py * head_width / 2.0),
        (base_x - px * head_width / 2.0, base_y - py * head_width / 2.0),
    ]
    draw.polygon(points, fill=fill)


def _clip_segment_to_unit_square(
    start: tuple[float, float],
    end: tuple[float, float],
) -> tuple[tuple[float, float], tuple[float, float]] | None:
    """Clip a 2D segment to the unit square with the Liang-Barsky algorithm."""

    x0, y0 = start
    x1, y1 = end
    dx = x1 - x0
    dy = y1 - y0
    lower = 0.0
    upper = 1.0
    for p_value, q_value in ((-dx, x0), (dx, 1.0 - x0), (-dy, y0), (dy, 1.0 - y0)):
        if math.isclose(p_value, 0.0, abs_tol=1e-12):
            if q_value < 0.0:
                return None
            continue
        ratio = q_value / p_value
        if p_value < 0.0:
            lower = max(lower, ratio)
        else:
            upper = min(upper, ratio)
        if lower > upper:
            return None
    return (
        (x0 + lower * dx, y0 + lower * dy),
        (x0 + upper * dx, y0 + upper * dy),
    )


def write_microstructure_preview(
    path: Path,
    config: CompositePlateConfig,
    layout: dict[str, Any],
) -> dict[str, Any]:
    fibers = layout.get("fibers", [])
    radius = float(layout["fiber_radius_normalized"])
    interface_radius = float(
        layout.get(
            "interface_radius_normalized",
            radius * (1.0 + float(config.interface_thickness_ratio)),
        )
    )

    size = 840
    margin = 70
    scale = size - 2 * margin
    image = Image.new("RGB", (size, size), "#eef2f3")
    draw = ImageDraw.Draw(image)
    font = _preview_font()
    title = "Oriented fiber RVE projection (schematic XY plane)"
    _draw_centered_text(draw, (size // 2, 25), title, font, fill="#17202a")
    rve_layer = Image.new("RGB", (scale, scale), "#f8faf9")
    rve_draw = ImageDraw.Draw(rve_layer)

    def point(x_value: float, y_value: float) -> tuple[float, float]:
        return (x_value * scale, (1.0 - y_value) * scale)

    physical_interface_width = max(3, int(round(2.0 * interface_radius * scale)))
    physical_fiber_width = max(2, int(round(2.0 * radius * scale)))
    readable_fiber_width = max(8, int(round(80.0 / math.sqrt(max(1, len(fibers))))))
    fiber_width = min(physical_fiber_width, readable_fiber_width)
    interface_width = min(physical_interface_width, fiber_width + max(5, fiber_width // 3))
    for fiber in fibers:
        start = fiber["start"]
        end = fiber["end"]
        clipped = _clip_segment_to_unit_square(
            (float(start[0]), float(start[1])),
            (float(end[0]), float(end[1])),
        )
        if clipped is None:
            continue
        start_px = point(*clipped[0])
        end_px = point(*clipped[1])
        rve_draw.line((*start_px, *end_px), fill="#d89b64", width=interface_width)
        rve_draw.line((*start_px, *end_px), fill="#2563a6", width=fiber_width)

    image.paste(rve_layer, (margin, margin))
    draw.rectangle((margin, margin, size - margin, size - margin), outline="#4b5563", width=3)

    _draw_arrow(draw, (margin + 18, size - margin - 18), (margin + 90, size - margin - 18), "#374151", width=4)
    _draw_arrow(draw, (margin + 18, size - margin - 18), (margin + 18, size - margin - 90), "#374151", width=4)
    draw.text((margin + 96, size - margin - 27), "X", font=font, fill="#374151")
    draw.text((margin + 9, size - margin - 106), "Y", font=font, fill="#374151")
    annotation = (
        f"theta={config.fiber_orientation_theta_deg:.1f} deg   "
        f"spread={config.fiber_orientation_spread_deg:.1f} deg   "
        f"actual Vf={float(layout['actual_vf']):.3f}"
    )
    _draw_centered_text(draw, (size // 2, size - 28), annotation, font, fill="#17202a")

    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)

    return {
        "fiber_count_preview": float(len(fibers)),
        "interface_thickness_ratio": float(config.interface_thickness_ratio),
        "interface_radius_normalized": float(interface_radius),
        "target_vf": float(layout["target_vf"]),
        "actual_vf": float(layout["actual_vf"]),
        "preview_vf": float(layout["preview_vf"]),
        "placement_attempts": float(layout.get("placement_attempts", 0)),
        "micro_voxel_elements": float(config.micro_nx * config.micro_ny * config.micro_nz),
        "fiber_radius_normalized": float(layout.get("fiber_radius_normalized", radius)),
        "fiber_length_normalized": float(config.fiber_length_normalized),
        "fiber_orientation_theta_deg": float(config.fiber_orientation_theta_deg),
        "fiber_orientation_spread_deg": float(config.fiber_orientation_spread_deg),
        "orientation_tensor": layout.get("orientation_tensor", {}),
    }


def write_micro_rve_inp(
    path: Path,
    phase_map_path: Path,
    config: CompositePlateConfig,
    layout: dict[str, Any],
) -> dict[str, float]:
    nx = int(config.micro_nx)
    ny = int(config.micro_ny)
    nz = int(config.micro_nz)
    lx = float(config.micro_length)
    ly = float(config.micro_width)
    lz = float(config.micro_height)
    dx = lx / nx
    dy = ly / ny
    dz = lz / nz
    radius = float(layout["fiber_radius_normalized"])
    interface_radius = radius * (1.0 + float(config.interface_thickness_ratio))
    fibers_data = layout.get("fibers", [])
    if not fibers_data:
        # Fallback: use legacy centers
        centers = [(item["y"], item["z"]) for item in layout.get("centers", [])]
        fibers_data = [{"start": (0.0, fy, fz), "end": (1.0, fy, fz)}
                       for fy, fz in centers]

    fiber_elements: list[int] = []
    interface_elements: list[int] = []
    matrix_elements: list[int] = []
    phase_rows: list[dict[str, Any]] = []

    def node_id(i: int, j: int, k: int) -> int:
        return 1 + i * (ny + 1) * (nz + 1) + j * (nz + 1) + k

    heading = (
        "** Oriented 3D fiber RVE generated by MaterialAI Workbench"
        if layout.get("fibers") else
        "** Explicit three-phase micro-scale voxel RVE generated by MaterialAI Workbench"
    )
    lines: list[str] = ["*Heading", heading, "*Node"]
    for i in range(nx + 1):
        for j in range(ny + 1):
            for k in range(nz + 1):
                lines.append(f"{node_id(i, j, k)}, {i*dx:.8g}, {j*dy:.8g}, {k*dz:.8g}")

    lines.append("*Element, type=C3D8R")
    eid = 0
    for i in range(nx):
        for j in range(ny):
            for k in range(nz):
                eid += 1
                conn = [
                    node_id(i, j, k), node_id(i + 1, j, k),
                    node_id(i + 1, j + 1, k), node_id(i, j + 1, k),
                    node_id(i, j, k + 1), node_id(i + 1, j, k + 1),
                    node_id(i + 1, j + 1, k + 1), node_id(i, j + 1, k + 1),
                ]
                lines.append(f"{eid}, " + ", ".join(str(item) for item in conn))
                px, py, pz = (i + 0.5) / nx, (j + 0.5) / ny, (k + 0.5) / nz
                best = min(
                    _point_to_segment_dist_sq(px, py, pz, *f["start"], *f["end"])
                    for f in fibers_data
                )
                if best <= radius**2:
                    phase_code = 2; phase_name = "fiber"
                    fiber_elements.append(eid)
                elif best <= interface_radius**2:
                    phase_code = 1; phase_name = "interface"
                    interface_elements.append(eid)
                else:
                    phase_code = 0
                    phase_name = "matrix"
                    matrix_elements.append(eid)
                phase_rows.append(
                    {
                        "element_id": eid,
                        "ix": i,
                        "iy": j,
                        "iz": k,
                        "phase_code": phase_code,
                        "phase": phase_name,
                        "center_x": round((i + 0.5) * dx, 8),
                        "center_y": round((j + 0.5) * dy, 8),
                        "center_z": round((k + 0.5) * dz, 8),
                    }
                )

    _append_id_set(lines, "FIBER_PHASE", fiber_elements, kind="Elset")
    _append_id_set(lines, "INTERFACE_PHASE", interface_elements, kind="Elset")
    _append_id_set(lines, "MATRIX_PHASE", matrix_elements, kind="Elset")
    xmin_nodes = [node_id(0, j, k) for j in range(ny + 1) for k in range(nz + 1)]
    xmax_nodes = [node_id(nx, j, k) for j in range(ny + 1) for k in range(nz + 1)]
    ymin_nodes = [node_id(i, 0, k) for i in range(nx + 1) for k in range(nz + 1)]
    zmin_nodes = [node_id(i, j, 0) for i in range(nx + 1) for j in range(ny + 1)]
    anchor_node = node_id(0, 0, 0)
    _append_id_set(lines, "XMIN_FACE", xmin_nodes, kind="Nset")
    _append_id_set(lines, "XMAX_FACE", xmax_nodes, kind="Nset")
    _append_id_set(lines, "YMIN_FACE", ymin_nodes, kind="Nset")
    _append_id_set(lines, "ZMIN_FACE", zmin_nodes, kind="Nset")
    _append_id_set(lines, "ANCHOR_NODE", [anchor_node], kind="Nset")

    ux = config.micro_load_strain * lx
    interface_e, interface_nu = _interface_elastic_constants(config)
    lines.extend(
        [
            "*Material, name=FIBER_MATERIAL",
            "*Elastic",
            f"{config.fiber_e:.8g}, {config.fiber_nu:.8g}",
            "*Material, name=INTERFACE_MATERIAL",
            "*Elastic",
            f"{interface_e:.8g}, {interface_nu:.8g}",
            "*Material, name=MATRIX_MATERIAL",
            "*Elastic",
            f"{config.matrix_e:.8g}, {config.matrix_nu:.8g}",
            "*Solid Section, elset=FIBER_PHASE, material=FIBER_MATERIAL",
            ",",
            "*Solid Section, elset=INTERFACE_PHASE, material=INTERFACE_MATERIAL",
            ",",
            "*Solid Section, elset=MATRIX_PHASE, material=MATRIX_MATERIAL",
            ",",
            "*Step, name=Micro_Uniaxial_X, nlgeom=NO",
            "*Static",
            "0.1, 1.0, 1e-05, 0.1",
            "*Boundary",
            "XMIN_FACE, 1, 1, 0.0",
            "ANCHOR_NODE, 2, 3, 0.0",
            f"XMAX_FACE, 1, 1, {ux:.8g}",
            "*Output, field",
            "*Node Output",
            "U, RF",
            "*Element Output, directions=YES",
            "S, E",
            "*Output, history",
            "*Node Output, nset=XMAX_FACE",
            "RF1, U1",
            "*End Step",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with phase_map_path.open("w", encoding="utf-8", newline="") as handle:
        if not phase_rows:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "element_id",
                    "ix",
                    "iy",
                    "iz",
                    "phase_code",
                    "phase",
                    "center_x",
                    "center_y",
                    "center_z",
                ],
            )
            writer.writeheader()
            return {
                "micro_rve_fiber_elements": 0.0,
                "micro_rve_interface_elements": 0.0,
                "micro_rve_matrix_elements": 0.0,
                "micro_rve_fiber_fraction_voxel": 0.0,
                "micro_rve_interface_fraction_voxel": 0.0,
                "micro_rve_matrix_fraction_voxel": 0.0,
                "micro_interface_radius_normalized": float(interface_radius),
                "micro_interface_elastic_modulus_mpa": float(interface_e),
            }
        writer = csv.DictWriter(handle, fieldnames=list(phase_rows[0].keys()))
        writer.writeheader()
        writer.writerows(phase_rows)
    total = max(1, len(phase_rows))
    return {
        "micro_rve_fiber_elements": float(len(fiber_elements)),
        "micro_rve_interface_elements": float(len(interface_elements)),
        "micro_rve_matrix_elements": float(len(matrix_elements)),
        "micro_rve_fiber_fraction_voxel": float(len(fiber_elements) / total),
        "micro_rve_interface_fraction_voxel": float(len(interface_elements) / total),
        "micro_rve_matrix_fraction_voxel": float(len(matrix_elements) / total),
        "micro_interface_radius_normalized": float(interface_radius),
        "micro_interface_elastic_modulus_mpa": float(interface_e),
        "micro_interface_poisson_ratio": float(interface_nu),
    }


def _append_id_set(lines: list[str], name: str, ids: list[int], *, kind: str) -> None:
    lines.append(f"*{kind}, {kind.lower()}={name}")
    if not ids:
        lines.append("")
        return
    for idx in range(0, len(ids), 16):
        lines.append(", ".join(str(item) for item in ids[idx : idx + 16]))


def micro_rve_load_cases(config: CompositePlateConfig) -> dict[str, dict[str, Any]]:
    strain = float(config.micro_load_strain)
    return {
        "EXX": {"strain_component": "E11", "reaction_set": "XMAX_FACE", "dof": 1, "value": strain * config.micro_length},
        "EYY": {"strain_component": "E22", "reaction_set": "YMAX_FACE", "dof": 2, "value": strain * config.micro_width},
        "EZZ": {"strain_component": "E33", "reaction_set": "ZMAX_FACE", "dof": 3, "value": strain * config.micro_height},
        "GXY": {"strain_component": "G12", "reaction_set": "YMAX_FACE", "dof": 1, "value": strain * config.micro_width},
        "GXZ": {"strain_component": "G13", "reaction_set": "ZMAX_FACE", "dof": 1, "value": strain * config.micro_height},
        "GYZ": {"strain_component": "G23", "reaction_set": "ZMAX_FACE", "dof": 2, "value": strain * config.micro_height},
    }


def write_micro_rve_pbc_jobs(job_dir: Path, config: CompositePlateConfig, layout: dict[str, Any]) -> dict[str, Path]:
    jobs: dict[str, Path] = {}
    for case_name, case in micro_rve_load_cases(config).items():
        path = job_dir / f"micro_rve_pbc_{case_name.lower()}.inp"
        _write_single_micro_rve_pbc_inp(path, config, layout, case_name, case)
        jobs[case_name] = path
    return jobs


def _write_single_micro_rve_pbc_inp(
    path: Path,
    config: CompositePlateConfig,
    layout: dict[str, Any],
    case_name: str,
    case: dict[str, Any],
) -> None:
    nx = int(config.micro_nx)
    ny = int(config.micro_ny)
    nz = int(config.micro_nz)
    lx = float(config.micro_length)
    ly = float(config.micro_width)
    lz = float(config.micro_height)
    dx = lx / nx
    dy = ly / ny
    dz = lz / nz
    radius = float(layout["fiber_radius_normalized"])
    interface_radius = radius * (1.0 + float(config.interface_thickness_ratio))
    fibers_data = layout.get("fibers", [])
    if not fibers_data:
        centers = [(item["y"], item["z"]) for item in layout.get("centers", [])]
        fibers_data = [
            {"start": (0.0, fy, fz), "end": (1.0, fy, fz)}
            for fy, fz in centers
        ]
    interface_e, interface_nu = _interface_elastic_constants(config)
    fiber_elements: list[int] = []
    interface_elements: list[int] = []
    matrix_elements: list[int] = []

    def node_id(i: int, j: int, k: int) -> int:
        return 1 + i * (ny + 1) * (nz + 1) + j * (nz + 1) + k

    lines: list[str] = [
        "*Heading",
        f"** Micro RVE periodic load case {case_name} generated by MaterialAI Workbench",
        "** Kinematic RVE homogenization applies face displacement jumps and reads volume-average stress.",
        "*Node",
    ]
    for i in range(nx + 1):
        for j in range(ny + 1):
            for k in range(nz + 1):
                lines.append(f"{node_id(i, j, k)}, {i*dx:.8g}, {j*dy:.8g}, {k*dz:.8g}")
    lines.append("*Element, type=C3D8R")

    eid = 0
    for i in range(nx):
        for j in range(ny):
            for k in range(nz):
                eid += 1
                conn = [
                    node_id(i, j, k),
                    node_id(i + 1, j, k),
                    node_id(i + 1, j + 1, k),
                    node_id(i, j + 1, k),
                    node_id(i, j, k + 1),
                    node_id(i + 1, j, k + 1),
                    node_id(i + 1, j + 1, k + 1),
                    node_id(i, j + 1, k + 1),
                ]
                lines.append(f"{eid}, " + ", ".join(str(item) for item in conn))
                point_xyz = (
                    (i + 0.5) / nx,
                    (j + 0.5) / ny,
                    (k + 0.5) / nz,
                )
                phase_code = _classify_voxel(
                    point_xyz,
                    fibers_data,
                    radius,
                    interface_radius,
                )
                if phase_code == 2:
                    fiber_elements.append(eid)
                elif phase_code == 1:
                    interface_elements.append(eid)
                else:
                    matrix_elements.append(eid)

    _append_id_set(lines, "FIBER_PHASE", fiber_elements, kind="Elset")
    _append_id_set(lines, "INTERFACE_PHASE", interface_elements, kind="Elset")
    _append_id_set(lines, "MATRIX_PHASE", matrix_elements, kind="Elset")
    _append_id_set(lines, "ANCHOR_NODE", [node_id(0, 0, 0)], kind="Nset")
    _append_micro_face_sets(lines, nx, ny, nz, node_id)
    boundary_lines = _micro_homogenization_boundary_lines(case_name, case)

    lines.extend(
        [
            "*Material, name=FIBER_MATERIAL",
            "*Elastic",
            f"{config.fiber_e:.8g}, {config.fiber_nu:.8g}",
            "*Material, name=INTERFACE_MATERIAL",
            "*Elastic",
            f"{interface_e:.8g}, {interface_nu:.8g}",
            "*Material, name=MATRIX_MATERIAL",
            "*Elastic",
            f"{config.matrix_e:.8g}, {config.matrix_nu:.8g}",
            "*Solid Section, elset=FIBER_PHASE, material=FIBER_MATERIAL",
            ",",
            "*Solid Section, elset=INTERFACE_PHASE, material=INTERFACE_MATERIAL",
            ",",
            "*Solid Section, elset=MATRIX_PHASE, material=MATRIX_MATERIAL",
            ",",
            f"*Step, name=PBC_{case_name}, nlgeom=NO",
            "*Static",
            "0.1, 1.0, 1e-05, 0.1",
            *boundary_lines,
            "*Output, field",
            "*Node Output",
            "U, RF",
            "*Element Output, directions=YES",
            "S, E",
            "*End Step",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _append_periodic_equations(
    lines: list[str],
    nx: int,
    ny: int,
    nz: int,
    node_id: Any,
    ref_nodes: dict[str, int],
) -> None:
    lines.append("** Periodic equations for non-overlapping face-interior node pairs.")
    for j in range(1, ny):
        for k in range(1, nz):
            _append_ref_equation(lines, node_id(nx, j, k), node_id(0, j, k), ref_nodes["REF_X"])
    for i in range(1, nx):
        for k in range(1, nz):
            _append_ref_equation(lines, node_id(i, ny, k), node_id(i, 0, k), ref_nodes["REF_Y"])
    for i in range(1, nx):
        for j in range(1, ny):
            _append_ref_equation(lines, node_id(i, j, nz), node_id(i, j, 0), ref_nodes["REF_Z"])


def _append_ref_equation(lines: list[str], plus_node: int, minus_node: int, ref_node: int) -> None:
    for dof in (1, 2, 3):
        lines.extend(
            [
                "*Equation",
                "3",
                f"{plus_node}, {dof}, 1.0, {minus_node}, {dof}, -1.0, {ref_node}, {dof}, -1.0",
            ]
        )


def _append_micro_face_sets(lines: list[str], nx: int, ny: int, nz: int, node_id: Any) -> None:
    _append_id_set(lines, "XMIN_FACE", [node_id(0, j, k) for j in range(ny + 1) for k in range(nz + 1)], kind="Nset")
    _append_id_set(lines, "XMAX_FACE", [node_id(nx, j, k) for j in range(ny + 1) for k in range(nz + 1)], kind="Nset")
    _append_id_set(lines, "YMIN_FACE", [node_id(i, 0, k) for i in range(nx + 1) for k in range(nz + 1)], kind="Nset")
    _append_id_set(lines, "YMAX_FACE", [node_id(i, ny, k) for i in range(nx + 1) for k in range(nz + 1)], kind="Nset")
    _append_id_set(lines, "ZMIN_FACE", [node_id(i, j, 0) for i in range(nx + 1) for j in range(ny + 1)], kind="Nset")
    _append_id_set(lines, "ZMAX_FACE", [node_id(i, j, nz) for i in range(nx + 1) for j in range(ny + 1)], kind="Nset")


def _micro_homogenization_boundary_lines(case_name: str, case: dict[str, Any]) -> list[str]:
    value = float(case["value"])
    lines = ["*Boundary"]
    if case_name == "EXX":
        lines.extend(["XMIN_FACE, 1, 1, 0.0", f"XMAX_FACE, 1, 1, {value:.8g}", "YMIN_FACE, 2, 2, 0.0", "ZMIN_FACE, 3, 3, 0.0"])
    elif case_name == "EYY":
        lines.extend(["YMIN_FACE, 2, 2, 0.0", f"YMAX_FACE, 2, 2, {value:.8g}", "XMIN_FACE, 1, 1, 0.0", "ZMIN_FACE, 3, 3, 0.0"])
    elif case_name == "EZZ":
        lines.extend(["ZMIN_FACE, 3, 3, 0.0", f"ZMAX_FACE, 3, 3, {value:.8g}", "XMIN_FACE, 1, 1, 0.0", "YMIN_FACE, 2, 2, 0.0"])
    elif case_name == "GXY":
        lines.extend([
            "YMIN_FACE, 1, 1, 0.0",
            f"YMAX_FACE, 1, 1, {value:.8g}",
            "XMIN_FACE, 2, 2, 0.0",
            "XMAX_FACE, 2, 2, 0.0",
            "ZMIN_FACE, 3, 3, 0.0",
        ])
    elif case_name == "GXZ":
        lines.extend([
            "ZMIN_FACE, 1, 1, 0.0",
            f"ZMAX_FACE, 1, 1, {value:.8g}",
            "XMIN_FACE, 3, 3, 0.0",
            "XMAX_FACE, 3, 3, 0.0",
            "YMIN_FACE, 2, 2, 0.0",
        ])
    elif case_name == "GYZ":
        lines.extend([
            "ZMIN_FACE, 2, 2, 0.0",
            f"ZMAX_FACE, 2, 2, {value:.8g}",
            "YMIN_FACE, 3, 3, 0.0",
            "YMAX_FACE, 3, 3, 0.0",
            "XMIN_FACE, 1, 1, 0.0",
        ])
    else:
        lines.append("ANCHOR_NODE, 1, 3, 0.0")
    return lines


def write_micro_pbc_plan(path: Path, config: CompositePlateConfig, jobs: dict[str, Path]) -> None:
    plan = {
        "purpose": "six-loadcase micro RVE homogenization plan",
        "note": "The current production-safe MVP uses kinematic face displacement jumps and volume-average stress extraction. The data schema keeps the PBC name so a stricter periodic-equation solver can replace the boundary block later without changing downstream ML workflows.",
        "micro_load_strain": config.micro_load_strain,
        "cell_size": {
            "x": config.micro_length,
            "y": config.micro_width,
            "z": config.micro_height,
        },
        "load_cases": {
            name: {**case, "job_input": str(jobs[name])}
            for name, case in micro_rve_load_cases(config).items()
        },
    }
    path.write_text(json.dumps(plan, indent=2), encoding="utf-8")


def write_micro_pbc_run_script(path: Path, config: CompositePlateConfig, job_dir: Path, jobs: dict[str, Path]) -> None:
    lines = [
        "$ErrorActionPreference = 'Stop'",
        f"Set-Location -LiteralPath '{job_dir.resolve()}'",
    ]
    for case_name, inp_path in jobs.items():
        job_name = inp_path.stem
        lines.append(f"& '{Path(config.abaqus_bat)}' job={job_name} input='{inp_path.resolve()}' cpus={int(config.cpus)} interactive")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_micro_pbc_postprocess_script(path: Path, config: CompositePlateConfig, job_dir: Path) -> None:
    plan = micro_rve_load_cases(config)
    script = f'''# -*- coding: mbcs -*-
from odbAccess import openOdb
import csv
import json
import os

JOB_DIR = r"{job_dir.resolve()}"
LOAD_CASES = {json.dumps(plan, indent=2)}
AREA = {{
    "EXX": {config.micro_width * config.micro_height!r},
    "EYY": {config.micro_length * config.micro_height!r},
    "EZZ": {config.micro_length * config.micro_width!r},
    "GXY": {config.micro_length * config.micro_height!r},
    "GXZ": {config.micro_length * config.micro_width!r},
    "GYZ": {config.micro_length * config.micro_width!r},
}}
GAUGE = {{
    "EXX": {config.micro_length!r},
    "EYY": {config.micro_width!r},
    "EZZ": {config.micro_height!r},
    "GXY": {config.micro_width!r},
    "GXZ": {config.micro_height!r},
    "GYZ": {config.micro_height!r},
}}
STRESS_COMPONENT_INDEX = {{
    "EXX": 0,
    "EYY": 1,
    "EZZ": 2,
    "GXY": 3,
    "GXZ": 4,
    "GYZ": 5,
}}


def _node_set_value(frame, node_set_name, dof_index):
    region = None
    if node_set_name in odb.rootAssembly.nodeSets:
        region = odb.rootAssembly.nodeSets[node_set_name]
    else:
        for instance in odb.rootAssembly.instances.values():
            if node_set_name in instance.nodeSets:
                region = instance.nodeSets[node_set_name]
                break
    if region is None:
        raise KeyError(node_set_name)
    field = frame.fieldOutputs["RF"].getSubset(region=region)
    values = [value.data[dof_index - 1] for value in field.values if len(value.data) >= dof_index]
    return sum(values) if values else 0.0


def _average_stress_component(frame, case_name):
    if "S" not in frame.fieldOutputs:
        return None
    index = STRESS_COMPONENT_INDEX[case_name]
    values = []
    for value in frame.fieldOutputs["S"].values:
        if len(value.data) > index:
            values.append(value.data[index])
    if not values:
        return None
    return sum(values) / float(len(values))


rows = []
for case_name, case in LOAD_CASES.items():
    job = "micro_rve_pbc_" + case_name.lower()
    odb_path = os.path.join(JOB_DIR, job + ".odb")
    row = {{
        "case": case_name,
        "strain_component": case["strain_component"],
        "odb_path": odb_path,
        "status": "missing_odb",
        "reaction": "",
        "applied_jump": case["value"],
        "effective_modulus_mpa": "",
        "close_warning": "",
        "extraction_error": "",
    }}
    if os.path.exists(odb_path):
        odb = openOdb(odb_path, readOnly=True)
        try:
            step = odb.steps[odb.steps.keys()[-1]]
            if len(step.frames) == 0:
                raise RuntimeError("no result frames in step " + step.name)
            frame = step.frames[-1]
            reaction = _node_set_value(frame, case["reaction_set"], int(case["dof"]))
            strain = float(case["value"]) / float(GAUGE[case_name])
            average_stress = _average_stress_component(frame, case_name)
            if average_stress is None:
                effective = abs(reaction) / max(float(AREA[case_name]) * abs(strain), 1e-12)
                source = "reference_node_reaction"
            else:
                effective = abs(average_stress) / max(abs(strain), 1e-12)
                source = "volume_average_stress"
            row.update({{
                "status": "ok",
                "reaction": reaction,
                "average_stress": average_stress,
                "effective_source": source,
                "effective_modulus_mpa": effective,
            }})
        except Exception as exc:
            row.update({{
                "status": "extract_failed",
                "extraction_error": str(exc),
            }})
        finally:
            try:
                odb.close()
            except Exception as exc:
                if not row.get("close_warning"):
                    row["close_warning"] = str(exc)
    rows.append(row)

csv_path = os.path.join(JOB_DIR, "rve_effective_stiffness.csv")
json_path = os.path.join(JOB_DIR, "rve_effective_stiffness.json")
with open(csv_path, "w") as handle:
    writer = csv.DictWriter(handle, fieldnames=["case", "strain_component", "odb_path", "status", "reaction", "average_stress", "effective_source", "applied_jump", "effective_modulus_mpa", "close_warning", "extraction_error"])
    writer.writeheader()
    writer.writerows(rows)
with open(json_path, "w") as handle:
    json.dump({{"rows": rows}}, handle, indent=2)
'''
    path.write_text(script, encoding="utf-8")


def run_micro_rve_pbc_homogenization(
    config: CompositePlateConfig,
    job_dir: Path,
    postprocess_script: Path,
    run_dir: Path,
) -> dict[str, Any]:
    started = datetime.now().isoformat(timespec="seconds")
    job_statuses: list[dict[str, Any]] = []
    if not Path(config.abaqus_bat).exists():
        summary = {
            "status": "abaqus_bat_not_found",
            "started_at": started,
            "finished_at": datetime.now().isoformat(timespec="seconds"),
            "job_statuses": job_statuses,
            "homogenized_properties": {},
        }
        _write_pbc_summary(run_dir, job_dir, summary)
        return summary

    for inp_path in sorted(job_dir.glob("micro_rve_pbc_*.inp")):
        job_name = inp_path.stem
        command = [str(Path(config.abaqus_bat)), f"job={job_name}", f"input={inp_path.name}", f"cpus={int(config.cpus)}", "interactive"]
        try:
            proc = subprocess.run(
                command,
                cwd=job_dir,
                capture_output=True,
                text=True,
                timeout=1800,
            )
            (job_dir / f"{job_name}_stdout.log").write_text(proc.stdout or "", encoding="utf-8", errors="replace")
            (job_dir / f"{job_name}_stderr.log").write_text(proc.stderr or "", encoding="utf-8", errors="replace")
            status = "completed" if proc.returncode == 0 else "failed"
            job_statuses.append({"job_name": job_name, "input": str(inp_path), "return_code": proc.returncode, "status": status})
        except subprocess.TimeoutExpired as exc:
            (job_dir / f"{job_name}_timeout.log").write_text(str(exc), encoding="utf-8", errors="replace")
            job_statuses.append({"job_name": job_name, "input": str(inp_path), "return_code": None, "status": "timeout"})

    extraction_status = "not_run"
    if Path(config.smapython).exists():
        post = subprocess.run(
            [str(Path(config.smapython)), str(postprocess_script.resolve())],
            cwd=job_dir,
            capture_output=True,
            text=True,
            timeout=600,
        )
        (job_dir / "rve_postprocess_stdout.log").write_text(post.stdout or "", encoding="utf-8", errors="replace")
        (job_dir / "rve_postprocess_stderr.log").write_text(post.stderr or "", encoding="utf-8", errors="replace")
        extraction_status = "completed" if post.returncode == 0 else f"failed_{post.returncode}"
    else:
        extraction_status = "smapython_not_found"

    rows = _load_pbc_rows(job_dir / "rve_effective_stiffness.json")
    homogenized = _pbc_rows_to_properties(rows)
    status = "completed" if job_statuses and all(item["status"] == "completed" for item in job_statuses) and homogenized else "incomplete"
    summary = {
        "status": status,
        "started_at": started,
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "extraction_status": extraction_status,
        "job_statuses": job_statuses,
        "rows": rows,
        "homogenized_properties": homogenized,
        "comparison": _compare_effective_properties(compute_effective_ud_properties(config), homogenized),
    }
    _write_pbc_summary(run_dir, job_dir, summary)
    return summary


def _write_pbc_summary(run_dir: Path, job_dir: Path, summary: dict[str, Any]) -> None:
    (job_dir / "rve_homogenization_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (run_dir / "rve_homogenization_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")


def _load_pbc_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError:
        return []
    rows = payload.get("rows", [])
    return rows if isinstance(rows, list) else []


def _pbc_rows_to_properties(rows: list[dict[str, Any]]) -> dict[str, float]:
    mapping = {"EXX": "E1", "EYY": "E2", "EZZ": "E3", "GXY": "G12", "GXZ": "G13", "GYZ": "G23"}
    props: dict[str, float] = {}
    for row in rows:
        case_name = str(row.get("case", "")).upper()
        target = mapping.get(case_name)
        value = _try_float(row.get("effective_modulus_mpa"))
        if target and value is not None and value > 0:
            props[target] = float(value)
    return props


def _compare_effective_properties(estimated: dict[str, float], homogenized: dict[str, float]) -> dict[str, dict[str, float]]:
    comparison: dict[str, dict[str, float]] = {}
    for key, pbc_value in homogenized.items():
        estimate = float(estimated.get(key, 0.0))
        rel_error = abs(pbc_value - estimate) / abs(estimate) if abs(estimate) > 1e-12 else 0.0
        comparison[key] = {
            "estimated": estimate,
            "abaqus_homogenized": float(pbc_value),
            "relative_difference": float(rel_error),
            "within_10_percent": bool(rel_error <= 0.10),
        }
    return comparison


def _merge_homogenized_properties(estimated: dict[str, float], homogenized: dict[str, float]) -> dict[str, float]:
    merged = dict(estimated)
    for key in ("E1", "E2", "E3", "G12", "G13", "G23"):
        if key in homogenized and homogenized[key] > 0:
            merged[key] = float(homogenized[key])
    return merged


def _try_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _interface_elastic_constants(config: CompositePlateConfig) -> tuple[float, float]:
    interface_e = math.sqrt(config.fiber_e * config.matrix_e) * config.interface_efficiency
    interface_nu = min(0.49, 0.5 * (config.fiber_nu + config.matrix_nu))
    return float(interface_e), float(interface_nu)


def write_micro_rve_run_script(path: Path, config: CompositePlateConfig, micro_inp: Path, run_dir: Path) -> None:
    job_name = micro_inp.stem
    text = f"""$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath '{(run_dir / "micro_rve").resolve()}'
& '{Path(config.abaqus_bat)}' job={job_name} input='{micro_inp.resolve()}' cpus={int(config.cpus)} interactive
"""
    path.write_text(text, encoding="utf-8")


def write_plate_preview(path: Path, config: CompositePlateConfig, estimates: dict[str, float]) -> None:
    half_l = config.length / 2.0
    half_w = config.width / 2.0
    width_px = 1180
    height_px = 520
    margin_x = 110
    margin_y = 110
    image = Image.new("RGB", (width_px, height_px), "#f8fafc")
    draw = ImageDraw.Draw(image)
    font = _preview_font()
    small_font = _preview_font()

    x_min = -half_l - 25.0
    x_max = half_l + 25.0
    y_min = -half_w - 14.0
    y_max = half_w + 14.0

    def point(x_value: float, y_value: float) -> tuple[float, float]:
        x_px = margin_x + (x_value - x_min) / (x_max - x_min) * (width_px - 2 * margin_x)
        y_px = height_px - margin_y - (y_value - y_min) / (y_max - y_min) * (height_px - 2 * margin_y)
        return (x_px, y_px)

    plate_left, plate_top = point(-half_l, half_w)
    plate_right, plate_bottom = point(half_l, -half_w)
    draw.rectangle((plate_left, plate_top, plate_right, plate_bottom), fill="#dde7ed", outline="#1e2d3a", width=3)
    for y_value in np.linspace(-half_w * 0.75, half_w * 0.75, 7):
        draw.line((*point(-half_l, y_value), *point(half_l, y_value)), fill="#b8c8d2", width=1)

    cx, cy = point(0.0, 0.0)
    rx = abs(point(config.hole_radius, 0.0)[0] - cx)
    ry = abs(point(0.0, config.hole_radius)[1] - cy)
    draw.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill="#ffffff", outline="#c93c3c", width=4)

    _draw_arrow(draw, point(half_l + 3.0, 0.0), point(half_l + 17.0, 0.0), "#2f7d32")
    _draw_arrow(draw, point(-half_l - 3.0, 0.0), point(-half_l - 17.0, 0.0), "#2f7d32")
    _draw_centered_text(
        draw,
        (width_px // 2, 42),
        f"Kt est. {estimates['stress_concentration_factor_estimate']:.2f}",
        font,
        fill="#1e2d3a",
    )
    _draw_centered_text(
        draw,
        (width_px // 2, height_px - 46),
        "3D plate-with-hole tension validation model",
        small_font,
        fill="#1e2d3a",
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def write_material_card(path: Path, props: dict[str, float]) -> None:
    lines = [
        "*Material, name=UD_CFRP_EFFECTIVE",
        "*Elastic, type=ENGINEERING CONSTANTS",
        (
            f"{props['E1']:.8g}, {props['E2']:.8g}, {props['E3']:.8g}, "
            f"{props['nu12']:.8g}, {props['nu13']:.8g}, {props['nu23']:.8g}, "
            f"{props['G12']:.8g}, {props['G13']:.8g}, {props['G23']:.8g}"
        ),
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_abaqus_build_script(
    path: Path,
    config: CompositePlateConfig,
    props: dict[str, float],
    run_dir: Path,
) -> None:
    model_name = _safe_name(config.name)
    job_name = f"{model_name}_plate_hole"
    script = f'''# -*- coding: mbcs -*-
from abaqus import *
from abaqusConstants import *
from caeModules import *
import mesh
import regionToolset
import json
import os

WORKDIR = r"{run_dir.resolve()}"
MODEL_NAME = "{model_name}"
JOB_NAME = "{job_name}"
LENGTH = {config.length!r}
WIDTH = {config.width!r}
THICKNESS = {config.thickness!r}
HOLE_RADIUS = {config.hole_radius!r}
MESH_SIZE = {config.mesh_size!r}
APPLIED_DISPLACEMENT = {config.applied_strain * config.length!r}
SUBMIT_JOB = {bool(config.submit_job)!r}
CPUS = {int(config.cpus)!r}

os.chdir(WORKDIR)
mdb.Model(name=MODEL_NAME)
model = mdb.models[MODEL_NAME]
if 'Model-1' in mdb.models and 'Model-1' != MODEL_NAME:
    del mdb.models['Model-1']

half_l = LENGTH / 2.0
half_w = WIDTH / 2.0
sketch = model.ConstrainedSketch(name='plate_profile', sheetSize=max(LENGTH, WIDTH) * 2.5)
sketch.rectangle(point1=(-half_l, -half_w), point2=(half_l, half_w))
sketch.CircleByCenterPerimeter(center=(0.0, 0.0), point1=(HOLE_RADIUS, 0.0))
part = model.Part(name='PlateWithHole3D', dimensionality=THREE_D, type=DEFORMABLE_BODY)
part.BaseSolidExtrude(sketch=sketch, depth=THICKNESS)
del model.sketches['plate_profile']

mat = model.Material(name='UD_CFRP_EFFECTIVE')
mat.Elastic(type=ENGINEERING_CONSTANTS, table=((
    {props["E1"]:.12g}, {props["E2"]:.12g}, {props["E3"]:.12g},
    {props["nu12"]:.12g}, {props["nu13"]:.12g}, {props["nu23"]:.12g},
    {props["G12"]:.12g}, {props["G13"]:.12g}, {props["G23"]:.12g}),))
section = model.HomogeneousSolidSection(name='CompositeSolidSection', material='UD_CFRP_EFFECTIVE')
all_cells_region = regionToolset.Region(cells=part.cells)
part.SectionAssignment(region=all_cells_region, sectionName='CompositeSolidSection')
fiber_csys_id = part.DatumCsysByThreePoints(
    name='FiberDirectionGlobalX',
    coordSysType=CARTESIAN,
    origin=(0.0, 0.0, 0.0),
    point1=(1.0, 0.0, 0.0),
    point2=(0.0, 1.0, 0.0),
).id
part.MaterialOrientation(
    region=all_cells_region,
    orientationType=SYSTEM,
    axis=AXIS_1,
    localCsys=part.datums[fiber_csys_id],
    additionalRotationType=ROTATION_NONE,
    angle=0.0,
    stackDirection=STACK_3,
)

part.seedPart(size=MESH_SIZE, deviationFactor=0.1, minSizeFactor=0.1)
part.setMeshControls(regions=part.cells, elemShape=TET, technique=FREE)
elem_type = mesh.ElemType(elemCode=C3D10, elemLibrary=STANDARD)
part.setElementType(regions=(part.cells,), elemTypes=(elem_type,))
part.generateMesh()

assembly = model.rootAssembly
assembly.DatumCsysByDefault(CARTESIAN)
instance = assembly.Instance(name='PlateWithHole3D-1', part=part, dependent=ON)
tol = max(MESH_SIZE, THICKNESS) * 0.25
left_faces = instance.faces.getByBoundingBox(xMin=-half_l - tol, xMax=-half_l + tol)
right_faces = instance.faces.getByBoundingBox(xMin=half_l - tol, xMax=half_l + tol)
anchor_vertices = instance.vertices.getByBoundingBox(
    xMin=-half_l - tol, xMax=-half_l + tol,
    yMin=-half_w - tol, yMax=-half_w + tol,
    zMin=-tol, zMax=tol,
)
assembly.Set(faces=left_faces, name='BC_XMIN_FACE')
assembly.Set(faces=right_faces, name='LOAD_XMAX_FACE')
assembly.Set(vertices=anchor_vertices, name='ANCHOR_VERTEX')
assembly.Surface(side1Faces=right_faces, name='PULL_SURFACE')

model.StaticStep(name='Tension', previous='Initial', nlgeom=OFF)
model.DisplacementBC(name='Fix_X_at_left_face', createStepName='Initial', region=assembly.sets['BC_XMIN_FACE'], u1=0.0, u2=UNSET, u3=UNSET)
model.DisplacementBC(name='Anchor_YZ', createStepName='Initial', region=assembly.sets['ANCHOR_VERTEX'], u1=UNSET, u2=0.0, u3=0.0)
model.DisplacementBC(name='Pull_right_face', createStepName='Tension', region=assembly.sets['LOAD_XMAX_FACE'], u1=APPLIED_DISPLACEMENT, u2=UNSET, u3=UNSET)
model.fieldOutputRequests['F-Output-1'].setValues(variables=('S', 'E', 'LE', 'U', 'RF'))
model.HistoryOutputRequest(name='RightFaceReaction', createStepName='Tension', variables=('RF1',), region=assembly.sets['LOAD_XMAX_FACE'])

job = mdb.Job(name=JOB_NAME, model=MODEL_NAME, numCpus=CPUS, numDomains=CPUS, multiprocessingMode=DEFAULT)
job.writeInput(consistencyChecking=OFF)
mdb.saveAs(pathName=os.path.join(WORKDIR, MODEL_NAME + '.cae'))
job_status = 'not_submitted'
if SUBMIT_JOB:
    job.submit(consistencyChecking=OFF)
    job.waitForCompletion()
    job_status = str(job.status)

summary = {{
    'model_name': MODEL_NAME,
    'job_name': JOB_NAME,
    'input_file': os.path.join(WORKDIR, JOB_NAME + '.inp'),
    'cae_file': os.path.join(WORKDIR, MODEL_NAME + '.cae'),
    'submitted': SUBMIT_JOB,
    'job_status': job_status,
    'node_count': len(part.nodes),
    'element_count': len(part.elements),
    'sets': sorted(assembly.sets.keys()),
    'surfaces': sorted(assembly.surfaces.keys()),
}}
with open(os.path.join(WORKDIR, 'abaqus_build_summary.json'), 'w') as handle:
    json.dump(summary, handle, indent=2)
'''
    path.write_text(script, encoding="utf-8")


def write_odb_postprocess_script(path: Path, config: CompositePlateConfig, run_dir: Path) -> None:
    model_name = _safe_name(config.name)
    job_name = f"{model_name}_plate_hole"
    script = f'''# -*- coding: mbcs -*-
from odbAccess import openOdb
import csv
import json
import os

WORKDIR = r"{run_dir.resolve()}"
JOB_NAME = "{job_name}"
odb_path = os.path.join(WORKDIR, JOB_NAME + '.odb')
odb = openOdb(odb_path, readOnly=True)
step = odb.steps[odb.steps.keys()[-1]]
frame = step.frames[-1]
summary = {{'job_name': JOB_NAME, 'odb_path': odb_path, 'step': step.name, 'frame': frame.incrementNumber}}

if 'S' in frame.fieldOutputs:
    values = frame.fieldOutputs['S'].values
    mises = [v.mises for v in values if hasattr(v, 'mises')]
    summary['max_mises'] = max(mises) if mises else None
if 'U' in frame.fieldOutputs:
    values = frame.fieldOutputs['U'].values
    mags = [sum(x*x for x in v.data) ** 0.5 for v in values]
    summary['max_displacement'] = max(mags) if mags else None
if 'RF' in frame.fieldOutputs:
    values = frame.fieldOutputs['RF'].values
    rf1 = [v.data[0] for v in values if len(v.data) > 0]
    summary['sum_rf1'] = sum(rf1) if rf1 else None

summary['max_mises_mpa'] = summary.get('max_mises')
json_path = os.path.join(WORKDIR, 'plate_odb_summary.json')
csv_path = os.path.join(WORKDIR, 'plate_odb_summary.csv')
abaqus_json_path = os.path.join(WORKDIR, 'abaqus', 'plate_results.json')
abaqus_csv_path = os.path.join(WORKDIR, 'abaqus', 'plate_results.csv')
with open(json_path, 'w') as handle:
    json.dump(summary, handle, indent=2)
with open(abaqus_json_path, 'w') as handle:
    json.dump(summary, handle, indent=2)
with open(csv_path, 'w') as handle:
    writer = csv.DictWriter(handle, fieldnames=sorted(summary.keys()))
    writer.writeheader()
    writer.writerow(summary)
with open(abaqus_csv_path, 'w') as handle:
    writer = csv.DictWriter(handle, fieldnames=sorted(summary.keys()))
    writer.writeheader()
    writer.writerow(summary)
try:
    odb.close()
except Exception as exc:
    warning_path = os.path.join(WORKDIR, 'abaqus', 'plate_results_close_warning.txt')
    with open(warning_path, 'w') as handle:
        handle.write(str(exc))
'''
    path.write_text(script, encoding="utf-8")


def write_run_script(
    path: Path,
    config: CompositePlateConfig,
    abaqus_script: Path,
    post_script: Path,
    run_dir: Path,
) -> None:
    text = f"""$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath '{run_dir.resolve()}'
& '{Path(config.abaqus_bat)}' cae noGUI='{abaqus_script.resolve()}'
if (Test-Path -LiteralPath '{(_safe_name(config.name) + "_plate_hole.odb")}') {{
  & '{Path(config.smapython)}' '{post_script.resolve()}'
}}
"""
    path.write_text(text, encoding="utf-8")


def write_dataset_row(
    path: Path,
    config: CompositePlateConfig,
    props: dict[str, float],
    estimates: dict[str, float],
    micro_metrics: dict[str, float],
    *,
    estimated_props: dict[str, float] | None = None,
    pbc_summary: dict[str, Any] | None = None,
) -> None:
    row: dict[str, Any] = {
        "case_type": "composite_plate_with_hole_3d",
        "fiber_volume_fraction": config.fiber_volume_fraction,
        "actual_vf": micro_metrics.get("actual_vf", config.fiber_volume_fraction),
        "fiber_e": config.fiber_e,
        "fiber_nu": config.fiber_nu,
        "matrix_e": config.matrix_e,
        "matrix_nu": config.matrix_nu,
        "interface_efficiency": config.interface_efficiency,
        "interface_thickness_ratio": config.interface_thickness_ratio,
        "micro_fiber_count": config.micro_fiber_count,
        "micro_nx": config.micro_nx,
        "micro_ny": config.micro_ny,
        "micro_nz": config.micro_nz,
        "length": config.length,
        "width": config.width,
        "thickness": config.thickness,
        "hole_radius": config.hole_radius,
        "applied_strain": config.applied_strain,
        # Fiber orientation features (Task 6)
        "fiber_orientation_theta_deg": config.fiber_orientation_theta_deg,
        "fiber_orientation_phi_deg": config.fiber_orientation_phi_deg,
        "fiber_orientation_spread_deg": config.fiber_orientation_spread_deg,
        "fiber_length_normalized": config.fiber_length_normalized,
        "fiber_radius_normalized": micro_metrics.get("fiber_radius_normalized", 0),
        "fiber_aspect_ratio": (
            micro_metrics.get("fiber_length_normalized", config.fiber_length_normalized) / max(
                micro_metrics.get("fiber_radius_normalized", 0.05) * 2, 0.001)
        ),
    }
    orient = micro_metrics.get("orientation_tensor", {})
    if orient:
        row["orientation_a11"] = orient.get("a11")
        row["orientation_a22"] = orient.get("a22")
        row["orientation_a33"] = orient.get("a33")
        row["orientation_a12"] = orient.get("a12")
    row.update(props)
    if estimated_props:
        for key, value in estimated_props.items():
            row[f"estimated_{key}"] = value
    pbc_props = (pbc_summary or {}).get("homogenized_properties", {}) if isinstance(pbc_summary, dict) else {}
    if isinstance(pbc_props, dict):
        for key, value in pbc_props.items():
            row[f"abaqus_homogenized_{key}"] = value
    comparison = (pbc_summary or {}).get("comparison", {}) if isinstance(pbc_summary, dict) else {}
    if isinstance(comparison, dict):
        for key, item in comparison.items():
            if isinstance(item, dict):
                row[f"pbc_{key}_relative_difference"] = item.get("relative_difference")
                row[f"pbc_{key}_within_10_percent"] = item.get("within_10_percent")
    if pbc_summary:
        row["pbc_homogenization_status"] = pbc_summary.get("status")
        row["pbc_homogenization_summary"] = str(path.parent / "rve_homogenization_summary.json")
    row.update(estimates)
    row.update(micro_metrics)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row.keys()))
        writer.writeheader()
        writer.writerow(row)


def run_abaqus_build(
    config: CompositePlateConfig,
    abaqus_script: Path,
    postprocess_script: Path,
    run_dir: Path,
) -> str:
    if not Path(config.abaqus_bat).exists():
        return "abaqus_bat_not_found"
    command = [str(Path(config.abaqus_bat)), "cae", f"noGUI={abaqus_script.resolve()}"]
    try:
        result = subprocess.run(
            command,
            cwd=run_dir,
            capture_output=True,
            text=True,
            timeout=1800,
        )
    except subprocess.TimeoutExpired:
        return "abaqus_timeout"
    (run_dir / "abaqus_stdout.log").write_text(result.stdout or "", encoding="utf-8", errors="replace")
    (run_dir / "abaqus_stderr.log").write_text(result.stderr or "", encoding="utf-8", errors="replace")
    if result.returncode != 0:
        return f"abaqus_failed_{result.returncode}"
    if config.submit_job:
        job_name = f"{_safe_name(config.name)}_plate_hole"
        log_text = _read_text_if_exists(run_dir / f"{job_name}.log").lower()
        dat_text = _read_text_if_exists(run_dir / f"{job_name}.dat").lower()
        if (
            "abaqus/analysis exited with errors" in log_text
            or "fatal errors" in dat_text
            or "the program has discovered" in dat_text and "fatal errors" in dat_text
        ):
            return "abaqus_job_failed"
        if not Path(config.smapython).exists():
            return "abaqus_completed_postprocess_unavailable"
        post_result = subprocess.run(
            [str(Path(config.smapython)), str(postprocess_script.resolve())],
            cwd=run_dir,
            capture_output=True,
            text=True,
            timeout=600,
        )
        (run_dir / "plate_postprocess_stdout.log").write_text(post_result.stdout or "", encoding="utf-8", errors="replace")
        (run_dir / "plate_postprocess_stderr.log").write_text(post_result.stderr or "", encoding="utf-8", errors="replace")
        if post_result.returncode != 0:
            return f"abaqus_completed_postprocess_failed_{post_result.returncode}"
    return "abaqus_completed"


def _read_text_if_exists(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def _load_json_if_exists(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError:
        return {}


def _prepare_run_dir(config: CompositePlateConfig) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = _safe_name(config.name)
    run_dir = Path(config.output_dir) / f"{stamp}_{safe}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def _safe_name(value: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in value.strip())
    return safe or "composite_plate_hole"


def _validate_config(config: CompositePlateConfig) -> None:
    if not 0.05 <= config.fiber_volume_fraction <= 0.8:
        raise ValueError("fiber_volume_fraction must be between 0.05 and 0.8.")
    if config.fiber_e <= 0 or config.matrix_e <= 0:
        raise ValueError("Elastic moduli must be positive.")
    if not 0.0 < config.hole_radius < config.width / 2.2:
        raise ValueError("hole_radius must be positive and smaller than half the plate width.")
    if config.length <= config.width:
        raise ValueError("length should be larger than width for a tensile coupon.")
    if config.thickness <= 0 or config.mesh_size <= 0:
        raise ValueError("thickness and mesh_size must be positive.")
    if config.applied_strain <= 0:
        raise ValueError("applied_strain must be positive.")
    if config.interface_thickness_ratio < 0:
        raise ValueError("interface_thickness_ratio must be zero or positive.")
    if min(config.micro_nx, config.micro_ny, config.micro_nz) < 2:
        raise ValueError("micro_nx, micro_ny and micro_nz must be at least 2.")
    if config.micro_fiber_count < 1:
        raise ValueError("micro_fiber_count must be positive.")
    if config.micro_load_strain <= 0:
        raise ValueError("micro_load_strain must be positive.")
    if config.fiber_orientation_spread_deg < 0:
        raise ValueError("fiber_orientation_spread_deg must be zero or positive.")
    if config.fiber_length_normalized <= 0 or config.fiber_length_std < 0:
        raise ValueError("Fiber length must be positive and its standard deviation non-negative.")
    if config.fiber_diameter_normalized is not None and config.fiber_diameter_normalized <= 0:
        raise ValueError("fiber_diameter_normalized must be positive when provided.")
    if config.fiber_geometry_mode not in {"ud", "oriented_cylinders", "chopped"}:
        raise ValueError("fiber_geometry_mode must be ud, oriented_cylinders or chopped.")


def _json_ready(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    return value


def _markdown_report(manifest: dict[str, Any]) -> str:
    cfg = manifest["config"]
    props = manifest["effective_properties"]
    est = manifest["engineering_estimates"]
    paths = manifest["paths"]
    plate_results = manifest.get("plate_results") if isinstance(manifest.get("plate_results"), dict) else {}
    pbc_summary = manifest.get("pbc_homogenization") if isinstance(manifest.get("pbc_homogenization"), dict) else {}
    pbc_props = pbc_summary.get("homogenized_properties", {}) if isinstance(pbc_summary, dict) else {}
    if pbc_props:
        pbc_lines = ["## Micro RVE Abaqus Homogenization", "", f"- Status: `{pbc_summary.get('status')}`", ""]
        pbc_lines.append("| Constant | Abaqus homogenized | Estimated | Relative diff |")
        pbc_lines.append("|---|---:|---:|---:|")
        comparison = pbc_summary.get("comparison", {}) if isinstance(pbc_summary.get("comparison"), dict) else {}
        for key in ("E1", "E2", "E3", "G12", "G13", "G23"):
            if key in pbc_props:
                item = comparison.get(key, {}) if isinstance(comparison.get(key), dict) else {}
                pbc_lines.append(
                    f"| {key} | {float(pbc_props[key]):.3f} | {float(item.get('estimated', props.get(key, 0.0))):.3f} | {float(item.get('relative_difference', 0.0)):.3%} |"
                )
        pbc_section = "\n".join(pbc_lines)
    else:
        pbc_section = f"""## Micro RVE Abaqus Homogenization

- Status: `{pbc_summary.get('status', 'not_run') if isinstance(pbc_summary, dict) else 'not_run'}`
- The six PBC micro-RVE jobs have not produced homogenized stiffness values yet.
"""
    if plate_results:
        plate_results_section = f"""
## Abaqus ODB Results

- Abaqus status: `{manifest.get('abaqus_status')}`
- Step / frame: `{plate_results.get('step')}` / `{plate_results.get('frame')}`
- Max Mises: `{plate_results.get('max_mises_mpa')}` MPa
- Max displacement: `{plate_results.get('max_displacement')}` mm
- Sum RF1: `{plate_results.get('sum_rf1')}`
- ODB: `{plate_results.get('odb_path')}`
"""
    else:
        plate_results_section = f"""
## Abaqus ODB Results

- Abaqus status: `{manifest.get('abaqus_status')}`
- ODB extraction has not run yet. Enable Abaqus job submission, or run the postprocess script after an ODB exists.
"""
    return f"""# Composite Micro-to-Macro 3D Plate-with-Hole Report

## Purpose

This run builds a first usable composite workflow:

micro-scale Fiber/Interface/Matrix voxel RVE -> phase-map ML input -> current effective-property label interface -> Abaqus 3D plate-with-hole validation model -> result extraction dataset row.

The RVE is not only an equivalent material placeholder. It is generated as a real Abaqus voxel model with separate element sets for fiber, interface and matrix phases. The effective constants in this MVP are the first label channel used to map microstructure to macro validation; they can be replaced by an Abaqus RVE/PBC solve without changing the downstream ML and plate-validation pipeline.

## Micro model

- Fiber volume fraction: `{cfg['fiber_volume_fraction']}`
- Fiber E / nu: `{cfg['fiber_e']} MPa`, `{cfg['fiber_nu']}`
- Matrix E / nu: `{cfg['matrix_e']} MPa`, `{cfg['matrix_nu']}`
- Interface efficiency: `{cfg['interface_efficiency']}`
- Interface thickness ratio: `{cfg['interface_thickness_ratio']}`
- Micro voxel grid: `{cfg['micro_nx']} x {cfg['micro_ny']} x {cfg['micro_nz']}`
- Micro fiber count: `{cfg['micro_fiber_count']}`

## Effective orthotropic material

| Constant | Value |
|---|---:|
| E1 | {props['E1']:.3f} MPa |
| E2 | {props['E2']:.3f} MPa |
| E3 | {props['E3']:.3f} MPa |
| nu12 | {props['nu12']:.5f} |
| nu13 | {props['nu13']:.5f} |
| nu23 | {props['nu23']:.5f} |
| G12 | {props['G12']:.3f} MPa |
| G13 | {props['G13']:.3f} MPa |
| G23 | {props['G23']:.3f} MPa |

## Macro Abaqus model

- Geometry: `{cfg['length']} x {cfg['width']} x {cfg['thickness']} mm`
- Hole radius: `{cfg['hole_radius']} mm`
- Applied axial strain: `{cfg['applied_strain']}`
- Right edge displacement: `{est['right_edge_displacement']:.6f} mm`
- Estimated stress concentration factor: `{est['stress_concentration_factor_estimate']:.3f}`
- Nominal axial stress estimate: `{est['nominal_axial_stress_mpa']:.3f} MPa`
- Max near-hole stress estimate: `{est['max_stress_near_hole_estimate_mpa']:.3f} MPa`
{pbc_section}
{plate_results_section}

## Generated files

- Micro RVE preview: `{paths['microstructure_png']}`
- Micro RVE Abaqus INP: `{paths['micro_rve_inp']}`
- Micro phase map CSV for ML: `{paths['micro_phase_map']}`
- Micro PBC loadcase plan: `{paths['micro_pbc_plan']}`
- Micro PBC run script: `{paths['micro_pbc_run_script']}`
- Micro PBC ODB postprocess script: `{paths['micro_pbc_postprocess_script']}`
- Plate preview: `{paths['plate_preview_png']}`
- Abaqus material card: `{paths['material_card']}`
- Abaqus build script: `{paths['abaqus_script']}`
- Abaqus postprocess script: `{paths['postprocess_script']}`
- PowerShell run script: `{paths['run_script']}`
- Dataset row: `{paths['dataset_csv']}`
- Plate ODB summary JSON: `{paths['plate_odb_summary']}`
- Plate ODB summary CSV: `{paths['plate_odb_summary_csv']}`

## How to run Abaqus

```powershell
& "{paths['run_script']}"
```

Run the six micro-RVE PBC jobs:

```powershell
& "{paths['micro_pbc_run_script']}"
```

After the six ODB files exist, extract effective stiffness labels:

```powershell
& "{cfg['smapython']}" "{paths['micro_pbc_postprocess_script']}"
```

## Machine-learning role

This case produces both image-like microstructure inputs and tabular engineering labels. The intended learning task is:

`phase_map + constituent properties + geometry + load -> effective constants / plate stress concentration / failure or allowable load`

The current workflow uses a fast micromechanics estimate for the first label and now also generates six Abaqus PBC load cases. When those ODBs are solved, the postprocess script can replace the estimated labels with RVE-derived stiffness data while keeping the same phase-map, effective-property and Abaqus mapping interface.
"""
