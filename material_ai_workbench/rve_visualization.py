"""Interactive 3D fiber RVE visualization using plotly Mesh3d cylinders.

Shows real oriented fiber cylinders with interface layers and transparent
matrix bounding box. No scatter point clouds or regular circle arrays.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from material_ai_workbench.composite_workflow import (
    CompositePlateConfig,
    classify_voxel_phase,
    generate_fiber_layout,
)


def cylinder_mesh_between_points(
    start: tuple[float, float, float],
    end: tuple[float, float, float],
    radius: float,
    n_sides: int = 16,
) -> dict[str, np.ndarray]:
    """Build a closed cylinder Mesh3d between two 3D points.

    Returns dict with keys x, y, z, i, j, k for plotly Mesh3d.
    """
    sx, sy, sz = start
    ex, ey, ez = end
    dx, dy, dz = ex - sx, ey - sy, ez - sz
    length = float(np.sqrt(dx*dx + dy*dy + dz*dz))
    if length < 1e-12:
        length = radius * 2.0
        dx, dy, dz = 0.0, 0.0, length

    # Unit direction
    ux, uy, uz = dx/length, dy/length, dz/length
    # Two perpendicular vectors
    if abs(ux) < 0.9:
        px, py, pz = 1.0, 0.0, 0.0
    else:
        px, py, pz = 0.0, 1.0, 0.0
    # perp1 = cross(u, p)
    r1x = uy*pz - uz*py
    r1y = uz*px - ux*pz
    r1z = ux*py - uy*px
    r1norm = float(np.sqrt(r1x*r1x + r1y*r1y + r1z*r1z))
    r1x, r1y, r1z = r1x/r1norm, r1y/r1norm, r1z/r1norm
    # perp2 = cross(u, perp1)
    r2x = uy*r1z - uz*r1y
    r2y = uz*r1x - ux*r1z
    r2z = ux*r1y - uy*r1x

    angles = np.linspace(0, 2*np.pi, n_sides, endpoint=False)
    cx = np.cos(angles) * radius
    sy_vals = np.sin(angles) * radius

    # Ring vertices at start and end
    n_verts = n_sides * 2 + 2  # ring_start, ring_end, +2 cap centers
    x = np.zeros(n_verts)
    y = np.zeros(n_verts)
    z = np.zeros(n_verts)

    for i in range(n_sides):
        x[i] = sx + r1x*cx[i] + r2x*sy_vals[i]
        y[i] = sy + r1y*cx[i] + r2y*sy_vals[i]
        z[i] = sz + r1z*cx[i] + r2z*sy_vals[i]
        x[n_sides+i] = ex + r1x*cx[i] + r2x*sy_vals[i]
        y[n_sides+i] = ey + r1y*cx[i] + r2y*sy_vals[i]
        z[n_sides+i] = ez + r1z*cx[i] + r2z*sy_vals[i]
    # Cap centers
    x[-2], y[-2], z[-2] = sx, sy, sz
    x[-1], y[-1], z[-1] = ex, ey, ez

    # Triangles: barrel + caps
    i_faces, j_faces, k_faces = [], [], []
    # Barrel quads -> 2 triangles each
    for ring_i in range(n_sides):
        a = ring_i
        b = (ring_i + 1) % n_sides
        c = n_sides + ring_i
        d = n_sides + (ring_i + 1) % n_sides
        i_faces.extend([a, a])
        j_faces.extend([b, c])
        k_faces.extend([c, d])
    # Caps
    si, ei = n_sides * 2, n_sides * 2 + 1
    for ring_i in range(n_sides):
        a = ring_i
        b = (ring_i + 1) % n_sides
        i_faces.extend([a, n_sides + a])
        j_faces.extend([b, n_sides + b])
        k_faces.extend([si, ei])

    return {"x": x, "y": y, "z": z, "i": np.array(i_faces), "j": np.array(j_faces), "k": np.array(k_faces)}


def plot_oriented_fiber_rve_3d(
    config: CompositePlateConfig | None = None,
    *,
    layout: dict[str, Any] | None = None,
    show_matrix: bool = True,
    show_interface: bool = True,
    width: int = 750,
    height: int = 650,
) -> Any:
    """Plot real fiber cylinders with interface layers using Mesh3d.

    This is the product-level RVE view — no scatter squares, no regular circles.
    """
    import plotly.graph_objects as go

    if layout is None and config is not None:
        layout = generate_fiber_layout(config)
    if layout is None:
        return go.Figure()

    fibers = layout.get("fibers", [])
    if not fibers:
        return go.Figure()

    fr = float(layout.get("fiber_radius_normalized", 0.06))
    ir = float(layout.get("interface_radius_normalized", fr * 1.18))
    orient = layout.get("orientation_tensor", {})
    n_sides = 14
    traces = []

    # Interface cylinders (drawn first, behind fibers)
    if show_interface:
        ix_all, iy_all, iz_all = [], [], []
        ii_all, ij_all, ik_all = [], [], []
        voff = 0
        for f in fibers:
            mesh = cylinder_mesh_between_points(
                (float(f["start"][0]), float(f["start"][1]), float(f["start"][2])),
                (float(f["end"][0]), float(f["end"][1]), float(f["end"][2])),
                ir, n_sides=n_sides,
            )
            ix_all.extend(mesh["x"]); iy_all.extend(mesh["y"]); iz_all.extend(mesh["z"])
            ii_all.extend(mesh["i"] + voff); ij_all.extend(mesh["j"] + voff); ik_all.extend(mesh["k"] + voff)
            voff += len(mesh["x"])
        traces.append(go.Mesh3d(
            x=ix_all, y=iy_all, z=iz_all, i=ii_all, j=ij_all, k=ik_all,
            name="Interface", color="#f59e0b", opacity=0.38, flatshading=True,
            showlegend=True, hoverinfo="name",
        ))

    # Fiber cylinders
    fx_all, fy_all, fz_all = [], [], []
    fi_all, fj_all, fk_all = [], [], []
    voff = 0
    for f in fibers:
        mesh = cylinder_mesh_between_points(
            (float(f["start"][0]), float(f["start"][1]), float(f["start"][2])),
            (float(f["end"][0]), float(f["end"][1]), float(f["end"][2])),
            fr, n_sides=n_sides,
        )
        fx_all.extend(mesh["x"]); fy_all.extend(mesh["y"]); fz_all.extend(mesh["z"])
        fi_all.extend(mesh["i"] + voff); fj_all.extend(mesh["j"] + voff); fk_all.extend(mesh["k"] + voff)
        voff += len(mesh["x"])
    traces.append(go.Mesh3d(
        x=fx_all, y=fy_all, z=fz_all, i=fi_all, j=fj_all, k=fk_all,
        name="Fiber", color="#2563eb", opacity=0.96, flatshading=True,
        showlegend=True, hoverinfo="name",
    ))

    # Transparent matrix volume and a separate RVE wireframe.
    if show_matrix:
        cube_x = [0, 1, 1, 0, 0, 1, 1, 0]
        cube_y = [0, 0, 1, 1, 0, 0, 1, 1]
        cube_z = [0, 0, 0, 0, 1, 1, 1, 1]
        cube_i = [0, 0, 4, 4, 0, 0, 1, 1, 2, 2, 3, 3]
        cube_j = [1, 2, 6, 7, 1, 5, 2, 6, 3, 7, 0, 4]
        cube_k = [2, 3, 5, 6, 5, 4, 6, 5, 7, 6, 4, 7]
        traces.append(go.Mesh3d(
            x=cube_x, y=cube_y, z=cube_z,
            i=cube_i, j=cube_j, k=cube_k,
            name="Matrix", color="#cbd5e1", opacity=0.10,
            flatshading=True, showlegend=True, hoverinfo="name",
        ))
        mb_verts = [
            (0,0,0),(1,0,0),(1,1,0),(0,1,0),(0,0,0),
            (0,0,1),(1,0,1),(1,1,1),(0,1,1),(0,0,1),
            (None,None,None),(1,0,0),(1,0,1),(None,None,None),
            (1,1,0),(1,1,1),(None,None,None),(0,1,0),(0,1,1),
        ]
        mbx, mby, mbz = zip(*mb_verts)
        traces.append(go.Scatter3d(
            x=mbx, y=mby, z=mbz, mode="lines",
            name="RVE bounds", line=dict(color="#374151", width=2),
            showlegend=True, hoverinfo="none",
        ))

    actual_vf = float(layout.get("actual_vf", 0))
    nf = len(fibers)
    title_text = (
        f"Fiber RVE &mdash; {nf} oriented cylinders &mdash; "
        f"Vf<sub>fiber</sub>={actual_vf:.1%} &mdash; "
        f"a11={orient.get('a11',0):.2f}"
    )

    fig = go.Figure(data=traces)
    fig.update_layout(
        title=dict(text=title_text, font=dict(size=14, color="#1f2937")),
        scene=dict(
            xaxis=dict(title="X (fiber mean)", showgrid=False, showbackground=False, color="#6b7280"),
            yaxis=dict(title="Y", showgrid=False, showbackground=False, color="#6b7280"),
            zaxis=dict(title="Z", showgrid=False, showbackground=False, color="#6b7280"),
            aspectmode="data",
            camera=dict(eye=dict(x=1.5, y=1.5, z=1.0)),
            bgcolor="rgba(0,0,0,0)",
        ),
        width=width, height=height,
        margin=dict(l=0, r=0, t=45, b=0),
        legend=dict(orientation="h", yanchor="top", y=-0.02, xanchor="center", x=0.5, font=dict(size=11)),
        paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig


# Legacy functions — kept for backward compat
def build_rve_phase_grid(config: CompositePlateConfig) -> dict[str, Any]:
    layout = generate_fiber_layout(config)
    nx, ny, nz = config.micro_nx, config.micro_ny, config.micro_nz
    phase_grid = np.zeros((nx, ny, nz), dtype=np.uint8)
    phase_codes = {"matrix": 0, "interface": 1, "fiber": 2}
    fibers = layout.get("fibers", [])
    fiber_radius = float(layout["fiber_radius_normalized"])
    interface_radius = float(layout["interface_radius_normalized"])
    for ix in range(nx):
        for iy in range(ny):
            for iz in range(nz):
                point = ((ix + 0.5) / nx, (iy + 0.5) / ny, (iz + 0.5) / nz)
                phase = classify_voxel_phase(point, fibers, fiber_radius, interface_radius)
                phase_grid[ix, iy, iz] = phase_codes[phase]
    return {"phase_grid": phase_grid,
            "nx": nx, "ny": ny, "nz": nz,
            "dx": 1.0/nx, "dy": 1.0/ny, "dz": 1.0/nz,
            "fiber_count": len(layout.get("fibers", [])),
            "fiber_volume_fraction": layout.get("actual_vf", 0.0),
            "interface_volume_fraction": layout.get("interface_vf", 0.0),
            "matrix_volume_fraction": layout.get("matrix_vf", 0.0),
            "layout": layout}


def plot_rve_3d(config=None, *, phase_grid=None, downsample=1, opacity=0.9, width=750, height=650):
    """Legacy wrapper — delegates to the new fiber cylinder renderer."""
    layout = phase_grid.get("layout") if isinstance(phase_grid, dict) else None
    if layout is None and config is not None:
        layout = generate_fiber_layout(config)
    return plot_oriented_fiber_rve_3d(config=config, layout=layout, width=width, height=height)


def plot_rve_3d_from_run(run_dir: Path | str, **kwargs: Any) -> Any:
    run_path = Path(run_dir)
    manifest_path = run_path / "manifest.json"
    if not manifest_path.exists():
        return _empty_figure("Run manifest not found")
    layout_path = run_path / "micro_rve" / "fiber_layout.json"
    if layout_path.exists():
        layout = json.loads(layout_path.read_text(encoding="utf-8"))
        return plot_oriented_fiber_rve_3d(layout=layout, **kwargs)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    cfg = manifest.get("config", {})
    config = CompositePlateConfig(
        fiber_volume_fraction=float(cfg.get("fiber_volume_fraction", 0.55)),
        fiber_e=float(cfg.get("fiber_e", 230000)),
        fiber_nu=float(cfg.get("fiber_nu", 0.2)),
        matrix_e=float(cfg.get("matrix_e", 3500)),
        matrix_nu=float(cfg.get("matrix_nu", 0.35)),
        interface_efficiency=float(cfg.get("interface_efficiency", 0.92)),
        interface_thickness_ratio=float(cfg.get("interface_thickness_ratio", 0.18)),
        micro_fiber_count=int(cfg.get("micro_fiber_count", 16)),
        micro_nx=int(cfg.get("micro_nx", 8)), micro_ny=int(cfg.get("micro_ny", 18)), micro_nz=int(cfg.get("micro_nz", 18)),
        random_seed=int(cfg.get("random_seed", 7)),
        fiber_orientation_theta_deg=float(cfg.get("fiber_orientation_theta_deg", 0)),
        fiber_orientation_phi_deg=float(cfg.get("fiber_orientation_phi_deg", 0)),
        fiber_orientation_spread_deg=float(cfg.get("fiber_orientation_spread_deg", 8)),
        fiber_length_normalized=float(cfg.get("fiber_length_normalized", 1.2)),
        fiber_length_std=float(cfg.get("fiber_length_std", 0.08)),
        fiber_diameter_normalized=cfg.get("fiber_diameter_normalized"),
        fiber_geometry_mode=str(cfg.get("fiber_geometry_mode", "oriented_cylinders")),
    )
    return plot_oriented_fiber_rve_3d(config=config, **kwargs)


def _empty_figure(message: str) -> Any:
    import plotly.graph_objects as go
    fig = go.Figure()
    fig.add_annotation(text=message, x=0.5, y=0.5, showarrow=False, font=dict(size=14))
    fig.update_layout(width=600, height=400)
    return fig
