"""
Build index.html for the Beauty Partner Incentive dropdown site.

Reads monthly incentive .xlsx files (sheet "result"), computes each pro's
"earned" amount, a peer benchmark, and a top-10 side-by-side leaderboard
per category (named, not anonymous) personalized per viewer, then injects
the resulting DATA + NAMES objects into index_template.html (markers
__DATA__ and __NAMES__) to produce index.html. There are no per-person
links -- one shared page, access via a searchable name dropdown.

Keyed internally by PROVIDER_ID, not L_NO: some source rows have two
different people sharing the same L_NO (a data-entry error upstream --
e.g. L_204015 is used by both "April Anne Vivero" and "Mary Grace A.
Decastro" in every month file). Keying by L_NO silently merges such pairs
into one record. PROVIDER_ID is the actually-unique system ID.

Usage:
    python build_data.py
"""

import json
import re
from datetime import date

import pandas as pd

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
MONTH_FILES = {
    "April": "April_incentives.xlsx",
    "May": "May_incentives.xlsx",
    "June": "June_incentives.xlsx",
    "July": "July_incentives.xlsx",
    "August": "August_incentives.xlsx",  # full month now (PAYABLE_DAYS=31), pulled live from Jarvis
}

BENCHMARK_PERCENTILE = 80
CATEGORIES = ["Salon Nails", "Spa for Women", "Advanced Facecare", "Hair for Women"]
LEADERBOARD_TOP_N = 10
PEER_WINDOWS = [10, 25, 40]
MIN_PEERS = 8

TEMPLATE_PATH = "index_template.html"
OUTPUT_PATH = "index.html"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def normalize_lno(raw):
    return str(raw).replace(" ", "").replace("\t", "").replace("\n", "").upper()


def display_name(raw):
    # some names arrive as "Nickname, Full Legal Name" -- the part before
    # the comma is the display name already, so prefer that over splitting
    # on whitespace (which would turn "Agda," into "Agda,").
    name = str(raw).strip()
    if not name:
        return "Unknown"
    first = name.split(",")[0].strip() if "," in name else name
    return first or "Unknown"


def load_month(path):
    df = pd.read_excel(path, sheet_name="result")
    df.columns = [c.strip() for c in df.columns]
    for col in ("RAMADAN_PRIZE", "RATING_INCENTIVE"):
        if col not in df.columns:
            df[col] = 0
    # PROVIDER_ID is the true unique identity. L_NO looks unique but is NOT --
    # some source rows have two different people sharing the same L_NO (a
    # data-entry error upstream), which silently merges them if used as the
    # key. Keep L_NO only as a normalized display/reference field.
    df["PROVIDER_ID"] = df["PROVIDER_ID"].astype(str).str.strip()
    df["L_NO"] = df["L_NO"].apply(normalize_lno)
    df["PROVIDER_NAME"] = df["PROVIDER_NAME"].astype(str).str.strip()
    df["DISPLAY_NAME"] = df["PROVIDER_NAME"].apply(display_name)
    df["CITY"] = df.get("CITY", "").fillna("")
    for col in ("TOTAL_INCENTIVE", "TOTAL_TIP", "TOTAL_OT", "RAMADAN_PRIZE", "JOBS",
                "AVERAGE_RATING", "REBOOKING_COUNT", "REBOOKING_INCENTIVE", "PERC_COMM",
                "PERFORMANCE_INCENTIVE"):
        if col not in df.columns:
            df[col] = 0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    df["EARNED"] = df["TOTAL_INCENTIVE"] + df["TOTAL_TIP"] + df["TOTAL_OT"] + df["RAMADAN_PRIZE"]
    # Source SQL doubles rebooking incentive + commission for any city other
    # than Riyadh/Jeddah (multiplier = 2 vs 1) -- confirmed directly against
    # the Jarvis query (2026-09-06) and against real data (e.g. Andrelyn Melo,
    # Dammam, whose "mystery" 2x total_incentive residual is exactly this).
    # Apply the same multiplier per component here so rbi/comm reflect what
    # the pro actually earned, not the pre-multiplier raw column value.
    df["CITY_MULT"] = df["CITY"].apply(lambda c: 1 if str(c).strip() in ("Riyadh", "Jeddah") else 2)
    df["ADJ_RBI"] = df["REBOOKING_INCENTIVE"] * df["CITY_MULT"]
    df["ADJ_COMM"] = df["PERC_COMM"] * df["CITY_MULT"]
    # the provider-vs-colleague comparison card deliberately excludes tips
    # (and OT/ramadan/etc.) -- it's rebooking incentive + commission only
    # (city-multiplier-adjusted), so the comparison isn't skewed by unrelated
    # tip income, and is apples-to-apples across cities.
    df["COMPARE"] = df["ADJ_RBI"] + df["ADJ_COMM"]
    # drop obvious non-provider test rows (no L_NO at all, zero jobs)
    df = df[~((df["L_NO"] == "NAN") & (df["JOBS"] == 0))]
    return df


