"""Normalize poster filenames per alignment spec and produce data/posters.json.



What it does:
  - Scans source directory for image files
  - Normalizes to snake_case per alignment spec
  - Detects season suffixes (S1, Season 2, etc.) and normalizes to _s1, _s2
  - Moves files to destination `posters/` directory
  - Writes canonical metadata to `data/posters.json`
  - Handles edge cases: collisions, unicode, long names, invalid chars
  - If `--apply` is used, performs file moves and writes JSON

This tool is used for initial ingestion AND future user uploads.
"""
from __future__ import annotations

import argparse
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Optional, Tuple


IMAGE_EXT = {".jpg", ".jpeg", ".jfif", ".png", ".webp", ".bmp", ".gif"}
MAX_FILENAME_LENGTH = 200  # reasonable limit to avoid filesystem issues


def extract_season(stem: str) -> Tuple[str, Optional[int]]:
    """Extract season number from filename and return (cleaned_stem, season_number).
    
    Patterns matched (case-insensitive):
    - 'S1', 'S01', 'S2', etc.
    - 'Season 1', 'Season 2', etc.
    - 'season1', 'season 2', etc.
    - ' - S1', ' S1', etc.
    
    Returns:
        Tuple of (stem without season, season_number or None)
    
    Examples:
        'attack on titan s3' -> ('attack on titan', 3)
        'Steins Gate Season 1' -> ('Steins Gate', 1)
        'Naruto' -> ('Naruto', None)
    """
    # Pattern: optional separator + 's' or 'season' + digits
    pattern = r'[\s_-]*((?:season|s)\s*(\d+))\s*$'
    match = re.search(pattern, stem, re.IGNORECASE)
    
    if match:
        season_num = int(match.group(2))
        # Remove the matched season part from stem
        clean_stem = stem[:match.start()].strip()
        return clean_stem, season_num
    
    return stem, None


def to_snake_case(text: str) -> str:
    """Convert text to snake_case per alignment spec.
    
    Rules:
    - Unicode normalization (NFKC)
    - Convert to lowercase
    - Replace spaces, hyphens, and underscores with single underscore
    - Remove non-alphanumeric except underscore
    - Collapse multiple underscores
    - Strip leading/trailing underscores
    - Handle edge cases: empty strings, very long names
    
    Examples:
        'Steins;Gate' -> 'steins_gate'
        'Attack on Titan' -> 'attack_on_titan'
        'Re:Zero' -> 're_zero'
    """
    if not text or not text.strip():
        return "unknown"
    
    # Unicode normalization
    s = unicodedata.normalize("NFKC", text)
    
    # Convert to lowercase
    s = s.lower()
    
    # Replace common separators with underscore
    s = s.replace(" ", "_").replace("-", "_")
    
    # Remove non-alphanumeric except underscore (keep basic latin + digits)
    s = re.sub(r"[^a-z0-9_]+", "_", s)
    
    # Collapse multiple underscores
    s = re.sub(r"_+", "_", s)
    
    # Strip leading/trailing underscores
    s = s.strip("_")
    
    # Handle edge cases
    if not s:
        return "unknown"
    
    # Truncate if too long (reserve space for _sNN and extension)
    if len(s) > MAX_FILENAME_LENGTH - 10:
        s = s[:MAX_FILENAME_LENGTH - 10]
    
    return s


def normalize_filename(stem: str) -> Tuple[str, str, Optional[int]]:
    """Normalize filename stem to slug + title + season.
    
    Returns:
        Tuple of (slug, title, season_number)
        - slug: snake_case normalized name for filesystem
        - title: human-readable title (Title Case)
        - season: season number or None
    
    Examples:
        'Steins Gate S1' -> ('steins_gate', 'Steins Gate', 1)
        'attack-on-titan season 2' -> ('attack_on_titan', 'Attack On Titan', 2)
    """
    # Extract season first
    clean_stem, season = extract_season(stem)
    
    # Generate slug (snake_case)
    slug = to_snake_case(clean_stem)
    
    # Generate human-readable title (Title Case, normalized)
    title_temp = unicodedata.normalize("NFKC", clean_stem)
    title_temp = re.sub(r"[^0-9A-Za-z\s\u00C0-\u017F]+", " ", title_temp)
    title_temp = re.sub(r"\s+", " ", title_temp).strip()
    title = title_temp.title() if title_temp else "Unknown"
    
    return slug, title, season


def scan_images(folder: Path) -> List[Path]:
    if not folder.exists():
        raise FileNotFoundError(f"Source folder not found: {folder}")
    files = [p for p in folder.iterdir() if p.suffix.lower() in IMAGE_EXT and p.is_file()]
    return sorted(files)


