# EMIS Exam Server — Updated Backend & Frontend Architecture Reference

> **Purpose:** Complete technical reference for the current EMIS Exam Server after the Phase 1–Phase 9 upgrade programme, including the Phase 9 academic-document refinements and cumulative-sheet accessibility correction.

> **Revision:** 24 September 2026

> **Current upgrade state:** Phase 1–Phase 9 implemented. Phase 9 refinements include the Unified Academic Documents update and the cumulative-sheet preview/PDF correction.

> **Scope:** Backend Python modules, Flask routes/APIs, frontend templates/JavaScript/CSS, school structure, Subject Registry, Teacher Assignments, Islamiyah School, Report Sheets 2.0, Permanent Academic History, Cumulative Results, Broadsheets, Transcripts, shared academic-document rendering, data storage, synchronization, navigation, safety rules, and remaining Phase 10 activation work.

---

# Table of Contents

1. Current Architecture Snapshot
2. Phase 1–Phase 9 Upgrade History
3. Current School Structure
4. Assessment and Grading Architecture
5. Data Authority and Identity Rules
6. Backend Module Reference
7. Frontend / UI Architecture
8. Official Academic Document Design Standard
9. Main End-to-End Workflows
10. Storage Map
11. Routes and API Map
12. Local → Deployed Synchronization
13. Navigation and Module Order
14. Deployment / Cache Rules
15. Current Pending Activation / Phase 10
16. Quick File Guide
17. Validation and Safety Summary

---

# 1. Current Architecture Snapshot

The current EMIS build is no longer only a JSS/SS CBT system. It now has an expanded school-structure foundation, dynamic subjects, Teacher assignments, a dedicated Islamiyah School, redesigned Report Sheets, permanent academic history, annual cumulative results, class broadsheets, integrated transcripts, and a shared official academic-document design.

## Current production student-database classes

The **active student database** still intentionally contains only:

```text
JSS1
JSS2
JSS3
SS1
SS2
SS3
```

These six classes remain the only classes used by the current master roster, Promotion Manager, student authentication, and synchronized class Excel databases.

## Configured but database-pending classes

The following classes are already configured in the school structure and Subject Registry, but are not yet active student databases:

```text
Starter
Pre-Class
Nursery 1
Nursery 2

Tahfeez 1
Tahfeez 2
Tahfeez 3
Tahfeez 4
Tahfeez 5

Primary 1
Primary 2
Primary 3
Primary 4
Primary 5
Primary 6
```

They will be activated when the Nursery/Primary/Tahfeez student databases are supplied and approved.

## Independent Islamiyah structure

Islamiyah is a separate academic classification:

```text
Islamiyah Starter
Islamiyah Prep-1
Islamiyah 1
Islamiyah 2
Islamiyah 3
Islamiyah 4
Islamiyah 5
Islamiyah 6
Islamiyah 7
```

A student's regular class and Islamiyah class are independent:

```text
Admission No.: std001
Regular Class: JSS2A
Islamiyah Class: Islamiyah 5
```

There is no fixed JSS/SS/Primary → Islamiyah mapping.

## Current academic-record chain

```text
Student Database
      +
Attendance
      +
CA/Test
      +
CBT / Essay Results
      +
Islamiyah
      ↓
Report Sheets
      ↓
Permanent Academic History
      ├── Cumulative Results
      ├── Broadsheets
      └── Transcript
```

The later modules derive from official archived Report Sheets instead of creating competing result databases.

---

# 2. Phase 1–Phase 9 Upgrade History

# Phase 1 — Architecture Foundation

## Purpose

Phase 1 created the non-breaking foundation for the wider school expansion without destabilizing the existing JSS/SS production database.

## Main changes

- Added `modules/school_structure.py`.
- Added `modules/grading_system.py`.
- Added the initial `modules/subject_registry.py`.
- Added initial `static/data/academic/subject_registry.json`.
- Updated `modules/class_config.py`.
- Updated `modules/report_sheet_manager.py` to use centralized grading.
- Preserved `SUPPORTED_CLASSES` as the six currently active JSS/SS database classes.
- Staged Nursery, Primary, Tahfeez and Islamiyah classes separately.
- Established the rule that regular class and Islamiyah class are independent.
- Established the future Academic History rule: historical records must not depend on a student's current promoted class.
- Established the future Transcript rule: transcript data must come from historical academic records, not current roster state.
- Preserved the Local-first synchronization architecture as a design requirement for later modules.

## Phase 1 design decisions

### School expansion safety

Directly inserting Nursery/Primary classes into the active database class list would have affected:

- Promotion Manager
- class XLSX generation
- student authentication
- current database synchronization
- active class validation

Phase 1 therefore separated **configured classes** from **active database classes**.

### Grading centralization

The former Report Sheet grading logic was moved behind `grading_system.py`.

Configured systems:

```text
REPORT_SECONDARY → Active current A–F report grading
WAEC             → Configured A1–F9 grading
PRIMARY          → Pending approved school scale
```

### Subject identity

Subjects began moving from hard-coded Python lists toward persistent stable subject identities, preparing EMIS for dynamic Admin subject management.

---

# Phase 2 — Expanded School Structure + Dynamic Subject Manager

## Confirmed structure decisions

- Nursery 1 and Nursery 2 are separate classes.
- Tahfeez 1–5 are separate classes.
- Hausa and Yoruba are separate subjects:
  - `Hausa Language`
  - `Yoruba Language`
- A pupil takes whichever language applies.
- Islamiyah remains independent from the regular school class.
- The duplicated Arabic entry in the source Tahfeez 3–5 list is stored once at runtime while the source discrepancy remains documented.

## Configured structure

Phase 2 established:

```text
6 school sections
30 configured classes
63 global subjects in the tested fresh registry
345 active class-subject assignments in the tested fresh registry
```

## New Admin Subject Manager

Page:

```text
/admin/subjects
```

Capabilities:

- View all subjects.
- Search subjects.
- Filter by section.
- Filter by class.
- Filter active/inactive state.
- Add a subject.
- Rename a subject.
- Activate/deactivate a subject.
- Assign/unassign subjects across classes.
- Configure SS Science / Arts / Commercial compatibility.
- Preserve stable subject identity when names change.
- Keep aliases for historical resolution.
- Avoid destructive hard deletion.

## Subject Registry storage

```text
static/data/academic/subject_registry.json
static/data/academic/backups/subject_registry/
```

The mutable live registry is not supposed to be overwritten by an upgrade ZIP.

## Phase 1 → Phase 2 migration

The registry engine can:

- detect an old Phase 1 registry;
- back it up;
- migrate it;
- split the former combined Hausa/Yoruba source entry;
- retain stable subject identities;
- retain intentional inactive assignments.

## Local → Deployed synchronization

New sync module:

```text
subject_registry
```

Typical action:

```text
upsert_subject
```

Subject configuration is saved locally first and synchronized later through the existing durable queue.

---

# Phase 3 — Teacher Assignment System

## Purpose

Phase 3 added a session-aware:

```text
Teacher → Class / Arm → Subject
```

assignment model.

## Main features

- Teacher directory with search/status filters.
- Teacher full-name and active/inactive profile editing.
- Academic-session-aware assignments.
- Multiple classes and subjects per teacher.
- Exact class-arm assignment where appropriate.
- `All applicable arms` mode.
- Subject options supplied by the dynamic Subject Registry.
- SS Science / Arts / Commercial compatibility validation.
- Teacher self-view of current teaching load.
- Assignment audit records.
- Teacher deletion cleanup.
- Local → Deployed assignment synchronization.

## Storage

The existing `database.db` is extended automatically with:

```text
teacher_assignments
teacher_assignment_audit
```

## Assignment identity

```text
teacher_id
academic_session
school_section
class_level
class_arm
subject_key
```

A blank class arm means **All applicable arms**.

## Important compatibility decision

Teacher assignments record responsibility, but the build did not immediately hard-block all older Attendance/CA pages for teachers with no assignments. This prevented accidental lockout while Admin was still populating teaching loads.

---

# Phase 4 — Islamiyah School

## Purpose

Phase 4 introduced a dedicated Islamiyah academic system linked to the central student database by Admission Number.

## Assessment scheme

```text
CA       /30
Exam     /70
Total   /100
```

Islamiyah does not use the normal JSS CA1/CA2/Test1/Test2 structure and does not use CBT for the written Islamiyah exam.

## Islamiyah subjects

### Islamiyah Starter

```text
Quran
Hadith
Arabiyah
Arqaam
Huruf
```

### Islamiyah Prep-1

