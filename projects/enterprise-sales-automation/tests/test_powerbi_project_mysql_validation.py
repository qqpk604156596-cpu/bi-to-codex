"""Regression test for native MySQL Import parameter validation."""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = PROJECT_ROOT.parents[1] / "scripts" / "Test-BIPowerBIProject.py"


def load_validator():
    specification = importlib.util.spec_from_file_location("bi_project_validator", VALIDATOR_PATH)
    if specification is None or specification.loader is None:
        raise AssertionError("Test-BIPowerBIProject.py cannot be imported")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


class MySqlParameterValidationTests(unittest.TestCase):
    def test_native_mysql_parameters_satisfy_portable_source_requirement(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_path = Path(temporary_directory)
            definition_path = project_path / "Model.SemanticModel" / "definition"
            (definition_path / "tables").mkdir(parents=True)
            (definition_path / "database.tmdl").write_text("database Model\n", encoding="utf-8")
            (definition_path / "model.tmdl").write_text("model Model\n", encoding="utf-8")
            (definition_path / "relationships.tmdl").write_text("relationship FactToDate\n", encoding="utf-8")
            (definition_path / "tables" / "Fact.tmdl").write_text(
                "table Fact\n\tpartition Fact = m\n\t\tmode: import\n"
                "\t\tsource =\n\t\t\t\tlet Source = MySQL.Database(MySqlServer, MySqlDatabase) in Source\n",
                encoding="utf-8",
            )
            (definition_path / "expressions.tmdl").write_text(
                'expression MySqlServer = "127.0.0.1" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]\n'
                'expression MySqlDatabase = "enterprise_sales" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]\n',
                encoding="utf-8",
            )
            (project_path / "Model.SemanticModel" / "definition.pbism").write_text("{}", encoding="utf-8")

            issues, checks = load_validator().validate_semantic_model(
                project_path / "Model.SemanticModel", project_path
            )

        self.assertEqual(issues, [])
        self.assertTrue(checks["source_parameter"])


if __name__ == "__main__":
    unittest.main()