def make_unique_filename(dest_dir: Path, slug: str, season: Optional[int], ext: str) -> str:
    """Build unique filename from slug + season + extension.
    
    Format: <slug>_s<N>.<ext> if season, else <slug>.<ext>
    If collision, append _1, _2, etc. before extension.
    
    Args:
        dest_dir: destination directory
        slug: normalized snake_case slug
        season: season number or None
        ext: file extension (e.g., '.png')
    
    Returns:
        Unique filename string
    """
    # Build base filename
    if season is not None:
        base = f"{slug}_s{season}"
    else:
        base = slug
    
    candidate = f"{base}{ext}"
    counter = 1
    
    # Handle collisions by appending _1, _2, etc.
    while (dest_dir / candidate).exists():
        if season is not None:
            candidate = f"{slug}_s{season}_{counter}{ext}"
        else:
            candidate = f"{slug}_{counter}{ext}"
        counter += 1
        
        # Safety: prevent infinite loop
        if counter > 1000:
            raise RuntimeError(f"Too many collisions for slug: {slug}")
    
    return candidate


def build_mappings(files: List[Path], dest_dir: Path, source_type: str = "user") -> List[Dict]:
    """Build mappings from source files to destination normalized files.
    
    Args:
        files: list of source image paths
        dest_dir: destination directory (posters/)
        source_type: 'user' or 'auto' for metadata
    
    Returns:
        List of mapping dicts with keys:
        - original_path, original_name
        - slug, title, season
        - dest_filename, dest_path
        - added_at, source
    """
    mappings = []
    slug_tracker = {}  # track slug collisions for warning
    
    for p in files:
        stem = p.stem
        ext = p.suffix.lower()
        
        # Normalize filename
        slug, title, season = normalize_filename(stem)
        
        # Build unique destination filename
        dest_filename = make_unique_filename(dest_dir, slug, season, ext)
        
        # Track slug usage for collision detection
        slug_key = f"{slug}_s{season}" if season else slug
        if slug_key in slug_tracker:
            print(f"Warning: Duplicate slug '{slug_key}' for '{p.name}' and '{slug_tracker[slug_key]}'")
        slug_tracker[slug_key] = p.name
        
        mappings.append(
            {
                "original_path": str(p.resolve().as_posix()),
                "original_name": p.name,
                "slug": slug,
                "title": title,
                "season": season,
                "dest_filename": dest_filename,
                "dest_path": str((dest_dir / dest_filename).as_posix()),
                "added_at": datetime.now(timezone.utc).isoformat(),
                "source": source_type,
                "ext": ext,
            }
        )
    
    return mappings


def apply_moves(mappings: List[Dict], dest_dir: Path) -> None:
    """Move files from source to destination directory.
    
    Args:
        mappings: list of mapping dicts from build_mappings
        dest_dir: destination directory (must exist)
    """
    if not dest_dir.exists():
        dest_dir.mkdir(parents=True, exist_ok=True)
        print(f"Created destination directory: {dest_dir}")
    
    for m in mappings:
        src = Path(m["original_path"])
        dst = dest_dir / m["dest_filename"]
        
        # Skip if source and dest are the same
        if src.resolve() == dst.resolve():
            print(f"Skipping (already at destination): {src.name}")
            continue
        
        # Safety check: destination shouldn't exist (we made it unique)
        if dst.exists():
            print(f"Error: Destination exists (skipping): {dst}")
            continue
        
        # Safety check: source must exist
        if not src.exists():
            print(f"Error: Source file not found (skipping): {src}")
            continue
        
        # Move file
        try:
            src.rename(dst)
            print(f"Moved: {src.name} -> {m['dest_filename']}")
        except Exception as e:
            print(f"Error moving {src.name}: {e}")