```text
Quran
Hadith
Fiqh
Tawheed
Murtala
Arabiyah
Hisab
Azkhar
```

### Islamiyah 1–3

```text
Quran
Hadith
Fiqh
Tawheed
Huruf
```

### Islamiyah 4–7

```text
Quran
Hadith
Fiqh
Tawheed
Sirah
Tajweed
```

## Islamiyah page

```text
/admin/islamiyah
```

Workspaces:

1. Overview
2. Score Entry
3. Student Placement
4. Results & History

## Student placement

- Imports the current central EMIS student roster.
- Preserves existing Islamiyah placement when roster sync is repeated.
- Adds new students as Unassigned.
- Marks no-longer-active students inactive instead of destroying old Islamiyah history.
- Supports bulk assignment/unassignment.

## Teacher permissions

Teacher access uses Phase 3 assignments:

- assigned Islamiyah classes only;
- assigned Islamiyah subjects only;
- Admin retains full access;
- roster placement remains Admin-only.

## Autosave

- CA validates `0–30`.
- Exam validates `0–70`.
- Partial records stay In Progress.
- Complete records require both CA and Exam.
- Clearing both removes the score record.
- Backend revalidates scores.
- Locking protects simultaneous autosaves.

## Storage

```text
static/data/islamiyah/student_enrollments.csv
static/data/islamiyah/score_records.csv
static/data/islamiyah/backups/
```

Enrollment identity:

```text
Academic Session + Admission Number
```

Score identity:

```text
Academic Session + Term + Admission Number + Islamiyah Class + Subject Key
```

## Report Sheet integration

Once an Islamiyah roster has been activated for a session, Islamiyah becomes the source for the regular report's single **Islamiyyah** subject row.

Aggregation:

```text
Islamiyyah CA /30
= average CA across all active Islamiyah subjects

Islamiyyah Exam /70
= average Exam across all active Islamiyah subjects

Islamiyyah Total /100
= aggregated CA + aggregated Exam
```

The row becomes complete only when all required active Islamiyah subjects are complete.

Missing Islamiyah subjects are never treated as zero.

## Phase 4 UI refinement

The Islamiyah interface was later visually upgraded without changing the backend model:

- larger typography;
- stronger hero section;
- richer metric cards;
- feature grid;
- clearer tabs;
- larger class cards;
- quick actions;
- improved score-entry workspace;
- improved Results/History pane;
- better responsive behavior;
- fewer tiny/scattered labels.

---

# Phase 5 — Report Sheets 2.0

## Core redesign

The old full **Manual Result Studio modal** was removed.

Manual and Hybrid work now live directly on the Report Sheets page.

Focused detail editors remain modal-based where appropriate, including:

- remarks/traits;
- student inspection;
- saved reports;
- rules;
- bulk attendance/details;
- other focused edit actions.

## Main features

1. Animated counters.
2. Premium gradient cards.
3. Class-completion progress.
4. Sticky score/report table headers.
5. Dark/light emphasis zones.
6. Better empty states.
7. Lightweight summary charts.
8. Source Readiness dashboard.
9. Teacher Quick Workspace.
10. Inline Manual + Hybrid workspace.
11. Browser safety draft + server Save Draft.
12. Smart Voice score-entry compatibility.
13. Previous/next student navigation and completion progress.

## Manual / Hybrid workflow

```text
Load Class
   ↓
Select Student
   ↓
Enter only missing/corrected values
   ↓
Save Draft
   ↓
Manual Generate
   OR
Hybrid Generate
```

Hybrid mode prioritizes available official automatic data and uses approved manual values for gaps/corrections.

## Backend impact

Phase 5 was primarily a frontend redesign. It continued to use the existing `report_sheet_manager.py` APIs and data rules.

---

# Phase 6 — Permanent Academic History

## Purpose

Phase 6 created a permanent academic-record archive independent of the student's current class.

Page:

```text
/admin/academic-history
```

## Main features

- Auto/Manual/Hybrid generated Report Sheets are archived.
- Historical class/arm is preserved.
- Promotion does not rewrite old records.
- One canonical current record per historical context.
- Replaced versions go to revision history.
- Search by student/session/class/term.
- Student timeline.
- Performance trend.
- Full subject-level archived result.
- Attendance and remarks preserved.
- Excel history export.
- Rebuild Archive command.
- Backfill from existing generated Report Sheet snapshots.
- Local → Deployed academic-history synchronization.

## Storage

```text
static/data/academic_history/academic_records.jsonl
static/data/academic_history/record_revisions.jsonl
```

## Admission-number reuse protection

Admission Number alone is not sufficient for permanent historical identity because released graduate numbers may later be recycled.

Phase 6 therefore introduced a separate historical:

```text
student_key
```

Historical identity is derived from archived student identity information so that two different people who used the same admission number at different times are not merged.

## Backfill rule

Raw CBT attempts do not become official history automatically.

A term becomes an official history record when a Report Sheet snapshot has been generated/saved for that student and term.

## Rebuild behavior

Rebuild is idempotent and should not create duplicate canonical history records.

---

# Phase 7 — Cumulative Result Sheets

## Purpose

Phase 7 introduced a dedicated annual cumulative system derived from Permanent Academic History.

Page:

```text
/admin/cumulative-results
```

## Main features

- First Term + Second Term + Third Term comparison.
- Dedicated student cumulative sheet.
- Subject-by-subject term totals.
- Annual subject average.
- Annual subject grade.
- Annual overall average.
- Annual overall grade.
- Annual class position.
- Combined annual attendance.
- Completion status.
- Class cumulative roster.
- Search.
- Progress bar.
- Individual Excel export.
- Class Excel export.
- Print / Save PDF.

## Calculation rules

Overall:

```text
Annual Average = average of available valid term averages
```

Subject:

```text
Subject Annual Average = average of available valid term subject totals
```

## Completion/ranking rule

A student is **Complete** only when all three term averages are available.

Final annual class position is calculated only among students with all three valid term averages.

Partial students can have a provisional annual average but no final annual position.

## Missing-data rule

```text
Missing term ≠ 0
Missing subject ≠ 0
```

Missing values display as blank/`—`.

## Data source

```text
static/data/academic_history/academic_records.jsonl
```

No separate cumulative database is created.

---

# Phase 8 — Broadsheets + Cumulative Hub

## Report Sheets cumulative compiler

Phase 8 added an inline **Cumulative Result Compiler** inside the existing Report Sheets page so cumulative compilation is visible in the main reporting workflow.

It exposes:

- First Term records available;
- Second Term records available;
- Third Term records available;
- 3-term complete students;
- annual class average;
- annual coverage progress;
- compact student annual preview;
- links/actions to the full Cumulative workspace and Broadsheets.

## Third Term report cumulative summary

The normal Third Term printable Report Sheet now has a stronger annual summary containing:

- First Term average;
- Second Term average;
- Third Term average;
- annual average;
- annual grade;
- annual position;
- terms available;
- annual attendance;
- Final / Provisional status.

## Broadsheets

Page:

```text
/admin/broadsheets
```

APIs:

```text
GET /api/broadsheets/config
GET /api/broadsheets/data
GET /api/broadsheets/export
```

## Broadsheet features

1. Term Summary Broadsheet.
2. Cumulative Broadsheet.
3. Sticky subject headers.
4. Frozen student identity columns.
5. Score heat-map cells.
6. Animated KPI counters.
7. Coverage progress.
8. Top 5 / Lowest 5 performance panels.
9. Grade-distribution chart.
10. Strongest/focus subject analytics.
11. Per-subject average/high/low/pass-rate analytics.
12. Search and Complete/Partial filters.
13. Multi-sheet Excel export.
14. Landscape print mode.
15. Cross-module links.

## Broadsheet source rules

```text
Term Broadsheet       → Permanent Academic History
Cumulative Broadsheet → Phase 7 cumulative engine
```

Broadsheets are read-only derived views and do not create another result database.

---

# Phase 9 — Integrated Student Transcript

## Integration rule

Transcript functionality was integrated into **Academic History** rather than creating another page/sidebar item.

Academic History now provides:

```text
History
Transcript
```

## Transcript features

- Multi-session transcript.
- Historical class progression.
- First/Second/Third Term averages.
- Annual/session averages.
- Annual grades.
- Subject term scores.
- Annual subject average.
- Overall recorded academic average.
- Complete/Partial archive status.
- Historical identity protection.
- Stable transcript reference.
- Print / Save PDF.
- Multi-sheet Excel export.
- Records Officer / Principal signature areas.

## Data source

Transcript is compiled on demand from canonical Permanent Academic History.

No transcript database is created.

## Cumulative selector correction

