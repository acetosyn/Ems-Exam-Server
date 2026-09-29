# MODULE: Subject Registry — persistent dynamic subject catalogue + class/track assignment engine

import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock

from modules.school_structure import ALL_CONFIGURED_CLASSES, SCHOOL_SECTIONS, SCHOOL_SECTION_ORDER, class_label, get_class_metadata, get_source_subjects, normalize_school_class, school_section_for_class


BASE_DIR = Path(__file__).resolve().parent.parent
REGISTRY_FILE = BASE_DIR / "static" / "data" / "academic" / "subject_registry.json"
BACKUP_DIR = BASE_DIR / "static" / "data" / "academic" / "backups" / "subject_registry"
REGISTRY_LOCK = RLock()
REGISTRY_VERSION = 2
SS_TRACKS = ["SCIENCE", "ART", "COMMERCIAL"]


def clean(value): return " ".join(str(value or "").strip().split())

def utc_now(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _base_subject_key(value):
    raw = clean(value).upper().replace("&", " AND ")
    raw = re.sub(r"[._()/\\-]+", " ", raw); raw = " ".join(raw.split())
    aliases = {
        "MATHS": "MATHEMATICS", "IRK": "IRS", "I R S": "IRS", "I R K": "IRS", "ISLAMIYAH": "ISLAMIYYAH", "ISLAMIYYA": "ISLAMIYYAH",
        "P H E": "PHE", "PHYSICAL AND HEALTH EDUCATION": "PHE", "CULTURE AND CREATIVE ARTS CCA": "CCA", "BASIC SCIENCE AND TECHNOLOGY": "BST",
        "SOCIAL AND CITIZENSHIP STUDIES": "SOC AND CIT STD", "SOC AND CIT STD": "SOC AND CIT STD", "CIT AND HER STD": "CIT AND HER STD",
        "HERITAGE AND CITIZENSHIP STUDIES": "CIT AND HER STD", "FINANCIAL ACCOUNTING": "FINANCIAL ACCOUNT", "ACCOUNTS": "FINANCIAL ACCOUNT",
        "ACCOUNTING": "FINANCIAL ACCOUNT", "DIGITAL TECHNOLOGY": "DIGITAL TECH", "HORTICULTURE AND CROP PRODUCTION": "HORT AND CROP PRODUCTION",
    }
    return aliases.get(raw, raw)


def subject_key(value): return _base_subject_key(value)

def subject_id_from_key(key): return "SUBJ_" + hashlib.sha1(str(key or "").encode("utf-8")).hexdigest()[:12].upper()


def _preferred_subject_name(key, candidate=""):
    preferred = {
        "IRS": "IRK", "ISLAMIYYAH": "Islamiyyah", "PHE": "Physical & Health Education", "CCA": "Culture & Creative Arts (CCA)",
        "BST": "Basic Science & Technology", "SOC AND CIT STD": "Social & Citizenship Studies", "CIT AND HER STD": "Heritage & Citizenship Studies",
        "DIGITAL TECH": "Digital Technology", "HORT AND CROP PRODUCTION": "Horticulture & Crop Production",
    }
    return preferred.get(key, clean(candidate) or str(key or "").title())


def _normalize_tracks(tracks, class_level=""):
    level = normalize_school_class(class_level)
    if not level.startswith("SS"): return []
    values = tracks if isinstance(tracks, (list, tuple, set)) else [tracks] if tracks else []
    normalized = [str(item or "").upper().strip() for item in values if str(item or "").upper().strip() in SS_TRACKS]
    return [track for track in SS_TRACKS if track in set(normalized)] or list(SS_TRACKS)


def _legacy_class_subjects(level):
    try:
        from modules.class_config import CLASS_SUBJECTS
        return list(CLASS_SUBJECTS.get(level, []))
    except Exception:
        return []


def _legacy_subject_tracks(level, name):
    if not str(level or "").startswith("SS"): return []
    try:
        from modules.class_config import SS_SCIENCE_SUBJECTS_BY_LEVEL, SS_ART_SUBJECTS_BY_LEVEL, SS_COMMERCIAL_SUBJECTS_BY_LEVEL, normalize_subject_key
        wanted = normalize_subject_key(name); tracks = []
        if wanted in {normalize_subject_key(item) for item in SS_SCIENCE_SUBJECTS_BY_LEVEL.get(level, [])}: tracks.append("SCIENCE")
        if wanted in {normalize_subject_key(item) for item in SS_ART_SUBJECTS_BY_LEVEL.get(level, [])}: tracks.append("ART")
        if wanted in {normalize_subject_key(item) for item in SS_COMMERCIAL_SUBJECTS_BY_LEVEL.get(level, [])}: tracks.append("COMMERCIAL")
        return tracks or list(SS_TRACKS)
    except Exception:
        return list(SS_TRACKS)


def _empty_registry():
    now = utc_now()
    return {"version": REGISTRY_VERSION, "created_at": now, "updated_at": now, "subjects": {}, "assignments": {level: [] for level in ALL_CONFIGURED_CLASSES}, "history": [], "source_notes": {"immutable_keys": "Subject keys/IDs remain stable when display names are edited so historical academic records can still resolve the subject."}}


def _ensure_subject(data, name, source="school_document"):
    name = clean(name)
    if not name: return None
    key = subject_key(name); subjects = data.setdefault("subjects", {})
    if key not in subjects:
        now = utc_now(); subjects[key] = {"id": subject_id_from_key(key), "key": key, "name": _preferred_subject_name(key, name), "active": True, "source": clean(source) or "admin", "aliases": [name] if name != _preferred_subject_name(key, name) else [], "name_overridden": False, "created_at": now, "updated_at": now}
    else:
        aliases = subjects[key].setdefault("aliases", [])
        if name and name != subjects[key].get("name") and name not in aliases: aliases.append(name)
    return subjects[key]


def _append_assignment(data, level, subject, display_name="", source="school_document", tracks=None, active=True, order=None):
    level = normalize_school_class(level)
    if not level or not subject: return None
    rows = data.setdefault("assignments", {}).setdefault(level, []); key = subject.get("key"); existing = next((row for row in rows if row.get("subject_key") == key), None)
    normalized_tracks = _normalize_tracks(tracks, level)
    if existing:
        existing.update({"subject_id": subject.get("id"), "display_name": clean(display_name) or existing.get("display_name") or subject.get("name"), "active": bool(active), "tracks": normalized_tracks, "source": existing.get("source") or clean(source) or "admin"})
        return existing
    if order is None: order = max([int(row.get("order") or 0) for row in rows] + [0]) + 1
    row = {"subject_id": subject.get("id"), "subject_key": key, "display_name": clean(display_name) or subject.get("name"), "active": bool(active), "tracks": normalized_tracks, "source": clean(source) or "admin", "order": int(order)}
    rows.append(row); return row


def _seed_registry():
    data = _empty_registry()
    for level in ALL_CONFIGURED_CLASSES:
        source_subjects = get_source_subjects(level); subjects = source_subjects or _legacy_class_subjects(level); source = "school_document" if source_subjects else "existing_emis_config"
        for index, name in enumerate(subjects, 1):
            if clean(name).upper() == "HAUSA/YORUBA":
                expanded = ["Hausa Language", "Yoruba Language"]
            else:
                expanded = [name]
            for expanded_name in expanded:
                subject = _ensure_subject(data, expanded_name, source); tracks = _legacy_subject_tracks(level, expanded_name) if level.startswith("SS") else []
                _append_assignment(data, level, subject, display_name=expanded_name, source=source, tracks=tracks, active=True, order=index)
    data["updated_at"] = utc_now(); return data


def _migrate_v1(data):
    migrated = _empty_registry(); classes = data.get("classes", {}) if isinstance(data, dict) else {}
    for level, info in classes.items():
        level = normalize_school_class(level)
        if not level: continue
        rows = info.get("subjects", []) if isinstance(info, dict) else []
        for index, row in enumerate(rows, 1):
            if not isinstance(row, dict): continue
            name = clean(row.get("name") or row.get("key")); active = bool(row.get("active", True)); source = clean(row.get("source")) or "migrated_phase1"
            names = ["Hausa Language", "Yoruba Language"] if name.upper() == "HAUSA/YORUBA" else [name]
            for expanded_name in names:
                subject = _ensure_subject(migrated, expanded_name, source); tracks = _legacy_subject_tracks(level, expanded_name) if level.startswith("SS") else []
                _append_assignment(migrated, level, subject, display_name=expanded_name, source=source, tracks=tracks, active=active, order=index)
    defaults = _seed_registry()
    for level, rows in defaults.get("assignments", {}).items():
        for row in rows:
            subject = defaults["subjects"].get(row.get("subject_key")); current_rows = migrated.setdefault("assignments", {}).setdefault(level, [])
            if not any(existing.get("subject_key") == row.get("subject_key") for existing in current_rows):
                target = _ensure_subject(migrated, subject.get("name"), subject.get("source")) if subject else None
                if target: _append_assignment(migrated, level, target, row.get("display_name"), row.get("source"), row.get("tracks"), True)
    migrated["history"].append({"at": utc_now(), "action": "migrate_v1_to_v2", "detail": "Phase 1 class-based subject registry migrated to stable global subjects + class assignments."})
    return migrated


def _normalize_registry(data):
    if not isinstance(data, dict): return _seed_registry()
    if int(data.get("version") or 0) < REGISTRY_VERSION: return _migrate_v1(data)
    data.setdefault("subjects", {}); data.setdefault("assignments", {}); data.setdefault("history", []); data.setdefault("created_at", utc_now()); data.setdefault("updated_at", utc_now())
    for subject in data["subjects"].values():
        if isinstance(subject, dict): subject.setdefault("name_overridden", False)
    for level in ALL_CONFIGURED_CLASSES: data["assignments"].setdefault(level, [])
    return data


def _backup_current_file():
    if not REGISTRY_FILE.exists(): return None
    BACKUP_DIR.mkdir(parents=True, exist_ok=True); stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f"); target = BACKUP_DIR / f"subject_registry_{stamp}.json"
    shutil.copy2(REGISTRY_FILE, target)
    backups = sorted(BACKUP_DIR.glob("subject_registry_*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    for old in backups[30:]:
        try: old.unlink()
        except OSError: pass
    return target


def ensure_subject_registry():
    REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not REGISTRY_FILE.exists(): write_subject_registry(_seed_registry(), backup=False)
    else:
        try:
            raw = json.loads(REGISTRY_FILE.read_text(encoding="utf-8-sig"))
            if int(raw.get("version") or 0) < REGISTRY_VERSION: write_subject_registry(_normalize_registry(raw), backup=True)
        except Exception: pass
    return REGISTRY_FILE


def read_subject_registry(seed_if_missing=True):
    if seed_if_missing: ensure_subject_registry()
    if not REGISTRY_FILE.exists(): return _empty_registry()
    with REGISTRY_LOCK:
        try:
            raw = json.loads(REGISTRY_FILE.read_text(encoding="utf-8-sig"))
            if not seed_if_missing and int(raw.get("version") or 0) < REGISTRY_VERSION: return _empty_registry()
            return _normalize_registry(raw)
        except Exception: return _seed_registry() if seed_if_missing else _empty_registry()


def write_subject_registry(data, backup=True):
    REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True); payload = _normalize_registry(data); payload["version"] = REGISTRY_VERSION; payload["updated_at"] = utc_now(); temp = REGISTRY_FILE.with_suffix(".tmp")
    with REGISTRY_LOCK:
        if backup: _backup_current_file()
        temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"); temp.replace(REGISTRY_FILE)
    return REGISTRY_FILE


def _record_history(data, action, detail=""):
    rows = data.setdefault("history", []); rows.append({"at": utc_now(), "action": clean(action), "detail": clean(detail)})
    if len(rows) > 150: del rows[:-150]


def resolve_subject_key(value, seed_if_missing=False):
    wanted = _base_subject_key(value)
    if not wanted: return ""
    data = read_subject_registry(seed_if_missing=seed_if_missing)
    if wanted in data.get("subjects", {}): return wanted
    normalized = _base_subject_key(value)
    for key, row in data.get("subjects", {}).items():
        candidates = [row.get("name"), row.get("key")] + list(row.get("aliases") or [])
        if any(_base_subject_key(candidate) == normalized for candidate in candidates if candidate): return key
    for rows in data.get("assignments", {}).values():
        for assignment in rows:
            if _base_subject_key(assignment.get("display_name")) == normalized: return assignment.get("subject_key") or wanted
    return wanted


def _find_subject_key(data, subject_id_or_key):
    token = clean(subject_id_or_key).upper()
    return next((key for key, row in data.get("subjects", {}).items() if key.upper() == token or str(row.get("id") or "").upper() == token), "")


def get_subject(subject_id_or_key):
    data = read_subject_registry(); key = _find_subject_key(data, subject_id_or_key)
    return dict(data.get("subjects", {}).get(key, {})) if key else None


def get_class_subject_rows(class_level, track="", active_only=True):
    level = normalize_school_class(class_level)
    if not level: return []
    data = read_subject_registry(); subjects = data.get("subjects", {}); wanted_track = str(track or "").upper().strip(); output = []
    for assignment in sorted(data.get("assignments", {}).get(level, []), key=lambda row: (int(row.get("order") or 9999), str(row.get("display_name") or ""))):
        subject = subjects.get(assignment.get("subject_key"), {})
        if not subject: continue
        if active_only and (not subject.get("active", True) or not assignment.get("active", True)): continue
        tracks = _normalize_tracks(assignment.get("tracks"), level) if level.startswith("SS") else []
        if level.startswith("SS") and wanted_track:
            if wanted_track == "ART_COMMERCIAL" and not set(tracks).intersection({"ART", "COMMERCIAL"}): continue
            if wanted_track in SS_TRACKS and wanted_track not in tracks: continue
        output.append({"id": subject.get("id"), "key": subject.get("key"), "name": assignment.get("display_name") or subject.get("name"), "catalog_name": subject.get("name"), "active": bool(subject.get("active", True) and assignment.get("active", True)), "tracks": tracks, "source": assignment.get("source") or subject.get("source"), "order": int(assignment.get("order") or 0)})
    return output


def get_registered_subjects(class_level, active_only=True): return get_class_subject_rows(class_level, active_only=active_only)


def get_subject_tracks(class_level, subject):
    level = normalize_school_class(class_level); key = resolve_subject_key(subject, seed_if_missing=False)
    if not level.startswith("SS") or not key: return set()
    data = read_subject_registry(); row = next((item for item in data.get("assignments", {}).get(level, []) if item.get("subject_key") == key and item.get("active", True)), None)
    if not row: return set()
    subject_row = data.get("subjects", {}).get(key, {})
    if not subject_row.get("active", True): return set()
    return set(_normalize_tracks(row.get("tracks"), level))


def list_subjects(section="", class_level="", active=None):
    data = read_subject_registry(); section = str(section or "").upper().strip(); level_filter = normalize_school_class(class_level); output = []
    for key, subject in data.get("subjects", {}).items():
        if active is not None and bool(subject.get("active", True)) != bool(active): continue
        assignments = []
        for level in ALL_CONFIGURED_CLASSES:
            if level_filter and level != level_filter: continue
            if section and school_section_for_class(level) != section: continue
            row = next((item for item in data.get("assignments", {}).get(level, []) if item.get("subject_key") == key and item.get("active", True)), None)
            if not row: continue
            meta = get_class_metadata(level); assignments.append({"class_level": level, "class_label": meta.get("label", class_label(level)), "section": meta.get("section", ""), "section_label": meta.get("section_label", ""), "database_status": meta.get("database_status", "pending"), "tracks": _normalize_tracks(row.get("tracks"), level), "display_name": row.get("display_name") or subject.get("name")})
        if (section or level_filter) and not assignments: continue
        output.append({**subject, "assignments": assignments, "assignment_count": len(assignments)})
    return sorted(output, key=lambda row: str(row.get("name") or "").lower())


def create_subject(name, assignments=None, source="admin"):
    name = clean(name)
    if not name: raise ValueError("Subject name is required.")
    data = read_subject_registry(); key = subject_key(name)
    if key in data.get("subjects", {}): raise ValueError("A subject with this name or canonical key already exists.")
    for existing in data.get("subjects", {}).values():
        candidates = [existing.get("name")] + list(existing.get("aliases") or [])
        if any(subject_key(item) == key for item in candidates if item): raise ValueError("A subject with this name or alias already exists.")
    subject = _ensure_subject(data, name, source); set_subject_assignments(subject.get("id"), assignments or [], data=data, save=False)
    _record_history(data, "create_subject", f"Created {name} ({subject.get('key')})."); write_subject_registry(data)
    return get_subject(subject.get("id"))


def _apply_subject_update(data, subject_id_or_key, name=None, active=None):
    key = _find_subject_key(data, subject_id_or_key)
    if not key: raise ValueError("Subject not found.")
    subject = data["subjects"][key]; old_name = clean(subject.get("name"))
    if name is not None:
        new_name = clean(name)
        if not new_name: raise ValueError("Subject name cannot be empty.")
        new_key = subject_key(new_name)
        for other_key, other in data.get("subjects", {}).items():
            if other_key == key: continue
            candidates = [other.get("name"), other.get("key")] + list(other.get("aliases") or [])
            if any(subject_key(candidate) == new_key for candidate in candidates if candidate): raise ValueError("Another subject already uses this name or alias.")
        if old_name and old_name != new_name and old_name not in subject.setdefault("aliases", []): subject["aliases"].append(old_name)
        subject["name"] = new_name
        if old_name != new_name: subject["name_overridden"] = True
        for rows in data.get("assignments", {}).values():
            for assignment in rows:
                if assignment.get("subject_key") == key: assignment["display_name"] = new_name
    if active is not None: subject["active"] = bool(active)
    subject["updated_at"] = utc_now(); return subject


def update_subject(subject_id_or_key, name=None, active=None):
    with REGISTRY_LOCK:
        data = read_subject_registry(); subject = _apply_subject_update(data, subject_id_or_key, name=name, active=active)
        _record_history(data, "update_subject", f"Updated {subject.get('name')} ({subject.get('key')})."); write_subject_registry(data)
        return dict(subject)


def save_subject_configuration(subject_id_or_key, name=None, active=None, assignments=None):
    """Atomically update subject identity/status and current class assignments in one registry write."""
    with REGISTRY_LOCK:
        data = read_subject_registry(); subject = _apply_subject_update(data, subject_id_or_key, name=name, active=active)
        if assignments is not None: set_subject_assignments(subject.get("id"), assignments, data=data, save=False)
        _record_history(data, "save_subject_configuration", f"Updated subject configuration for {subject.get('name')} ({subject.get('key')})."); write_subject_registry(data)
        return dict(subject)

def set_subject_assignments(subject_id_or_key, assignments, data=None, save=True):
    data = data or read_subject_registry(); key = _find_subject_key(data, subject_id_or_key)
    if not key: raise ValueError("Subject not found.")
    assignments = assignments if isinstance(assignments, list) else []; selected = {}
    for item in assignments:
        if isinstance(item, str): item = {"class_level": item}
        if not isinstance(item, dict): continue
        level = normalize_school_class(item.get("class_level") or item.get("class"))
        if level not in ALL_CONFIGURED_CLASSES: raise ValueError(f"Invalid configured class: {item.get('class_level') or item.get('class')}")
        selected[level] = {"tracks": _normalize_tracks(item.get("tracks"), level), "display_name": clean(item.get("display_name")), "source": clean(item.get("source")) or "admin"}
    for level in ALL_CONFIGURED_CLASSES:
        rows = data.setdefault("assignments", {}).setdefault(level, []); existing = next((row for row in rows if row.get("subject_key") == key), None)
        if level in selected:
            config = selected[level]
            if existing:
                existing.update({"active": True, "tracks": config["tracks"], "display_name": config["display_name"] or existing.get("display_name") or data["subjects"][key].get("name"), "source": existing.get("source") or config["source"]})
            else:
                _append_assignment(data, level, data["subjects"][key], display_name=config["display_name"] or data["subjects"][key].get("name"), source=config["source"], tracks=config["tracks"], active=True)
        elif existing:
            existing["active"] = False
    if save:
        _record_history(data, "update_assignments", f"Updated class assignments for {data['subjects'][key].get('name')} ({key})."); write_subject_registry(data)
    return list_subjects()


def set_subject_status(subject_id_or_key, active=True): return update_subject(subject_id_or_key, active=bool(active))


def add_registered_subject(class_level, name, source="admin"):
    level = normalize_school_class(class_level)
    if not level: raise ValueError("A valid configured class is required.")
    data = read_subject_registry(); key = subject_key(name); subject = data.get("subjects", {}).get(key)
    if not subject: subject = _ensure_subject(data, name, source)
    current = []
    for class_key, rows in data.get("assignments", {}).items():
        row = next((item for item in rows if item.get("subject_key") == key and item.get("active", True)), None)
        if row: current.append({"class_level": class_key, "tracks": row.get("tracks", [])})
    if not any(item.get("class_level") == level for item in current): current.append({"class_level": level, "tracks": list(SS_TRACKS) if level.startswith("SS") else []})
    set_subject_assignments(subject.get("id"), current, data=data, save=False); _record_history(data, "add_registered_subject", f"Assigned {name} to {level}."); write_subject_registry(data)
    return next((row for row in get_class_subject_rows(level, active_only=False) if row.get("key") == key), None)


def set_registered_subject_active(class_level, subject, active=True):
    level = normalize_school_class(class_level); key = resolve_subject_key(subject, seed_if_missing=True); data = read_subject_registry(); row = next((item for item in data.get("assignments", {}).get(level, []) if item.get("subject_key") == key), None)
    if not row: return False
    row["active"] = bool(active); _record_history(data, "set_assignment_status", f"Set {key} in {level} active={bool(active)}."); write_subject_registry(data); return True


def build_subject_sync_payload(subject_id_or_key):
    """Build the complete current state for one subject for Local -> Deployed sync."""
    data = read_subject_registry(); key = _find_subject_key(data, subject_id_or_key)
    if not key: raise ValueError("Subject not found.")
    subject = dict(data["subjects"][key]); assignments = []
    for level in ALL_CONFIGURED_CLASSES:
        row = next((item for item in data.get("assignments", {}).get(level, []) if item.get("subject_key") == key and item.get("active", True)), None)
        if not row: continue
        assignments.append({"class_level": level, "tracks": _normalize_tracks(row.get("tracks"), level), "display_name": clean(row.get("display_name")) or subject.get("name"), "source": clean(row.get("source")) or subject.get("source") or "admin"})
    return {"registry_version": REGISTRY_VERSION, "subject": subject, "assignments": assignments}


def apply_subject_registry_sync_event(action, payload, event=None):
    """Apply a trusted synchronized subject snapshot without creating a return sync loop."""
    if clean(action).lower() != "upsert_subject": raise ValueError(f"Unsupported subject registry sync action: {action}")
    if not isinstance(payload, dict) or not isinstance(payload.get("subject"), dict): raise ValueError("Subject registry sync payload is invalid.")

    incoming = dict(payload["subject"]); key = clean(incoming.get("key")).upper(); name = clean(incoming.get("name")); incoming_id = clean(incoming.get("id"))
    if not key or not name: raise ValueError("Synchronized subject key and name are required.")
    expected_id = subject_id_from_key(key)
    if incoming_id and incoming_id != expected_id: raise ValueError("Synchronized subject identity does not match its stable key.")

    with REGISTRY_LOCK:
        data = read_subject_registry(); existing = data.setdefault("subjects", {}).get(key, {}); now = utc_now()
        aliases = []
        for alias in list(existing.get("aliases") or []) + list(incoming.get("aliases") or []):
            alias = clean(alias)
            if alias and alias != name and alias not in aliases: aliases.append(alias)
        data["subjects"][key] = {
            "id": expected_id, "key": key, "name": name, "active": bool(incoming.get("active", True)),
            "source": clean(incoming.get("source")) or clean(existing.get("source")) or "sync", "aliases": aliases,
            "name_overridden": bool(incoming.get("name_overridden", existing.get("name_overridden", False))),
            "created_at": clean(existing.get("created_at")) or clean(incoming.get("created_at")) or now, "updated_at": clean(incoming.get("updated_at")) or now,
        }

        # Replace the current active class scope for this subject. Historical rows remain in
        # the registry as inactive assignments, preserving identity while matching Local state.
        for level in ALL_CONFIGURED_CLASSES:
            rows = data.setdefault("assignments", {}).setdefault(level, [])
            for row in rows:
                if row.get("subject_key") == key: row["active"] = False

        for item in payload.get("assignments") or []:
            if not isinstance(item, dict): continue
            level = normalize_school_class(item.get("class_level") or item.get("class"))
            if level not in ALL_CONFIGURED_CLASSES: raise ValueError(f"Invalid synchronized class assignment: {item.get('class_level') or item.get('class')}")
            _append_assignment(data, level, data["subjects"][key], display_name=clean(item.get("display_name")) or name, source=clean(item.get("source")) or "sync", tracks=item.get("tracks"), active=True)

        _record_history(data, "sync_upsert_subject", f"Applied synchronized subject {name} ({key})."); write_subject_registry(data)

    return {"subject_id": expected_id, "subject_key": key, "name": name, "active": bool(data["subjects"][key].get("active", True)), "assignment_count": len(payload.get("assignments") or [])}


def get_registry_stats():
    data = read_subject_registry(); subjects = list(data.get("subjects", {}).values()); active_subjects = sum(1 for row in subjects if row.get("active", True)); active_assignments = 0; configured_classes = 0
    for level in ALL_CONFIGURED_CLASSES:
        count = sum(1 for row in data.get("assignments", {}).get(level, []) if row.get("active", True) and data.get("subjects", {}).get(row.get("subject_key"), {}).get("active", True))
        active_assignments += count
        if count: configured_classes += 1
    return {"total_subjects": len(subjects), "active_subjects": active_subjects, "inactive_subjects": len(subjects) - active_subjects, "active_assignments": active_assignments, "configured_classes": configured_classes, "school_sections": len(SCHOOL_SECTIONS), "registry_version": int(data.get("version") or REGISTRY_VERSION), "updated_at": data.get("updated_at")}


def get_subject_manager_config():
    sections = []
    for section_key in SCHOOL_SECTION_ORDER:
        info = SCHOOL_SECTIONS.get(section_key, {}); classes = []
        for level in info.get("classes", []):
            meta = get_class_metadata(level); meta["subject_count"] = len(get_class_subject_rows(level)); meta["supports_tracks"] = level.startswith("SS"); classes.append(meta)
        sections.append({"key": section_key, "label": info.get("label", section_key.title()), "short_label": info.get("short_label", info.get("label", section_key.title())), "classes": classes})
    return {"sections": sections, "tracks": [{"key": "SCIENCE", "label": "Science"}, {"key": "ART", "label": "Arts"}, {"key": "COMMERCIAL", "label": "Commercial"}], "stats": get_registry_stats()}
