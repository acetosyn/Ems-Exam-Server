# EMIS complete database update

This package updates the important server files supplied in files(6).zip using Emis DB 2026.docx and the uploaded CSVs.

## Included records

| Database | Records | Change |
|---|---:|---|
| students2026.csv | 720 | All 695 existing records preserved; 25 Basic 5A students added |
| tahfeez2026.csv | 823 | One combined register containing 56 Tahfeez and 767 Islamiyyah entries |
| Islamiyyah session roster | 767 | Source classes preassigned for 2026/2027 |

Basic 5A uses PRIMARY5A in the existing server schema. Its new IDs are std696–std720. Existing Tahfeez IDs thf001–thf056 remain unchanged. Islamiyyah source entries use isl001–isl767. Names keep their source order in the existing three name columns; no surname inference or matching to regular-school students was performed.

Islamiyyah has 30 populated classes: 1A–1D, 2A–2H, 3A–3F, 4A–4F, 5A–5C, 6A–6B and 7. Starter and Prep remain configured with no supplied students. Legacy base-level class keys remain supported for older records and teacher assignments. Class arms inherit their level's configured subjects, and existing base-level teacher subject assignments grant access to that level's arms.

The combined register retains its existing filename tahfeez2026.csv for compatibility. Added Islamiyah_Class, Islamiyah_Class_category, Islamiyah_Source and Source_note fields hold Islamiyyah placement and review information. Regular_Class links remain blank for independently supplied students. Current placement updates use this shared register. Enrollment and score CSVs remain session-specific to preserve academic history. Editing an older session does not overwrite current placement.

## Installation

1. Stop the existing Flask/Passenger server and keep a copy of its current project and data.
2. Extract the ZIP. Copy the contents of its files folder into the existing server project, replacing the corresponding files. Keep root modules and deployment configuration that were not part of the uploaded important-files archive.
3. Restart Flask/Passenger so the updated Python modules load.
4. Open the Students page and check Primary 5A: 25 students. Open Tahfeez & Islamiyyah: 56 Tahfeez students and 767 Islamiyyah students, with the supplied arms selectable.
5. The administrator can use Export Combined Database to download both school sections together.

Copies of the original CSVs and enrollment file are in static/data/database/backups/complete_database_20261008. The Primary 5 Excel mirror includes both A and B; all other class workbooks already matched the master and were preserved.

## Source notes

Unclear Basic 5A phone numbers remain ??. Existing phone values and uncertainty markers are preserved. Islamiyyah phones and Sex are blank because they were not supplied. The three repeated names in Islamiyyah 2D, 2F and 2G retain both source entries with separate IDs and visible review notes. Counts are roster entries, not a deduplicated count of individual pupils across both schools.

Import / Sync Current School Database is optional. It retains the supplied 767 Islamiyyah placements and imports the 720 regular-school profiles as unassigned until a verified placement is made. This does not guess which independently supplied name belongs to a regular-school student. Tahfeez 5 transitions update the same student's combined-register row, keeping the existing Tahfeez transition workflow.

Automatic Islamiyyah promotion keeps the arm when that arm exists at the next level. When it does not exist, select the destination manually. Level 6A or 6B advances to Islamiyyah 7.

## Validation

Records were compared by class, full name, phone and Sex against all 52 Word-document class lists. All 695 existing regular-school rows and all 56 Tahfeez source identities were preserved. Every admission ID is unique across the two registers. All 17 regular-school Excel mirrors were checked against the final CSV.

Isolated database and Flask API checks cover class arms, subject inheritance, teacher access, placement, promotion, scoring and score history, regular-roster import, combined export, Tahfeez transitions, and updates/sync preserving the other school section. Python modules, JavaScript syntax and the Islamiyyah template were checked. A full application startup was not possible from the supplied partial archive: app.py references root files such as engine.py, uploads.py and exam_document_export.py that were not included. The updated database and Islamiyyah blueprint were tested independently.
