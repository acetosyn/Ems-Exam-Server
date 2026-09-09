# EMIS Backend Module Reference

> **Purpose:** Concise technical reference for the reviewed EMIS backend Python files.

> **Scope:** Key responsibilities, important functions/routes, storage locations, and major dependencies only.

---

# 1. `modules/admin_routes.py`

## Purpose
Handles the **Admin and Teacher side of EMIS**, including login, permissions, administrative routing, and teacher account management.

### Key Features
- Admin and Teacher authentication.
- Role-based access using `admin_only` and `teacher_allowed`.
- Teacher ID generation and deletion.
- Administrative page routing.
- Viewing generated credentials and older/mock results.
- Logout.

### Important Dependencies
```text
engine.py
user_exam.py
modules/promotion_manager.py
Flask sessions
```

### Summary
> **`admin_routes.py` = Admin/Teacher authentication + permissions + administrative routing + teacher management.**

---

# 2. `modules/api_routes.py`

## Purpose
Provides the **main examination-results API** used by Admin and Teacher interfaces.

### Key Features
- Read and filter examination results.
- Discover available years, classes, terms, and subjects.
- JSS term-aware result handling.
- Backward compatibility with older result structures.
- Search student examination history.
- Delete result records.
- Manage academic session and term.
- Live examination notifications through SSE.
- Export formatted results to Excel.

### Main APIs
```text
/api/results/years
/api/results/classes
/api/results/terms
/api/results/subjects
/api/results/load
/api/results/all
/api/results/search_admission
/api/results/delete
/api/academic-settings
/api/results/export/excel
```

### Result Storage
```text
JSS: RESULTS/<year>/CLASS/JSS1/FIRST/<subject>/results.xlsx
SS:  RESULTS/<year>/CLASS/SS1/<subject>/results.xlsx
```

### Summary
> **`api_routes.py` = Result retrieval + filtering + search + deletion + academic settings + live notifications + Excel export.**

---

# 3. `modules/class_config.py`

## Purpose
Acts as the **central school configuration module** for classes, arms, subjects, streams, and shared paths.

### Key Features
- Defines `JSS1`–`JSS3` and `SS1`–`SS3`.
- Defines valid class arms.
- Defines JSS, Science, Art, and Commercial subjects.
- Normalizes class and subject formats.
- Determines Senior Secondary stream/track.
- Defines the master student database path.

### Important Functions
```python
normalize_class_level()
normalize_class_arm()
normalize_subject_key()
normalize_subject_display()
get_subjects_for_class()
get_ss_stream()
```

### Summary
> **`class_config.py` = Central configuration for classes + arms + streams + subjects + normalization.**

---

# 4. `modules/excel_manager.py`

## Purpose
Handles the **physical Excel storage and retrieval of examination results**.

### Key Features
- Create result workbooks.
- Save and read submitted results.
- Build JSS term-aware and SS result paths.
- Normalize class, term, and subject values.
- Repair older workbook headers and legacy result formats.

### Important Functions
```python
append_result_to_excel()
read_results()
get_excel_path()
repair_missing_headers()
map_result_row()
```

### Result Paths
```text
JSS: RESULTS/<year>/CLASS/JSS1/FIRST/<subject>/results.xlsx
SS:  RESULTS/<year>/CLASS/SS1/<subject>/results.xlsx
```

### Summary
> **`excel_manager.py` = Creates + saves + reads + repairs examination result Excel files.**

---

# 5. `modules/promotion_manager.py`

## Purpose
Acts as the **Flask/API orchestration layer for student database administration, promotion, repetition, and graduation**.

The actual student-database operations are delegated to the new `modules/student_database/` package. fileciteturn10file0L13-L40

### Key Features
- Return student/promotion summaries.
- List students by class and arm.
- Add and edit students.
- Reserve admission numbers for new students.
- Delete students from the active roster.
- Enforce the strict yearly promotion path.
- Resolve destination class arms.
- Mark students to repeat their current class.
- Graduate SS3 students.
- Export student lists to CSV or Excel.
- Create manual database backups.
- Record Promotion Manager activity logs.

### Promotion Path
```text
JSS1 → JSS2 → JSS3 → SS1 → SS2 → SS3 → GRADUATED
```

Rules:
```text
JSS1/JSS2 arms can normally continue automatically.
JSS3 → SS1 requires an explicit SS1 destination arm.
SS classes attempt to preserve compatible stream/arm suffixes.
SS3 must use Graduation, not normal Promotion.
```