def percentile_pick(sorted_ascending_values, percentile):
    n = len(sorted_ascending_values)
    if n == 0:
        return None
    idx = round((percentile / 100) * (n - 1))
    idx = max(0, min(n - 1, idx))
    return sorted_ascending_values[idx]


def find_peer_benchmark(active_df, row):
    # Comparison metric is rebooking incentive + commission ONLY (COMPARE),
    # never the full "earned" total -- tips (and OT/ramadan/etc.) must not
    # influence who counts as "earning more" or how the gap is shown.
    my_jobs = row["JOBS"]
    my_compare = row["COMPARE"]
    my_rating = row["AVERAGE_RATING"]
    my_reb = row["REBOOKING_COUNT"]
    my_pid = row["PROVIDER_ID"]

    others = active_df[active_df["PROVIDER_ID"] != my_pid]

    peers = others.iloc[0:0]
    for window in PEER_WINDOWS:
        candidate = others[(others["JOBS"] - my_jobs).abs() <= window]
        peers = candidate
        if len(candidate) >= MIN_PEERS:
            break

    earned_more = peers[peers["COMPARE"] > my_compare]
    if earned_more.empty:
        return None  # top performer

    preferred = earned_more[
        (earned_more["AVERAGE_RATING"] > my_rating) & (earned_more["REBOOKING_COUNT"] > my_reb)
    ]
    pool = preferred if not preferred.empty else earned_more
    pool_sorted = pool.sort_values("COMPARE")
    exemplar_compare = percentile_pick(pool_sorted["COMPARE"].tolist(), BENCHMARK_PERCENTILE)
    exemplar_row = pool_sorted.iloc[(pool_sorted["COMPARE"] - exemplar_compare).abs().values.argmin()]

    return {
        "e": round(float(exemplar_row["COMPARE"]), 2),
        "r": round(float(exemplar_row["AVERAGE_RATING"]), 2),
        "rb": int(exemplar_row["REBOOKING_COUNT"]),
    }


def build_category_board(month_df, category, top_n=LEADERBOARD_TOP_N):
    cat_df = month_df[month_df["CATEGORY"] == category].copy()
    cat_df = cat_df.sort_values("EARNED", ascending=False).head(top_n)
    board = []
    for _, r in cat_df.iterrows():
        board.append({
            "pid": r["PROVIDER_ID"],
            "n": r["DISPLAY_NAME"],
            "e": round(float(r["EARNED"]), 2),
            "r": round(float(r["AVERAGE_RATING"]), 2),
            "rb": int(r["REBOOKING_COUNT"]),
        })
    return board


def personalize_board(board, viewer_pid):
    return [
        {"n": entry["n"], "e": entry["e"], "r": entry["r"], "rb": entry["rb"],
         "me": entry["pid"] == viewer_pid}
        for entry in board
    ]


