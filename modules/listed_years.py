# # modules/listed_years.py
# # ==========================================================
# # EMIS — Available WAEC Years Scanner
# # ==========================================================

# import os

# BASE_SUBJECTS_PATH = os.path.join("static", "subjects")


# def get_available_waec_years():
#     """
#     Scans static/subjects/*/subjects-json/** for .json files.
#     Returns sorted list of years that actually contain JSON.
#     """

#     available_years = []

#     if not os.path.exists(BASE_SUBJECTS_PATH):
#         return available_years

#     for year in os.listdir(BASE_SUBJECTS_PATH):
#         year_path = os.path.join(BASE_SUBJECTS_PATH, year)

#         if not year.isdigit() or not os.path.isdir(year_path):
#             continue

#         subjects_json_path = os.path.join(year_path, "subjects-json")
#         if not os.path.isdir(subjects_json_path):
#             continue

#         found_json = False

#         for root, _, files in os.walk(subjects_json_path):
#             for file in files:
#                 if file.endswith(".json"):
#                     found_json = True
#                     break
#             if found_json:
#                 break

#         if found_json:
#             available_years.append(int(year))

#     return sorted(available_years)