### Main APIs
```text
/api/promotion/summary
/api/promotion/students
/api/promotion/logs
/api/promotion/student/save
/api/promotion/delete
/api/promotion/promote
/api/promotion/repeat
/api/promotion/graduate
/api/promotion/graduates
/api/promotion/backup
/api/promotion/export
```

### Summary
> **`promotion_manager.py` = Promotion/Admin API layer coordinating student records, admission numbers, repetition, graduation, backups, and exports.**

---

# 6. `modules/student_database/student_database.py`

## Purpose
Provides the **core active-student database and synchronization engine** used by Promotion Manager.

`students2026.csv` remains the authoritative active roster, while six class Excel files are synchronized from it.

### Key Features
- Read and validate the master active-student CSV.
- Add, edit, delete, move, and correct student records.
- Keep admission numbers unique.
- Validate class level and exact class arm.
- Synchronize all six class Excel databases.
- Verify CSV/XLSX consistency.
- Create full transaction backups.
- Roll back automatically if an update fails.
- Provide database summaries and health checks.

### Authoritative Database
```text
static/data/database/students2026.csv
```

### Class Excel Databases
```text
JSS1_Students.xlsx
JSS2_Students.xlsx
JSS3_Students.xlsx
SS1_Students.xlsx
SS2_Students.xlsx
SS3_Students.xlsx
```

### Important Functions
```python
read_master_students()
add_student()
edit_student()
delete_students()
move_students()
update_student_class()
sync_all_class_workbooks()
verify_database_sync()
create_database_backup()
restore_database_backup()
commit_master_transaction()
database_health_check()
```

### Transaction Safety
```text
Validate proposed data
        ↓
Backup master CSV + six class XLSX files
        ↓
Write students2026.csv
        ↓
Regenerate class XLSX files
        ↓
Verify synchronization
        ↓
Rollback if verification fails
```

### Backup Location
```text
static/data/database/backups/student_database/
```

### Summary
> **`student_database.py` = Active student master database + class XLSX synchronization + transactional backups/rollback + student CRUD/movement.**

---

# 7. `modules/student_database/admission_manager.py`

## Purpose
Manages **student admission-number generation, reservation, and recycling**.

### Key Features
- Uses the `stdNNN` admission format.
- Detects currently assigned numbers from the active master database.
- Generates the next new number when needed.
- Keeps released graduate numbers in an available-number pool.
- Reserves either a recycled or new admission number.
- Prevents active numbers from being released or reassigned.
- Restores a recycled reservation if student creation fails.

### Important Functions
```python
generate_new_admission_number()
peek_next_admission_number()
reserve_admission_number()
release_admission_number()
restore_reserved_admission_number()
assign_admission_number()
get_admission_number_summary()
```

### Recycled Number Storage
```text
static/data/database/admission_numbers/available_numbers.json
```

### Current Assignment Rule
```text
New JSS1 student
   ↓
Prefer the lowest recycled admission number if available
   ↓
Otherwise generate the next new stdNNN number
```

### Summary
> **`admission_manager.py` = Generates new admission IDs + reserves/recycles released graduate IDs + prevents duplicate active assignment.**

---

# 8. `modules/student_database/graduation_manager.py`

## Purpose
Handles the **formal graduation and archiving of SS3 students**.

### Key Features
- Allows only active SS3 students to graduate.
- Archives graduates by year in Excel.
- Removes graduates from the active master database.
- Uses the transactional student database engine for removal.
- Releases completed admission numbers for future reuse.
- Records graduation history.
- Supports graduate search and summaries.
- Protects the archive if a graduation transaction fails.

### Graduation Flow
```text
Validate selected SS3 students
        ↓
Archive students in graduation workbook
        ↓
Remove them from students2026.csv
        ↓
Synchronize all class databases
        ↓
Release their admission numbers
        ↓
Write graduation log
```

### Graduate Archive
```text
static/data/database/graduates/<year>/graduated_students_<year>.xlsx
```

### Graduation Log
```text
static/data/database/graduates/graduation_log.csv
```

### Important Functions
```python
graduate_students()
read_graduates()
search_graduates()
get_graduate_by_admission()
get_graduation_summary()
```

### Important Rule
> Admission numbers are released for reuse **only after graduation**. Deleting/removing a student from the active roster does not automatically release the number.

### Summary
> **`graduation_manager.py` = SS3 graduation + graduate archive + active-roster removal + admission-number release + graduation history.**

---

# 9. `modules/student_lookup.py`

## Purpose
Handles **student lookup, normalization, and login authentication** using the active master student database.

### Key Features
- Find students by admission number.
- Authenticate active students.
- Normalize names, admission numbers, class level, and class arm.
- Build the standard student object used by EMIS.
- Validate the student database.