def save_posters_json(mappings: List[Dict], out_path: Path) -> None:
    """Save metadata to data/posters.json per alignment spec.
    
    Schema per retrieval_specs.md:
    {
      "<slug>": {
        "title": "<canonical anime title>",
        "slug": "<normalized_slug>",
        "path": "posters/<filename>",
        "season": <number or null>,
        "embedding": null,  # will be populated by embedder
        "added_at": "<ISO timestamp>",
        "source": "user" | "auto",
        "notes": null
      }
    }
    """
    # Load existing data if file exists (merge mode)
    existing_data = {}
    if out_path.exists():
        try:
            with out_path.open("r", encoding="utf-8") as f:
                existing_data = json.load(f)
            print(f"Loaded {len(existing_data)} existing entries from {out_path}")
        except Exception as e:
            print(f"Warning: Could not load existing {out_path}: {e}")
    
    # Build new entries
    for m in mappings:
        # Use slug_sN as key if season present, else just slug
        if m["season"] is not None:
            key = f"{m['slug']}_s{m['season']}"
        else:
            key = m["slug"]
        
        # Skip if already exists (don't overwrite)
        if key in existing_data:
            print(f"Skipping existing entry: {key}")
            continue
        
        existing_data[key] = {
            "title": m["title"],
            "slug": m["slug"],
            "path": f"posters/{m['dest_filename']}",
            "season": m["season"],
            "embedding": None,  # populated later by embedder
            "added_at": m["added_at"],
            "source": m["source"],
            "notes": None,
        }
    
    # Ensure parent directory exists
    out_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Write atomically (write to temp, then rename)
    temp_path = out_path.with_suffix(".json.tmp")
    try:
        with temp_path.open("w", encoding="utf-8") as f:
            json.dump(existing_data, f, ensure_ascii=False, indent=2)
        temp_path.replace(out_path)
        print(f"Saved metadata to {out_path} ({len(existing_data)} total entries)")
    except Exception as e:
        print(f"Error saving {out_path}: {e}")
        if temp_path.exists():
            temp_path.unlink()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Normalize poster filenames per alignment spec and write data/posters.json",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry-run (preview only, writes provisional JSON)
  python backend/scripts/normalize_filenames.py --source poster_db --dest posters --output data/posters.json
  
  # Apply changes (move files and write JSON)
  python backend/scripts/normalize_filenames.py --source poster_db --dest posters --output data/posters.json --apply
  
  # Process only first 10 files
  python backend/scripts/normalize_filenames.py --source poster_db --dest posters --output data/posters.json --limit 10
        """
    )
    p.add_argument("--source", required=True, help="Source directory containing original images (e.g., poster_db)")
    p.add_argument("--dest", required=True, help="Destination directory for normalized images (e.g., posters)")
    p.add_argument("--output", required=True, help="Output JSON metadata file (e.g., data/posters.json)")
    p.add_argument("--apply", action="store_true", help="Apply file moves and write JSON (default: dry-run only)")
    p.add_argument("--limit", type=int, default=0, help="Limit number of files to process (0 = all)")
    p.add_argument("--source-type", choices=["user", "auto"], default="user", help="Source type for metadata")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    
    src_dir = Path(args.source)
    dest_dir = Path(args.dest)
    out_json = Path(args.output)
    
    # Scan source directory
    print(f"Scanning {src_dir}...")
    files = scan_images(src_dir)
    
    if not files:
        print(f"No image files found in {src_dir}")
        return
    
    if args.limit and args.limit > 0:
        files = files[: args.limit]
        print(f"Limited to first {args.limit} files")
    
    # Build mappings
    print(f"\nProcessing {len(files)} file(s)...")
    mappings = build_mappings(files, dest_dir, source_type=args.source_type)
    
    # Display preview (first 30 entries)
    print(f"\n{'='*80}")
    print("PREVIEW (showing first 30):")
    print(f"{'='*80}")
    print(f"{'Original':<40} | {'Normalized':<35}")
    print(f"{'-'*40}-+-{'-'*35}")
    
    for m in mappings[:30]:
        season_suffix = f" (S{m['season']})" if m['season'] else ""
        print(f"{m['original_name']:<40} | {m['dest_filename']:<35}")
    
    if len(mappings) > 30:
        print(f"... and {len(mappings) - 30} more")
    
    print(f"\n{'='*80}")
    print(f"Total files: {len(mappings)}")
    print(f"Destination: {dest_dir}")
    print(f"Metadata: {out_json}")
    print(f"{'='*80}\n")
    
    # Apply changes or dry-run
    if args.apply:
        print("⚠️  APPLYING CHANGES (files will be moved)...\n")
        
        # Move files
        apply_moves(mappings, dest_dir)
        
        # Save metadata
        save_posters_json(mappings, out_json)
        
        print(f"\n✅ Done! Files moved to {dest_dir} and metadata saved to {out_json}")
    else:
        print("ℹ️  DRY-RUN MODE (no files moved)")
        print(f"   Provisional metadata written to {out_json}")
        print(f"   Use --apply to move files and finalize.\n")
        
        # In dry-run, still write provisional JSON for preview
        save_posters_json(mappings, out_json)
        print(f"\n⚠️  To apply changes, run with --apply flag")


if __name__ == "__main__":
    main()
