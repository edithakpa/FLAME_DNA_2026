"""Targeted FLAME DNA Scientific Library search fix.

At FLAME_DNA_2026 root:
  python .\tools\fix_scientific_library_search.py          # preview
  python .\tools\fix_scientific_library_search.py --apply  # backup + fix

Changes only the Scientific Library search control in modules/flame_catalog_v2.py.
"""
from __future__ import annotations

import argparse
import ast
from datetime import datetime
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / 'modules' / 'flame_catalog_v2.py'

BEFORE = '''    search = st.text_input("Search saved NASA publications", key="v2_library_search")
    value = search.casefold().strip()
    if value != st.session_state.get("v2_lib_last_query", ""):
        st.session_state["v2_library_page"] = 1
        st.session_state["v2_lib_last_query"] = value'''

AFTER = '''    # One form: pressing Enter and clicking Search do the same thing.
    with st.form("v2_library_search_form", clear_on_submit=False,
                 enter_to_submit=True, border=False):
        search = st.text_input("Search saved NASA publications", key="v2_library_search")
        submitted = st.form_submit_button("Search", type="primary")

    # Keep the last submitted query during pagination and other reruns.
    if submitted:
        value = search.casefold().strip()
        if value != st.session_state.get("v2_lib_last_query", ""):
            st.session_state["v2_library_page"] = 1
        st.session_state["v2_lib_last_query"] = value
        st.session_state["v2_library_query"] = value

    value = st.session_state.get("v2_library_query", "")'''


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true', help='Back up and modify the target.')
    args = parser.parse_args()

    if not TARGET.is_file():
        print('NOT FOUND: modules/flame_catalog_v2.py')
        print('No changes made. Your Scientific Library may live in a different module.')
        return

    original = TARGET.read_text(encoding='utf-8-sig')
    if 'with st.form("v2_library_search_form"' in original:
        print('ALREADY UPDATED: Scientific Library uses the Enter-enabled search form.')
        return
    count = original.count(BEFORE)
    if count != 1:
        print(f'SAFETY STOP: expected 1 original search block, found {count}.')
        print('No changes made. Please share:')
        print('Select-String -Path .\\modules\\flame_catalog_v2.py -Pattern "Search saved NASA publications" -Context 6,12')
        return

    patched = original.replace(BEFORE, AFTER, 1)
    ast.parse(patched, filename=str(TARGET))
    print('DRY RUN OK — Search button below the bar + Enter submits, five-per-page navigation unchanged.')
    if not args.apply:
        print('Run with --apply to save the patch.')
        return

    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup = ROOT / 'backups' / f'flame_catalog_v2_before_library_search_{stamp}.py'
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(TARGET, backup)
    TARGET.write_text(patched, encoding='utf-8')
    print('UPDATED: modules/flame_catalog_v2.py')
    print(f'BACKUP: {backup.relative_to(ROOT)}')
    print('Check: python -m py_compile .\\modules\\flame_catalog_v2.py .\\app.py')


if __name__ == '__main__':
    main()
