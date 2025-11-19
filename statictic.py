# file: analyze_reca_clean.py

import pandas as pd
import numpy as np
from scipy import stats

# ===============================
# 1) LOAD DATA
# ===============================
DF_PATH = "eval/recap.xlsx"
df = pd.read_excel(DF_PATH)

# Kalau mau NR NaN dianggap 0, bisa aktifkan ini:
# df[["NR_vec", "NR_api", "NR_hyb"]] = df[["NR_vec", "NR_api", "NR_hyb"]].fillna(0)

# ===============================
# 2) KONFIG METRIK & ARAH
# ===============================
# higher_better = True  → makin besar makin bagus
# higher_better = False → makin kecil makin bagus (untuk No Result Score)
METRICS = {
    "PCA":    {"higher_better": True},
    "Strict": {"higher_better": True},
    "CPR":    {"higher_better": True},
    "NR":     {"higher_better": False},
}

METHOD_COL_PREFIX = {
    "Vector": "vec",
    "API":    "api",
    "Hybrid": "hyb",
}

PAIRS = [
    ("Vector", "API"),
    ("Hybrid", "API"),   # baseline utama
    ("Hybrid", "Vector"),
]

# ===============================
# 3) UTIL: CI 95% & SIGNIFICANCE
# ===============================
def ci95_from_array(arr: np.ndarray):
    """Hitung mean dan 95% CI dari array 1D (tanpa NaN)."""
    arr = np.asarray(arr, dtype=float)
    N = len(arr)
    mean = arr.mean()
    if N < 2:
        return mean, np.nan, np.nan, N
    std = arr.std(ddof=1)
    se  = std / np.sqrt(N)
    tcrit = stats.t.ppf(0.975, df=N-1)  # two-sided 95%
    ci_low  = mean - tcrit * se
    ci_high = mean + tcrit * se
    return mean, ci_low, ci_high, N

def significance_marker(p):
    if p is None or np.isnan(p):
        return ""
    if p < 0.001:
        return "***"
    if p < 0.01:
        return "**"
    if p < 0.05:
        return "*"
    return ""

def analyze_pair(metric_name, method_a, method_b, higher_better=True):
    """
    Bandingkan method_a vs method_b UNTUK SATU METRIK dengan:
    - mean & 95% CI per metode (dari query yang punya kedua nilai)
    - paired t-test
    - absolute gain / reduction
    - relative improvement (%)
    """
    prefix_a = METHOD_COL_PREFIX[method_a]
    prefix_b = METHOD_COL_PREFIX[method_b]
    col_a = f"{metric_name}_{prefix_a}"
    col_b = f"{metric_name}_{prefix_b}"

    if col_a not in df.columns or col_b not in df.columns:
        print(f"[WARN] Kolom {col_a} atau {col_b} tidak ditemukan, skip.")
        return

    # Mask: hanya query yang PUNYA nilai di kedua metode
    mask = ~df[col_a].isna() & ~df[col_b].isna()
    sub_a = df.loc[mask, col_a].to_numpy(dtype=float)
    sub_b = df.loc[mask, col_b].to_numpy(dtype=float)

    if len(sub_a) < 2:
        print(f"[WARN] Terlalu sedikit sampel untuk {metric_name} {method_a} vs {method_b} (N={len(sub_a)}).")
        return

    # CI per metode (berdasarkan subset yang sama)
    mean_a, ci_a_low, ci_a_high, N_a = ci95_from_array(sub_a)
    mean_b, ci_b_low, ci_b_high, N_b = ci95_from_array(sub_b)

    # Paired t-test
    t_stat, p_val = stats.ttest_rel(sub_a, sub_b)
    diff = sub_a - sub_b
    mean_diff, ci_d_low, ci_d_high, N_d = ci95_from_array(diff)

    # Improvement
    if higher_better:
        # a lebih bagus dari b kalau nilainya lebih BESAR
        abs_gain = mean_a - mean_b
        rel_impr = abs_gain / mean_b * 100 if mean_b != 0 else np.nan
        direction_word = "improvement"
    else:
        # a lebih bagus dari b kalau nilainya lebih KECIL (reduction)
        abs_gain = mean_b - mean_a  # reduction (b - a)
        rel_impr = abs_gain / mean_b * 100 if mean_b != 0 else np.nan
        direction_word = "reduction"

    sig = significance_marker(p_val)

    print(f"\n===== {metric_name} — {method_a} vs {method_b} =====")
    print(f"N (common queries) = {N_a}")

    print(f"{method_a}: mean={mean_a:.3f}, 95% CI=[{ci_a_low:.3f}, {ci_a_high:.3f}]")
    print(f"{method_b}: mean={mean_b:.3f}, 95% CI=[{ci_b_low:.3f}, {ci_b_high:.3f}]")

    # Δmean = mean_a - mean_b (dalam arah 'a - b')
    print(f"Δmean ({method_a} - {method_b}) = {mean_diff:.3f}, "
          f"95% CI=[{ci_d_low:.3f}, {ci_d_high:.3f}], "
          f"p={p_val:.4f} {sig}")

    # Global improvement in direction of "a vs b"
    print(f"{direction_word.capitalize()} of {method_a} over {method_b}: "
          f"{abs_gain:.3f} ({rel_impr:.1f}%)")


# ===============================
# 4) MAIN: LOOP SEMUA METRIK & PAIRS
# ===============================
if __name__ == "__main__":
    for metric_name, cfg in METRICS.items():
        higher_better = cfg["higher_better"]
        print("\n" + "#" * 60)
        print(f"##########  METRIC: {metric_name}  ##########")
        print("#" * 60)
        for (m_a, m_b) in PAIRS:
            analyze_pair(metric_name, m_a, m_b, higher_better=higher_better)
