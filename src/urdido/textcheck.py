"""VM61 / PW700: declared text integrity, font coverage and measured layout."""
from __future__ import annotations

import base64
import io
import json
import re
import unicodedata
import warnings
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path

from urdido.declaration import BEAT, held
from urdido.sources.model import RecordingRefused


@dataclass(frozen=True)
class Policy:
    action: str = "off"
    protected_tokens: tuple[str, ...] = ()
    glyphs: bool = True


CURRENT = ContextVar("text_checks", default=Policy())


def policy(spec, language, *, enabled=True):
    tokens = spec.get("protected_tokens", [])
    if isinstance(tokens, dict):
        tokens = tokens.get(language, [])
    action = spec.get("action", "error" if enabled else "off")
    if action not in {"off", "warn", "error"} or not isinstance(tokens, list) \
            or not all(isinstance(t, str) and t for t in tokens) or not isinstance(spec.get("glyphs", True), bool):
        raise ValueError("text_checks needs action off/warn/error, protected_tokens and boolean glyphs")
    return Policy(action, tuple(tokens), spec.get("glyphs", True))


@contextmanager
def configured(spec, language="", *, enabled=True):
    token = CURRENT.set(policy(spec, language, enabled=enabled))
    try:
        yield CURRENT.get()
    finally:
        CURRENT.reset(token)


def corruption(text):
    # Query strings and normal sentence punctuation must remain valid.
    prose = re.sub(r"https?://\S+", "", text)
    found = []
    if "\ufffd" in text:
        found.append("replacement character U+FFFD")
    if re.search(r"(?<=[A-Za-zÀ-ÖØ-öø-ÿ])\?(?=[a-zà-öø-ÿ])", prose):
        found.append("question mark inside a word; review the original encoding")
    if re.search(r"[ÃÂ][\u00a1-\u00bf]", prose):
        found.append("possible UTF-8 mojibake; review the original encoding")
    return found


@lru_cache(maxsize=16)
def glyphs(url):
    from fontTools.ttLib import TTFont

    data = base64.b64decode(url.split(",", 1)[1])
    with TTFont(io.BytesIO(data), lazy=True) as font:
        return frozenset(font.getBestCmap() or {})


def inputs(document, script, language, theme, settings):
    if settings.action == "off":
        return []
    from urdido.sources.illustrated import brand_mark

    fields = [(key, document.get(key, ""), None) for key in ("title", "description", "credits", "generated")]
    for take, values in {"intro": script.get("intro", {}), "outro": script.get("outro", {}),
                         **{f"chapter-{key}": ch.get("card", {}) for key, ch in script.get("chapters", {}).items()},
                         **{f"chapter-{key}-result": ch.get("result", {}) for key, ch in script.get("chapters", {}).items()}}.items():
        fields.append((f"narration.{take}.{language}", values.get(language, ""), None))
    for take, beats in document.get("scenes", {}).items():
        for i, beat in enumerate(beats):
            prefix = f"scenes.{take}.{i}"
            full = beat.get("layout") in {"footage", "picture"} and held(beat, BEAT, "presentation") == "full"
            for key, role in (("caption", "display-800"), ("text", "text")):
                fields.append((f"{prefix}.{key}", beat.get(key, beat.get("title", "") if key == "caption" else ""), role))
            if brand_mark(beat, document) != "none":
                fields.append(("brand", document.get("brand", ""), "display-800"))
                if not full:
                    fields.append(("series", document.get("series", ""), "text"))
            if not full:
                fields.append((f"{prefix}.kicker", beat.get("kicker", ""), "display-800"))
                layout = held(beat, BEAT, "layout")
                for key, role in ({"date": [("big", "display-800")], "quote": [("quote", "display-800"), ("by", "text")]}.get(layout, [])):
                    fields.append((f"{prefix}.{key}", beat.get(key, ""), role))
                for n, item in enumerate(beat.get("items", [])):
                    fields.append((f"{prefix}.items.{n}", item, "display-800"))
                source = document.get("sources", {}).get(beat.get("source"), {})
                for key in ("label", "url"):
                    fields.append((f"sources.{beat.get('source')}.{key}", source.get(key, ""), "text"))
    findings, seen, maps = [], set(), {}
    for field, text, role in fields:
        text = str(text)
        if (field, text, role) in seen or not text:
            continue
        seen.add((field, text, role))
        for message in corruption(text):
            findings.append({"field": field, "rule": "encoding", "text": text, "message": message})
        if not settings.glyphs or role is None or theme is None:
            continue
        if role not in maps:
            try:
                maps[role] = glyphs(theme.fonts[role])
            except Exception as exc:
                maps[role] = None
                findings.append({"field": f"cards.theme.fonts.{role}", "rule": "font", "message": f"cannot read required font: {exc}"})
        if maps[role] is not None:
            rendered = text.upper() if field.endswith(".kicker") else text
            missing = sorted({ord(char) for char in rendered if not char.isspace() and unicodedata.category(char) not in {"Cf", "Cc"}
                              and ord(char) not in maps[role]})
            if missing:
                findings.append({"field": field, "rule": "glyph", "font_role": role, "text": text,
                                 "message": "missing font glyphs: " + ", ".join(f"U+{cp:04X}" for cp in missing)})
    return findings


