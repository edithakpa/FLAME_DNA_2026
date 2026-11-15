"""FLAME DNA — convertit les classeurs SAFFIRE (NASA PSI) en JSON pour le front web.

Usage (depuis la racine du projet FLAME_DNA_2026) :
    python tools/build_web_data.py --src "C:/Users/USER/Desktop/saffire" --out web/data

Lit uniquement la feuille « Calibrated Data » de chaque classeur (données
calibrées NASA : O2, CO2, radiomètres, thermocouples, anémomètres, igniteur),
puis écrit :
  - web/data/saffire_index.json   : métriques dérivées par échantillon
  - web/data/series/<id>.json     : séries temporelles sous-échantillonnées
Aucune valeur n'est inventée : toutes les métriques sont calculées sur les fichiers.
"""
from __future__ import annotations

import argparse
import warnings
import json
import math
import re
from pathlib import Path

import numpy as np
import pandas as pd

MISSIONS = {
    "saffire_1": {"mission": "SAFFIRE-I", "vehicle": "Cygnus OA-6", "year": 2016},
    "saffire_2": {"mission": "SAFFIRE-II", "vehicle": "Cygnus OA-5", "year": 2016},
    "saffire_3": {"mission": "SAFFIRE-III", "vehicle": "Cygnus OA-7", "year": 2017},
}

# Métadonnées vérifiées (experimental_table.csv fourni avec SAFFIRE-I)
KNOWN_META = {
    "SAFFIRE-I-S1": {"material": "SIBAL Fabric", "flow_direction": "Concurrent",
                     "nominal_flow_cm_s": 20, "nominal_o2_pct": "21.5–21.7",
                     "size_cm": "40.6 × 94", "thickness_cm": 0.37},
    "SAFFIRE-I-S2": {"material": "SIBAL Fabric", "flow_direction": "Opposed",
                     "nominal_flow_cm_s": 20, "nominal_o2_pct": "~21.5",
                     "size_cm": "40.6 × 94", "thickness_cm": 0.37},
}

CHANNEL_GROUPS = {
    "atmosphere": ["O2", "CO2", "Ambient Pressure", "Humidity"],
    "flow": ["Anemometer 1", "Anemometer 2", "Average Fan Speed"],
    "radiation": ["Radiometer 1", "Radiometer 2", "Radiometer 3", "Radiometer 4"],
    "plume": [f"Plume Temp {i} (TC{i})" for i in range(1, 7)],
    "sample": [f"Sample Temp {i} (TC{i + 6})" for i in range(1, 7)],
    "inlet": ["Test Section Inlet Temp"],
    "igniter": ["Igniter Current", "Igniter Voltage"],
}
ALL_CHANNELS = [c for g in CHANNEL_GROUPS.values() for c in g]
SENTINEL = -1000.0
warnings.filterwarnings("ignore", category=RuntimeWarning)  # valeurs < -1000 = codes capteur / saturation basse


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def clean(series: pd.Series) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce")
    s[(s < SENTINEL) | (s.abs() > 1e6)] = np.nan
    return s


def downsample(t: np.ndarray, y: np.ndarray, n: int = 500):
    mask = ~np.isnan(t)
    t, y = t[mask], y[mask]
    if len(t) == 0:
        return [], []
    bins = np.linspace(t.min(), t.max(), n + 1)
    idx = np.clip(np.digitize(t, bins) - 1, 0, n - 1)
    out_t, out_y = [], []
    for b in range(n):
        sel = idx == b
        if not sel.any():
            continue
        yy = y[sel]
        yy = yy[~np.isnan(yy)]
        out_t.append(round(float(t[sel].mean()), 2))
        out_y.append(None if len(yy) == 0 else round(float(yy.mean()), 4))
    return out_t, out_y


def r(x, nd=3):
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return None
    return round(float(x), nd)


