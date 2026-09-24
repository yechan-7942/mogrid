import os
import tempfile
import unittest
from unittest.mock import patch

from tools.sandbox import PROJECT_ROOT_ENV
from tools.skills import (
    MAX_SKILL_BODY_CHARS,
    GLOBAL_SKILLS_DIR_ENV,
    SkillError,
    discover_skills,
    load_skill,
    parse_frontmatter,
    render_skill_index,
)

VALID_SKILL = """---
description: 테스트를 실행하고 실패를 고치는 절차
---

1. python3 -m unittest discover -s tests -t . 를 실행한다.
2. 실패가 있으면 원인을 고친다.
"""


class SkillsTestCase(unittest.TestCase):
    def setUp(self):
        self._project_tmp = tempfile.TemporaryDirectory()
        self._global_tmp = tempfile.TemporaryDirectory()
        self.project_skills = os.path.join(self._project_tmp.name, ".mogrid", "skills")
        self.global_skills = os.path.join(self._global_tmp.name, "skills")
        os.makedirs(self.project_skills)
        os.makedirs(self.global_skills)
        # 전역 스킬 경로를 tmpdir로 덮어쓰지 않으면 테스트 결과가 실행하는 사람의
        # 홈 디렉터리 내용에 따라 달라진다.
        self._env_patch = patch.dict(
            os.environ,
            {
                PROJECT_ROOT_ENV: self._project_tmp.name,
                GLOBAL_SKILLS_DIR_ENV: self.global_skills,
            },
        )
        self._env_patch.start()

    def tearDown(self):
        self._env_patch.stop()
        self._project_tmp.cleanup()
        self._global_tmp.cleanup()

    def write_skill(self, directory: str, name: str, content: str) -> str:
        path = os.path.join(directory, f"{name}.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path


class ParseFrontmatterTests(unittest.TestCase):
    def test_parses_meta_and_body(self):
        meta, body = parse_frontmatter("---\ndescription: 설명\n---\n\n본문입니다\n")
        self.assertEqual(meta["description"], "설명")
        self.assertEqual(body, "본문입니다")

    def test_value_containing_colon_is_kept_whole(self):
        # 'description: 참고: https://...' 처럼 값 안에 콜론이 있어도 잘리면 안 된다.
        meta, _ = parse_frontmatter("---\ndescription: 참고: https://example.com\n---\n본문\n")
        self.assertEqual(meta["description"], "참고: https://example.com")

    def test_missing_frontmatter_raises(self):
        with self.assertRaises(SkillError):
            parse_frontmatter("그냥 본문만 있는 파일")

    def test_unclosed_frontmatter_raises(self):
        with self.assertRaises(SkillError):
            parse_frontmatter("---\ndescription: 설명\n본문\n")

    def test_non_key_value_line_raises(self):
        with self.assertRaises(SkillError):
            parse_frontmatter("---\n키값없음\n---\n본문\n")


class DiscoverSkillsTests(SkillsTestCase):
    def test_no_skills_returns_empty(self):
        skills, errors = discover_skills()
        self.assertEqual(skills, {})
        self.assertEqual(errors, [])

    def test_discovers_project_skill(self):
        self.write_skill(self.project_skills, "run-tests", VALID_SKILL)
        skills, errors = discover_skills()
        self.assertEqual(errors, [])
        self.assertIn("run-tests", skills)
        self.assertEqual(skills["run-tests"].source, "project")
        self.assertIn("unittest", skills["run-tests"].body)

    def test_discovers_global_skill(self):
        self.write_skill(self.global_skills, "commit-style", VALID_SKILL)
        skills, _ = discover_skills()
        self.assertEqual(skills["commit-style"].source, "global")

    def test_project_skill_overrides_global_with_same_name(self):
        self.write_skill(self.global_skills, "run-tests", VALID_SKILL)
        self.write_skill(
            self.project_skills,
            "run-tests",
            "---\ndescription: 이 프로젝트 전용 절차\n---\n프로젝트 본문\n",
        )
        skills, _ = discover_skills()
        self.assertEqual(skills["run-tests"].source, "project")
        self.assertEqual(skills["run-tests"].body, "프로젝트 본문")

    def test_directory_form_skill_is_discovered(self):
        # <name>/SKILL.md 형태는 스킬이 참고 파일을 같이 끼고 다닐 수 있게 해준다.
        skill_dir = os.path.join(self.project_skills, "deploy")
        os.makedirs(skill_dir)
        with open(os.path.join(skill_dir, "SKILL.md"), "w", encoding="utf-8") as f:
            f.write(VALID_SKILL)
        skills, errors = discover_skills()
        self.assertEqual(errors, [])
        self.assertIn("deploy", skills)

    def test_broken_skill_is_reported_not_silently_dropped(self):
        self.write_skill(self.project_skills, "good", VALID_SKILL)
        self.write_skill(self.project_skills, "broken", "frontmatter가 없는 파일")
        skills, errors = discover_skills()
        self.assertIn("good", skills)
        self.assertNotIn("broken", skills)
        self.assertEqual(len(errors), 1)
        self.assertIn("broken", errors[0][0])

    def test_missing_description_is_an_error(self):
        self.write_skill(self.project_skills, "nodesc", "---\nname: nodesc\n---\n본문\n")
        skills, errors = discover_skills()
        self.assertEqual(skills, {})
        self.assertIn("description", errors[0][1])

    def test_empty_body_is_an_error(self):
        self.write_skill(self.project_skills, "empty", "---\ndescription: 설명\n---\n")
        skills, errors = discover_skills()
        self.assertEqual(skills, {})

    def test_name_mismatching_filename_is_an_error(self):
        # 이름이 어긋나면 목록에 뜨는 이름과 load_skill로 부르는 이름이 달라진다.
        self.write_skill(
            self.project_skills, "actual", "---\nname: different\ndescription: 설명\n---\n본문\n"
        )
        skills, errors = discover_skills()
        self.assertEqual(skills, {})
        self.assertIn("different", errors[0][1])

    def test_matching_name_in_frontmatter_is_accepted(self):
        self.write_skill(
            self.project_skills, "same", "---\nname: same\ndescription: 설명\n---\n본문\n"
        )
        skills, errors = discover_skills()
        self.assertEqual(errors, [])
        self.assertIn("same", skills)

    def test_oversized_body_is_an_error(self):
        big = "---\ndescription: 설명\n---\n" + ("가" * (MAX_SKILL_BODY_CHARS + 1))
        self.write_skill(self.project_skills, "huge", big)
        skills, errors = discover_skills()
        self.assertEqual(skills, {})
        self.assertIn("깁니다", errors[0][1])

    def test_non_markdown_files_are_ignored(self):
        with open(os.path.join(self.project_skills, "notes.txt"), "w", encoding="utf-8") as f:
            f.write("스킬이 아님")
        skills, errors = discover_skills()
        self.assertEqual(skills, {})
        self.assertEqual(errors, [])


class RenderSkillIndexTests(SkillsTestCase):
    def test_index_has_names_and_descriptions_but_not_bodies(self):
        self.write_skill(self.project_skills, "run-tests", VALID_SKILL)
        skills, _ = discover_skills()
        index = render_skill_index(skills)
        self.assertIn("run-tests", index)
        self.assertIn("테스트를 실행하고", index)
        # 본문이 인덱스에 새어 들어가면 매 스텝 프롬프트가 스킬 개수만큼 불어난다.
        self.assertNotIn("unittest", index)

    def test_empty_skills_renders_empty_string(self):
        self.assertEqual(render_skill_index({}), "")


class LoadSkillTests(SkillsTestCase):
    def test_returns_body(self):
        self.write_skill(self.project_skills, "run-tests", VALID_SKILL)
        result = load_skill("run-tests")
        self.assertIn("unittest", result)
        self.assertIn("run-tests", result)

    def test_unknown_name_lists_available_skills(self):
        self.write_skill(self.project_skills, "run-tests", VALID_SKILL)
        with self.assertRaises(SkillError) as ctx:
            load_skill("nope")
        # 없는 이름을 불렀을 때 있는 목록을 같이 줘야 모델이 재추측하지 않는다.
        self.assertIn("run-tests", str(ctx.exception))

    def test_empty_name_raises(self):
        with self.assertRaises(SkillError):
            load_skill("  ")

    def test_surrounding_whitespace_is_tolerated(self):
        self.write_skill(self.project_skills, "run-tests", VALID_SKILL)
        self.assertIn("unittest", load_skill(" run-tests "))


if __name__ == "__main__":
    unittest.main()