The Cumulative page originally discovered class choices only from classes already in Academic History. The current sample archive contained JSS1 and SS1, so those were the only options shown.

Phase 9 corrected the selector to expose all six active production classes:

```text
JSS1
JSS2
JSS3
SS1
SS2
SS3
```

Selecting a class with no history shows an empty state instead of hiding the class.

Nursery/Primary/Tahfeez remain pending until their databases are activated.

---

# Phase 9 Refinement — Unified Academic Documents

This refinement is considered part of the Phase 9 reporting/transcript work.

## Official visual standard

The existing Student Report Sheet became the master visual language for:

- term Report Sheets;
- Cumulative Result Sheets;
- Academic History printable term records;
- Transcripts;
- Term Broadsheets;
- Cumulative Broadsheets;
- Third Term cumulative summary.

## Shared renderer

New shared frontend assets:

```text
static/js/academic_document.js
static/css/academic_document.css
```

These provide reusable official academic-document rendering and print behavior.

## Score interpretation upgrade

Academic documents now prioritize interpretable real scores alongside percentage.

Examples:

```text
Term:
629.2 / 1300 • 48.4%

Subject:
48 / 100

Three-term subject:
226 / 300 • 75.33%

Annual:
2350 / 3900 • 60.26%
```

Older archived records without an explicit maximum can derive:

```text
maximum score = assessed subject count × 100
```

Missing values still remain missing.

## Dynamic document features

- Score View toggle:
  - Score + %
  - Score
  - %
- Real score + maximum.
- Performance trend indicators.
- Completion progress.
- Automatic document density for many subjects.
- Multi-page transcript printing.
- Official History sheet printing.
- Copy Transcript Reference.
- Landscape official Broadsheets.
- Isolated print target.
- Dual-value Broadsheet cells.
- Existing sticky/frozen working tables retained.

## Phase 9.1.1 cumulative sheet correction

The official cumulative sheet renderer was retained, but access to it had become too hidden behind the table.

The correction added:

- first student auto-preview after compilation;
- clickable student rows;
- visible **View Sheet** action beside student name;
- selected-row highlighting;
- official cumulative preview pane;
- **Generate PDF** for selected student;
- **Class PDF** for all loaded students, one official cumulative sheet per page;
- Excel export retained;
- real score/max/% retained.

---

# 3. Current School Structure

# 3.1 School Sections

```text
EARLY_YEARS
TAHFEEZ
PRIMARY
JUNIOR_SECONDARY
SENIOR_SECONDARY
ISLAMIYAH
```

# 3.2 Regular configured classes

```text
Starter
Pre-Class
Nursery 1
Nursery 2

Tahfeez 1
Tahfeez 2
Tahfeez 3
Tahfeez 4
Tahfeez 5

Primary 1
Primary 2
Primary 3
Primary 4
Primary 5
Primary 6

JSS1
JSS2
JSS3

SS1
SS2
SS3
```

# 3.3 Islamiyah configured classes

```text
Islamiyah Starter
Islamiyah Prep-1
Islamiyah 1
Islamiyah 2
Islamiyah 3
Islamiyah 4
Islamiyah 5
Islamiyah 6
Islamiyah 7
```

# 3.4 Early Years subjects

## Starter / Pre-Class

```text
Letter Works
Number Work
Picture Reading
Creative Art
Free Writing Skill
Islamiyyah
```

## Nursery 1 / Nursery 2

```text
Letter Works
Number Work
Pre-Science
Social Habits
Creative Art
Writing Skill
Arabic
I. R. S
Islamiyyah
```

# 3.5 Tahfeez subjects

## Tahfeez 1–2

```text
Letter Works
Number Work
Pre-Science
Social Habits
Creative Art
Writing Skill
Arabic
Quran
Islamiyyah
```

## Tahfeez 3–5

```text
Mathematics
English Studies
Basic Science
Social and Citizenship Studies
Hand Writing
Arabic
I. R. S
Quran
Hausa Language
Yoruba Language
Basic Digital Literacy
Islamiyyah
```

The source document contained Arabic twice; runtime stores it once.

# 3.6 Primary subjects

## Primary 1–3

```text
English Studies
Mathematics
Hausa Language
Yoruba Language
Basic Science
Physical & Health Education
IRK
Nigerian History
Social & Citizenship Studies
Culture & Creative Arts (CCA)
Arabic
Islamiyyah
```

## Primary 4–6

```text
English Studies
Mathematics
Hausa Language
Yoruba Language
Basic Science & Technology
Physical & Health Education
Basic Digital Literacy
IRK
Nigerian History
Social & Citizenship Studies
Culture & Creative Arts (CCA)
Pre-Vocational Studies
Arabic
Islamiyyah
```

Hausa and Yoruba are intentionally separate offered subjects.

---

# 4. Assessment and Grading Architecture

# 4.1 JSS

```text
CA1      /10
CA2      /10
Test 1   /20
Test 2   /20
CA Total /60
Exam     /40
Total    /100
```

# 4.2 SS

```text
Assignment 1 /5
Assignment 2 /5
Test         /20
CA Total     /30
Exam         /70
Total        /100
```

# 4.3 Islamiyah

```text
CA       /30
Exam     /70
Total   /100
```

# 4.4 Current secondary report grading

```text
A  80–100   Excellent
B  70–79    Very Good
C  60–69    Good
D  45–59    Pass
E  40–44    Pass
F  0–39     Fail / Needs Improvement
```

# 4.5 WAEC grading

Configured in `grading_system.py`:

```text
A1  75–100
B2  70–74.99
B3  65–69.99
C4  60–64.99
C5  55–59.99
C6  50–54.99
D7  45–49.99
E8  40–44.99
F9  0–39.99
```

This scale is configured for later controlled use.

# 4.6 Primary grading

```text
Status: pending_school_scale
```

Primary grading must not be activated until the approved school grading boundaries are supplied.

---

# 5. Data Authority and Identity Rules

# 5.1 Active student authority

```text
static/data/database/students2026.csv
```

The six class workbooks are synchronized mirrors.

# 5.2 Examination result authority

```text
RESULTS/<year>/CLASS/.../results.xlsx
```

Admin Results continues to treat Excel under `RESULTS/` as the active examination-result authority.

SQLite remains local write-through / duplicate-check support.

Supabase is legacy/optional compatibility.

# 5.3 Report Sheet authority

Report Sheets combine:

```text
Student Roster
Attendance
CA/Test
CBT Results
Essay/Theory
Islamiyah
Manual/Hybrid approved fallback
```

Saved official snapshots are written to Report Sheet storage.

# 5.4 Permanent historical authority

```text
static/data/academic_history/academic_records.jsonl
```

Academic History is the canonical historical layer for:

- Cumulative Results
- Broadsheets
- Transcripts

# 5.5 Student historical identity

Historical data does not rely on Admission Number alone.

```text
student_key
```

protects against future admission-number recycling.

# 5.6 Subject identity

Dynamic subjects use stable machine identity so a visible name can change without breaking historical references.

The Subject Registry retains aliases for renamed subjects.

# 5.7 Teacher assignment identity

```text
teacher_id
academic_session
school_section
class_level
class_arm
subject_key
```

# 5.8 Islamiyah identities

Enrollment:

```text
academic_session + admission_number
```

Score:

```text
academic_session + term + admission_number + islamiyah_class + subject_key
```

# 5.9 Missing-data rule

Across Report Sheets, History, Cumulative, Broadsheets and Transcript:

```text
Missing ≠ Zero
```

A missing CA, exam, subject or term must remain incomplete/blank unless an authorized manual/hybrid value is supplied.

---

# 6. Backend Module Reference

# 6.1 `modules/admin_routes.py`

## Purpose

Admin/Teacher authentication, role guards and page routing.

## Current responsibilities

- Admin login.
- Teacher login/session handling.
- `admin_only`.
- `teacher_allowed`.
- Admin Dashboard.
- Teachers.
- Converter.
- Attendance.
- CA Tests.
- Islamiyah.
- Report Sheets.
- Academic History.
- Cumulative Results.
- Broadsheets.
- Subject Manager.
- IDs.
- Promotion/Student Database.
- Settings.
- Support.
- Admin Results.
- Logout.

## Students & Classes naming decision

The user-facing navigation may display:

```text
Students
or
Students & Classes
```

but the existing backend Promotion route/file may remain unchanged:

```text
/admin/promotion
templates/promotion.html
static/css/promotion.css
static/js/promotion.js
modules/promotion_manager.py
```

This avoids unnecessary renaming risk while accurately describing the module to users.

---

# 6.2 `modules/api_routes.py`