def disambiguate_labels(entries):
    # entries: list of dicts with "pid", "display_name", "city"
    by_name = {}
    for e in entries:
        by_name.setdefault(e["display_name"], []).append(e)

    for name, group in by_name.items():
        if len(group) == 1:
            group[0]["label"] = name
            continue
        # try city first
        cities = {g["city"] for g in group}
        if len(cities) == len(group):
            for g in group:
                g["label"] = f"{name} ({g['city']})" if g["city"] else name
            continue
        # fall back to a stable disambiguator using a short hash of the
        # provider ID (L_NO is NOT safe here -- it can collide between
        # different people, which is exactly the bug this key change fixes)
        for g in group:
            suffix = g["pid"][-4:]
            g["label"] = f"{name} (#{suffix})"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    month_dfs = {label: load_month(path) for label, path in MONTH_FILES.items()}
    months = list(MONTH_FILES.keys())

    pros = {}  # PROVIDER_ID -> {"cat":..., "name":..., "city":..., "m": {month: {...}}}
    boards = {}  # month -> category -> top-N board (unpersonalized, "me" always false)
    # -- lets a viewer browse OTHER categories' leaderboards too, not just their own.

    for label, df in month_dfs.items():
        active_df = df[df["JOBS"] > 0]
        category_boards = {cat: build_category_board(df, cat) for cat in CATEGORIES}
        boards[label] = {
            cat: [{"n": e["n"], "e": e["e"], "r": e["r"], "rb": e["rb"]} for e in board]
            for cat, board in category_boards.items()
        }

        for _, row in df.iterrows():
            pid = row["PROVIDER_ID"]
            if not pid or pid == "nan":
                continue

            pros.setdefault(pid, {"cat": row["CATEGORY"], "name": row["DISPLAY_NAME"],
                                   "city": row["CITY"], "m": {}})
            pros[pid]["cat"] = row["CATEGORY"] or pros[pid]["cat"]
            pros[pid]["name"] = row["DISPLAY_NAME"] or pros[pid]["name"]
            pros[pid]["city"] = row["CITY"] or pros[pid]["city"]

            peer = None
            if row["JOBS"] > 0:
                peer = find_peer_benchmark(active_df, row)

            board = category_boards.get(row["CATEGORY"])
            lb = personalize_board(board, pid) if board else None

            # breakdown of the "you earned" total, so tips/commission aren't
            # hidden inside one opaque number. rbi/comm below are already
            # city-multiplier-adjusted (see ADJ_RBI/ADJ_COMM above). "perf" is
            # its own line (not lumped into "other") so a performance-incentive
            # indicator can be shown. "other" is now just the small remainder
            # (referral/shadowing/rating incentive, if any) -- confirmed to
            # reconcile to ~0 for June/July/August once the city multiplier is
            # correctly applied; April/May still carry a small residual from
            # an older query version.
            other = (row["TOTAL_INCENTIVE"] - row["ADJ_RBI"] - row["ADJ_COMM"]
                     - row["PERFORMANCE_INCENTIVE"] + row["TOTAL_OT"] + row["RAMADAN_PRIZE"])
            other = max(0.0, round(float(other), 2))

            pros[pid]["m"][label] = {
                "j": int(row["JOBS"]),
                "r": round(float(row["AVERAGE_RATING"]), 2),
                "rb": int(row["REBOOKING_COUNT"]),
                "you": round(float(row["EARNED"]), 2),      # full earned, for the "You earned" hero
                "yc": round(float(row["COMPARE"]), 2),      # rebooking + commission only, for the comparison bars
                "rbi": round(float(row["ADJ_RBI"]), 2),
                "comm": round(float(row["ADJ_COMM"]), 2),
                "tip": round(float(row["TOTAL_TIP"]), 2),
                "perf": round(float(row["PERFORMANCE_INCENTIVE"]), 2),
                "other": other,
                "peer": peer,
                "lb": lb,
            }

    # DATA object
    data = {
        pid: {"name": info["name"], "cat": info["cat"], "m": info["m"]}
        for pid, info in pros.items()
    }

    # NAMES list -- only pros who were active (JOBS > 0) in at least one month
    active_pids = set()
    for df in month_dfs.values():
        active_pids.update(df[df["JOBS"] > 0]["PROVIDER_ID"].tolist())

    name_entries = [
        {"pid": pid, "display_name": info["name"], "city": info["city"], "cat": info["cat"]}
        for pid, info in pros.items()
        if pid in active_pids
    ]
    disambiguate_labels(name_entries)
    name_entries.sort(key=lambda e: (e["cat"], e["label"]))
    names = [{"l": e["pid"], "label": e["label"], "cat": e["cat"]} for e in name_entries]

    data_json = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    names_json = json.dumps(names, separators=(",", ":"), ensure_ascii=False)
    boards_json = json.dumps(boards, separators=(",", ":"), ensure_ascii=False)

    template = open(TEMPLATE_PATH, encoding="utf-8").read()
    output = (template.replace("__DATA__", data_json)
                       .replace("__NAMES__", names_json)
                       .replace("__BOARDS__", boards_json))

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(output)

    print(f"Wrote {OUTPUT_PATH}: {len(pros)} pros total, {len(names)} active in dropdown, "
          f"across {len(months)} months ({', '.join(months)}).")


if __name__ == "__main__":
    main()