def analyse(df: pd.DataFrame, units: dict) -> dict:
    t = clean(df["Elapsed Time (s)"]).to_numpy()
    m: dict = {"duration_s": r(np.nanmax(t) - np.nanmin(t), 1), "records": int(len(df))}

    def base(col, frac=0.05):
        s = clean(df[col]).dropna()
        if s.empty:
            return None, s
        return float(s.iloc[: max(5, int(len(s) * frac))].median()), s

    # Igniteur → instant d'allumage électrique
    if "Igniter Current" in df:
        ic = clean(df["Igniter Current"]).to_numpy()
        if np.nanmax(ic) > 0.5:
            on = np.where(ic > 0.5 * np.nanmax(ic))[0]
            m["ignition_time_s"] = r(t[on[0]], 1)
            m["igniter_on_s"] = r(t[on[-1]] - t[on[0]], 1)
            m["igniter_peak_a"] = r(np.nanmax(ic), 2)

    # Atmosphère
    for col, key in (("O2", "o2"), ("CO2", "co2")):
        if col in df:
            b, s = base(col)
            if b is not None:
                m[f"{key}_initial_pct"] = r(b, 3)
                m[f"{key}_min_pct"] = r(s.min(), 3)
                m[f"{key}_max_pct"] = r(s.max(), 3)
    if "o2_initial_pct" in m:
        m["o2_drop_pct"] = r(m["o2_initial_pct"] - m["o2_min_pct"], 3)
    if "co2_initial_pct" in m:
        m["co2_rise_pct"] = r(m["co2_max_pct"] - m["co2_initial_pct"], 3)
    if "Ambient Pressure" in df:
        s = clean(df["Ambient Pressure"]).dropna()
        if not s.empty:
            m["pressure_mean_psia"] = r(s.mean(), 3)
            m["pressure_rise_psia"] = r(s.max() - s.iloc[: max(5, len(s) // 20)].median(), 3)

    # Rayonnement de flamme : signal radiométrique max sur 4 capteurs.
    # Ligne de base = avant allumage ; détection seulement après l'allumage,
    # avec un seuil > 6 × bruit pré-allumage pour éviter les faux positifs.
    ign = m.get("ignition_time_s") or 0.0
    rads = [c for c in CHANNEL_GROUPS["radiation"] if c in df]
    m["flame_detection_method"] = "undetermined"
    if rads:
        R = np.vstack([clean(df[c]).to_numpy() for c in rads])
        with np.errstate(all="ignore"):
            rmax = np.nanmax(R, axis=0)
        valid = ~np.isnan(t) & ~np.isnan(rmax)
        pre, post = valid & (t < ign), valid & (t >= ign)
        if pre.sum() < 5:
            pre = valid & (t <= np.nanmin(t) + 20)
        b = float(np.nanmedian(rmax[pre]))
        noise = float(np.nanstd(rmax[pre])) if pre.sum() > 2 else 0.0
        if post.any():
            ipk = np.where(post)[0][int(np.nanargmax(rmax[post]))]
            amp = float(rmax[ipk]) - b
            m["radiometer_baseline_mw_cm2"] = r(b, 3)
            m["radiometer_rise_mw_cm2"] = r(amp, 3)
            m["radiometer_peak_time_s"] = r(t[ipk], 1)
            if amp > max(2.0, 6 * noise):
                # plage contiguë autour du pic au-dessus de 10 % de l'amplitude
                thr = b + 0.10 * amp
                i0 = i1 = ipk
                while i0 > 0 and post[i0 - 1] and (np.isnan(rmax[i0 - 1]) or rmax[i0 - 1] > thr):
                    i0 -= 1
                while i1 < len(rmax) - 1 and (np.isnan(rmax[i1 + 1]) or rmax[i1 + 1] > thr):
                    i1 += 1
                m["flame_signal_start_s"] = r(t[i0], 1)
                m["flame_signal_end_s"] = r(t[i1], 1)
                m["flame_duration_s"] = r(t[i1] - t[i0], 1)
                m["flame_confidence"] = "high" if amp >= 20 else "medium" if amp >= 8 else "low"
                m["flame_detection_method"] = "radiometer"
                win = np.zeros_like(rmax, dtype=bool)
                win[i0:i1 + 1] = True
                y = np.where(win, np.nan_to_num(rmax - b), 0.0)
                y[y < 0] = 0
                tt = np.nan_to_num(t)
                m["radiant_dose_mj_cm2"] = r(float(np.sum((y[1:] + y[:-1]) / 2 * np.diff(tt))), 1)

    # Températures
    for grp, key in (("plume", "plume"), ("sample", "sample")):
        cols = [c for c in CHANNEL_GROUPS[grp] if c in df]
        if cols:
            T = np.vstack([clean(df[c]).to_numpy() for c in cols])
            m[f"{key}_temp_peak_c"] = r(np.nanmax(T), 1)
            peaks = []
            for c in cols:
                arr = clean(df[c]).to_numpy()
                if np.all(np.isnan(arr)):
                    continue
                i = int(np.nanargmax(arr))
                peaks.append({"channel": c, "peak_c": r(arr[i], 1), "time_s": r(t[i], 1)})
            m[f"{key}_tc_peaks"] = peaks
    if "Test Section Inlet Temp" in df:
        s = clean(df["Test Section Inlet Temp"]).dropna()
        if not s.empty:
            m["inlet_temp_mean_c"] = r(s.mean(), 2)

    if m["flame_detection_method"] == "undetermined" or m.get("flame_confidence") == "low":
        cols = [c for c in CHANNEL_GROUPS["sample"] if c in df]
        if cols:
            with np.errstate(all="ignore"):
                T = np.nanmax(np.vstack([clean(df[c]).to_numpy() for c in cols]), axis=0)
            hot = np.where((T > 100) & (t >= ign))[0]
            if len(hot):
                m["flame_signal_start_s"] = r(t[hot[0]], 1)
                m["flame_signal_end_s"] = r(t[hot[-1]], 1)
                m["flame_duration_s"] = r(t[hot[-1]] - t[hot[0]], 1)
                m["flame_detection_method"] = "thermocouple"
                m["flame_confidence"] = "medium"

    # Écoulement (pendant la phase de flamme si détectée)
    an = [c for c in ("Anemometer 1", "Anemometer 2") if c in df]
    if an:
        with np.errstate(all="ignore"):
            A = np.nanmean(np.vstack([clean(df[c]).to_numpy() for c in an]), axis=0)
        if m.get("flame_signal_start_s") is not None and m.get("flame_signal_end_s") is not None:
            sel = (t >= m["flame_signal_start_s"]) & (t <= m["flame_signal_end_s"])
            if sel.any():
                m["airflow_during_flame_cm_s"] = r(np.nanmean(A[sel]), 2)
        valid = A[(A > 0.5)]
        if len(valid):
            m["airflow_median_cm_s"] = r(np.nanmedian(valid), 2)

    # Ordre d'arrivée du front sur les thermocouples d'échantillon → indicateur de propagation
    pk = [p for p in m.get("sample_tc_peaks", []) if p["peak_c"] and p["peak_c"] > 60]
    if len(pk) >= 2:
        ts = sorted(p["time_s"] for p in pk)
        m["sample_front_transit_s"] = r(ts[-1] - ts[0], 1)
    return m


def process(path: Path, folder: str, out_series: Path) -> dict:
    df = pd.read_excel(path, sheet_name="Calibrated Data", header=0, engine="openpyxl")
    units = {c: (str(u) if isinstance(u, str) else "") for c, u in df.iloc[0].items()}
    df = df.iloc[1:].reset_index(drop=True)
    meta = MISSIONS[folder]
    sid = f"{meta['mission']}-{path.stem}"
    metrics = analyse(df, units)

    t = clean(df["Elapsed Time (s)"]).to_numpy()
    series = {"t": None, "channels": {}}
    for c in ALL_CHANNELS:
        if c in df:
            tt, yy = downsample(t, clean(df[c]).to_numpy())
            series["t"] = tt
            if any(v is not None for v in yy):
                series["channels"][c] = {"unit": units.get(c, ""), "y": yy}
    (out_series / f"{slug(sid)}.json").write_text(json.dumps(series, separators=(",", ":")))

    entry = {
        "id": sid,
        "slug": slug(sid),
        "mission": meta["mission"],
        "vehicle": meta["vehicle"],
        "year": meta["year"],
        "sample": path.stem,
        "source_file": f"{folder}/{path.name}",
        "channels": sorted(series["channels"].keys()),
        "units": {c: units.get(c, "") for c in series["channels"]},
        "metrics": metrics,
        "meta": KNOWN_META.get(sid, {}),
    }
    print(f"✓ {sid}: {metrics.get('flame_duration_s')} s de signal flamme, "
          f"pic radiométrique {metrics.get('radiometer_peak_mw_cm2')} mW/cm²")
    return entry


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", default="web/data")
    ap.add_argument("--only", nargs="*", help="ex: saffire_1/S2 (debug)")
    args = ap.parse_args()
    src, out = Path(args.src), Path(args.out)
    (out / "series").mkdir(parents=True, exist_ok=True)
    entries = []
    for folder in sorted(MISSIONS):
        for f in sorted((src / folder).glob("S*.xlsx")):
            if args.only and f"{folder}/{f.stem}" not in args.only:
                continue
            try:
                entries.append(process(f, folder, out / "series"))
            except Exception as e:  # noqa: BLE001
                print(f"✗ {f}: {e}")
    (out / "saffire_index.json").write_text(json.dumps({
        "source": "NASA Physical Science Informatics — SAFFIRE I/II/III, sheet 'Calibrated Data'",
        "samples": entries,
        "channel_groups": CHANNEL_GROUPS,
    }, indent=1, ensure_ascii=False))
    print(f"{len(entries)} échantillons écrits dans {out}")


if __name__ == "__main__":
    main()
