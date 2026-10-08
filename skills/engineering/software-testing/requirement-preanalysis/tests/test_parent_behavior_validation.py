from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import validate_preanalysis as validator  # noqa: E402


def rsu_row(rsu_id: str, parent: str, source: str) -> tuple[int, list[str]]:
    return (
        10,
        [rsu_id, parent, source, "SRC-MOD", "业务规则", "无", "无", "captured"],
    )


class ParentBehaviorValidationTests(unittest.TestCase):
    def test_pure_parent_condition_is_not_hidden_behavior(self) -> None:
        issues: list[validator.Issue] = []
        validator.validate_rsu_source_shape(
            issues,
            Path("map.md"),
            [rsu_row("RSU-001", "查询条件包括：", "彩票年：下拉选择框，默认为全部。")],
        )
        self.assertFalse(any("observable parent behavior" in issue.message for issue in issues))

    def test_observable_parent_behavior_must_not_exist_only_in_parent_cell(self) -> None:
        issues: list[validator.Issue] = []
        validator.validate_rsu_source_shape(
            issues,
            Path("map.md"),
            [
                rsu_row(
                    "RSU-001",
                    "校验通过后，系统生成计奖审核任务，任务状态为“待核查”，并进入任务详情页。",
                    "顶部展示奖期编号和彩票年。",
                )
            ],
        )
        self.assertTrue(any("observable parent behavior" in issue.message for issue in issues))

    def test_separate_rsu_source_content_exposes_parent_behavior(self) -> None:
        parent = "校验通过后，系统生成计奖审核任务，任务状态为“待核查”，并进入任务详情页。"
        issues: list[validator.Issue] = []
        validator.validate_rsu_source_shape(
            issues,
            Path("map.md"),
            [
                rsu_row("RSU-001", "无", parent),
                rsu_row("RSU-002", parent, "顶部展示奖期编号和彩票年。"),
            ],
        )
        self.assertFalse(any("observable parent behavior" in issue.message for issue in issues))

    def test_source_match_ignores_inline_prototype_image(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            source_path = Path(temp) / "requirement.md"
            source_path.write_text(
                "校验通过后进入详情页。![image.png](https://example.test/prototype.png)"
                "顶部展示奖期编号。\n",
                encoding="utf-8",
            )
            issues: list[validator.Issue] = []

            checked, skipped = validator.validate_source_match(
                issues,
                Path("map.md"),
                [rsu_row("RSU-001", "无", "校验通过后进入详情页。顶部展示奖期编号。")],
                {"SRC-MOD": source_path},
            )

            self.assertEqual((checked, skipped), (1, 0))
            self.assertEqual(issues, [])

    def test_condition_event_is_not_mistaken_for_an_observable_result(self) -> None:
        self.assertFalse(validator.parent_has_observable_behavior("进入任务详情页后"))
        self.assertFalse(validator.parent_has_observable_behavior("任务状态为待核查时"))
        self.assertTrue(validator.parent_has_observable_behavior("系统进入任务详情页。"))

    def test_link_validation_can_exclude_downstream_output_tree(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            module_dir = Path(temp)
            target = module_dir / "target.md"
            source = module_dir / "source.md"
            generated = module_dir / "test-points" / "inputs" / "RSU-001-input.md"
            target.write_text("# target\n", encoding="utf-8")
            source.write_text("[valid](target.md)\n", encoding="utf-8")
            generated.parent.mkdir(parents=True)
            generated.write_text("[relocated](missing.md)\n", encoding="utf-8")

            issues: list[validator.Issue] = []
            checked, broken = validator.validate_links(
                issues,
                module_dir,
                set(),
                {module_dir / "test-points"},
            )

            self.assertEqual((checked, broken), (1, 0))
            self.assertEqual(issues, [])


if __name__ == "__main__":
    unittest.main()
