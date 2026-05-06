# ============================================================
# convert_single_test.py — Test a Single DOCX Conversion
# Target: literature_ss2.docx (in same directory)
# Outputs JSON in same directory
# ============================================================

import os
import json
from convert import convert_exam, detect_subject, detect_class_category, detect_version, class_from_version

# ------------------------------------------------------------
# MAIN TEST FUNCTION
# ------------------------------------------------------------
def convert_single():
    filename = "literature_ss2.docx"   # fixed target file

    # Path = current folder
    base_path = os.path.dirname(os.path.abspath(__file__))
    input_path = os.path.join(base_path, filename)

    if not os.path.exists(input_path):
        print(f"❌ File not found: {input_path}")
        return

    print("\n=== 🎯 SINGLE FILE TEST — LITERATURE SS2 ===")
    print(f"📄 Input DOCX: {input_path}\n")

    # Run conversion pipeline (full processing)
    subject, class_cat, data = convert_exam(input_path)

    print(f"📚 Subject: {subject}")
    print(f"🏷 Class:   {class_cat}")

    # Output JSON in same place
    safe_subject = subject.lower().replace(" ", "_")
    output_name = f"{safe_subject}_{class_cat.lower()}_TEST.json"
    output_path = os.path.join(base_path, output_name)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print("\n✅ DONE! JSON saved at:")
    print(f"   → {output_path}")
    print("\n📂 Open it and verify:")
    print("   • Passage preserved")
    print("   • Questions grouped correctly")
    print("   • Sub/Sup formatting if present")
    print("   • No missing items\n")


# ------------------------------------------------------------
# CLI ENTRY
# ------------------------------------------------------------
if __name__ == "__main__":
    convert_single()
