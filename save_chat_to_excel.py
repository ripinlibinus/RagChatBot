# save_chat_to_excel.py
import os
import json
import datetime as dt
import pandas as pd
from typing import Dict, Any, List

EXCEL_PATH = "uji_mysql.xlsx"
SHEET_NAME = "testing"

# Urutan kolom yang diinginkan (boleh ditambah sesuai kebutuhan)
BASE_COLUMNS = [
    "timestamp",
    "chat_session_id",
    "human",
    "ai",
    "method",
    "input_token",
    "output_token",
    "total_token",
    "response_count",
    "response_time",
    "cost_usd",
    "cost_idr",
    "doc",
    "gold",
    # kolom hasil flatten json
    # "json_keyword",
    # "json_jenis_properti",
    # "json_page",
    # "json_paginate",
]

def _to_row(record: Dict[str, Any]) -> Dict[str, Any]:
    """Ubah dict hasil chat menjadi 1 baris siap tulis ke Excel (flatten JSON)."""
    row = {k: None for k in BASE_COLUMNS}
    row["timestamp"] = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Ambil kolom top-level kalau ada
    for k in [
        "chat_session_id", "human", "ai", "method", "input_token", "output_token",
        "total_token", "response_count", "response_time", "cost_usd", "cost_idr","doc","gold"
    ]:
        if k in record:
            row[k] = record[k]

    # Flatten bagian `json`
    # json_part = record.get("json", {}) or {}
    # if isinstance(json_part, dict):
    #     row["json_keyword"]        = json_part.get("keyword")
    #     row["json_jenis_properti"] = json_part.get("jenis_properti")
    #     row["json_page"]           = json_part.get("page")
    #     row["json_paginate"]       = json_part.get("paginate")
    #     row["json_raw"]            = json.dumps(json_part, ensure_ascii=False)
    # else:
    #     # Kalau bukan dict, simpan apa adanya sebagai raw string
    
    # row["json_raw"] = str(json_part)

    return row

def append_record_to_excel(record: Dict[str, Any],
                           excel_path: str = EXCEL_PATH,
                           sheet_name: str = SHEET_NAME) -> None:
    """Append 1 record (dict) ke file Excel. Buat file jika belum ada."""
    row = _to_row(record)

    # Jika file belum ada → tulis langsung dengan header
    if not os.path.exists(excel_path):
        df = pd.DataFrame([row], columns=BASE_COLUMNS)
        with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name=sheet_name)
        print(f"Created {excel_path} with first row.")
        return

    # Jika file ada → baca, concat, tulis ulang
    try:
        existing = pd.read_excel(excel_path, sheet_name=sheet_name, dtype=str)
    except ValueError:
        # Sheet belum ada → buat sheet baru
        existing = pd.DataFrame(columns=BASE_COLUMNS)

    # Pastikan semua kolom ada (union)
    all_cols = list(dict.fromkeys(list(existing.columns) + BASE_COLUMNS))
    new_df = pd.DataFrame([row], columns=all_cols)

    # Reindex existing agar kolomnya sejajar
    existing = existing.reindex(columns=all_cols)
    out = pd.concat([existing, new_df], ignore_index=True)

    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        out.to_excel(writer, index=False, sheet_name=sheet_name)

    print(f"Appended 1 row to {excel_path}:{sheet_name} (total rows: {len(out)})")

def append_many(records: List[Dict[str, Any]],
                excel_path: str = EXCEL_PATH,
                sheet_name: str = SHEET_NAME) -> None:
    """Lebih efisien untuk batch: kumpulkan semua rows lalu tulis sekaligus (append-style)."""
    rows = [_to_row(r) for r in records]

    if not os.path.exists(excel_path):
        df = pd.DataFrame(rows, columns=BASE_COLUMNS)
        with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name=sheet_name)
        print(f"Created {excel_path} with {len(df)} rows.")
        return

    try:
        existing = pd.read_excel(excel_path, sheet_name=sheet_name, dtype=str)
    except ValueError:
        existing = pd.DataFrame(columns=BASE_COLUMNS)

    all_cols = list(dict.fromkeys(list(existing.columns) + BASE_COLUMNS))
    existing = existing.reindex(columns=all_cols)
    new_df = pd.DataFrame(rows, columns=all_cols)
    out = pd.concat([existing, new_df], ignore_index=True)

    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        out.to_excel(writer, index=False, sheet_name=sheet_name)

    print(f"Appended {len(rows)} rows to {excel_path}:{sheet_name} (total rows: {len(out)})")

if __name__ == "__main__":
    # ====== CONTOH PAKAI (1 per 1) ======
    sample = {
        'json': {'keyword': 'Cemara', 'jenis_properti': 1, 'page': 1, 'paginate': 5},
        'chat_session_id': '628126577345',
        'human': 'cari rumah di cemara',
        'ai': 'Berikut adalah beberapa pilihan rumah di area Cemara: ...',
        'method': 'mysql',
        'input_token': 2458,
        'output_token': 475,
        'total_token': 2933,
        'response_count': 4,
        'response_time': 14397.112400009064,
        'cost_usd': 0.0006536999999999999,
        'cost_idr': 11.112899999999998
    }
    append_record_to_excel(sample)

    # ====== CONTOH PAKAI (batch) ======
    # append_many([sample, sample, sample])