def enforce(findings, settings=None):
    settings = settings or CURRENT.get()
    if not findings or settings.action == "off":
        return
    message = "text checks:\n" + "\n".join(f"{row['field']}: {row.get('message', row['rule'])}" for row in findings)
    if settings.action == "error":
        raise RecordingRefused(message)
    warnings.warn(message, UserWarning, stacklevel=2)


def measure(page, frame, name, layer):
    settings = CURRENT.get()
    if settings.action == "off":
        return []
    rows = page.evaluate(r"""({tokens,width,height}) => {
      const mapping=JSON.parse(document.body.dataset.textFields||'{}');
      const selectors=Object.keys(mapping).length?Object.keys(mapping):['h1','h2','p','.badge','.url'];
      const result=[];
      const rect=r=>({x:r.x,y:r.y,width:r.width,height:r.height});
      for(const selector of selectors) for(const [index,el] of [...document.querySelectorAll(selector)].entries()) {
        const style=getComputedStyle(el), box=el.getBoundingClientRect();
        if(style.display==='none'||style.visibility==='hidden'||Number(style.opacity)===0||!box.width||!box.height) continue;
        let hidden=false;for(let parent=el.parentElement;parent;parent=parent.parentElement){const s=getComputedStyle(parent);if(s.display==='none'||s.visibility==='hidden'||Number(s.opacity)===0){hidden=true;break;}}
        if(hidden) continue;
        const field=(mapping[selector]||selector)+(selector==='.tile strong'?'.'+index:'');
        const nodes=[];const walker=document.createTreeWalker(el,NodeFilter.SHOW_TEXT);
        while(walker.nextNode()) nodes.push(walker.currentNode);
        const text=nodes.map(n=>n.textContent).join('');
        if(!text.trim()) continue;
        const ranges=nodes.flatMap(node=>{const r=document.createRange();r.selectNodeContents(node);return [...r.getClientRects()]});
        const issue=(rule,message,detail)=>result.push({field,rule,text,message,box:rect(box),...detail});
        if(ranges.some(r=>r.left<box.left-2||r.right>box.right+2)) issue('overflow','text exceeds its own horizontal box',{});
        const viewport={left:0,top:0,right:width,bottom:height};
        const containers=[{node:null,box:viewport}];
        const boundary=el.closest('[data-text-box]');
        if(boundary) containers.push({node:boundary,box:boundary.getBoundingClientRect()});
        for(let parent=el;parent;parent=parent.parentElement){const s=getComputedStyle(parent);
          if(['hidden','clip','auto','scroll'].includes(s.overflowX)||['hidden','clip','auto','scroll'].includes(s.overflowY)) containers.push({node:parent,box:parent.getBoundingClientRect()});}
        for(const container of containers) {
          const b=container.box;
          if(ranges.some(r=>r.left<b.left-2||r.right>b.right+2||r.top<b.top-2||r.bottom>b.bottom+2)) {
            issue('clipping','text exceeds its assigned or clipping box',{boundary:{x:b.left,y:b.top,width:b.right-b.left,height:b.bottom-b.top}});break;
          }
        }
        const span=(start,end)=>{let at=0,first,last;for(const node of nodes){const next=at+node.textContent.length;
          if(first===undefined&&start<next) first=[node,start-at];
          if(end<=next){last=[node,end-at];break;}at=next;}
          if(!first||!last)return [];const r=document.createRange();r.setStart(...first);r.setEnd(...last);return [...r.getClientRects()].filter(b=>b.width&&b.height);};
        for(const token of tokens){let at=text.indexOf(token);while(at>=0){const parts=span(at,at+token.length);
          const lines=[];for(const r of parts)if(!lines.some(y=>Math.abs(y-r.top)<2))lines.push(r.top);
          if(lines.length>1)issue('protected_break','protected token is split across lines',{token,lines:lines.length});
          at=text.indexOf(token,at+token.length);}}
      }
      return result;
    }""", {"tokens": list(settings.protected_tokens), "width": frame.width, "height": frame.height})
    return [{**row, "page": name, "layer": layer} for row in rows]


def publish(findings, path):
    path = Path(path)
    settings = CURRENT.get()
    if settings.action == "off":
        path.unlink(missing_ok=True)
        return
    path.write_text(json.dumps({**asdict(settings), "findings": findings}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    enforce(findings, settings)