## Purpose

Main examination-results API, live notifications, academic-setting compatibility and result export.

## Authority

```text
Excel under RESULTS/ = Admin Results source of truth
```

## Main APIs

```text
/api/results/years
/api/results/classes
/api/results/terms
/api/results/subjects
/api/results/load
/api/results
/api/results/all
/api/results/search_admission
/api/results/search/<query>
/api/results/delete
/api/academic-settings
/api/notifications/notify/exam_start
/api/notifications/notify/exam_end
/api/notifications/fetch
/api/notifications/stream
/api/results/export/excel
```

---

# 6.3 `modules/class_config.py`

## Purpose

Compatibility layer for classes, arms, streams/tracks and subject resolution.

## Phase upgrades

- Keeps active production classes restricted to JSS1–SS3 and SS1–SS3.
- Exposes configured future classes separately.
- Integrates the dynamic Subject Registry for active/configured subject lookup.
- Preserves legacy hard-coded lists as fallback only where appropriate.
- Supports SS track compatibility.
- Exposes class-arm metadata and normalization.

---

# 6.4 `modules/school_structure.py`

## Purpose

Canonical school-structure definition.

## Important constants

```text
ACTIVE_DATABASE_CLASSES
REGULAR_CLASS_LEVELS
PENDING_DATABASE_CLASSES
ISLAMIYAH_CLASS_LEVELS
ALL_CONFIGURED_CLASSES
SCHOOL_SECTIONS
CLASS_LABELS
ASSESSMENT_SCHEMES
SOURCE_NOTES
```

## Important functions

```python
normalize_school_class()
class_label()
is_islamiyah_class()
is_regular_class()
database_is_active_for_class()
school_section_for_class()
get_school_classes()
get_class_metadata()
get_school_structure_payload()
get_source_subjects()
get_assessment_scheme()
```

---

# 6.5 `modules/grading_system.py`

## Purpose

Centralized grading scales.

## Important functions

```python
get_grading_system()
get_grade_scale()
grade_score()
grading_system_ready()
```

---

# 6.6 `modules/subject_registry.py`

## Purpose

Persistent dynamic subject catalogue and class assignment engine.

## Main responsibilities

- Seed canonical subjects.
- Migrate old registry format.
- Repair safe default assignment state.
- Preserve stable subject ID/key.
- Preserve aliases.
- List/filter subjects.
- Create subject.
- Rename subject.
- Activate/deactivate subject.
- Assign/unassign classes.
- Manage SS tracks.
- Build synchronization payload.
- Apply deployed synchronization event.
- Report registry statistics/configuration.

## Important functions

```python
ensure_subject_registry()
read_subject_registry()
write_subject_registry()
resolve_subject_key()
get_subject()
get_class_subject_rows()
get_registered_subjects()
list_subjects()
create_subject()
update_subject()
save_subject_configuration()
set_subject_assignments()
set_subject_status()
build_subject_sync_payload()
apply_subject_registry_sync_event()
get_registry_stats()
get_subject_manager_config()
```

---

# 6.7 `modules/subject_manager.py`

## Purpose

Admin-only Subject Manager HTTP/API layer.

## APIs

```text
GET   /api/subject-manager/config
GET   /api/subject-manager/subjects
POST  /api/subject-manager/subjects
PUT   /api/subject-manager/subjects/<subject_id>
PUT   /api/subject-manager/subjects/<subject_id>/assignments
PATCH /api/subject-manager/subjects/<subject_id>/status
```

---

# 6.8 `modules/teacher_assignment_manager.py`

## Purpose

Teacher academic-assignment persistence and validation.

## Main responsibilities

- initialize assignment tables;
- normalize academic session;
- retrieve teacher profile;
- update profile;
- validate class/arm/subject assignment;
- enforce subject-track compatibility;
- list teacher assignments;
- replace session assignment scope;
- delete assignments;
- write audit entries;
- build assignment statistics;
- build/apply sync payload.

## Important functions

```python
init_teacher_assignment_tables()
get_teacher()
update_teacher_profile()
get_teacher_assignments()
replace_teacher_assignments()
delete_teacher_assignments()
get_teacher_assignment_stats()
list_teachers_with_assignment_summary()
get_teacher_assignment_config()
build_teacher_assignment_sync_payload()
apply_teacher_assignment_sync_event()
```

---

# 6.9 `modules/teacher_assignment_routes.py`

## Purpose

Admin assignment APIs and Teacher self-view APIs.

## APIs

```text
GET   /api/teacher-assignments/config
GET   /api/teacher-assignments/teachers
GET   /api/teacher-assignments/teachers/<teacher_id>
PATCH /api/teacher-assignments/teachers/<teacher_id>
PUT   /api/teacher-assignments/teachers/<teacher_id>/assignments
GET   /api/teacher-assignments/mine
```

---

# 6.10 `modules/excel_manager.py`

## Purpose

Physical examination-result Excel storage and retrieval.

## Result paths

```text
JSS:
RESULTS/<year>/CLASS/JSS1/<TERM>/<subject>/results.xlsx

SS:
RESULTS/<year>/CLASS/SS1/<subject>/results.xlsx
```

## Main responsibilities

- create workbook;
- append result;
- read result;
- normalize result structure;
- repair old headers;
- map old/legacy result formats.

---

# 6.11 `modules/promotion_manager.py`

## Purpose

Student administration and lifecycle orchestration.

## Current user-facing concept

This page can be presented in navigation as **Students & Classes** while retaining the existing backend Promotion route and implementation.

## Features

- student listing;
- add/edit student;
- deletion;
- promotion;
- repeat;
- selected-student demotion;
- SS3 graduation;
- Smart Promotion Guard/Roadmap;
- Smart Import;
- admission-number handling;
- backups;
- exports;
- graduate access;
- logs.

## APIs

```text
/api/promotion/summary
/api/promotion/students
/api/promotion/logs
/api/promotion/student/save
/api/promotion/delete
/api/promotion/promote
/api/promotion/repeat
/api/promotion/demote
/api/promotion/graduate
/api/promotion/graduates
/api/promotion/guard
/api/promotion/import/analyze
/api/promotion/import/commit
/api/promotion/import/template
/api/promotion/backup
/api/promotion/export
```

---

# 6.12 `modules/student_database/student_database.py`

## Purpose

Authoritative active-student database transaction engine.

## Authority

```text
static/data/database/students2026.csv
```

## Mirrors

```text
JSS1_Students.xlsx
JSS2_Students.xlsx
JSS3_Students.xlsx
SS1_Students.xlsx
SS2_Students.xlsx
SS3_Students.xlsx
```

## Transaction rule

```text
Validate
   ↓
Backup
   ↓
Write master CSV
   ↓
Rebuild class workbooks
   ↓
Verify
   ↓
Rollback on failure
```

---

# 6.13 `modules/student_database/admission_manager.py`

## Purpose

Admission-number generation, reservation and graduate-number recycling.

## Rule

Only successfully graduated students release their number for later reuse.

Ordinary deletion does not automatically recycle the admission number.

---

# 6.14 `modules/student_database/graduation_manager.py`

## Purpose

Protected SS3 graduation archive and active-roster removal.

## Storage

```text
static/data/database/graduates/<year>/graduated_students_<year>.xlsx
static/data/database/graduates/graduation_log.csv
```

---

# 6.15 `modules/student_database/student_import_manager.py`

## Purpose

Smart multi-format student import.

## Input

```text
CSV
XLSX/XLSM
DOCX
TXT
MD
text-based PDF
```

## Safety

Approved rows are committed through the same transactional master-database engine.

---

# 6.16 `modules/student_database/promotion_safeguards.py`

## Purpose

Promotion validation/safety helpers used by the Promotion/Students module.

The module supports guarded class movement and reduces unsafe class/arm changes.

---

# 6.17 `modules/student_database/promotion_ai.py`

## Purpose

Optional AI-assisted Promotion Guard/Roadmap guidance.

It supplements deterministic promotion safety rather than replacing transaction validation.

---

# 6.18 `modules/student_lookup.py`

## Purpose

Student normalization, lookup and login authentication.

## Login rule

```text
Admission Number + First Name OR Last Name
```

---

# 6.19 `modules/student_portal.py`

## Purpose

Student CBT portal and exam lifecycle.

## Important authority rule

Live student exams use pushed class/arm year/term state.

Global staff Academic Settings do not silently move an active exam into a different period.

---

# 6.20 `modules/student_results.py`

## Purpose

Local result-save layer.

## Flow

```text
Student submission
      ↓
database.db
      +
RESULTS/.../results.xlsx
      ↓
Sync queue
```

