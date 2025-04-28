import json
import re
import shutil
import struct
import winreg
from pathlib import Path
from tkinter import messagebox
from typing import Any


def align_up(value: int, alignment: int) -> int:
    """Aligns an integer 'value' up to the nearest multiple of 'alignment'."""
    return (value + alignment - 1) & ~(alignment - 1)


def patch_asar(
    asar_file: Path,
    target_file: str = "dist/main/index.js",
    pattern: str = r"devTools\s*:\s*[^,]*,",
    replacement: str = "devTools:true,",
) -> bool:
    """Patches the asar file by replacing a regex pattern in the specified target file."""

    backup_file = asar_file.with_suffix(asar_file.suffix + ".bak")
    if not backup_file.exists():
        shutil.copyfile(asar_file, backup_file)

    # Read ASAR header
    with asar_file.open("rb") as f:
        magic, header_size, header_object_size, header_string_size = struct.unpack(
            "<4I", f.read(16)
        )
        header_json_data = f.read(header_string_size).decode("utf-8")
        header = json.loads(header_json_data)

    base_offset = align_up(16 + header_string_size, 4)
    file_info = find_file(header["files"], target_file.split("/"))
    if not file_info or "offset" not in file_info:
        return False

    # Read the content of the target file
    with asar_file.open("rb") as f:
        f.seek(base_offset + int(file_info["offset"]))
        original_content = f.read(int(file_info["size"])).decode("utf-8")

    # Replace with new content if there's a difference
    new_content = re.sub(pattern, replacement, original_content)
    if new_content == original_content:
        return False

    # Gather all files data from the asar
    files_data: list[dict[str, Any]] = []
    collect_asar_files(asar_file, header["files"], "", files_data, base_offset)

    # Update the target file's content
    for fd in files_data:
        if fd["path"] == target_file:
            fd["content"] = new_content.encode("utf-8")
            fd["size"] = len(fd["content"])

    # Recompute offsets
    offset = 0
    for fd in files_data:
        fd["offset"] = offset
        offset += fd["size"]

    # Update header
    update_asar_header(header["files"], files_data)

    # Write the updated asar file
    new_header_json = json.dumps(header, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    new_header_size = len(new_header_json)

    temp_file = asar_file.with_suffix(".temp")
    with temp_file.open("wb") as f:
        # Write header
        f.write(
            struct.pack(
                "<4I",
                4,
                align_up(new_header_size, 4) + 8,
                align_up(new_header_size, 4) + 4,
                new_header_size,
            )
        )
        f.write(new_header_json)

        # Write padding
        padding = align_up(16 + new_header_size, 4) - (16 + new_header_size)
        if padding > 0:
            f.write(b"\0" * padding)

        # Write file contents
        for fd in files_data:
            f.write(fd["content"])

    shutil.move(temp_file, asar_file)
    return True


def find_file(files: dict[str, Any], path_parts: list[str]) -> dict[str, Any] | None:
    """Finds a file entry in the ASAR structure by a list of path components."""
    if not path_parts:
        return None
    name = path_parts[0]
    if name not in files:
        return None

    entry = files[name]
    if len(path_parts) == 1:
        return entry
    if "files" not in entry:
        return None
    return find_file(entry["files"], path_parts[1:])


def collect_asar_files(
    asar_file: Path,
    files: dict[str, Any],
    prefix: str,
    result: list[dict[str, Any]],
    base_offset: int,
) -> None:
    """Recursively collects file entries from the ASAR structure."""
    for name, entry in files.items():
        path_str = f"{prefix}/{name}" if prefix else name
        if "files" in entry:
            collect_asar_files(asar_file, entry["files"], path_str, result, base_offset)
        elif "offset" in entry:
            with asar_file.open("rb") as f:
                f.seek(base_offset + int(entry["offset"]))
                content = f.read(int(entry["size"]))

            result.append(
                {
                    "path": path_str,
                    "offset": int(entry["offset"]),
                    "size": int(entry["size"]),
                    "content": content,
                }
            )


def update_asar_header(
    files: dict[str, Any], files_data: list[dict[str, Any]], current_path: str = ""
) -> None:
    """Updates the header with new offsets and sizes based on the files_data list."""
    for name, entry in files.items():
        path_str = f"{current_path}/{name}" if current_path else name
        if "files" in entry:
            update_asar_header(entry["files"], files_data, path_str)
        elif "offset" in entry:
            for fd in files_data:
                if fd["path"] == path_str:
                    entry["offset"] = str(fd["offset"])
                    entry["size"] = fd["size"]
                    break


def get_ridi_path() -> str | None:
    """Gets the path to 'ridi.exe' from the Windows registry."""
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CLASSES_ROOT, "ridi\\shell\\open\\command", 0, winreg.KEY_READ
        )
        value, _ = winreg.QueryValueEx(key, "")
        winreg.CloseKey(key)
        match = re.match(r'^(?:"([^"]+)"|([^\s"]+))', value.strip())
        return match.group(1) or match.group(2) if match else None
    except Exception:
        return None


if __name__ == "__main__":
    ridi = get_ridi_path()
    if not ridi:
        messagebox.showerror(
            "Error", "Cannot find ridi.exe. Registry value may be broken."
        )
        raise SystemExit(1)

    asar = Path(ridi).parent / "resources" / "app.asar"
    if not asar.exists():
        messagebox.showerror("Error", "Cannot find app.asar. Please reinstall ridi.")
        raise SystemExit(1)

    try:
        if patch_asar(asar):
            messagebox.showinfo("Success", "Patch applied successfully!")
            raise SystemExit(0)
        messagebox.showwarning("Warning", "Patch already applied or failed.")
        raise SystemExit(1)
    except PermissionError:
        messagebox.showerror(
            "Error", "Permission denied. You do not have sufficient privileges."
        )
        raise SystemExit(1)
