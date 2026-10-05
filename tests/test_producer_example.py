import runpy

from conftest import EXAMPLES
from world_map_interchange import validate


def test_climate_producer_example_writes_conformant_package(tmp_path):
    module = runpy.run_path(str(EXAMPLES / "code" / "write_climate_package.py"))
    module["main"](str(tmp_path / "pkg"))
    report = validate(tmp_path / "pkg")
    assert report.conformant, [i.render() for i in report.errors]
    assert not report.warnings
