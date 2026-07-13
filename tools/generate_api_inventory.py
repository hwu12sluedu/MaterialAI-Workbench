"""Generate a Markdown API inventory for pyLabFEA and MaterialAI Workbench."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "api" / "API_INVENTORY_AUTOGEN_CN.md"


@dataclass
class FunctionInfo:
    name: str
    line: int
    signature: str
    doc: str


@dataclass
class ClassInfo:
    name: str
    line: int
    signature: str
    doc: str
    methods: list[FunctionInfo]


@dataclass
class ModuleInfo:
    module_path: Path
    module_name: str
    doc: str
    functions: list[FunctionInfo]
    classes: list[ClassInfo]


def main() -> None:
    modules = []
    for path in source_files():
        modules.append(parse_module(path))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(render(modules), encoding="utf-8")
    print(OUTPUT)


def source_files() -> list[Path]:
    files = []
    files.extend(sorted((ROOT / "src" / "pylabfea").glob("*.py")))
    files.extend(sorted((ROOT / "material_ai_workbench").glob("*.py")))
    return [path for path in files if path.name != "__pycache__"]


def parse_module(path: Path) -> ModuleInfo:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    module_name = module_name_for(path)
    functions: list[FunctionInfo] = []
    classes: list[ClassInfo] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if is_public(node.name):
                functions.append(function_info(node))
        elif isinstance(node, ast.ClassDef):
            if is_public(node.name):
                methods = [
                    function_info(item)
                    for item in node.body
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and is_public(item.name)
                ]
                classes.append(
                    ClassInfo(
                        name=node.name,
                        line=node.lineno,
                        signature=class_signature(node),
                        doc=doc_first_line(ast.get_docstring(node)),
                        methods=methods,
                    )
                )
    return ModuleInfo(
        module_path=path.relative_to(ROOT),
        module_name=module_name,
        doc=doc_first_line(ast.get_docstring(tree)),
        functions=functions,
        classes=classes,
    )


def module_name_for(path: Path) -> str:
    rel = path.relative_to(ROOT)
    if rel.parts[0] == "src":
        parts = rel.parts[1:]
    else:
        parts = rel.parts
    return ".".join(parts).removesuffix(".py")


def function_info(node: ast.FunctionDef | ast.AsyncFunctionDef) -> FunctionInfo:
    return FunctionInfo(
        name=node.name,
        line=node.lineno,
        signature=function_signature(node),
        doc=doc_first_line(ast.get_docstring(node)),
    )


def function_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    args = []
    posonly = list(getattr(node.args, "posonlyargs", []))
    normal = list(node.args.args)
    defaults = [None] * (len(posonly) + len(normal) - len(node.args.defaults)) + list(node.args.defaults)
    for arg, default in zip(posonly + normal, defaults):
        args.append(format_arg(arg, default))
    if posonly:
        args.insert(len(posonly), "/")
    if node.args.vararg:
        args.append("*" + node.args.vararg.arg)
    elif node.args.kwonlyargs:
        args.append("*")
    for arg, default in zip(node.args.kwonlyargs, node.args.kw_defaults):
        args.append(format_arg(arg, default))
    if node.args.kwarg:
        args.append("**" + node.args.kwarg.arg)
    prefix = "async " if isinstance(node, ast.AsyncFunctionDef) else ""
    return f"{prefix}{node.name}({', '.join(args)})"


def class_signature(node: ast.ClassDef) -> str:
    bases = [safe_unparse(base) for base in node.bases]
    return f"{node.name}({', '.join(bases)})" if bases else node.name


def format_arg(arg: ast.arg, default: ast.AST | None) -> str:
    text = arg.arg
    if arg.annotation:
        text += f": {safe_unparse(arg.annotation)}"
    if default is not None:
        text += f" = {safe_unparse(default)}"
    return text


def safe_unparse(node: ast.AST) -> str:
    try:
        text = ast.unparse(node)
    except Exception:
        return "..."
    return text.replace("|", "\\|")


def doc_first_line(doc: str | None) -> str:
    if not doc:
        return ""
    return doc.strip().splitlines()[0].strip().replace("|", "\\|")


def is_public(name: str) -> bool:
    return not name.startswith("_")


def render(modules: list[ModuleInfo]) -> str:
    total_functions = sum(len(module.functions) for module in modules)
    total_classes = sum(len(module.classes) for module in modules)
    total_methods = sum(len(cls.methods) for module in modules for cls in module.classes)
    lines = [
        "# API 功能清单（自动生成）",
        "",
        "> 本文件由 `tools/generate_api_inventory.py` 生成，用于保证教学文档覆盖全部公开函数与类。修改源码后重新运行脚本即可刷新。",
        "",
        "## 统计",
        "",
        f"- 模块数：{len(modules)}",
        f"- 顶层公开函数：{total_functions}",
        f"- 公开类：{total_classes}",
        f"- 公开类方法：{total_methods}",
        "",
        "## 使用方式",
        "",
        "```powershell",
        "conda run -n pylabfea python tools/generate_api_inventory.py",
        "```",
        "",
    ]
    for module in modules:
        lines.extend(render_module(module))
    return "\n".join(lines) + "\n"


def render_module(module: ModuleInfo) -> list[str]:
    lines = [
        f"## `{module.module_name}`",
        "",
        f"- 文件：`{module.module_path.as_posix()}`",
    ]
    if module.doc:
        lines.append(f"- 模块说明：{module.doc}")
    if module.functions:
        lines.extend(["", "### 顶层函数", "", "| 函数 | 行号 | 说明 |", "|---|---:|---|"])
        for func in module.functions:
            lines.append(f"| `{func.signature}` | {func.line} | {func.doc or '待补充'} |")
    if module.classes:
        lines.extend(["", "### 类与方法", ""])
        for cls in module.classes:
            lines.append(f"#### `{cls.signature}`")
            lines.append("")
            lines.append(f"- 行号：{cls.line}")
            if cls.doc:
                lines.append(f"- 说明：{cls.doc}")
            if cls.methods:
                lines.extend(["", "| 方法 | 行号 | 说明 |", "|---|---:|---|"])
                for method in cls.methods:
                    lines.append(f"| `{method.signature}` | {method.line} | {method.doc or '待补充'} |")
            lines.append("")
    lines.append("")
    return lines


if __name__ == "__main__":
    main()
