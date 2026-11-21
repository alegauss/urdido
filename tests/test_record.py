"""A scene video recorded with one command, stopping at the first failure (UR10)."""

import pytest

from urdido.record import Recorder, RecordFailed, Step, main, steps_of

STEPS = [
    Step("scenes", "x", ("rec/scenes", "rec/instance.json")),
    Step("agent", "x", ("rec/session.json",)),
    Step("replay", "x", ("rec/replay.json",)),
    Step("down", "x", (), always=True),
]


def fake(here, fails=()):
    """A run that writes what each step makes, marked new, unless the step fails."""
    ran = []

    def run(step):
        ran.append(step.name)
        if step.name in fails:
            (here / "rec").mkdir(exist_ok=True)
            for made in step.makes:
                (here / made).write_text("partial", encoding="utf-8")
            return 1
        for made in step.makes:
            path = here / made
            if made.endswith(".json"):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(f"new {step.name}", encoding="utf-8")
            else:
                path.mkdir(parents=True, exist_ok=True)
                (path / "clip.webm").write_text("new", encoding="utf-8")
        return 0

    return run, ran


def old_recording(here):
    (here / "rec/scenes").mkdir(parents=True)
    (here / "rec/scenes/clip.webm").write_text("old", encoding="utf-8")
    for name in ("instance", "session", "replay"):
        (here / f"rec/{name}.json").write_text(f"old {name}", encoding="utf-8")


def read(here, made):
    return (here / made).read_text(encoding="utf-8")


def test_a_complete_run_replaces_the_recording_and_tears_down(tmp_path):
    old_recording(tmp_path)
    run, ran = fake(tmp_path)
    assert Recorder(tmp_path, STEPS, run).go() == ["scenes", "agent", "replay"]
    assert ran == ["scenes", "agent", "replay", "down"]
    assert read(tmp_path, "rec/session.json") == "new agent"
    assert read(tmp_path, "rec/scenes/clip.webm") == "new"
    assert not (tmp_path / ".urdido/record/previous").exists()


def test_a_failed_step_stops_the_run_and_leaves_the_previous_recording_intact(tmp_path):
    old_recording(tmp_path)
    run, ran = fake(tmp_path, fails={"agent"})
    with pytest.raises(RecordFailed, match="Resume with --from agent"):
        Recorder(tmp_path, STEPS, run).go()
    assert ran == [
        "scenes",
        "agent",
        "down",
    ]  # replay never ran; the instance still went down
    for name in ("instance", "session", "replay"):
        assert read(tmp_path, f"rec/{name}.json") == f"old {name}"
    assert read(tmp_path, "rec/scenes/clip.webm") == "old"
    pending = tmp_path / ".urdido/record/pending"
    assert (pending / "rec/instance.json").read_text(encoding="utf-8") == "new scenes"


def test_a_resumed_run_keeps_the_finished_steps_and_runs_from_the_failed_one(tmp_path):
    old_recording(tmp_path)
    run, _ = fake(tmp_path, fails={"agent"})
    with pytest.raises(RecordFailed):
        Recorder(tmp_path, STEPS, run).go()
    run, ran = fake(tmp_path)
    assert Recorder(tmp_path, STEPS, run).go("agent") == ["scenes", "agent", "replay"]
    assert ran == ["agent", "replay", "down"]
    assert read(tmp_path, "rec/instance.json") == "new scenes"
    assert read(tmp_path, "rec/session.json") == "new agent"
    assert not (tmp_path / ".urdido/record").joinpath("state.json").exists()


def test_a_second_failure_on_resume_still_restores_the_old_recording(tmp_path):
    old_recording(tmp_path)
    run, _ = fake(tmp_path, fails={"agent"})
    with pytest.raises(RecordFailed):
        Recorder(tmp_path, STEPS, run).go()
    run, _ = fake(tmp_path, fails={"replay"})
    with pytest.raises(RecordFailed, match="--from replay"):
        Recorder(tmp_path, STEPS, run).go("agent")
    assert read(tmp_path, "rec/instance.json") == "old instance"
    assert read(tmp_path, "rec/session.json") == "old session"


def test_resume_is_refused_without_a_failed_run_before_that_step(tmp_path):
    with pytest.raises(ValueError, match="no failed run"):
        Recorder(tmp_path, STEPS, fake(tmp_path)[0]).go("replay")
    with pytest.raises(ValueError, match="no step named"):
        Recorder(tmp_path, STEPS, fake(tmp_path)[0]).go("nope")


def test_steps_are_declared_with_names_commands_and_inside_paths():
    assert steps_of(
        {"record": {"step": [{"name": "a", "command": ["py"], "makes": ["x"]}]}}
    )[0].makes == ("x",)
    with pytest.raises(ValueError, match="declares no"):
        steps_of({})
    with pytest.raises(ValueError, match="name of its own"):
        steps_of(
            {
                "record": {
                    "step": [
                        {"name": "a", "command": "x"},
                        {"name": "a", "command": "y"},
                    ]
                }
            }
        )
    with pytest.raises(ValueError, match="inside the video's folder"):
        steps_of(
            {"record": {"step": [{"name": "a", "command": "x", "makes": ["../out"]}]}}
        )


def test_the_cli_runs_real_commands_and_stops_at_a_failure(tmp_path, capsys):
    import sys

    py = sys.executable.replace("\\", "/")
    toml = tmp_path / "video.toml"
    toml.write_text(
        f"""
[[record.step]]
name = "write"
command = ["{py}", "-c", "open('made.txt', 'w').write('new')"]
makes = ["made.txt"]
[[record.step]]
name = "break"
command = ["{py}", "-c", "raise SystemExit(3)"]
""",
        encoding="utf-8",
    )
    (tmp_path / "made.txt").write_text("old", encoding="utf-8")
    assert main([str(toml)]) == 1
    assert "--from break" in capsys.readouterr().err
    assert (tmp_path / "made.txt").read_text(encoding="utf-8") == "old"
    assert main([str(toml), "--list"]) == 0
    assert "write  done\nbreak  failed" in capsys.readouterr().out
