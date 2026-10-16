# MODULE: Academy Identity Link — safely links Tahfeez/Islamiyyah academy IDs to the regular students2026.csv admission ID.
# RULE: Preserve thf... / isl... IDs. Only create std... links from an existing valid link, a direct std admission, or a unique exact normalized full-name signature.

import re
import unicodedata
from collections import defaultdict

from modules.student_lookup import STUDENT_DATABASE, read_student_database, normalize_admission_number


def clean(value): return str(value or "").strip()

_IDENTITY_CACHE_KEY = None
_IDENTITY_CACHE_VALUE = None


def name_signature(last_name="", first_name="", other_names="", full_name=""):
    text = clean(full_name) or " ".join(part for part in [clean(last_name), clean(first_name), clean(other_names)] if part)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii").upper(); tokens = [token for token in re.findall(r"[A-Z0-9]+", text) if len(token) > 1]
    return " ".join(sorted(tokens))


def master_identity_indexes():
    global _IDENTITY_CACHE_KEY, _IDENTITY_CACHE_VALUE
    try:
        stat = STUDENT_DATABASE.stat(); cache_key = (stat.st_mtime_ns, stat.st_size)
    except OSError:
        cache_key = None
    if _IDENTITY_CACHE_VALUE is not None and cache_key == _IDENTITY_CACHE_KEY: return _IDENTITY_CACHE_VALUE
    students = [row for row in read_student_database() if row.get("is_active", True)]; by_admission, by_signature = {}, defaultdict(list)
    for student in students:
        admission = normalize_admission_number(student.get("admission_number")); signature = name_signature(student.get("last_name"), student.get("first_name"), student.get("other_names"), student.get("full_name"))
        if admission: by_admission[admission] = student
        if signature: by_signature[signature].append(student)
    _IDENTITY_CACHE_KEY, _IDENTITY_CACHE_VALUE = cache_key, (by_admission, by_signature); return _IDENTITY_CACHE_VALUE


def resolve_master_identity(admission_number="", last_name="", first_name="", other_names="", full_name="", linked_admission_number="", indexes=None):
    by_admission, by_signature = indexes or master_identity_indexes(); explicit = normalize_admission_number(linked_admission_number)
    if explicit and explicit in by_admission: return by_admission[explicit]
    admission = normalize_admission_number(admission_number)
    if admission and admission in by_admission: return by_admission[admission]
    signature = name_signature(last_name, first_name, other_names, full_name); candidates = by_signature.get(signature, []) if signature else []
    return candidates[0] if len(candidates) == 1 else None


def regular_admission_for(record, indexes=None):
    record = record or {}; match = resolve_master_identity(record.get("Admission_number") or record.get("admission_number"), record.get("Last_name") or record.get("last_name"), record.get("First_name") or record.get("first_name"), record.get("Other_names") or record.get("other_names"), record.get("Full_name") or record.get("full_name"), record.get("Regular_Admission_number") or record.get("Linked_admission_number") or record.get("regular_admission_number"), indexes=indexes)
    return clean(match.get("admission_number")) if match else ""
