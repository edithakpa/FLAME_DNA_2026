"""Safe, optional wrapper patch for existing FLAME DNA app.py.

Dry-run:  python tools/add_workbook_telemetry.py
Apply:    python tools/add_workbook_telemetry.py --apply

Backs up app.py, checks exact page branches, preserves original modules.
"""
from __future__ import annotations
import argparse
import ast
from datetime import datetime
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"
IMP = "from modules.saffire_i_workbook_telemetry import render_workbook_panel, render_workbook_status, render_workbook_context\n"


def wrap_page(source, page, label, key):
    pat = rf'(?ms)^(elif page == "{re.escape(page)}":\n)(.*?)(?=^elif page == "|^else:|\Z)'
    found = list(re.finditer(pat, source))
    if len(found) != 1:
        raise ValueError(f"Cannot safely locate '{page}' page (expected exactly one).")
    block = found[0].group(2)
    if not block.strip():
        raise ValueError(f"Empty page block: {page}")
    prefix = (
        f'    original_tab, workbook_tab = st.tabs(["{label}", "SAFFIRE-I Workbook Telemetry"])\n'
        '    with original_tab:\n'
    )
    # Keep every existing statement, just indent it under an unchanged existing-tab wrapper.
    original = ''.join('    ' + ln if ln.strip() else ln for ln in block.splitlines(True))
    suffix = (
        '    with workbook_tab:\n'
        f'        render_workbook_panel(key="{key}")\n'
        '\n'
    )
    return source[:found[0].start(2)] + prefix + original + suffix + source[found[0].end(2):]


def build_patch(text):
    if 'render_workbook_panel(' in text:
        return text, 'Workbook telemetry panels already installed; no changes necessary.'
    if 'from modules.saffire_i_workbook_telemetry import' not in text:
        m = re.search(r'(?m)^st\.set_page_config\(', text)
        if m is None:
            raise ValueError('st.set_page_config(...) not found: cannot safely add import.')
        text = text[:m.start()] + IMP + '\n' + text[m.start():]
    text = wrap_page(text, 'Data Explorer', 'Existing Data Explorer', 'uploaded_explorer')
    text = wrap_page(text, 'Scientific Analysis & Comparison', 'Existing Scientific Analysis', 'uploaded_science')
    if 'render_workbook_status()' not in text:
        pat = r'(?m)^if page == "Overview":\n'
        if len(re.findall(pat, text)) != 1:
            raise ValueError('Overview branch not found uniquely.')
        text = re.sub(pat, 'if page == "Overview":\n    render_workbook_status()\n', text, count=1)
    if 'render_workbook_context()' not in text:
        pat = r'(?m)^elif page == "Space Mission Fire Safety":\n'
        if len(re.findall(pat, text)) != 1:
            raise ValueError('Space Mission Fire Safety branch not found uniquely.')
        text = re.sub(pat, 'elif page == "Space Mission Fire Safety":\n    render_workbook_context()\n', text, count=1)
    ast.parse(text, filename=str(APP))
    return text, 'Will add separate workbook tabs in two pages and short Overview/Fire Safety context.'


def main():
    args = argparse.ArgumentParser()
    args.add_argument('--apply', action='store_true')
    opt = args.parse_args()
    if not APP.is_file():
        raise SystemExit(f'Not found: {APP}')
    if not (ROOT / 'modules' / 'saffire_i_workbook_telemetry.py').is_file():
        raise SystemExit('Install modules/saffire_i_workbook_telemetry.py first.')
    old = APP.read_text(encoding='utf-8-sig')
    try:
        updated, note = build_patch(old)
    except (ValueError, SyntaxError) as exc:
        raise SystemExit(f'SAFETY STOP: app.py left unchanged. {exc}') from exc
    print(note)
    if old == updated:
        return
    if not opt.apply:
        print('DRY RUN OK; to apply: python .\\tools\\add_workbook_telemetry.py --apply')
        return
    backupdir = ROOT / 'backups'
    backupdir.mkdir(exist_ok=True)
    bk = backupdir / ('app_before_workbook_' + datetime.now().strftime('%Y%m%d_%H%M%S') + '.py')
    shutil.copy2(APP, bk)
    APP.write_text(updated, encoding='utf-8')
    print('Updated:', APP)
    print('Backup:', bk)
    print('Verify with: python -m py_compile .\\app.py .\\modules\\saffire_i_workbook_telemetry.py')

if __name__ == '__main__':
    main()
