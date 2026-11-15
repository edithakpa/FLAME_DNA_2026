"""FLAME DNA — safe UI interaction improvements.

Run at project root:
    python .\tools\apply_ui_interactions.py
    python .\tools\apply_ui_interactions.py --apply

Only patches exact, known source patterns; backs up files and validates Python
AST before touching live files. Unsupported/modified layouts are reported.
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
MODULES = ROOT / 'modules'


def replace_once(text: str, old: str, new: str, name: str) -> tuple[str, bool]:
    count = text.count(old)
    if count == 1:
        return text.replace(old, new, 1), True
    if new in text:
        return text, False  # already patched
    raise ValueError(f'{name}: expected one matching code block, found {count}. Source left unchanged.')


def patch_workspace(text: str) -> str:
    old = '''    sensors = st.multiselect("Sensor variables", options, default=options[:3],
                             max_selections=6, key="v2_explorer_variables")
    if sensors:
        fig = sensor_trend_chart(df, sensors, f"{selected} — Sensor Trends")'''
    new = '''    sensor = st.selectbox("Sensor variable", options, key="v2_explorer_variable_single")
    if sensor:
        fig = sensor_trend_chart(df, [sensor], f"{selected} — {sensor} Sensor Trend")'''
    text, _ = replace_once(text, old, new, 'Data Explorer single-variable selector')
    old = '''    selected = st.multiselect("Compare sensor curves", candidates, default=candidates[:3],
                              max_selections=6, key=f"{key}_sensor_selection")
    if selected:
        figure = sensor_trend_chart(df, selected, f"{name} — Sensor Trends")'''
    new = '''    selected = st.selectbox("Sensor variable", candidates, key=f"{key}_single_sensor") if candidates else None
    if selected:
        figure = sensor_trend_chart(df, [selected], f"{name} — {selected} Sensor Trend")'''
    text, _ = replace_once(text, old, new, 'S1/S2/II single time-series selector')
    return text


def patch_catalog(text: str) -> str:
    old = '''    typed = st.text_input("NASA research keywords", value="microgravity fire saffire", key="v2_ntrs_input")
    if st.button("Search NASA", key="v2_ntrs_submit"):
        st.session_state["v2_ntrs_query"] = typed.strip()
        st.session_state["v2_ntrs_page"] = 1'''
    new = '''    with st.form("v2_ntrs_search_form", clear_on_submit=False, enter_to_submit=True, border=False):
        typed = st.text_input("NASA research keywords", value="microgravity fire saffire", key="v2_ntrs_input")
        submitted = st.form_submit_button("Search NASA", type="primary")
    if submitted:
        st.session_state["v2_ntrs_query"] = typed.strip()
        st.session_state["v2_ntrs_page"] = 1'''
    text, _ = replace_once(text, old, new, 'NASA Online Search Enter support')
    return text


def patch_ai(text: str) -> str:
    old = '''    question = st.text_area(
        "Ask a scientific question / Posez une question scientifique",
        placeholder="What do NASA publications say about flames in microgravity?",
        key="flame_nlp_question",
        height=105,
    )
    if not st.button("Analyze NASA Research", type="primary", key="flame_nlp_submit"):
        return'''
    new = '''    with st.form("flame_nlp_search_form", clear_on_submit=False, enter_to_submit=True, border=False):
        question = st.text_input(
            "Ask a scientific question",
            placeholder="What do NASA publications say about flames in microgravity?",
            key="flame_nlp_question",
        )
        submitted = st.form_submit_button("Analyze NASA Research", type="primary")
    if not submitted:
        return'''
    text, _ = replace_once(text, old, new, 'NASA AI Enter support')
    return text


def patch_workbook(text: str) -> str:
    old = '''    selected = st.multiselect(
        "Choose sensor channels", sensor_names, default=preferred[:3] or sensor_names[:3],
        max_selections=6, key=f"{key}_variables",
    )
    if selected:
        st.plotly_chart(_line_plot(df, selected, f"{name} — Recorded Sensor Trends"),
                        width="stretch", key=f"{key}_trends")'''
    new = '''    if not sensor_names:
        st.info("No numeric sensor channels available for plotting.")
        return
    selected = st.selectbox(
        "Sensor channel", sensor_names,
        index=sensor_names.index(preferred[0]) if preferred else 0,
        key=f"{key}_single_variable",
    )
    if selected:
        st.plotly_chart(_line_plot(df, [selected], f"{name} — {selected} Sensor Trend"),
                        width="stretch", key=f"{key}_trends")'''
    text, _ = replace_once(text, old, new, 'Workbook single time-series selector')
    old = '''        stats = df[selected].apply(pd.to_numeric, errors="coerce").describe().T'''
    new = '''        stats = df[[selected]].apply(pd.to_numeric, errors="coerce").describe().T'''
    text, _ = replace_once(text, old, new, 'Workbook single-sensor statistics')
    old = '''        if len(selected) >= 2:
            st.markdown("#### Correlation Analysis")
            corr = df[selected].apply(pd.to_numeric, errors="coerce").corr()'''
    new = '''        corr_sensors = [c for c in sensor_names if c != selected][:5]
        if corr_sensors:
            st.markdown("#### Correlation Analysis")
            st.caption("Correlation uses multiple independent channels; it does not change the single sensor trend selection.")
            corr_names = [selected] + corr_sensors
            corr = df[corr_names].apply(pd.to_numeric, errors="coerce").corr()'''
    text, _ = replace_once(text, old, new, 'Workbook correlation separate from selected line')
    old = '''                z=corr.values, x=selected, y=selected,'''
    new = '''                z=corr.values, x=corr_names, y=corr_names,'''
    text, _ = replace_once(text, old, new, 'Workbook correlation axes')
    return text


def _expander_text(call: ast.Call) -> str:
    if not call.args:
        return ''
    arg = call.args[0]
    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
        return arg.value
    if isinstance(arg, ast.JoinedStr):
        return ''.join(part.value for part in arg.values if isinstance(part, ast.Constant) and isinstance(part.value, str))
    return ''


def patch_experiment_expander(text: str) -> tuple[str, str]:
    """Replace exactly one strongly identified telemetry expander with a visible container.

    If unknown dynamic text or multiple candidates, do not change source.
    """
    tree = ast.parse(text)
    matches = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.With, ast.AsyncWith)) or len(node.items) != 1:
            continue
        ctx = node.items[0].context_expr
        if not isinstance(ctx, ast.Call):
            continue
        fn = ctx.func
        if not isinstance(fn, ast.Attribute) or fn.attr != 'expander':
            continue
        if not isinstance(fn.value, ast.Name) or fn.value.id != 'st':
            continue
        label = _expander_text(ctx)
        label_normalized = label.casefold()
        if 'saffire' in label_normalized and re.search(r'telemetr|t[ée]l[ée]m[ée]tr|sensor|capteur', label_normalized):
            matches.append((node, ctx, label))
    if len(matches) != 1:
        return text, f'Telemetry expander not changed: {len(matches)} unambiguous matching expander(s) found.'
    node, ctx, label = matches[0]
    if not node.body:
        return text, 'Target telemetry expander has no statements; not changed.'
    lines = text.splitlines(keepends=True)
    start_offsets = [0]
    for line in lines:
        start_offsets.append(start_offsets[-1] + len(line.encode('utf-8')))
    start = start_offsets[ctx.lineno - 1] + ctx.col_offset
    end = start_offsets[ctx.end_lineno - 1] + ctx.end_col_offset
    data = text.encode('utf-8')
    replacement = b'st.container(border=True)'
    updated = data[:start] + replacement + data[end:]
    # Before the existing with statement, write a heading at the exact same indentation level.
    insertion = start_offsets[node.lineno - 1]
    existing_line = lines[node.lineno - 1]
    indent = re.match(r'^[ \t]*', existing_line).group(0)
    heading = f'{indent}st.markdown("#### SAFFIRE-I — Sensor Telemetry Analysis")\n'.encode('utf-8')
    updated = updated[:insertion] + heading + updated[insertion:]
    parsed = updated.decode('utf-8')
    ast.parse(parsed)
    return parsed, f'Converted collapsible telemetry panel to always-visible bordered section: {label}'


def list_search_candidates(root: Path) -> list[str]:
    out = []
    candidates = ([root / 'app.py'] if (root / 'app.py').is_file() else [])
    candidates += sorted((root / 'modules').rglob('*.py'))
    for p in candidates:
        if '__pycache__' in p.parts:
            continue
        try:
            src = p.read_text(encoding='utf-8-sig')
        except (UnicodeDecodeError, OSError):
            continue
        if not any(x in src for x in ('text_input(', 'text_area(', 'Search', 'search')):
            continue
        for i, line in enumerate(src.splitlines(), start=1):
            if ('st.text_input(' in line or 'st.text_area(' in line
                    or ('st.button(' in line and re.search(r'search|recherch|analy[sz]e|submit', line, re.I))):
                out.append(f'  {p.relative_to(root)}:{i}: {line.strip()[:120]}')
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true', help='Save verified changes; default is dry run')
    opt = parser.parse_args()
    targets = [
        (MODULES / 'flame_catalog_v2.py', patch_catalog),
        (MODULES / 'flame_workspace_v2.py', patch_workspace),
        (MODULES / 'nasa_ai_ml.py', patch_ai),
        (MODULES / 'saffire_i_workbook_telemetry.py', patch_workbook),
    ]
    pending = []
    print('FLAME DNA — UI INTERACTIONS', 'APPLY' if opt.apply else 'DRY RUN')
    for path, patcher in targets:
        if not path.exists():
            print(f'SKIP: {path.relative_to(ROOT)} (not installed)')
            continue
        original = path.read_text(encoding='utf-8-sig')
        try:
            modified = patcher(original)
            ast.parse(modified)
        except (ValueError, SyntaxError) as exc:
            print(f'SAFETY STOP: {path.relative_to(ROOT)} — {exc}')
            continue
        if modified != original:
            pending.append((path, original, modified))
            print(f'OK: {path.relative_to(ROOT)} — {"will update" if not opt.apply else "update ready"}')
        else:
            print(f'ALREADY UPDATED: {path.relative_to(ROOT)}')

    # The original catalog uses unknown private code; inspect candidate expander safely.
    for rel in (
        'modules/research_catalog/experiments/experiment_ui.py',
        'modules/research_catalog/experiments/telemetry_ui.py',
        'modules/research_catalog/catalog_ui.py',
    ):
        path = ROOT / rel
        if not path.is_file():
            continue
        original = path.read_text(encoding='utf-8-sig')
        try:
            modified, note = patch_experiment_expander(original)
        except (ValueError, SyntaxError) as exc:
            note = f'Not changed: {exc}'
            modified = original
        print(f'CATALOG {rel}: {note}')
        if modified != original:
            pending.append((path, original, modified))

    print('\nSearch controls found in installed modules (for any remaining Enter-key checks):')
    matches = list_search_candidates(ROOT)
    if matches:
        print('\n'.join(matches[:60]))
    else:
        print('  No search inputs were found under modules/.')
    print(f'\nValidated changes proposed: {len(pending)} file(s).')
    if not pending:
        print('No changes applied. If the current UI still uses old search buttons, inspect source at the listed lines.')
        return
    if not opt.apply:
        print('DRY RUN OK — nothing has been written. Run with --apply to save updates.')
        return
    backup_dir = ROOT / 'backups' / ('ui_interactions_' + datetime.now().strftime('%Y%m%d_%H%M%S'))
    backup_dir.mkdir(parents=True, exist_ok=True)
    # All transformed Python already passed AST checks. Keep relative paths in backups.
    for path, original, modified in pending:
        backup = backup_dir / path.relative_to(ROOT)
        backup.parent.mkdir(parents=True, exist_ok=True)
        backup.write_text(original, encoding='utf-8')
        path.write_text(modified, encoding='utf-8')
        print(f'UPDATED: {path.relative_to(ROOT)}')
    print(f'Backup folder: {backup_dir}')
    print('Run: python -m compileall -q app.py modules')


if __name__ == '__main__':
    main()
