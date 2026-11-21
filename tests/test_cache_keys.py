"""Cache keys survive a move: roots and the package name a file, not its path (UR32)."""

import json
import shutil

from urdido import cache


def checkout(folder):
    """A project with one take and a stage that names it in its settings."""
    (folder / "narration").mkdir(parents=True)
    take = folder / "narration" / "intro.mp3"
    take.write_bytes(b"take bytes")
    return take


def key_in(folder, take, settings_extra=""):
    session = cache.Session(
        folder / "report.json", {"root": str(folder), "video": str(folder / "video")}
    )
    settings = [
        "-i",
        str(take),
        "-o",
        str(folder / "video" / "out.mp4") + settings_extra,
    ]
    return session.key(settings, [cache.__file__, take])


def test_two_checkouts_of_the_same_project_share_their_keys(tmp_path):
    first = checkout(tmp_path / "one")
    second = checkout(tmp_path / "elsewhere" / "two")
    assert key_in(tmp_path / "one", first) == key_in(
        tmp_path / "elsewhere" / "two", second
    )


def test_a_changed_input_or_setting_still_misses(tmp_path):
    take = checkout(tmp_path / "one")
    before = key_in(tmp_path / "one", take)
    take.write_bytes(b"another take")
    assert key_in(tmp_path / "one", take) != before
    assert key_in(tmp_path / "one", take, "x") != key_in(tmp_path / "one", take)


def test_an_upgrade_misses_only_where_the_stages_code_changed(tmp_path, monkeypatch):
    import urdido

    take = checkout(tmp_path / "one")
    before = key_in(tmp_path / "one", take)
    monkeypatch.setattr(urdido, "__version__", "9.9.9")
    assert key_in(tmp_path / "one", take) == before  # same code, new version: a hit


def test_files_are_labelled_by_root_and_package(tmp_path):
    session = cache.Session(
        tmp_path / "r.json", {"root": str(tmp_path), "video": str(tmp_path / "video")}
    )
    assert (
        session.label(tmp_path / "video" / "parts" / "a.png") == "<video>/parts/a.png"
    )
    assert session.label(tmp_path / "script.json") == "<root>/script.json"
    assert session.label(cache.__file__) == "urdido:cache.py"
    written = session.portable({"x": [str(tmp_path / "video" / "a.mp4")]})["x"][0]
    assert written.replace("\\", "/") == "<video>/a.mp4"


def test_a_stamp_from_an_older_urdido_rebuilds_and_is_reported(tmp_path, capsys):
    out = tmp_path / "out.txt"
    out.write_text("old", encoding="utf-8")
    stamp = out.with_name(out.name + ".cache.json")
    stamp.write_text(json.dumps({"key": "anything", "outputs": []}), encoding="utf-8")
    session = cache.Session(tmp_path / "report.json", {"root": str(tmp_path)})

    def make():
        out.write_text("new", encoding="utf-8")

    session.run("stage", [out], ["settings"], make)
    assert out.read_text(encoding="utf-8") == "new"
    assert session.events[0]["old_format"] is True
    assert json.loads(stamp.read_text(encoding="utf-8"))["format"] == cache.FORMAT
    session.publish()
    assert (
        "1 from an older urdido that could not be verified" in capsys.readouterr().out
    )
    hit = cache.Session(tmp_path / "report.json", {"root": str(tmp_path)})
    hit.run("stage", [out], ["settings"], lambda: None)
    assert hit.events[0]["hit"] is True


def test_a_moved_project_hits_the_stamps_it_carries(tmp_path):
    one = tmp_path / "one"
    take = checkout(one)
    out = one / "video" / "out.txt"
    out.parent.mkdir(parents=True)
    roots = lambda base: {"root": str(base), "video": str(base / "video")}  # noqa: E731

    def stage(base, made):
        session = cache.Session(base / "report.json", roots(base))
        session.run(
            "stage",
            [base / "video" / "out.txt"],
            ["-i", str(base / "narration/intro.mp3")],
            made,
            inputs=[base / "narration" / "intro.mp3"],
        )
        return session.events[0]["hit"]

    assert stage(one, lambda: out.write_text("made", encoding="utf-8")) is False
    shutil.copytree(one, tmp_path / "two")
    assert (
        stage(
            tmp_path / "two", lambda: (_ for _ in ()).throw(AssertionError("rebuilt"))
        )
        is True
    )
    assert take.exists()
