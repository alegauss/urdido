"""VM46: stale writes fail, dry runs are inert and beat IDs survive reordering."""
import json

import pytest

from urdido.storyboard import digest, edit


@pytest.fixture
def storyboard(tmp_path):
    file = tmp_path / "storyboard.json"
    data = {"brand": "Viglet", "scenes": {"intro": [{"id": "a", "title": "Olá"}, {"id": "b", "title": "B"}]},
            "credits": "Original", "unknown": {"keep": [1, 2]}}
    file.write_bytes((json.dumps(data, ensure_ascii=False, indent=2) + "\n").replace("\n", "\r\n").encode())
    return file


def test_dry_run_matches_write_and_preserves_utf8_order_and_newlines_vm46(storyboard):
    raw = storyboard.read_bytes()
    operations = [{"op": "set", "beat": "a", "values": {"title": "Diário da Ana"}},
                  {"op": "credits", "value": "Créditos"}]
    preview = edit(storyboard, digest(raw), operations, dry_run=True)
    assert storyboard.read_bytes() == raw
    assert "Diário da Ana" in preview["diff"]
    assert not list(storyboard.parent.glob("*.lock"))
    actual = edit(storyboard, digest(raw), operations)
    assert actual == preview
    output = storyboard.read_bytes()
    assert b"\r\n" in output and b"\n" not in output.replace(b"\r\n", b"")
    data = json.loads(output)
    assert list(data) == ["brand", "scenes", "credits", "unknown"]
    assert data["unknown"] == {"keep": [1, 2]}


def test_stale_edit_cannot_replace_a_later_change_vm46(storyboard):
    old = digest(storyboard.read_bytes())
    edit(storyboard, old, [{"op": "credits", "value": "Newer"}])
    current = storyboard.read_bytes()
    with pytest.raises(ValueError, match="stale"):
        edit(storyboard, old, [{"op": "credits", "value": "Old generator"}])
    assert storyboard.read_bytes() == current


def test_ids_survive_insert_and_move_vm46(storyboard):
    operations = [{"op": "insert", "take": "intro", "after": "a", "value": {"id": "c", "title": "C"}},
                  {"op": "move", "beat": "b", "take": "intro"},
                  {"op": "set", "beat": "a", "values": {"seconds": 3}}]
    edit(storyboard, digest(storyboard.read_bytes()), operations)
    beats = json.loads(storyboard.read_bytes())["scenes"]["intro"]
    assert [b["id"] for b in beats] == ["b", "a", "c"]
    assert beats[1]["seconds"] == 3


def test_failed_atomic_replace_preserves_original_and_releases_lock_vm46(storyboard, monkeypatch):
    raw = storyboard.read_bytes()

    def fail(*args):
        raise PermissionError("file busy")

    monkeypatch.setattr("urdido.storyboard.os.replace", fail)
    with pytest.raises(PermissionError):
        edit(storyboard, digest(raw), [{"op": "credits", "value": "New"}])
    assert storyboard.read_bytes() == raw
    assert sorted(p.name for p in storyboard.parent.iterdir()) == ["storyboard.json"]


def test_assign_ids_is_repeatable_and_preserves_existing_ids_vm46(storyboard):
    data = json.loads(storyboard.read_bytes())
    del data["scenes"]["intro"][1]["id"]
    storyboard.write_text(json.dumps(data), encoding="utf-8")
    sha = digest(storyboard.read_bytes())
    preview = edit(storyboard, sha, [{"op": "assign-ids"}], dry_run=True)
    assert edit(storyboard, sha, [{"op": "assign-ids"}])["after"] == preview["after"]
    after = json.loads(storyboard.read_bytes())
    assert after["scenes"]["intro"][0]["id"] == "a"
    assert not edit(storyboard, preview["after"], [{"op": "assign-ids"}])["changed"]


def test_duplicate_id_or_empty_take_never_writes_vm46(storyboard):
    raw = storyboard.read_bytes()
    for operations in ([{"op": "insert", "take": "intro", "value": {"id": "a", "title": "duplicate"}}],
                       [{"op": "remove", "beat": "a"}, {"op": "remove", "beat": "b"}]):
        with pytest.raises(ValueError):
            edit(storyboard, digest(raw), operations)
        assert storyboard.read_bytes() == raw