---

# 6.21 `modules/academic_records.py`

## Purpose

Shared academic normalization/lookup layer.

## Used by

- Attendance
- CA/Test
- Report Sheets
- Islamiyah roster import
- other staff academic modules

## Important functions

```python
normalize_academic_session()
normalize_academic_term()
get_current_academic_context()
normalize_academic_class()
validate_class_selection()
get_students_for_class()
get_student()
get_subjects_for_selection()
get_subjects_for_student()
build_academic_record_key()
```

---

# 6.22 `modules/academic_settings.py`

## Purpose

Single global staff academic context.

## Storage

```text
static/data/academic/academic_settings.json
```

## Example

```text
result_year: 2026
academic_session: 2026/2027
term: FIRST
```

---

# 6.23 `modules/attendance_manager.py`

## Purpose

Daily attendance, history and reporting source.

## Features

- Present
- Absent
- Late
- Sick
- Excused
- Unmarked
- Holiday
- overwrite confirmation
- backups
- history
- class summary
- student summary/history
- Local → Deployed sync

## Storage

```text
static/data/attendance/attendance_<CLASS_ARM>.csv
static/data/attendance/backups/
```

---

# 6.24 `modules/ca_test_manager.py`

## Purpose

Structured CA/Test entry, validation, completeness and Report Sheet source.

## JSS

```text
CA1 /10
CA2 /10
TEST1 /20
TEST2 /20
```

## SS

```text
ASS1 /5
ASS2 /5
TEST /20
```

## Storage

```text
static/data/ca_tests/ca_test_records.csv
static/data/ca_tests/backups/
```

---

# 6.25 `modules/essay_results.py`

## Purpose

Manual Essay/Theory score layer combined with CBT objective results.

## Main behavior

- detects essay configuration;
- loads objective result;
- validates essay score;
- stores manual theory score;
- combines final score;
- participates in sync.

---

# 6.26 `modules/islamiyah_manager.py`

## Purpose

Core Islamiyah roster, placement, score, history, report-integration and synchronization engine.

## Important functions

```python
ensure_islamiyah_storage()
read_enrollments()
write_enrollments()
read_scores()
write_scores()
import_current_student_database()
assign_students()
save_student_score()
get_score_entry_roster()
get_student_history()
get_report_islamiyah_row()
get_class_result_summary()
get_islamiyah_dashboard()
build_enrollment_sync_payload()
build_score_scope_sync_payload()
apply_islamiyah_sync_event()
```

---

# 6.27 `modules/islamiyah_routes.py`

## Purpose

Islamiyah staff/admin HTTP/API layer.

## APIs

```text
GET   /api/islamiyah/config
GET   /api/islamiyah/dashboard
GET   /api/islamiyah/roster
POST  /api/islamiyah/roster/import
PUT   /api/islamiyah/roster/assign
GET   /api/islamiyah/scores
PATCH /api/islamiyah/scores/autosave
GET   /api/islamiyah/results
GET   /api/islamiyah/history/<admission_number>
GET   /api/islamiyah/export
```

---

# 6.28 `modules/report_sheet_manager.py`

## Purpose

Central Report Sheet aggregation, grading, class statistics, Auto/Manual/Hybrid generation, saved report snapshots, exports, audit, cumulative attachment and Permanent Academic History handoff.

## Sources

```text
Student Database
Attendance
CA/Test
CBT / Essay
Islamiyah
Manual fallback
```

## Main capabilities

- class/student report preview;
- source readiness;
- Auto generation;
- Manual generation;
- Hybrid generation;
- missing-data preservation;
- subject totals;
- grades;
- class statistics;
- student/class positions;
- strongest/focus subject;
- attendance;
- traits;
- teacher/principal remarks;
- defaults;
- report detail overrides;
- saved snapshots;
- audit usage;
- CSV/Excel export;
- Third Term cumulative attachment;
- Permanent Academic History archiving.

## APIs

```text
/api/report-sheets/config
/api/report-sheets/students
/api/report-sheets/source-status
/api/report-sheets/preview
/api/report-sheets/generate
/api/report-sheets/saved
/api/report-sheets/delete-saved
/api/report-sheets/details
/api/report-sheets/defaults
/api/report-sheets/export/csv
/api/report-sheets/export/excel
/api/report-sheets/mark-used
/api/report-sheets/manual
/api/report-sheets/manual/generate
/api/report-sheets/bulk-details
```

## Storage

```text
static/data/report_sheets/generated_reports.jsonl
static/data/report_sheets/report_details.json
static/data/report_sheets/report_defaults.json
static/data/report_sheets/report_usage.jsonl
static/data/report_sheets/manual_report_records.json
```

---

# 6.29 `modules/academic_history.py`

## Purpose

Permanent canonical historical result archive plus Transcript compiler.

## Main capabilities

- archive generated Report Sheets;
- retain replacement revisions;
- search history;
- student timeline;
- official archived record detail;
- history Excel export;
- archive rebuild;
- historical identity protection;
- transcript compilation;
- transcript reference;
- transcript Excel export;
- real score/max/percentage derivation;
- session annual summaries;
- Local → Deployed history sync.

## APIs

```text
GET  /api/academic-history/config
GET  /api/academic-history/search
GET  /api/academic-history/student/<admission_number>
GET  /api/academic-history/record/<record_id>
POST /api/academic-history/rebuild
GET  /api/academic-history/transcript/<admission_number>
GET  /api/academic-history/transcript/export/<admission_number>
GET  /api/academic-history/export/<admission_number>
```

## Storage

```text
static/data/academic_history/academic_records.jsonl
static/data/academic_history/record_revisions.jsonl
```

---

# 6.30 `modules/cumulative_results.py`

## Purpose

Three-term annual result compilation derived from Academic History.

## Main capabilities

- class cumulative payload;
- student cumulative payload;
- term score bundles;
- subject annual rows;
- annual score/max/%;
- annual attendance;
- provisional/final status;
- complete-only final annual ranking;
- individual Excel export;
- class Excel export.

## APIs

```text
GET /api/cumulative-results/config
GET /api/cumulative-results/class
GET /api/cumulative-results/student/<admission_number>
GET /api/cumulative-results/export/class
GET /api/cumulative-results/export/student/<admission_number>
```

---

# 6.31 `modules/broadsheet_manager.py`

## Purpose

Term and cumulative class-wide academic analysis.

## Main capabilities

- term matrix;
- cumulative matrix;
- class analytics;
- subject catalogue;
- grade distribution;
- strongest/focus analytics;
- top/lowest performers;
- subject statistics;
- real score/max/%;
- multi-sheet Excel workbook.

## APIs

```text
GET /api/broadsheets/config
GET /api/broadsheets/data
GET /api/broadsheets/export
```

---

# 6.32 `modules/result_sync.py`

## Purpose

Durable offline-first Local → Deployed synchronization.

## Core guarantees

- Local save succeeds first.
- Network failure does not roll back school work.
- Queue persists.
- Automatic retry/backoff.
- HMAC-SHA256 signing.
- Idempotency receipts.
- Per-entity revision protection.
- Sender/receiver modes.
- Manual flush/requeue.

## APIs

```text
GET  /api/sync/status
POST /api/sync/flush
POST /api/sync/requeue
POST /api/sync/results
POST /api/sync/events
```

## Current generalized sync modules

```text
attendance
ca_tests
essay
report_sheets
academic_settings
subject_registry
teacher_assignments
islamiyah
academic_history
```

CBT result synchronization remains supported through the dedicated result flow.

## Storage

```text
sync_data/result_sync.db
```

---

# 6.33 `modules/supabase_client.py`

Basic Supabase connection helper.

Supabase is not the current primary authority for active examination results.

---

# 6.34 `modules/supabase_results.py`

Legacy/optional Supabase result/settings compatibility.

Current authority remains:

```text
Admin Results → Excel under RESULTS/
Academic Settings → local settings + durable sync
```

---

# 6.35 `modules/user_routes.py`

Student authentication/session routes.

```text
/student_login
/logout
```

---

# 6.36 `modules/convert_routes.py`

Admin/Teacher converter API layer.

```text
/convert/api/extract
/convert/api/generate-json
/convert/api/save-json
/convert/api/drafts
/convert/api/drafts/<draft_id>
/convert/api/drafts/clear
```

---

# 6.37 `convert.py`

Main exam-document extraction and CBT JSON construction engine.

Responsibilities include:

- text extraction;
- diagram extraction;
- class/subject/year/term detection;
- objective parsing;
- passage/group handling;
- JSON structural validation/repair.

---

# 6.38 `convert_ext.py`

