# 源码开发与 Windows 打包

## 1. 开发环境

```powershell
conda env create -f environment.yml
conda activate pylabfea
python -m pip install -e ".[app,desktop,dev,packaging]"
```

运行 Web 界面：

```powershell
materialai-streamlit
```

运行桌面壳：

```powershell
materialai-desktop
```

只检查桌面后台能否启动：

```powershell
python -m material_ai_workbench.desktop_launcher --smoke-test --startup-timeout 120
```

## 2. 测试

```powershell
python -m pytest tests material_ai_workbench/tests -q -m "not slow"
python -m build
python -m twine check dist/*
```

`slow` 测试包含耗时更长的上游训练或集成检查，发布前按需要单独运行。

## 3. 便携客户端构建

```powershell
powershell -ExecutionPolicy Bypass -File packaging/windows/build_portable.ps1
```

构建脚本会：

1. 使用 PyInstaller 生成 one-folder 应用。
2. 运行冻结后后台健康检查。
3. 加入启动说明、许可证与第三方声明。
4. 生成 Windows x64 ZIP 和 SHA256 文件。

产物位于 `dist/`。one-folder 体积大于 Python wheel，但启动和排错更稳定，适合包含 NumPy、SciPy、scikit-learn、Matplotlib、Streamlit 的工程软件。

## 4. 运行时结构

桌面 EXE 只负责进程生命周期：

```text
MaterialAIWorkbench.exe
  -> 选择空闲的 127.0.0.1 端口
  -> 启动私有 Streamlit 子进程
  -> 等待 /_stcore/health
  -> 打开 pywebview 原生窗口
  -> 窗口关闭时终止子进程
```

写入路径在 `%LOCALAPPDATA%\MaterialAIWorkbench`，因此程序目录可只读，升级也不会覆盖用户数据。

## 5. GitHub 发布

推送符合 `v*.*.*` 的标签后，Release workflow 会分别构建：

- Python wheel 和 source distribution；
- Windows x64 便携 ZIP 与 SHA256；
- GitHub Release 附件。

普通提交只运行 CI，不创建 Release。发布前确认 `pyproject.toml`、`material_ai_workbench.__version__`、`CHANGELOG.md` 和 Windows 版本资源一致。
