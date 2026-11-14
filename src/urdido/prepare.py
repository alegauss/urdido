"""VM60 / PW703: plan and explicitly authorize one coherent narration preparation."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import tomllib
import uuid
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from types import SimpleNamespace

from videomaker import keywords, media
from videomaker.build import Build
from videomaker.cache import file_hash
from videomaker.narration import Takes
from videomaker.narration_words import transcribe
from videomaker.sources.model import RecordingRefused


def opening(script_file, language):
    """Reuse VM29's existing Node gate; no duplicate opening rules or purchases."""
    folder = Path(__file__).resolve().parents[1] / "narration"
    code = """const {pathToFileURL}=await import('node:url');
const {readFileSync}=await import('node:fs');
const {takes}=await import(pathToFileURL(process.argv[1]));
const {checkOpening}=await import(pathToFileURL(process.argv[2]));
const script=JSON.parse(readFileSync(process.argv[3],'utf8').replace(/^\\uFEFF/,''));
checkOpening({narration:takes({script,dir:'.'}),locale:process.argv[4]});"""
    run = subprocess.run(["node", "--input-type=module", "-e", code, str(folder / "takes.mjs"),
                          str(folder / "opening.mjs"), str(script_file), language], capture_output=True, text=True, encoding="utf-8")
    if run.returncode:
        raise RecordingRefused(run.stderr or run.stdout)


def voice(root, lines_file, language, service, *, keys=None, spend=False):
    args = [sys.executable, "-m", "polyweave", "voice.lines", "--script", str(lines_file), "--locale", language,
            "--service", service, "--spend", str(spend).lower(), "--root", str(root), "--json"]
    if keys:
        args += ["--keys", *keys]
    run = subprocess.run(args, capture_output=True, text=True, encoding="utf-8")
    if run.returncode:
        raise RuntimeError(f"voice.lines refused: {run.stderr or run.stdout}")
    answer = json.loads(run.stdout)
    if answer.get("ok") is False or answer.get("error"):
        raise RuntimeError(f"voice.lines refused: {json.dumps(answer, ensure_ascii=False)}")
    return answer


def suggestions(words, phrase):
    """Actual transcript spans for human review; none is accepted as an anchor."""
    target = keywords.fold(phrase)
    size = max(1, len(phrase.split()))
    candidates = []
    for first in range(len(words)):
        for count in range(max(1, size - 2), size + 3):
            chosen = words[first:first + count]
            if len(chosen) != count:
                continue
            text = " ".join(w["text"] for w in chosen)
            score = SequenceMatcher(None, target, keywords.fold(text)).ratio()
            if score >= .45:
                candidates.append({"heard": text, "start": chosen[0]["start"], "end": chosen[-1]["end"],
                                   "similarity": round(score, 4), "requires_review": True})
    return sorted(candidates, key=lambda c: -c["similarity"])[:3]


def assessments(name, audio, highlight_lines, beats, aliases):
    try:
        words = keywords.word_record(audio)
    except (RecordingRefused, ValueError, KeyError, OSError):
        return []
    result, cursor = [], 0
    for i, item in enumerate(highlight_lines.get(name, [])):
        phrase = item.get("hear", item["show"])
        found = keywords.matches(words, phrase, cursor, aliases=aliases)
        row = {"kind": "highlight", "field": f"lines.{name}.{i}.hear", "text": phrase}
        if found:
            cursor = found[0][1]
            row["status"] = "matched"
        else:
            row.update(status="needs_review", candidates=suggestions(words, phrase))
        result.append(row)
    for i, beat in enumerate(beats):
        if "from_word" not in beat:
            continue
        spec = beat["from_word"]
        phrase = spec if isinstance(spec, str) else spec["text"]
        row = {"kind": "beat", "beat": beat.get("id", f"{name}-{i}"), "field": "from_word", "text": phrase}
        try:
            keywords.anchor(audio, spec, aliases=aliases)
            row["status"] = "matched"
        except RecordingRefused as exc:
            row.update(status="needs_review", reason=str(exc), candidates=suggestions(words, phrase))
        result.append(row)
    return result


