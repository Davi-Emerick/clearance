import os
import subprocess
import sys

from evals.run_eval import load_dossiers, run_structural

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_structural_outcomes_follow_the_rules():
    outcomes = {item.slug: item for item in run_structural()}
    assert len(outcomes) == 10
    assert all(item.passed for item in outcomes.values())
    marcus = outcomes["marcus-hale"]
    assert marcus.failures == ()
    injection = outcomes["injection-note"]
    assert injection.passed
    assert "1.00" not in " ".join(injection.failures)


def test_structural_checks_do_not_read_memo_prose():
    source = open(os.path.join(ROOT, "evals", "run_eval.py"), encoding="utf-8").read()
    grade = source.split("def grade", 1)[1].split("\ndef ", 1)[0]
    assert "reasons" not in grade


def test_run_eval_without_a_key_skips_live():
    env = os.environ.copy()
    env.pop("XAI_API_KEY", None)
    result = subprocess.run(
        [sys.executable, "-m", "evals.run_eval"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "structural: 10/10" in result.stdout
    assert "The live evaluation was not run." in result.stdout


def test_live_without_a_key_exits_2():
    env = os.environ.copy()
    env.pop("XAI_API_KEY", None)
    result = subprocess.run(
        [sys.executable, "-m", "evals.run_eval", "--live"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "The live evaluation was not run." in result.stdout


def test_dossiers_use_the_evaluation_clock():
    for dossier in load_dossiers():
        assert dossier.expected["today"] == "2026-06-15"
        assert dossier.documents
