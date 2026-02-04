# app/vision/normalize.py
from __future__ import annotations

from typing import List, Dict
from collections import defaultdict

from app.models.room import RoomObject, ObjectType
from app.vision.labels import normalize_label, STRUCTURAL_LABELS, CANONICAL_LABELS


def _clamp_int(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, int(v)))


def assign_ids(objects: List[RoomObject]) -> List[RoomObject]:
    """
    Ensure stable IDs like bed_1, bed_2...
    If Gemini already returns good IDs, we keep them unless duplicates exist.
    """
    seen = set()
    counts: Dict[str, int] = defaultdict(int)

    out: List[RoomObject] = []
    for obj in objects:
        label = normalize_label(obj.label)
        counts[label] += 1
        proposed = obj.id.strip() if obj.id else ""

        if not proposed or proposed in seen:
            proposed = f"{label}_{counts[label]}"

        seen.add(proposed)
        out.append(obj.model_copy(update={"id": proposed, "label": label}))
    return out


def infer_object_type(label: str) -> ObjectType:
    return ObjectType.STRUCTURAL if label in STRUCTURAL_LABELS else ObjectType.MOVABLE


def normalize_objects(
    objects: List[RoomObject],
    room_width: int,
    room_height: int,
    locked_ids: List[str] | None = None,
) -> List[RoomObject]:
    """
    Normalize labels, clamp bboxes, set type, set lock flags.
    Keeps your downstream (constraints/solver/ui) stable across providers.
    """
    locked = set(locked_ids or [])

    normalized: List[RoomObject] = []
    for obj in objects:
        label = normalize_label(obj.label)

        # Allow only canonical or pass through (your choice). Here: pass-through but normalized.
        # If you want strict: if label not in CANONICAL_LABELS: continue
        x, y, w, h = obj.bbox

        # clamp to image bounds (best effort)
        x = _clamp_int(x, 0, room_width - 1)
        y = _clamp_int(y, 0, room_height - 1)
        w = _clamp_int(w, 1, room_width - x)
        h = _clamp_int(h, 1, room_height - y)

        obj_type = infer_object_type(label)
        is_locked = (obj.id in locked) or obj.is_locked

        normalized.append(
            obj.model_copy(
                update={
                    "label": label,
                    "bbox": [x, y, w, h],
                    "type": obj_type,
                    "is_locked": is_locked,
                }
            )
        )

    # ensure unique, stable IDs after normalization
    normalized = assign_ids(normalized)

    # re-apply locked_ids after possible ID changes
    # if user locked "bed_1" etc. this should already match; if not, you can add a mapping layer later.
    for i, obj in enumerate(normalized):
        if obj.id in locked:
            normalized[i] = obj.model_copy(update={"is_locked": True})

    return normalized
