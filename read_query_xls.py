import json
from pathlib import Path
import pandas as pd

def build_answer_gold_list(
    excel_path: str | Path,
    sheet_name: str | int = 0,     # <- default ke sheet pertama (bukan None)
    answer_col: str = "ai",
    gold_col: str = "gold",
    drop_empty: bool = True
) -> list[dict]:
    """
    Kembalikan: [{"answer": <kolom ai>, "gold": <kolom gold>}, ...]
    """
    excel_path = Path(excel_path)

    # Baca Excel
    try:
        df = pd.read_excel(excel_path, sheet_name=sheet_name)
    except Exception as e:
        raise RuntimeError(
            f"Gagal membaca Excel. Pastikan file ada dan paket 'openpyxl' terpasang. Detail: {e}"
        )

    # Jika user tetap pakai sheet_name=None, df akan berupa dict -> ambil sheet pertama
    if isinstance(df, dict):
        if not df:
            raise RuntimeError("Workbook tidak memiliki sheet.")
        # ambil DataFrame dari sheet pertama sesuai urutan kunci
        first_key = next(iter(df.keys()))
        df = df[first_key]

    # Validasi kolom
    missing = [c for c in (answer_col, gold_col) if c not in df.columns]
    if missing:
        raise KeyError(f"Kolom berikut tidak ditemukan: {missing}. "
                       f"Kolom tersedia: {list(df.columns)}")

    # Normalisasi NaN -> string kosong
    df[answer_col] = df[answer_col].fillna("")
    df[gold_col]   = df[gold_col].fillna("")

    items = []
    for _, row in df.iterrows():
        answer = row[answer_col]
        gold = row[gold_col]
        if drop_empty and (str(answer).strip() == "" and str(gold).strip() == ""):
            continue
        items.append({"answer": answer, "gold": gold})

    return items

if __name__ == "__main__":
    excel_file = "uji_rag_mysql.xlsx"
    result = build_answer_gold_list(excel_file, sheet_name=0)
    print(result)

    # (opsional) simpan ke JSON
    # out_path = Path("answer_gold_list.json")
    # out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    # print(f"Disimpan ke: {out_path.resolve()}")
