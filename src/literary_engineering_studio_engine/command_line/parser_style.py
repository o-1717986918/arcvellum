"""Parser registration for style engineering and reusable style libraries."""

from __future__ import annotations

from ..style_evaluator import STYLE_EVAL_MODES


def register_style_commands(sub) -> None:
    style = sub.add_parser("style-profile", help="Compile a literary style profile from a corpus.")
    style.add_argument("corpus", help="Corpus file or directory containing .txt/.md files.")
    style.add_argument("--out-dir", required=True, help="Output style asset directory.")
    style.add_argument("--name", required=True, help="Style profile name.")
    style.add_argument("--author", default="", help="Author or source label.")
    style.add_argument("--mode", default="public_domain_or_authorized")
    style.add_argument("--source-note", default="")

    style_eval = sub.add_parser("style-eval", help="Evaluate a candidate text against a style profile and reference text.")
    style_eval.add_argument("profile_dir", help="Directory containing style_metrics.json.")
    style_eval.add_argument("--reference", required=True, help="Original/reference text file.")
    style_eval.add_argument("--candidate", required=True, help="Candidate/back-translated/expanded text file.")
    style_eval.add_argument("--mode", default="back-translation", choices=sorted(STYLE_EVAL_MODES))
    style_eval.add_argument("--out-dir", default="", help="Output directory. Defaults to profile_dir/evaluation_results/{mode}.")

    style_prompt = sub.add_parser("style-prompt", help="Write a platform-agent task for an LLM-facing style constraint prompt.")
    style_prompt.add_argument("profile_dir", help="Directory containing style-profile.md and style_metrics.json.")
    style_prompt.add_argument("--provider", default="platform-agent", help="Legacy compatibility only; formal command always targets the platform agent.")
    style_prompt.add_argument("--out", default="", help="Output style prompt path. Defaults to profile_dir/style_prompt.md.")
    style_prompt.add_argument("--manifest-out", default="", help="Output prompt manifest path. Defaults to profile_dir/style_prompt.prompt.json.")

    style_prompt_eval = sub.add_parser("style-prompt-eval", help="Write a platform-agent task for a style-prompt evaluation candidate.")
    style_prompt_eval.add_argument("profile_dir", help="Directory containing style_prompt.md and style_metrics.json.")
    style_prompt_eval.add_argument("--reference", required=True, help="Original/reference Chinese text file.")
    style_prompt_eval.add_argument("--input", required=True, help="Back-translation English text, outline, or blind-review task input.")
    style_prompt_eval.add_argument("--mode", default="back-translation", choices=sorted(STYLE_EVAL_MODES))
    style_prompt_eval.add_argument("--provider", default="platform-agent", help="Legacy compatibility only; formal command always targets the platform agent.")
    style_prompt_eval.add_argument("--style-prompt", default="", help="Style prompt path. Defaults to profile_dir/style_prompt.md.")
    style_prompt_eval.add_argument("--out-dir", default="", help="Output directory. Defaults to profile_dir/evaluation_results/{mode}.")

    style_review = sub.add_parser(
        "prepare-style-review",
        help="Prepare an independent digest-bound semantic review for a formal style evaluation.",
    )
    style_review.add_argument("project", help="Work project directory.")
    style_review.add_argument("--profile-dir", required=True, help="Project-relative formal style profile directory.")
    style_review.add_argument("--target-id", required=True, help="Stable style route target id.")

    style_version = sub.add_parser(
        "build-style-version",
        help="Build an immutable content-addressed version from passing formal style evidence.",
    )
    style_version.add_argument("project", help="Work project directory.")
    style_version.add_argument("--profile-dir", required=True, help="Project-relative formal style profile directory.")
    style_version.add_argument("--target-id", required=True, help="Stable style route target id.")

    _register_style_library_commands(sub)


def _register_style_library_commands(sub) -> None:
    style_lab_list = sub.add_parser("style-lab-list", help="List author style projects and mountable style skills.")
    style_lab_list.add_argument("--library", default="", help="Style library root. Defaults to global config.")

    style_lab_author = sub.add_parser("style-lab-author", help="Create or update an author-centered style project.")
    style_lab_author.add_argument("--library", default="", help="Style library root. Defaults to global config.")
    style_lab_author.add_argument("--name", required=True, help="Author/project display name.")
    style_lab_author.add_argument("--author-id", default="", help="Stable author id.")
    style_lab_author.add_argument("--mode", default="public_domain_or_authorized")
    style_lab_author.add_argument("--source-note", default="")

    style_lab_work = sub.add_parser("style-lab-work", help="Create or update one work subproject under an author.")
    style_lab_work.add_argument("--library", default="", help="Style library root. Defaults to global config.")
    style_lab_work.add_argument("--author-id", required=True)
    style_lab_work.add_argument("--title", required=True)
    style_lab_work.add_argument("--work-id", default="")
    style_lab_work.add_argument("--year", default="")
    style_lab_work.add_argument("--notes", default="")

    style_lab_import = sub.add_parser("style-lab-import", help="Import a source text into an author work project.")
    style_lab_import.add_argument("--library", default="", help="Style library root. Defaults to global config.")
    style_lab_import.add_argument("--author-id", required=True)
    style_lab_import.add_argument("--work-id", required=True)
    style_lab_import.add_argument("--file", default="", help="Source .txt/.md file.")
    style_lab_import.add_argument("--text", default="", help="Inline source text.")
    style_lab_import.add_argument("--filename", default="")
    style_lab_import.add_argument("--chunk-chars", type=int, default=4000)

    style_lab_compile = sub.add_parser("style-lab-compile", help="Compile an author profile and write a platform-agent style prompt task.")
    style_lab_compile.add_argument("--library", default="", help="Style library root. Defaults to global config.")
    style_lab_compile.add_argument("--author-id", required=True)
    style_lab_compile.add_argument("--profile-id", default="default")
    style_lab_compile.add_argument("--provider", default="platform-agent", help="Legacy compatibility only; formal command always targets the platform agent.")

    style_lab_skill = sub.add_parser("style-lab-build-skill", help="Build a mountable style skill from an author profile.")
    style_lab_skill.add_argument("--library", default="", help="Style library root. Defaults to global config.")
    style_lab_skill.add_argument("--author-id", required=True)
    style_lab_skill.add_argument("--profile-id", default="default")
    style_lab_skill.add_argument("--style-id", default="")

    style_lab_mount = sub.add_parser("style-lab-mount", help="Mount a style skill into a creative project with highest priority.")
    style_lab_mount.add_argument("project", help="Work project directory.")
    style_lab_mount.add_argument("--library", default="", help="Style library root. Defaults to global config.")
    style_lab_mount.add_argument("--style-id", required=True)
    style_lab_mount.add_argument("--allow-unreviewed", action="store_true", help="Maintainer/debug only; formal Skill hosts must not bypass style readiness gates.")
