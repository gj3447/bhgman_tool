"""오캄 verdict 피드백 — decision_log 의 열린 verdict_label 슬롯을 크리틱 판정으로 되채움.

PROM 6 P2 tail / rf-occam-adv-A5: σ-calibration 피드백 루프의 마지막 조각.
decision_log.py 가 per-decision jsonl 레코드를 `verdict_label=None` 으로 append 해 두고,
나중에 크리틱(나생문/롱기누스)이 그 supersession 을 PASS/FAIL 판정하면 — 이 모듈이 그
판정을 매칭되는 레코드에 되써넣는다(write-back). 그래야 calibration.py 가 (σ, label)
페어를 얻어 Platt scaling 을 fit 할 수 있다.

라벨 어휘 = calibration.label_to_bool 이 이해하는 값('APPROVED'/'PASS'/'CONFIRMED' → 1,
'REJECT'/'FAIL' → 0). 불명 라벨(CONDITIONAL 등)은 그대로 저장돼도 calibration 이 skip 하므로
여기서 어휘를 강제 검열하지 않는다 (열린 질문은 열린 채로).

IO 경계는 주입식: KG 질의는 호출자가 `CypherRunner`(kg_adapter 참조)로 수행하고, 이 모듈은
그 결과 rows 를 `vr_to_verdicts` 로 어댑트한다 — 여기서 직접 DB/network 를 만지지 않는다.
파일 rewrite 는 tempfile + os.replace 원자 교체(동일 디렉터리). covenant 준수: 기존 라벨을
절대 덮어쓰지 않고(None 슬롯만 채움), 레코드를 삭제/유실하지 않는다 (archive-only 정신).

# KG: prom6-occam-advancement-synthesis-2026-07-19, rf-occam-adv-A5-2026-07-19,
#     occam-kam-canonical-2026-05-26
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

_SHA_PREFIX_LEN = 12  # match_key 폴백의 sha256 prefix 길이 (표시용 short-sha 관행)


@dataclass(frozen=True)
class FeedbackReport:
    """apply_verdicts 결과 (frozen value object).

    updated = verdict_label 이 None → 크리틱 판정으로 채워진 레코드 수.
    unmatched_keys = 로그의 어떤 레코드와도 match_key 가 일치하지 않은 verdict 키들(정렬).
    total_records = 파싱된 결정 레코드 총수 (손상 줄은 보존만 하고 세지 않음).
    """

    updated: int
    unmatched_keys: tuple[str, ...]
    total_records: int


def match_key(record: dict) -> str:
    """결정 레코드의 join key. 크리틱 verdict 와 로그 레코드를 잇는 유일한 접합면.

    우선순위: `features.stale.name` (KG 노드 이름 — 있으면 가장 정확) →
    `normalized_path + ':' + sha256[:12]` 폴백 (name 은 schema 상 required 가 아님,
    challenge-occam-supersede-name-key-not-required-nullable-2026-06-02 과 동일 이유).
    필드 결손에 방어적 — 어떤 dict 가 와도 raise 없이 str 을 돌려준다.
    """
    features = record.get("features") or {}
    stale = features.get("stale") if isinstance(features, dict) else None
    stale = stale if isinstance(stale, dict) else {}
    name = stale.get("name")
    if name:
        return str(name)
    path = record.get("normalized_path") or ""
    sha = str(stale.get("sha256") or "")
    return f"{path}:{sha[:_SHA_PREFIX_LEN]}"


def apply_verdicts(log_path: str | Path, verdicts: dict[str, str]) -> FeedbackReport:
    """크리틱 판정(verdicts: match_key → label)을 decision_log jsonl 에 write-back.

    - `verdict_label is None` 인 레코드만 채운다 — 기존 라벨은 절대 덮어쓰지 않는다
      (먼저 착지한 판정이 정본; 재판정은 새 결정 레코드로 흘러야지 덮어쓰기가 아님).
    - rewrite 는 원자적: 같은 디렉터리에 tempfile 을 쓰고 os.replace 로 교체
      (crash 중간에도 원본 or 완성본 둘 중 하나만 존재, 반쪽 파일 없음).
    - 로그에 없는 verdict 키는 unmatched_keys 로 보고 (조용히 삼키지 않음).
    - 손상(비JSON) 줄은 그대로 보존 — 삭제/유실 금지 (covenant).
    - 갱신이 0건이면 파일을 건드리지 않는다 (mtime 불변, no-op).
    """
    p = Path(log_path).expanduser()
    if not p.exists():
        return FeedbackReport(
            updated=0, unmatched_keys=tuple(sorted(verdicts)), total_records=0
        )

    matched: set[str] = set()
    updated = 0
    total = 0
    out_lines: list[str] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue  # 공백 줄 정규화 (레코드 아님)
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            out_lines.append(line)  # 방어: 손상 줄은 그대로 보존, 레코드로 세지 않음
            continue
        if not isinstance(rec, dict):
            out_lines.append(line)
            continue
        total += 1
        key = match_key(rec)
        if key in verdicts:
            matched.add(key)
            if rec.get("verdict_label") is None:
                rec["verdict_label"] = verdicts[key]
                updated += 1
                out_lines.append(json.dumps(rec, ensure_ascii=False))
                continue
        out_lines.append(line)  # 미변경 레코드는 원문 그대로 (byte-stable)

    unmatched = tuple(sorted(k for k in verdicts if k not in matched))
    if updated:
        _atomic_rewrite(p, out_lines)
    return FeedbackReport(updated=updated, unmatched_keys=unmatched, total_records=total)


def _atomic_rewrite(path: Path, lines: list[str]) -> None:
    """같은 디렉터리 tempfile + os.replace — cross-device 없이 원자 교체."""
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            for ln in lines:
                fh.write(ln + "\n")
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)  # best-effort 청소 — 실패 시 원본은 무손상으로 남는다
        except OSError:
            pass
        raise


def vr_to_verdicts(rows: list[dict]) -> dict[str, str]:
    """KG ValidationResult 질의 rows → apply_verdicts 용 verdicts dict 어댑터.

    rows = `CypherRunner` 가 돌려준 `[{subject, verdict}, ...]` (subject = match_key 와
    같은 접합면: 노드 name 또는 `normalized_path:sha12`). verdict 문자열은 대문자로 정규화
    ('approved' → 'APPROVED' → calibration.label_to_bool 어휘와 정합). subject/verdict
    결손 row 는 방어적 skip. 동일 subject 중복 시 나중 row 가 이긴다 (dict 갱신 의미론 —
    질의를 시간 오름차순 정렬하면 최신 판정 우선).
    """
    out: dict[str, str] = {}
    for r in rows or []:
        if not isinstance(r, dict):
            continue
        subject = r.get("subject")
        verdict = r.get("verdict")
        if not subject or verdict is None:
            continue
        out[str(subject)] = str(verdict).strip().upper()
    return out


__all__ = ["FeedbackReport", "apply_verdicts", "match_key", "vr_to_verdicts"]
