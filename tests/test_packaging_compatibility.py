from importlib import metadata

import pylabfea.material as material_module


def test_bundled_pylabfea_version_without_standalone_distribution(monkeypatch):
    def missing_distribution(name):
        raise metadata.PackageNotFoundError(name)

    monkeypatch.setattr(material_module.metadata, "version", missing_distribution)

    assert material_module._pylabfea_distribution_version() == "4.4.2"