### Student Login Rule
```text
Admission Number + First Name OR Last Name
```

### Important Functions
```python
authenticate_student()
find_student_by_admission()
find_active_student_by_admission()
normalize_student_row()
student_name_matches()
validate_student_database()
```

### Data Source
```text
static/data/database/students2026.csv
```

### Summary
> **`student_lookup.py` = Student lookup + normalization + authentication + database validation.**

---

# 10. `modules/student_portal.py`

## Purpose
Controls the **student examination portal and examination lifecycle**.

### Key Features
- Display subjects available to the logged-in student.
- Resolve class, arm, stream, exam year, and JSS term.
- Locate the correct exam JSON.
- Validate subject access.
- Prevent duplicate submissions.
- Submit and save results.
- Send live Admin/Teacher exam notifications.
- Display the latest student result.

### Main Routes
```text
/student_portal
/exam_dashboard
/start_exam
/exam
/submit_exam
/result
/api/student/subjects
```

### Exam JSON Location
```text
JSS: static/portal/<year>/<class_arm>/<term>/<subject>.json
SS:  static/portal/<year>/<class_arm>/<subject>.json
```

### Summary
> **`student_portal.py` = Student subject access + exam loading + exam submission + result display.**

---

# 11. `modules/student_results.py`

## Purpose
Handles the **main local result-saving layer** using SQLite, while also writing each result to Excel.

### Key Features
- Creates/migrates the `student_results` SQLite table.
- Saves submitted examination results.
- Prevents duplicate submissions.
- Requires a term for JSS results.
- Calculates PASS/FAIL using a 50% pass mark.
- Writes results to the appropriate Excel file.
- Retrieves latest, student, class, and filtered results.
- Produces result summaries.

### Important Functions
```python
init_db()
save_result()
result_exists()
get_latest_result()
get_student_results()
get_results_by_class()
get_filtered_results()
get_result_summary()
```

### Save Flow
```text
save_result()
   ├── database.db
   └── excel_manager.append_result_to_excel()
           └── RESULTS/.../results.xlsx
```

### Summary
> **`student_results.py` = Primary local result storage in SQLite + Excel write-through + result queries.**

---

# 12. `modules/supabase_client.py`

## Purpose
Creates a **basic reusable Supabase client connection**.

### Key Feature
Loads:
```text
SUPABASE_URL
SUPABASE_ANON_KEY
```

and exposes:
```python
supabase
```

### Summary
> **`supabase_client.py` = Basic Supabase connection helper using the anon key.**

---

# 13. `modules/supabase_results.py`

## Purpose
Handles **cloud result storage and academic settings in Supabase**.

### Key Features
- Save CBT results to `exam_results`.
- Convert CBT percentage to the `/70` exam score used by Staff Management Software.
- Upsert results to avoid duplicate cloud records.
- Read and update current academic session and term.

### Important Functions
```python
save_exam_result_to_supabase()
calculate_exam_score_70()
get_academic_settings()
update_academic_settings()
```

### Summary
> **`supabase_results.py` = Supabase result synchronization + /70 score conversion + academic session/term settings.**

---

# 14. `modules/user_routes.py`

## Purpose
Handles **student login, session creation, login security, and logout**.

### Key Features
- Login using admission number + first or last name.
- Uses `student_lookup.authenticate_student()`.
- Locks login for 5 minutes after 5 failed attempts.
- Builds the student Flask session.
- Initializes exam session state.
- Sends a live Admin notification after successful login.
- Clears the session on logout.

### Main Routes
```text
/student_login
/logout
```

### Summary
> **`user_routes.py` = Student authentication + login security + session setup + logout.**

---

# 15. `modules/convert_routes.py`

## Purpose
Provides the **Admin/Teacher API endpoints for the examination conversion system**.

### Key Features
- Restricts converter access to Admins and Teachers.
- Uploads and extracts source exam documents.
- Generates CBT JSON.
- Builds clean student-facing JSON.
- Saves converted exams to the library.
- Manages temporary converter drafts.

### Main APIs
```text
/convert/api/extract
/convert/api/generate-json
/convert/api/save-json
/convert/api/drafts
/convert/api/drafts/<draft_id>
/convert/api/drafts/clear
```

### Summary
> **`convert_routes.py` = HTTP/API layer for document extraction + CBT JSON generation + saving + draft management.**

---

# 16. `convert.py`

## Purpose
Contains the **main examination document-to-CBT conversion engine**.

