# MaterialAI Workbench v0.1.1 补丁说明

`v0.1.1` 是首个公开 MVP 的干净安装兼容性补丁，不改变 `v0.1.0` 的产品能力边界。

## 修复内容

在开发机上曾经安装过独立的 `pylabfea` 发行包，而 MaterialAI Workbench 的 wheel 是把 pyLabFEA 源码作为内置模块一起发布。上游模型参数导出函数仍通过发行名 `pylabfea` 查询版本，因此在全新 Python 环境中会触发 `PackageNotFoundError`。

补丁版完成以下修复：

1. 独立发行元数据存在时读取其版本；不存在时明确回退到内置 pyLabFEA `4.4.2`。
2. 增加无独立 `pylabfea` 发行包场景的回归测试。
3. GitHub CI 只对 `main` 和 Pull Request 执行完整矩阵，避免标签推送重复测试。
4. GitHub 官方 Actions 升级到兼容 Node 24 的当前主版本。

## 版本关系

- `MaterialAI Workbench 0.1.1`：产品发行版本。
- `pyLabFEA 4.4.2`：仓库内置并保留署名的材料建模底座版本。

两者是不同层级的版本号；导出的材料模型元数据应记录 pyLabFEA 底座版本，而不是把产品版本误写成 pyLabFEA 版本。