OpenAI solver/verifier and clean JSON output layer.

Typical flow:

```text
Questions
   ↓
Solver
   ↓
Verifier
   ↓
Review Report
   ↓
Final correctOption
```

---

# 6.39 `modules/document_routes.py`

Document-related Flask/API orchestration retained by the core exam/document workflow.

---

# 6.40 `modules/notifications.py`

Live notification API used by Admin/Teacher interfaces.

Works with result/exam activity and the global dashboard.

---

# 6.41 `modules/listed_years.py`

Small helper for configured/listed result/exam years retained for compatibility.

---

# 6.42 `email_server.py`

Optional email result notifications and one-page PDF result summary.

---

# 6.43 `exam_document_export.py`

Exam-document export helper for generating downloadable/printable exam documents from structured exam data.

---

# 6.44 `engine.py`

General backend utilities and Teacher account storage.

Teacher credentials remain in:

```text
database.db → teachers table
```

Phase 3 assignment tables are separate from the credential row.

---

# 6.45 `push.py`

Exam deployment to the live student portal.

State includes:

```text
static/portal/latest_year.txt
static/portal/class_active_years.json
static/portal/class_active_terms.json
pushed_subjects.json
```

Supports single and multi-subject pushing.

---

# 6.46 `uploads.py`

Admin exam JSON library management.

Storage:

```text
JSS:
static/subjects/<year>/subjects-json/JSS1/<TERM>/

SS:
static/subjects/<year>/subjects-json/SS1/
```

---

# 6.47 `app.py`

## Purpose

Main Flask bootstrap.

## Current academic blueprint set

The current build registers the core blueprints plus:

```text
Attendance
CA/Test
Report Sheets
Subject Manager
Teacher Assignments
Islamiyah
Academic History
Cumulative Results
Broadsheets
```

## Other responsibilities

- environment loading;
- Flask initialization;
- global Academic Context injection;
- static cache/version handling;
- strict HTML/API cache policy;
- blueprint registration;
- sync database/worker startup;
- local development entry point.

---

# 7. Frontend / UI Architecture

# 7.1 `templates/base.html`

Global staff layout:

- top header;
- EMIS brand;
- Modules dropdown;
- notifications;
- theme toggle;
- user identity;
- desktop sidebar;
- mobile sidebar;
- global flash messages;
- content slots;
- global Academic Context;
- global scripts.

## Recommended/current navigation workflow

Admin:

```text
Dashboard
Students / Students & Classes
Islamiyah
Attendance
CA Tests
Results
Report Sheets
Cumulative
Broadsheets
History
Teachers
Subjects
IDs
Settings
Support
```

The visible Students label can still point to the existing `/admin/promotion` route.

Teacher:

```text
My Workspace
Islamiyah
Attendance
CA Tests
Report Sheets
Support
```

---

# 7.2 Dashboard

The Dashboard remains the main operational overview.

Phase upgrades added shortcuts/links for:

- Subjects;
- Islamiyah;
- Academic History;
- Cumulative;
- Broadsheets;
- other academic modules.

The Dashboard uses live academic APIs rather than introducing a separate reporting database.

---

# 7.3 Subject Manager frontend

```text
templates/subjects.html
static/css/subjects.css
static/js/subjects.js
```

UI:

- filters;
- subject list;
- add/edit configuration;
- active/inactive status;
- class assignment;
- SS track assignment;
- stable-key behavior hidden behind normal Admin controls.

---

# 7.4 Teacher Assignment frontend

```text
templates/teachers.html
static/css/teachers.css
static/js/teacher_assignments.js
```

UI:

- teacher directory;
- search/status filters;
- profile editor;
- assignment editor;
- session selection;
- class/arm/subject assignment;
- Teacher self teaching-load view.

---

# 7.5 Islamiyah frontend

```text
templates/islamiyah.html
static/css/islamiyah.css
static/js/islamiyah.js
```

Main workspaces:

- Overview
- Score Entry
- Student Placement
- Results & History

The later visual redesign enlarged typography, improved cards/layout and reduced the tiny/scattered appearance of the first Phase 4 UI.

---

# 7.6 Report Sheets 2.0 frontend

```text
templates/report_sheets.html
static/css/report_sheets.css
static/js/report_sheet.js
static/js/report_sheet_pdf.js
static/js/report_voice_entry.js
```

## Main workspaces

- Automatic reporting
- Manual + Hybrid inline workspace
- source readiness
- student report preview
- saved reports
- cumulative compiler
- PDF/print
- supporting edit modals

## Important UI rule

The **Manual Result Studio itself is not a modal**.

Focused editors can remain modal-based.

---

# 7.7 Academic History + Transcript frontend

```text
templates/academic_history.html
static/css/academic_history.css
static/js/academic_history.js
```

Views:

```text
History
Transcript
```

No separate Transcript page/sidebar item is required.

---

# 7.8 Cumulative Results frontend

```text
templates/cumulative_results.html
static/css/cumulative_results.css
static/js/cumulative_results.js
```

Features:

- class/session selection;
- class roster;
- score display modes;
- completion status;
- cumulative sheet preview;
- visible View Sheet;
- selected student PDF;
- class PDF;
- Excel exports;
- selected-row highlighting;
- first-student auto-preview.

---

# 7.9 Broadsheets frontend

```text
templates/broadsheets.html
static/css/broadsheets.css
static/js/broadsheets.js
```

Supports wide matrix navigation, frozen/sticky sections, analytics and landscape official printing.

---

# 7.10 Shared official academic-document renderer

```text
static/js/academic_document.js
static/css/academic_document.css
```

Used by:

- Cumulative
- History print
- Transcript
- Broadsheet print
- related official academic documents

It reuses the visual language of the approved Student Report Sheet.

---

# 8. Official Academic Document Design Standard

The Student Report Sheet is the master visual reference for EMIS official academic documents.

# 8.1 Header

Official documents should contain:

- school logo;
- `EPITOME MODEL ISLAMIC SCHOOLS`;
- school motto;
- school address;
- document title;
- term/session where relevant.

# 8.2 Student identity block

Typical fields:

```text
Student Name
Admission Number
Class
Sex
Age
Session
Term
```

# 8.3 Summary cards

Normal term Report Sheet:

```text
Final Average
Final Grade
Class Position
Attendance
Class Average
```

Annual/cumulative documents adapt the same card language for:

```text
Annual Score
Annual Percentage
Annual Grade
Annual Position
Terms Available
Annual Attendance
```

# 8.4 Academic performance table

Normal Report Sheet keeps component-level scoring.

Example JSS columns:

```text
Subject
CA1 /10
CA2 /10
T1 /20
T2 /20
Exam /40
Total /100
Grade
Position
Out
Low
High
Average
Comment
```

Islamiyyah receives its special:

```text
CA /30
Exam /70
Total /100
```

layout.

# 8.5 Interpretable score rule

Official cumulative/history/transcript documents should not show percentage alone where a real score can be shown.

Preferred:

```text
629.2 / 1300 • 48.4%
```

instead of only:

```text
48.4%
```

For three terms:

```text
229 / 300 • 76.33%
```

For annual whole-result score:

```text
2350 / 3900 • 60.26%
```

# 8.6 Grade key

Keep a compact grade key consistent with the selected grading system.

# 8.7 Insight blocks

The existing term Report Sheet supports:

- Strongest Subject
- Focus Subject
- Compared with Class
- Subjects Passed

Cumulative/History/Transcript may use equivalent annual/trend insights where appropriate.

# 8.8 Attendance / traits / remarks

Normal Report Sheets continue to support:

- Attendance
- Affective Traits
- Psychomotor
- Rating Scale
- Form Teacher
- Form Teacher Remark
- Principal Remark
- Next Term Begins
- signature lines

# 8.9 Footer

Official EMIS academic documents should retain a consistent footer identifying the EMIS academic report/document.

# 8.10 Print behavior

- A4 portrait for student-level Report Sheet/Cumulative/History.
- Transcript can span multiple report-style pages.
- Broadsheets use official landscape layout.
- Dashboard/sidebar controls are excluded from isolated print targets.
- Long subject tables use adaptive density.

---

# 9. Main End-to-End Workflows

# 9.1 Student administration

```text
Promotion / Students & Classes page
      ↓
promotion_manager.py
      ↓
student_database.py
      ├── students2026.csv
      └── six class XLSX mirrors
```

---

# 9.2 Subject configuration

```text
Admin Subject Manager
      ↓
subject_manager.py
      ↓
subject_registry.py
      ↓
subject_registry.json
      ↓
Sync Queue
```

---

# 9.3 Teacher configuration