def transcription_rate(profile, unit):
    price = profile.get("prices", {}).get("scribe_v1")
    if not price:
        return None
    divisors = {"second": 1, "minute": 60, "hour": 3600}
    rate = price.get("rate")
    if price.get("per") not in divisors or not isinstance(rate, (int, float)) or isinstance(rate, bool) \
            or not math.isfinite(rate) or rate < 0 or price.get("unit", unit) != unit:
        raise ValueError("Scribe price needs a finite rate per second/minute/hour in the voice quote's unit")
    return rate / divisors[price["per"]]


def prepare(args):
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.language):
        raise ValueError("invalid narration language")
    build = Build(Path(args.declaration), SimpleNamespace(language=args.language, plan=True, cards=False))
    root = Path(args.root).resolve() if args.root else build.here
    script_file = Path(build.path(build.decl["narration"]["script"]))
    script = build.load(build.decl["narration"]["script"])
    takes = Takes(script, build.path(build.decl["narration"]["takes"]))
    selected = args.take or list(takes.lines)
    if len(set(selected)) != len(selected) or set(selected) - set(takes.lines) \
            or any(not re.fullmatch(r"[A-Za-z0-9_-]+", name) for name in selected):
        raise ValueError("select known narration takes once each")
    authorized = set(args.authorize_take or [])
    if authorized - set(selected):
        raise ValueError("authorized takes must be part of this plan's selection")
    if args.max_cost is not None and (not math.isfinite(args.max_cost) or args.max_cost < 0):
        raise ValueError("--max-cost must be a finite nonnegative estimate ceiling")
    opening(script_file, args.language)
    config_file = root / "polyweave.toml"
    config = tomllib.loads(config_file.read_text("utf-8-sig"))
    profiles = config.get("service", {})
    matching = [name for name, profile in profiles.items() if script["model"] in profile.get("prices", {})]
    service = args.service or (matching[0] if len(matching) == 1 else None)
    if service not in profiles:
        raise ValueError("select the Polyweave service profile pricing this narration model")
    profile = profiles[service]
    folder = Path(takes.folder).resolve()
    if not folder.is_relative_to(root):
        raise ValueError("the narration folder must stay inside the Polyweave project root")
    inputs = {script_file: file_hash(script_file), config_file: file_hash(config_file)}
    payload = {"voice": script["voice"], "model": script["model"],
               "out": folder.relative_to(root).as_posix() + "/{locale}/{key}.mp3",
               "lines": [{"key": name, "locale": args.language, "text": takes.spoken(args.language, takes.lines[name][args.language])}
                         for name in selected],
               **{key: script[key] for key in ("stability", "similarity", "style", "speed") if key in script}}
    identity = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]
    work = root / ".polyweave/prepare" / identity
    work.mkdir(parents=True, exist_ok=True)
    lines_file = work / "lines.json"
    lines_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    quote = voice(root, lines_file, args.language, service)
    if quote.get("spent"):
        raise RuntimeError("voice.lines reported spending during a dry plan")
    for row in [*quote.get("voice", []), *quote.get("current", []), *quote.get("adoptable", [])]:
        if row.get("key") not in selected or row.get("locale") != args.language \
                or (root / row["out"]).resolve() != Path(takes.take_file(args.language, row["key"])).resolve():
            raise RuntimeError("voice plan changed the selected language, take or output path")
        if "price" in row and (not isinstance(row["price"], (int, float)) or isinstance(row["price"], bool) or not math.isfinite(row["price"]) or row["price"] < 0):
            raise RuntimeError("voice plan returned an invalid estimate")
    adopted = {row["key"] for row in quote.get("adoptable", [])}
    unchanged = {name for name in selected if takes.current(takes.take_file(args.language, name), args.language, takes.lines[name][args.language])}
    pending = {row["key"]: row for row in quote.get("voice", []) if row["key"] not in adopted and row["key"] not in unchanged}
    remaining_voice = set(pending)
    if set(pending) - set(selected):
        raise RuntimeError("voice plan included an unselected take")
    unit = quote.get("unit")
    rate = transcription_rate(profile, unit)
    aliases = keywords.aliases(script, args.language)
    keywords.normalizer(aliases)
    document = build.load(build.decl["source"]["declaration"]) if build.decl["source"]["kind"] == "illustrated" else {}
    highlights = build.load(build.decl["highlights"]["declaration"]) if build.decl.get("highlights") else {"lines": {}}
    for file, sha in build.input_hashes.items():
        inputs[file] = sha
    report = {"voice": script["voice"], "model": script["model"], "language": args.language,
              "pronounce": script.get("pronounce", {}).get(args.language, {}), "authorized": sorted(authorized),
              "unit": unit, "voice_estimate": sum(row["price"] for row in pending.values()),
              "transcription_rate_per_second": rate, "quote": quote, "takes": [], "executed": [],
              "estimated_spent": 0.0, "status": "planned", "aliases": aliases,
              "speech_review": [],
              "reused_existing_takes": sorted(unchanged),
              "inputs": [{"file": str(path), "sha256": sha} for path, sha in inputs.items()]}

    def verify_inputs():
        if any(file_hash(path) != sha for path, sha in inputs.items()):
            raise RecordingRefused("prepare inputs changed after quotation; run a new plan")

    def states():
        rows = []
        for name in selected:
            audio = Path(takes.take_file(args.language, name))
            current = name not in remaining_voice and takes.current(str(audio), args.language, takes.lines[name][args.language])
            try:
                words = keywords.word_record(audio) if current else None
            except (RecordingRefused, ValueError, KeyError, OSError):
                words = None
            beats = document.get("scenes", {}).get(name, [])
            rows.append({"take": name, "voice_current": current, "voice_needed": name in remaining_voice,
                         "transcript_current": words is not None,
                         "transcription_estimate": media.seconds(str(audio)) * rate if current and words is None and rate is not None else (0 if words is not None else None),
                         "impacts": {"beats": [b.get("id", f"{name}-{i}") for i, b in enumerate(beats)],
                                     "word_anchored_beats": [b.get("id", f"{name}-{i}") for i, b in enumerate(beats) if "from_word" in b],
                                     "highlight_labels": [line["show"] for line in highlights["lines"].get(name, [])],
                                     "translated_caption_tracks": list(build.decl.get("captions", {}).get("translations", {})),
                                     "following_takes_may_move": list(takes.lines)[list(takes.lines).index(name) + 1:]},
                         "anchors": assessments(name, audio, highlights["lines"], beats, aliases) if current and words is not None else []})
        return rows

    report["takes"] = states()
    report["planned_takes"] = copy.deepcopy(report["takes"])
    lock = root / ".polyweave/prepare/EXECUTING.lock"
    acquired = False
    try:
        verify_inputs()
        if args.execute:
            if not authorized and any(row["voice_needed"] or not row["transcript_current"] for row in report["takes"]):
                raise RecordingRefused("no changed takes authorized; add --authorize-take NAME to execute their preparation")
            paid = [row for row in report["takes"] if row["take"] in authorized and (row["voice_needed"] or not row["transcript_current"])]
            if paid and (args.max_cost is None or not unit):
                raise RecordingRefused("authorized preparation needs --max-cost and a priced service unit")
            if paid and rate is None:
                raise RecordingRefused(f"declare prices.scribe_v1 in {config_file} with a rate per second/minute/hour before authorizing transcription")
            keys = [name for name in selected if name in pending and name in authorized]
            price = sum(pending[name]["price"] for name in keys)
            ceiling = args.max_cost
            if paid and quote.get("left") is not None:
                ceiling = min(ceiling, float(quote["left"]))
            report["estimate_ceiling"] = ceiling
            if paid and price > ceiling + 1e-9:
                raise RecordingRefused("authorized voice estimate exceeds --max-cost")
            if paid:
                descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.close(descriptor)
                acquired = True
            verify_inputs()
            if keys:
                purchase_file = work / "authorized-lines.json"
                purchase_file.write_text(json.dumps({**payload, "lines": [line for line in payload["lines"] if line["key"] in keys]},
                                                   ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                answer = voice(root, purchase_file, args.language, service, keys=keys, spend=True)
                report["executed"].append({"stage": "voice", "answer": answer})
                report["speech_review"].extend({"kind": "voice_check", "take": row["key"], "status": "needs_review", "failed": row["failed"]}
                                                for row in answer.get("voiced", []) if row.get("failed"))
                voiced = {row["key"] for row in answer.get("voiced", [])}
                if voiced - set(keys):
                    raise RuntimeError("voice.lines generated an unauthorized take")
                report["estimated_spent"] += sum(pending[name]["price"] for name in voiced)
                fulfilled = voiced | {row["key"] for row in answer.get("current", [])}
                remaining_voice.difference_update(fulfilled)
            for name in selected:
                if name not in authorized:
                    continue
                audio = Path(takes.take_file(args.language, name))
                if name in remaining_voice or not takes.current(str(audio), args.language, takes.lines[name][args.language]):
                    continue  # a provider budget stop never transcribes the old voice
                try:
                    keywords.word_record(audio)
                    continue
                except (RecordingRefused, ValueError, KeyError, OSError):
                    pass
                verify_inputs()
                estimate = media.seconds(str(audio)) * rate
                if report["estimated_spent"] + estimate > ceiling + 1e-9:
                    raise RecordingRefused("transcription estimate exceeds the remaining project/--max-cost ceiling; generated takes were kept")
                message = transcribe(audio, build.decl["video"]["languages"][args.language],
                                     base_url=profile.get("base", "https://api.elevenlabs.io"),
                                     key_env=profile.get("key_env", "ELEVENLABS_API_KEY"))
                if message.startswith("transcribed "):
                    report["estimated_spent"] += estimate
                report["executed"].append({"stage": "transcription", "take": name, "message": message, "estimate": estimate})
            verify_inputs()
            report["status"] = "prepared"
    except BaseException as exc:
        report.update(status="stopped", reason=str(exc))
        raise
    finally:
        if acquired:
            lock.unlink(missing_ok=True)
        report["takes"] = states()
        report["needs_review"] = [*report["speech_review"], *[{"take": row["take"], **anchor} for row in report["takes"] for anchor in row["anchors"] if anchor["status"] == "needs_review"]]
        report["selected_takes_ready"] = all(row["voice_current"] and row["transcript_current"] for row in report["takes"]) and not report["needs_review"]
        if report["status"] == "prepared" and not report["selected_takes_ready"]:
            report["status"] = "needs_review" if report["needs_review"] else "partial"
        report["at"] = datetime.now(timezone.utc).isoformat()
        text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        attempt = work / f"attempt-{uuid.uuid4().hex}.json"
        attempt.write_text(text, encoding="utf-8")
        pending_report = work / f"report-{uuid.uuid4().hex}.tmp"
        try:
            pending_report.write_text(text, encoding="utf-8")
            os.replace(pending_report, work / "report.json")
        finally:
            pending_report.unlink(missing_ok=True)
        print(f"prepare {report['status']}: voice estimate {report['voice_estimate']:g} {unit}; {work / 'report.json'}")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("declaration", type=Path)
    parser.add_argument("--language", required=True)
    parser.add_argument("--take", action="append")
    parser.add_argument("--authorize-take", action="append", help="explicitly allow generation/transcription of this take")
    parser.add_argument("--execute", action="store_true", help="prepare authorized takes; default only plans with no paid calls")
    parser.add_argument("--max-cost", type=float, help="maximum combined estimate in the quoted service unit")
    parser.add_argument("--root", type=Path, help="Polyweave project root; defaults to the video's folder")
    parser.add_argument("--service", help="the project's configured narration service profile")
    prepare(parser.parse_args(argv))
    return 0