### Key Features
- Extracts text and diagrams.
- Detects class, subject, year, and JSS term.
- Removes document noise and theory/essay sections.
- Parses objective questions and four-option answers.
- Handles passages, diagrams, and grouped questions.
- Validates generated structure.
- Uses Groq for structured JSON repair when required.
- Passes completed JSON to `convert_ext.py` for answer solving/verification.

### Important Functions
```python
save_uploaded_convert_file()
extract_source_file()
detect_class_category()
detect_subject()
detect_exam_metadata()
generate_exam_json_from_text()
```

### AI Responsibility
```text
Groq   → structural JSON repair
OpenAI → answer solving/verification through convert_ext.py
```

### Summary
> **`convert.py` = Source document extraction + cleaning + objective-question parsing + JSON construction/repair.**

---

# 17. `convert_ext.py`

## Purpose
Extends the converter with **OpenAI answer solving, verification, review reporting, clean JSON saving, and draft management**.

### Key Features
- OpenAI solver pass.
- OpenAI verifier pass.
- Review flags for disagreement, low confidence, suspicious wording, or typos.
- Applies final verified answers.
- Tracks token usage and estimated cost.
- Builds clean student-facing JSON.
- Enforces JSS term-aware saving.
- Saves review reports and drafts.

### Main AI Flow
```text
Questions
   ↓
OpenAI Solver
   ↓
OpenAI Verifier
   ↓
Review Report
   ↓
Final correctOption
```

### Important Functions
```python
solve_answers_with_openai()
ask_openai_solver()
ask_openai_verifier()
build_openai_answer_report()
apply_openai_answers()
build_clean_student_json()
save_exam_json()
save_convert_draft()
```

### Summary
> **`convert_ext.py` = OpenAI solver/verifier + review system + clean CBT JSON saving + converter drafts.**

---

# 18. `email_server.py`

## Purpose
Provides **email result notifications and PDF result summaries**.

### Key Features
- Compose Admin and candidate result emails.
- Generate a one-page PDF result summary.
- Attach PDF and optional Admin CSV log.
- Send through SMTP or configured HTTPS relay.

### Important Functions
```python
send_admin_email()
send_candidate_email()
send_result_emails()
```

### Summary
> **`email_server.py` = Optional email result notification + PDF result-summary helper.**

---

# 19. `engine.py`

## Purpose
Contains **general backend utility logic**, mainly document uploads and Teacher account management.

### Teacher Functions
```python
init_teacher_table()
generate_teacher_ids()
get_all_teachers()
validate_teacher_login()
delete_teacher_from_db()
```

Teacher accounts are stored in:
```text
database.db → teachers table
```

### Summary
> **`engine.py` = General upload utilities + Teacher account creation/authentication/storage.**

---

# 20. `push.py`

## Purpose
Handles the **deployment of saved examination JSON files to the live student portal**.

### Key Features
- Push exams to a broad class or exact class arm.
- Maintain active year per target.
- Maintain JSS active term per target.
- Copy JSON files into `static/portal/`.
- Maintain `pushed_subjects.json`.
- Clear pushed portal content.
- Provide current pushed subject lists.

### Important State Files
```text
static/portal/latest_year.txt
static/portal/class_active_years.json
static/portal/class_active_terms.json
```

### Summary
> **`push.py` = Publishes saved exam JSON to selected classes/arms and manages active exam year/term state.**

---

# 21. `uploads.py`

## Purpose
Manages the **Admin examination JSON library** stored under `static/subjects/`.

### Key Features
- Upload JSON/DOCX files.
- Detect class and JSS term.
- Enforce JSS term folders.
- Keep SS storage flat.
- List, preview, and delete stored JSON files.
- Support legacy flat JSS files where required.

### Storage Structure
```text
JSS: static/subjects/<year>/subjects-json/JSS1/FIRST/
SS:  static/subjects/<year>/subjects-json/SS1/
```

### Summary
> **`uploads.py` = Exam JSON library upload + listing + preview + deletion + JSS term-aware organization.**

---

# 22. `app.py`

## Purpose
Acts as the **main Flask application entry point**.

### Key Features
- Loads environment variables.
- Creates the Flask application.
- Registers EMIS blueprints.
- Redirects `/` to Admin login.
- Initializes credential/result databases.
- Runs the local server on port `5005`.

### Summary
> **`app.py` = EMIS application bootstrap + blueprint registration + startup initialization.**

---

# EMIS Backend Workflow

## 1. Application Startup
```text
app.py
   ├── Registers backend Blueprints
   ├── Initializes credential database
   └── Initializes student_results table
```