```text
Teacher account
      ↓
Teacher Assignment UI
      ↓
teacher_assignment_manager.py
      ↓
database.db
   teacher_assignments
   teacher_assignment_audit
```

---

# 9.4 Islamiyah workflow

```text
Central Student Roster
      ↓
Import / Sync Islamiyah Roster
      ↓
Independent Islamiyah Placement
      ↓
Teacher Class/Subject Assignment
      ↓
CA /30 + Exam /70 Autosave
      ↓
Islamiyah History / Class Results
      ↓
Aggregated Islamiyyah row
      ↓
Regular Report Sheet
```

---

# 9.5 Daily academic workflow

```text
Attendance
   ↓
CA Tests
   ↓
CBT / Essay Results
   ↓
Islamiyah
   ↓
Report Sheet
```

This ordering matches how the data becomes available for final reporting.

---

# 9.6 Report generation

```text
Class + Session + Term
      ↓
Source Readiness
      ↓
Auto / Manual / Hybrid
      ↓
Report Sheet
      ↓
Save official snapshot
      ↓
Permanent Academic History
```

---

# 9.7 Annual workflow

```text
First Term History
Second Term History
Third Term History
      ↓
Cumulative Engine
      ├── Student Cumulative Sheet
      ├── Annual ranking
      ├── Annual attendance
      └── Excel / PDF
```

---

# 9.8 Broadsheet workflow

```text
Academic History
      +
Cumulative Engine
      ↓
Broadsheet Manager
      ├── Term Matrix
      ├── Cumulative Matrix
      ├── Analytics
      └── Excel / Print
```

---

# 9.9 Transcript workflow

```text
Permanent Academic History
      ↓
Select historical student identity
      ↓
Compile sessions/classes/terms
      ↓
Transcript
      ├── Official print/PDF
      └── Multi-sheet Excel
```

---

# 10. Storage Map

# Active students

```text
static/data/database/students2026.csv
```

# Class roster mirrors

```text
static/data/database/JSS1_Students.xlsx
static/data/database/JSS2_Students.xlsx
static/data/database/JSS3_Students.xlsx
static/data/database/SS1_Students.xlsx
static/data/database/SS2_Students.xlsx
static/data/database/SS3_Students.xlsx
```

# Student database backups

```text
static/data/database/backups/student_database/
```

# Admission-number pool

```text
static/data/database/admission_numbers/available_numbers.json
```

# Graduates

```text
static/data/database/graduates/<year>/graduated_students_<year>.xlsx
static/data/database/graduates/graduation_log.csv
```

# Promotion logs

```text
static/data/database/promotion_logs.csv
```

# Teacher accounts + Teacher assignments

```text
database.db
  ├── teachers
  ├── teacher_assignments
  └── teacher_assignment_audit
```

# Subject Registry

```text
static/data/academic/subject_registry.json
static/data/academic/backups/subject_registry/
```

# Academic Settings

```text
static/data/academic/academic_settings.json
```

# Attendance

```text
static/data/attendance/attendance_<CLASS_ARM>.csv
static/data/attendance/backups/
```

# CA/Test

```text
static/data/ca_tests/ca_test_records.csv
static/data/ca_tests/backups/
```

# Examination results

```text
RESULTS/<year>/CLASS/.../results.xlsx
```

# Islamiyah

```text
static/data/islamiyah/student_enrollments.csv
static/data/islamiyah/score_records.csv
static/data/islamiyah/backups/
```

# Report Sheets

```text
static/data/report_sheets/generated_reports.jsonl
static/data/report_sheets/report_details.json
static/data/report_sheets/report_defaults.json
static/data/report_sheets/report_usage.jsonl
static/data/report_sheets/manual_report_records.json
```

# Permanent Academic History

```text
static/data/academic_history/academic_records.jsonl
static/data/academic_history/record_revisions.jsonl
```

# Cumulative Results

No separate result database.

Derived from Academic History.

# Broadsheets

No separate result database.

Derived from Academic History and Cumulative Results.

# Transcript

No separate result database.

Compiled from Academic History.

# Sync

```text
sync_data/result_sync.db
```

# Exam library

```text
static/subjects/<year>/subjects-json/...
```

# Live student portal exams

```text
static/portal/<year>/...
```

# Converter drafts

```text
static/uploads/convert-drafts/
```

---

# 11. Routes and API Map

# Admin/staff pages

```text
/admin
/admin/dashboard
/admin/teachers
/admin/convert
/admin/attendance
/admin/ca-tests
/admin/islamiyah
/admin/report-sheets
/admin/academic-history
/admin/cumulative-results
/admin/broadsheets
/admin/ids
/admin/promotion
/admin/subjects
/admin/settings
/admin/support
/admin/results
```

The visible navigation label for `/admin/promotion` can be **Students** or **Students & Classes**.

# Subject Manager

```text
GET   /api/subject-manager/config
GET   /api/subject-manager/subjects
POST  /api/subject-manager/subjects
PUT   /api/subject-manager/subjects/<subject_id>
PUT   /api/subject-manager/subjects/<subject_id>/assignments
PATCH /api/subject-manager/subjects/<subject_id>/status
```

# Teacher Assignments

```text
GET   /api/teacher-assignments/config
GET   /api/teacher-assignments/teachers
GET   /api/teacher-assignments/teachers/<teacher_id>
PATCH /api/teacher-assignments/teachers/<teacher_id>
PUT   /api/teacher-assignments/teachers/<teacher_id>/assignments
GET   /api/teacher-assignments/mine
```

# Islamiyah

```text
GET   /api/islamiyah/config
GET   /api/islamiyah/dashboard
GET   /api/islamiyah/roster
POST  /api/islamiyah/roster/import
PUT   /api/islamiyah/roster/assign
GET   /api/islamiyah/scores
PATCH /api/islamiyah/scores/autosave
GET   /api/islamiyah/results
GET   /api/islamiyah/history/<admission_number>
GET   /api/islamiyah/export
```

# Report Sheets

```text
GET/POST routes under /api/report-sheets/...
```

Important:

```text
/api/report-sheets/config
/api/report-sheets/students
/api/report-sheets/source-status
/api/report-sheets/preview
/api/report-sheets/generate
/api/report-sheets/saved
/api/report-sheets/delete-saved
/api/report-sheets/details
/api/report-sheets/defaults
/api/report-sheets/export/csv
/api/report-sheets/export/excel
/api/report-sheets/mark-used
/api/report-sheets/manual
/api/report-sheets/manual/generate
/api/report-sheets/bulk-details
```

# Academic History / Transcript

```text
/api/academic-history/config
/api/academic-history/search
/api/academic-history/student/<admission_number>
/api/academic-history/record/<record_id>
/api/academic-history/rebuild
/api/academic-history/transcript/<admission_number>
/api/academic-history/transcript/export/<admission_number>
/api/academic-history/export/<admission_number>
```

# Cumulative

```text
/api/cumulative-results/config
/api/cumulative-results/class
/api/cumulative-results/student/<admission_number>
/api/cumulative-results/export/class
/api/cumulative-results/export/student/<admission_number>
```

# Broadsheets

```text
/api/broadsheets/config
/api/broadsheets/data
/api/broadsheets/export
```

# Synchronization

```text
/api/sync/status
/api/sync/flush
/api/sync/requeue
/api/sync/results
/api/sync/events
```

---

# 12. Local → Deployed Synchronization

# Core model

```text
LOCAL EMIS
Save locally
   ↓
Durable queue
   ↓
Signed HTTPS
   ↓
DEPLOYED EMIS
Verify + apply
```

# Reliability features

```text
UUID/idempotency
HMAC-SHA256
timestamp validation
retry/backoff
receipt tracking
per-entity revision protection
sender/receiver configuration
manual requeue
manual flush
```

# Current synchronized modules

```text
CBT Results
Attendance
CA/Test
Essay/Theory
Report Sheets
Academic Settings
Subject Registry
Teacher Assignments
Islamiyah
Academic History
```

# Key rule

Cloud sync failure must not destroy or roll back a successful local academic save.

---

# 13. Navigation and Module Order

The staff UI should be arranged by real school workflow rather than by development history.

## Admin order

```text
1. Dashboard
2. Students / Students & Classes
3. Islamiyah
4. Attendance
5. CA Tests
6. Results
7. Report Sheets
8. Cumulative
9. Broadsheets
10. History
11. Teachers
12. Subjects
13. IDs
14. Settings
15. Support
```

## Rationale

