"""Normalize poster filenames and produce a provisional labels.json mapping.

Usage examples (windows cmd.exe):
  python scripts\normalize_filenames.py --source "../poster_db" --dry-run
  python scripts\normalize_filenames.py --source "../poster_db" --apply

What it does:
  - Scans the `poster_db` directory for image files
  - Produces a suggested normalized title for each file
  - Writes `poster_db/labels.json` containing mappings
  - If `--apply` is used, safely renames files to suggested names

This is a beginner-friendly tool to create provisional labels before
we add AniList matching and manual review.
"""
from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path
from typing import List, Dict

from tqdm import tqdm


IMAGE_EXT = {".jpg", ".jpeg", ".jfif", ".png", ".webp", ".bmp", ".gif"}


def normalize_title(stem: str) -> str:
    """Normalize filename stem to a readable title.

    Rules (conservative, reversible):
    - Unicode normalization (NFKC)
    - Replace underscores and punctuation with spaces
    - Collapse multiple spaces
    - Title-case the result (makes UI nicer)
    """
    s = unicodedata.normalize("NFKC", stem)
    s = s.replace("_", " ")
    # replace non-alphanumeric (allow some latin chars) with space
    s = re.sub(r"[^0-9A-Za-z\u00C0-\u017F]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s.title()


def scan_images(folder: Path) -> List[Path]:
    if not folder.exists():
        raise FileNotFoundError(f"Source folder not found: {folder}")
    files = [p for p in folder.iterdir() if p.suffix.lower() in IMAGE_EXT and p.is_file()]
    return sorted(files)


def make_unique_name(dest_dir: Path, base_name: str, ext: str) -> str:
    """Ensure the suggested filename does not collide with existing files.

    If collision occurs, append ' (1)', ' (2)', ... before the extension.
    """
    candidate = f"{base_name}{ext}"
    i = 1
    while (dest_dir / candidate).exists():
        candidate = f"{base_name} ({i}){ext}"
        i += 1
    return candidate


def build_mappings(files: List[Path], dest_dir: Path) -> List[Dict]:
    mappings = []
    for idx, p in enumerate(files, start=1):
        stem = p.stem
        ext = p.suffix.lower()
        suggested_title = normalize_title(stem)
        suggested_filename = make_unique_name(dest_dir, suggested_title, ext)
        mappings.append(
            {
                "id": idx,
                "original_path": str(p.as_posix()),
                "original_name": p.name,
                "suggested_title": suggested_title,
                "suggested_filename": suggested_filename,
                "ext": ext,
            }
        )
    return mappings


def apply_renames(mappings: List[Dict], dest_dir: Path) -> None:
    for m in mappings:
        src = Path(m["original_path"]).resolve()
        dst = dest_dir / m["suggested_filename"]
        if src.samefile(dst):
            continue
        # If destination exists (shouldn't because we made unique), skip
        if dst.exists():
            print(f"Skipping rename, destination exists: {dst}")
            continue
        src.rename(dst)


def save_labels_json(mappings: List[Dict], out_path: Path) -> None:
    data = {m["id"]: {"filename": m["suggested_filename"], "title": m["suggested_title"]} for m in mappings}
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Normalize poster filenames and create provisional labels.json")
    p.add_argument("--source", required=True, help="Path to poster folder (e.g. ../poster_db)")
    p.add_argument("--apply", action="store_true", help="Apply suggested renames (unsafe). Default is dry-run")
    p.add_argument("--limit", type=int, default=0, help="Limit number of files processed (0 => all)")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    src = Path(args.source)
    files = scan_images(src)
    if args.limit and args.limit > 0:
        files = files[: args.limit]

    mappings = build_mappings(files, src)

    print(f"Found {len(mappings)} image(s) in {src}")
    for m in mappings[:20]:
        print(f"{m['original_name']} -> {m['suggested_filename']}")

    out_json = src / "labels.json"
    if args.apply:
        print("Applying renames (this will change files on disk)...")
        apply_renames(mappings, src)
        # After renaming, suggested filenames are final, save labels.json
        save_labels_json(mappings, out_json)
        print(f"Renames applied and labels saved to {out_json}")
    else:
        # dry-run: just write provisional labels.json (without renames)
        save_labels_json(mappings, out_json)
        print(f"Dry run complete. Provisional labels written to {out_json}. Use --apply to rename files.")


if __name__ == "__main__":
    main()