## 2. Active Student Database
```text
students2026.csv
      ↓
student_database/student_database.py
      ├── Validate active students
      ├── Add / edit / remove / move students
      ├── Backup transactions
      ├── Synchronize six class XLSX files
      └── Verify CSV/XLSX consistency
```

## 3. Admission Number Management
```text
admission_manager.py
      ├── Read active admission numbers
      ├── Read recycled-number pool
      ├── Reserve recycled or new stdNNN
      └── Prevent duplicate active assignment
```

## 4. Promotion & Graduation
```text
promotion_manager.py
      ├── Promotion API/orchestration
      ├── Repeat action
      ├── Student CRUD
      └── Export / backup / logs
      │
      ├───────────────┬─────────────────────┐
      ▼               ▼                     ▼
student_database.py  admission_manager.py  graduation_manager.py
      │               │                     │
      │               │                     ├── Archive SS3 graduate
      │               │                     ├── Remove from active roster
      │               │                     └── Release admission number
      │               │
      └── Transactional database movement
```

## 5. Student Login
```text
students2026.csv
       ↓
student_lookup.py
       ↓
user_routes.py
       ├── Login security
       ├── Creates Flask session
       └── Redirects to Student Portal
```

## 6. Exam Creation
```text
Source DOCX/TXT
      ↓
convert_routes.py
      ↓
convert.py
      ↓
convert_ext.py
      ↓
static/subjects/<year>/subjects-json/
```

## 7. Exam Deployment
```text
static/subjects/
      ↓
uploads.py
      ↓
push.py
      ↓
static/portal/
```

## 8. Student Examination
```text
student_portal.py
      ├── Resolve class / arm / stream
      ├── Resolve active year / JSS term
      ├── Filter allowed subjects
      ├── Locate exam JSON
      └── Run examination
```

## 9. Result Submission
```text
student_portal.py
        ├──────────────────────────────┐
        ▼                              ▼
student_results.py              supabase_results.py
        │                              │
        ├── database.db                └── Supabase exam_results
        ↓
excel_manager.py
        ↓
RESULTS/<year>/CLASS/.../results.xlsx
```

## 10. Main Storage Map
```text
Active Student Master Database
└── static/data/database/students2026.csv

Synchronized Class Databases
├── static/data/database/JSS1_Students.xlsx
├── static/data/database/JSS2_Students.xlsx
├── static/data/database/JSS3_Students.xlsx
├── static/data/database/SS1_Students.xlsx
├── static/data/database/SS2_Students.xlsx
└── static/data/database/SS3_Students.xlsx

Student Database Transaction Backups
└── static/data/database/backups/student_database/

Available/Recycled Admission Numbers
└── static/data/database/admission_numbers/available_numbers.json

Graduate Archives
└── static/data/database/graduates/<year>/graduated_students_<year>.xlsx

Graduation Log
└── static/data/database/graduates/graduation_log.csv

Promotion Activity Log
└── static/data/database/promotion_logs.csv

Teacher / Local Result Database
└── database.db

Excel Examination Results
└── RESULTS/<year>/CLASS/...

Saved Exam Library
└── static/subjects/<year>/subjects-json/...

Live Student Exams
└── static/portal/<year>/...

Converter Drafts
└── static/uploads/convert-drafts/
```

---

# Quick File Guide

| Need to Change | Main File |
|---|---|
| Admin/Teacher login or Admin page access | `modules/admin_routes.py` |
| Student login | `modules/user_routes.py` |
| Student lookup/authentication rules | `modules/student_lookup.py` |
| Student exam portal | `modules/student_portal.py` |
| Local SQLite result saving | `modules/student_results.py` |
| Excel examination result files | `modules/excel_manager.py` |
| Result APIs/Admin result filtering | `modules/api_routes.py` |
| Classes, arms, subjects, streams | `modules/class_config.py` |
| Promotion/repeat/graduation API routes | `modules/promotion_manager.py` |
| Active student database and class XLSX sync | `modules/student_database/student_database.py` |
| Admission number generation/recycling | `modules/student_database/admission_manager.py` |
| SS3 graduation/archive | `modules/student_database/graduation_manager.py` |
| Supabase CBT results/settings | `modules/supabase_results.py` |
| Converter API routes | `modules/convert_routes.py` |
| Document extraction/question parsing | `convert.py` |
| AI answer solving/verifying | `convert_ext.py` |
| Exam library uploads | `uploads.py` |
| Push exams to students | `push.py` |
| Teacher account database | `engine.py` |
| Email/PDF result notifications | `email_server.py` |
| Flask startup/blueprints | `app.py` |
