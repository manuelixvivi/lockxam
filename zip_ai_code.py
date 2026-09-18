import os
import zipfile


def zip_ai_backend(output_path, root_dir):
    paths_to_include = [
        "app/services/ai",
        "app/schemas/ai",
        "app/models/ai",
        "app/repositories/ai",
        "app/api/ai.py",
        "app/api/superadmin_ai.py",
    ]

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for p in paths_to_include:
            full_path = os.path.join(root_dir, p)
            if os.path.isdir(full_path):
                for root, dirs, files in os.walk(full_path):
                    # Skip __pycache__
                    if "__pycache__" in root:
                        continue
                    for file in files:
                        if file.endswith(".pyc"):
                            continue
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, root_dir)
                        zipf.write(file_path, arcname)
            elif os.path.isfile(full_path):
                arcname = os.path.relpath(full_path, root_dir)
                zipf.write(full_path, arcname)


if __name__ == "__main__":
    project_root = "C:/Users/irul2/Downloads/Equigrade_x_Lockxam"
    desktop_zip = "C:/Users/irul2/Desktop/Backend_AI_Equigrade_Source_Code.zip"
    zip_ai_backend(desktop_zip, project_root)
    print(f"Successfully created {desktop_zip}")
