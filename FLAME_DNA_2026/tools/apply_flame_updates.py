"""Install FLAME DNA 2026 UI upgrades without rewriting unrelated pages.

Run from project root: python .\tools\apply_flame_updates.py --apply
Creates timestamped backup. Refuses to patch if expected navigation anchors are
missing or modified, instead of risking a broken or truncated app.py.
"""
from __future__ import annotations
import argparse
import ast
from datetime import datetime
from pathlib import Path
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"
IMPORTS = (
    "from modules.flame_catalog_v2 import render_catalog_v2\n"
    "from modules.flame_workspace_v2 import (\n"
    "    render_explorer_v2, render_analysis_v2,\n"
    "    render_mission_context_v2, render_overview_update_v2,\n"
    ")\n"
)


def change_app(text):
    new = text
    if "from modules.flame_catalog_v2 import render_catalog_v2" not in new:
        # Insert before the first top-level st.set_page_config; don't break import sections.
        match = re.search(r"(?m)^st\.set_page_config\(", new)
        if not match:
            raise RuntimeError("Could not find st.set_page_config in app.py. No changes made.")
        new = new[:match.start()] + IMPORTS + "\n" + new[match.start():]

    if "render_overview_update_v2()" not in new:
        pat = r'(?m)^if page == "Overview":\s*\n'
        if len(re.findall(pat, new)) != 1:
            raise RuntimeError("Overview branch not found exactly once; no changes made.")
        new = re.sub(pat, 'if page == "Overview":\n    render_overview_update_v2()\n', new, count=1)

    if "render_catalog_v2()" not in new:
        pat = r'(?m)^(elif page == "NASA Research Catalog":)\s*\n(?:\s*render_catalog\(\)\s*\n)'
        if len(re.findall(pat, new)) != 1:
            raise RuntimeError("NASA Research Catalog renderer does not match expected form; no changes made.")
        new = re.sub(pat, '\\1\n    render_catalog_v2()\n', new, count=1)

    if "render_explorer_v2()" not in new:
        pat = r'(?ms)^elif page == "Data Explorer":\s*\n.*?(?=^elif page == "Scientific Analysis & Comparison":)'
        if len(re.findall(pat, new)) != 1:
            raise RuntimeError("Data Explorer branch layout unknown; no changes made.")
        new = re.sub(pat, 'elif page == "Data Explorer":\n    render_explorer_v2()\n\n', new, count=1)

    if "render_analysis_v2()" not in new:
        pat = r'(?ms)^elif page == "Scientific Analysis & Comparison":\s*\n.*?(?=^elif page == "Space Mission Fire Safety":)'
        if len(re.findall(pat, new)) != 1:
            raise RuntimeError("Scientific Analysis branch layout unknown; no changes made.")
        new = re.sub(pat, 'elif page == "Scientific Analysis & Comparison":\n    render_analysis_v2()\n\n', new, count=1)

    if "render_mission_context_v2()" not in new:
        pat = r'(?m)^(elif page == "Space Mission Fire Safety":\s*\n\s*render_fire_safety\(\)\s*\n)'
        if len(re.findall(pat, new)) != 1:
            raise RuntimeError("Space Mission Fire Safety branch layout unknown; no changes made.")
        new = re.sub(pat, '\\1    render_mission_context_v2()\n', new, count=1)

    try:
        ast.parse(new, filename=str(APP))
    except SyntaxError as exc:
        raise RuntimeError(f"Patch produced invalid Python at line {exc.lineno}; no changes made.") from exc
    return new


def main():
    parser = argparse.ArgumentParser(description="Apply safe FLAME DNA enhancements")
    parser.add_argument("--apply", action="store_true", help="Save update (default prints a dry-run summary)")
    args = parser.parse_args()
    if not APP.is_file():
        sys.exit(f"ERROR: app.py not found in {ROOT}. Copy this tool into the correct project first.")
    required = [ROOT / "modules/flame_catalog_v2.py", ROOT / "modules/flame_workspace_v2.py"]
    missing = [str(p) for p in required if not p.is_file()]
    if missing:
        sys.exit("ERROR: Required new modules not installed:\n" + "\n".join(missing))
    original = APP.read_text(encoding="utf-8-sig")
    try:
        modified = change_app(original)
    except RuntimeError as exc:
        sys.exit("PATCH ABORTED SAFELY: " + str(exc))
    if modified == original:
        print("Already patched: no changes needed.")
        return
    if not args.apply:
        print("DRY RUN OK: all required navigation blocks identified and updated in memory.")
        print("Run: python .\\tools\\apply_flame_updates.py --apply")
        return
    backup_dir = ROOT / "backups"
    backup_dir.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = backup_dir / f"app_before_v2_{stamp}.py"
    shutil.copy2(APP, backup)
    APP.write_text(modified, encoding="utf-8")
    print("FLAME DNA UI update applied successfully.")
    print(f"Backup: {backup}")
    print("Now run: python -m py_compile .\\app.py .\\modules\\flame_catalog_v2.py .\\modules\\flame_workspace_v2.py")

if __name__ == "__main__":
    main()
