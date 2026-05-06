# ============================================================
# convert_test.py — MASS JSON REGENERATOR (2025 GROUPED EDITION)
# Works with the NEW convert.py (groups + passages + fixed counts)
# ============================================================

import os
import time
from convert import convert_exam, save_output

BASE_DOCX = "static/subjects/subjects-docx"
BASE_JSON = "static/subjects/subjects-json"

# ------------------------------------------------------------
# ENSURE JSON FOLDERS EXIST
# ------------------------------------------------------------
for cls in ["SS1", "SS2", "SS3", "GENERAL"]:
    os.makedirs(os.path.join(BASE_JSON, cls), exist_ok=True)


# ------------------------------------------------------------
# CLEAN OLD JSON FILES
# ------------------------------------------------------------
def clear_old_jsons():
    print("\n=== 🧹 Clearing OLD JSONs (SS1 / SS2 / SS3 / GENERAL) ===\n")

    for cls in ["SS1", "SS2", "SS3", "GENERAL"]:
        folder = os.path.join(BASE_JSON, cls)
        if not os.path.exists(folder):
            os.makedirs(folder)

        for file in os.listdir(folder):
            if file.endswith(".json"):
                path = os.path.join(folder, file)
                print(f"🗑 Removing → {path}")
                try:
                    os.remove(path)
                except PermissionError:
                    print(f"⚠ Skipped locked file → {path}")

    print("\n✅ JSON folders cleaned.\n")


# ------------------------------------------------------------
# SAFE CONVERSION with RETRY LOGIC
# ------------------------------------------------------------
def safe_convert(full_path, filename, max_retries=2):
    retries = 0

    while retries <= max_retries:
        try:
            print(f"🔍 Running convert_exam on: {filename}")
            return convert_exam(full_path)

        except Exception as e:
            print(f"\n⚠ ERROR converting {filename}")
            print(f"   → Reason: {e}")

            retries += 1
            if retries <= max_retries:
                print(f"🔁 Retrying ({retries}/{max_retries}) …\n")
                time.sleep(2)
            else:
                print("⛔ FAILED — skipping this file.\n")
                return None


# ------------------------------------------------------------
# PROCESS ALL DOCX FILES
# ------------------------------------------------------------
def convert_all():
    print("\n=== 🚀 STARTING MASS CONVERSION OF ALL SUBJECTS ===\n")

    if not os.path.exists(BASE_DOCX):
        print(f"❌ subjects-docx folder NOT FOUND → {BASE_DOCX}")
        return

    docx_files = sorted([f for f in os.listdir(BASE_DOCX) if f.lower().endswith(".docx")])

    if not docx_files:
        print("❌ No .docx files found in subjects-docx folder.")
        return

    for filename in docx_files:
        print(f"\n📘 Converting → {filename}")
        full_path = os.path.join(BASE_DOCX, filename)

        result = safe_convert(full_path, filename)

        if not result:
            continue  # skip failed extraction

        subject, class_cat, data = result

        # Save JSON
        save_output(subject, class_cat, data)

        print(f"✅ Finished → {filename}\n")

    print("\n🎉 COMPLETED — All subjects processed successfully!\n")


# ------------------------------------------------------------
# MAIN ENTRY
# ------------------------------------------------------------
if __name__ == "__main__":
    clear_old_jsons()
    convert_all()
