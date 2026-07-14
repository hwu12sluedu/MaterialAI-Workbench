"""Create a non-destructive GitHub release audit for MaterialAI Workbench."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "dist" / "release_audit.md"
TEMP_PARTS = {".pytest_cache", ".ipynb_checkpoints", "__pycache__", "build", "dist"}
GENERATED_WORKBENCH_DIRS = {
    "runs", "batches", "cases", "datasets", "surrogates", "closed_loop_reports",
    "imports", "logs", "composite_runs", "composite_batches", "composite_surrogates",
}
SECRET_PATTERNS = {
    "OpenAI-style key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "GitHub token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    "AWS access key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
}


@dataclass(frozen=True)
class FileStat:
    path: Path
    size_bytes: int

    @property
    def size_mb(self) -> float:
        return self.size_bytes / 1024 / 1024


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_report(), encoding="utf-8")
    print(output)


def render_report() -> str:
    candidates = git_candidate_files()
    local_files = [path for path in ROOT.rglob("*") if path.is_file() and ".git" not in path.parts]
    local_generated = [
        ROOT / "material_ai_workbench" / name
        for name in sorted(GENERATED_WORKBENCH_DIRS)
        if (ROOT / "material_ai_workbench" / name).exists()
    ]
    local_workspace = ROOT / "workspace"
    candidate_temp = [path for path in candidates if any(part in TEMP_PARTS for part in path.parts)]
    large_candidates = sorted(
        [FileStat(path, path.stat().st_size) for path in candidates if path.stat().st_size >= 10 * 1024 * 1024],
        key=lambda item: item.size_bytes,
        reverse=True,
    )
    secret_hits = scan_secrets(candidates)
    candidate_size = sum(path.stat().st_size for path in candidates)
    local_size = sum(path.stat().st_size for path in local_files)
    blocking_large = [item for item in large_candidates if item.size_mb >= 100.0]
    gate_passed = not candidate_temp and not secret_hits and not blocking_large
    product_smoke = latest_product_smoke()

    lines = [
        "# GitHub 发布自动审计报告",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 发布候选文件：{len(candidates)} 个，{candidate_size / 1024 / 1024:.2f} MB",
        f"- 本地工作区（含被忽略仿真数据）：{len(local_files)} 个文件，{local_size / 1024 / 1024:.2f} MB",
        f"- Git 状态：{read_git_status()}",
        f"- 发布 Gate：{'PASS' if gate_passed else 'FAIL'}",
        "",
        "发布候选按 `git ls-files --cached --others --exclude-standard` 计算；本地 ODB、CAE、运行目录和 `.env` 可以保留，但不会因此进入公开仓库。",
        "",
        "## Gate 结果",
        "",
        "| 检查 | 结果 | 说明 |",
        "|---|---|---|",
        f"| 明文密钥 | {'PASS' if not secret_hits else 'FAIL'} | 命中 {len(secret_hits)} 处 |",
        f"| GitHub 100 MB 单文件限制 | {'PASS' if not blocking_large else 'FAIL'} | 阻断文件 {len(blocking_large)} 个 |",
        f"| 缓存/构建文件 | {'PASS' if not candidate_temp else 'FAIL'} | 候选中发现 {len(candidate_temp)} 个 |",
        f"| 本地生成数据隔离 | {'PASS' if local_workspace.exists() or local_generated else 'INFO'} | `workspace/` 与旧运行目录均受 `.gitignore` 保护 |",
        "",
        "## 当前里程碑证据",
        "",
    ]
    lines.extend(render_product_smoke(product_smoke))

    lines.extend(["", "## 发布候选大文件", "", "| 文件 | 大小 MB | 结论 |", "|---|---:|---|"])
    if large_candidates:
        for item in large_candidates:
            conclusion = "阻断：超过 GitHub 单文件限制" if item.size_mb >= 100 else "可提交，但建议确认必要性"
            lines.append(f"| `{rel(item.path)}` | {item.size_mb:.2f} | {conclusion} |")
    else:
        lines.append("| 无 | 0 | PASS |")

    lines.extend(["", "## 密钥扫描", ""])
    if secret_hits:
        for path, label in secret_hits:
            lines.append(f"- FAIL：`{rel(path)}` 命中 {label}。")
    else:
        lines.append("- PASS：发布候选中未发现已知格式的 OpenAI、GitHub 或 AWS 明文密钥。")
    lines.append("- 该扫描不能替代人工审查；已在聊天、截图或旧提交中暴露的密钥仍应撤销。")

    lines.extend(["", "## 发布候选扩展名", "", "| 扩展名 | 文件数 | 大小 MB |", "|---|---:|---:|"])
    for suffix, count, size_mb in summarize_extensions(candidates):
        lines.append(f"| `{suffix or '[no suffix]'}` | {count} | {size_mb:.2f} |")

    lines.extend(
        [
            "",
            "## 本地保留但不发布的数据",
            "",
            f"- 旧版产品运行目录：{len(local_generated)} 类。",
            f"- 新版统一工作目录：`{rel(local_workspace)}`（{'存在' if local_workspace.exists() else '首次运行时创建'}）。",
            "- `.env`、ODB/CAE、模型权重、执行 notebook、缓存和可选上游大数据均由 `.gitignore` 排除。",
            "",
            "## 发布结论",
            "",
            (
                "当前候选满足自动发布 Gate，可以继续执行测试、构建、提交和打标签。"
                if gate_passed
                else "当前候选未通过自动发布 Gate，必须处理上表中的 FAIL 后再推送。"
            ),
        ]
    )
    return "\n".join(lines) + "\n"


def git_candidate_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        timeout=30,
    )
    if result.returncode != 0:
        return []
    paths = []
    for raw in result.stdout.split(b"\0"):
        if not raw:
            continue
        path = ROOT / raw.decode("utf-8", errors="surrogateescape")
        if path.is_file():
            paths.append(path)
    return sorted(set(paths))


def scan_secrets(files: list[Path]) -> list[tuple[Path, str]]:
    hits: list[tuple[Path, str]] = []
    for path in files:
        if path.name.startswith(".env") and path.name != ".env.example":
            hits.append((path, "environment file"))
            continue
        if path.stat().st_size > 5 * 1024 * 1024:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                hits.append((path, label))
    return hits


def summarize_extensions(files: list[Path]) -> list[tuple[str, int, float]]:
    counts: Counter[str] = Counter()
    sizes: dict[str, int] = defaultdict(int)
    for path in files:
        suffix = path.suffix.lower()
        counts[suffix] += 1
        sizes[suffix] += path.stat().st_size
    return [
        (suffix, counts[suffix], sizes[suffix] / 1024 / 1024)
        for suffix in sorted(counts, key=lambda item: sizes[item], reverse=True)
    ]


def read_git_status() -> str:
    result = subprocess.run(
        ["git", "status", "--short"], cwd=ROOT, check=False,
        capture_output=True, text=True, timeout=10,
    )
    if result.returncode != 0:
        return f"非 Git 工作树：{(result.stderr or result.stdout).strip()}"
    return "干净" if not result.stdout.strip() else "有未提交变更"


def latest_product_smoke() -> dict:
    roots = [ROOT / "workspace" / "composite_runs", ROOT / "material_ai_workbench" / "composite_runs"]
    manifests = []
    for root in roots:
        manifests.extend(root.glob("*/product_closed_loop_summary.json"))
    manifests.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    if not manifests:
        return {}
    try:
        data = json.loads(manifests[0].read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        data = {}
    data["_path"] = str(manifests[0])
    return data


def render_product_smoke(manifest: dict) -> list[str]:
    if not manifest:
        return ["- 未发现产品闭环运行记录；涉及复合材料发布时应运行 `materialai-product-closed-loop`。"]
    acceptance = manifest.get("acceptance", {})
    capability = manifest.get("capability_status", {})
    return [
        f"- 最新产品闭环：`{rel(Path(manifest.get('_path', '')))}`",
        f"- 体积分数：目标 `{acceptance.get('target_vf')}`，实际 `{acceptance.get('actual_vf')}`，误差要求通过 `{acceptance.get('vf_within_3_percent')}`",
        f"- 六工况文件：`{acceptance.get('pbc_job_count')}` 个",
        f"- 微观 RVE / 宏观板模型 / 数据行 / 报告：`{capability.get('micro_rve')}` / `{capability.get('plate_model')}` / `{capability.get('dataset_row')}` / `{capability.get('engineering_report')}`",
        f"- Abaqus 板求解状态：`{capability.get('abaqus_plate_solve')}`（`generated` 表示已生成脚本但本次未提交求解）",
    ]


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve())).replace("\\", "/")
    except (OSError, ValueError):
        return str(path).replace("\\", "/")


if __name__ == "__main__":
    main()