- **Students & Classes** is near the top because it is the central student/class database.
- **Islamiyah** is early because Islamiyyah contributes to regular Report Sheets.
- **Attendance** comes before CA in the daily school workflow.
- **CA** precedes final Results/Report compilation.
- **Results** contains examination result data.
- **Report Sheets** aggregate all sources.
- **Cumulative** depends on official term history.
- **Broadsheets** summarize term/annual class performance.
- **History** is the permanent archive and Transcript home.
- **Teachers / Subjects / IDs** are configuration/administration rather than the most frequent daily academic workflow.

## Important route decision

Only the visible label needs to change if desired.

The existing Promotion backend can remain:

```text
/admin/promotion
promotion.html
promotion.css
promotion.js
promotion_manager.py
```

---

# 14. Deployment / Cache Rules

`app.py` includes strict static/template cache handling.

## Current behavior

- HTML responses use no-store/revalidation protection.
- API responses use no-store protection.
- JS/CSS receive strict cache protection.
- static URLs receive version query values tied to physical file metadata.
- old hardcoded `/static/...` links in rendered HTML can be rewritten with version parameters.
- templates auto-reload.
- Python backend changes still require Flask/Passenger restart.

## Deployment rule

After replacing Python modules:

```text
Restart Flask / Passenger
```

For frontend-only CSS/JS/template replacement, cache-busting is designed to reduce stale browser assets, but production deployment procedures should still verify the new files are being served.

---

# 15. Current Pending Activation / Phase 10

The following items remain intentionally pending rather than being treated as errors.

# 15.1 Nursery / Primary / Tahfeez student databases

Configured but not active.

Required before full activation:

- authoritative student roster;
- class-arm policy where applicable;
- database migration/creation;
- Student Database integration;
- Promotion-path decisions for lower school;
- final report validation.

# 15.2 Primary grading scale

The Primary subject structure exists, but the approved Primary grading boundaries are still required.

# 15.3 Primary/Nursery assessment scheme

The exact official CA/Exam component structure should be confirmed before lower-school report generation is activated.

# 15.4 Final cross-module regression testing

Phase 10 should include:

- database migration checks;
- lower-school activation;
- grading activation;
- role/permission checks;
- report/cumulative/broadsheet/history/transcript regression;
- print/PDF checks;
- Local → Deployed sync regression;
- deployment verification.

# 15.5 Sidebar growth

Future capabilities should preferentially be integrated into existing logical pages rather than creating unnecessary new sidebar pages.

The Phase 9 Transcript integration into Academic History is the preferred pattern.

---

# 16. Quick File Guide

| Need to Change | Main File(s) |
|---|---|
| Admin/Teacher login or page access | `modules/admin_routes.py` |
| Global staff navigation | `templates/base.html`, `static/css/admin1.css` |
| Dashboard | `templates/dashboard.html`, `static/css/dashboard.css`, dashboard JS |
| Students / Promotion / Classes | `modules/promotion_manager.py`, `templates/promotion.html`, `static/js/promotion.js`, `static/css/promotion.css` |
| Active student database | `modules/student_database/student_database.py` |
| Admission-number generation/recycling | `modules/student_database/admission_manager.py` |
| Graduation | `modules/student_database/graduation_manager.py` |
| Student import | `modules/student_database/student_import_manager.py` |
| School sections / configured classes | `modules/school_structure.py` |
| Active class/arm/stream compatibility | `modules/class_config.py` |
| Dynamic subjects | `modules/subject_registry.py`, `modules/subject_manager.py`, `templates/subjects.html` |
| Grading | `modules/grading_system.py` |
| Teacher credentials | `engine.py` |
| Teacher academic assignments | `modules/teacher_assignment_manager.py`, `modules/teacher_assignment_routes.py`, `static/js/teacher_assignments.js` |
| Academic year/session/term | `modules/academic_settings.py` |
| Shared academic lookup | `modules/academic_records.py` |
| Attendance | `modules/attendance_manager.py` |
| CA/Test | `modules/ca_test_manager.py` |
| CBT result APIs | `modules/api_routes.py` |
| Local result saving | `modules/student_results.py` |
| Excel result files | `modules/excel_manager.py` |
| Essay/Theory | `modules/essay_results.py` |
| Islamiyah backend | `modules/islamiyah_manager.py`, `modules/islamiyah_routes.py` |
| Islamiyah frontend | `templates/islamiyah.html`, `static/js/islamiyah.js`, `static/css/islamiyah.css` |
| Report aggregation | `modules/report_sheet_manager.py` |
| Report Sheet UI | `templates/report_sheets.html`, `static/js/report_sheet.js`, `static/css/report_sheets.css` |
| Report PDF/print | `static/js/report_sheet_pdf.js` |
| Voice score entry | `static/js/report_voice_entry.js` |
| Permanent Academic History | `modules/academic_history.py` |
| Academic History / Transcript UI | `templates/academic_history.html`, `static/js/academic_history.js`, `static/css/academic_history.css` |
| Cumulative Results | `modules/cumulative_results.py`, `templates/cumulative_results.html`, `static/js/cumulative_results.js`, `static/css/cumulative_results.css` |
| Broadsheets | `modules/broadsheet_manager.py`, `templates/broadsheets.html`, `static/js/broadsheets.js`, `static/css/broadsheets.css` |
| Shared official academic document renderer | `static/js/academic_document.js`, `static/css/academic_document.css` |
| Local → Deployed sync | `modules/result_sync.py` |
| Exam conversion routes | `modules/convert_routes.py` |
| Document extraction/parser | `convert.py` |
| AI solver/verifier | `convert_ext.py` |
| Exam upload library | `uploads.py` |
| Push exams live | `push.py` |
| Student portal | `modules/student_portal.py` |
| Student authentication | `modules/student_lookup.py`, `modules/user_routes.py` |
| Flask bootstrap | `app.py` |

---

# 17. Validation and Safety Summary

Across the phased upgrade work, validation included combinations of:

```text
Python syntax / compile checks
JavaScript syntax checks
Jinja template parsing
CSS structural checks
duplicate HTML-ID checks
JS ↔ HTML element-contract checks
Subject Registry migration tests
Teacher assignment compatibility tests
Islamiyah score-range tests
Islamiyah concurrent autosave tests
Report Sheet frontend integration checks
Academic History backfill/idempotence tests
admission-number reuse protection tests
Cumulative partial-year tests
3-term ranking protection
Broadsheet workbook tests
Transcript compilation/export tests
official document score/max/% derivation
cumulative sheet preview/PDF accessibility correction
```

## Critical permanent rules

```text
1. Active production roster remains JSS1–SS3 + SS1–SS3 until lower-school databases arrive.
2. Regular class and Islamiyah class remain independent.
3. Missing score/term data is never silently converted to zero.
4. Historical records preserve historical class/session/term.
5. Promotion does not rewrite Academic History.
6. Admission-number reuse must not merge historical students.
7. Dynamic subjects retain stable identity.
8. Local saves succeed before cloud synchronization.
9. Cumulative/Broadsheet/Transcript derive from Permanent Academic History.
10. Final annual position requires complete three-term annual data.
11. The approved Student Report Sheet is the master design language for official academic documents.
12. Real score / maximum should be shown alongside percentage where available.
13. New features should be integrated into existing logical pages where possible instead of unnecessarily expanding the sidebar.
```

---

# Current Architecture Summary

```text
                           ┌─────────────────────────┐
                           │   STUDENT DATABASE      │
                           │ students2026.csv + XLSX │
                           └────────────┬────────────┘
                                        │
                 ┌──────────────────────┼──────────────────────┐
                 │                      │                      │
                 ▼                      ▼                      ▼
          Attendance              CA / Tests             CBT / Essay
                 │                      │                      │
                 └──────────────┬───────┴──────────────┬──────┘
                                │                      │
                                ▼                      ▼
                         Islamiyah /100          Exam Results
                                │                      │
                                └──────────┬───────────┘
                                           ▼
                                REPORT SHEETS 2.0
                          Auto / Manual / Hybrid
                                           │
                                           ▼
                             PERMANENT ACADEMIC HISTORY
                                   │        │        │
                                   ▼        ▼        ▼
                             Cumulative  Broadsheets Transcript
                                   │        │        │
                                   └────────┴────────┘
                                           │
                                           ▼
                              OFFICIAL ACADEMIC DOCUMENTS
                      Report-Sheet Visual Standard + Score/Max/%
```

---

# End of Reference

This document reflects the implemented EMIS architecture through **Phase 9**, including the Phase 9 unified academic-document and cumulative-sheet accessibility refinements. The next major activation stage is the controlled Phase 10 integration of Nursery/Primary/Tahfeez databases, Primary grading/assessment rules, migration and full regression testing.
