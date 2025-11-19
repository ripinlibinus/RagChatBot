# analyze_accuracy.py
# Hitung statistik Accuracy (mean, 95% CI, p-value, % improvement)
# dari file recap1.xlsx dengan kolom:
# query_id, acc_vec, acc_api, acc_hyb

import pandas as pd
import numpy as np
from scipy import stats
import math

FILE_PATH = "eval/recap1.xlsx"  # ubah kalau nama file beda

# ===============================
# 1) Load data
# ===============================
df = pd.read_excel(FILE_PATH)

# Pastikan kolom yang dibutuhkan ada
required_cols = ["acc_vec", "acc_api", "acc_hyb"]
for c in required_cols:
    if c not in df.columns:
        raise ValueError(f"Kolom {c} tidak ditemukan di {FILE_PATH}")

# ===============================
# 2) Util: 95% CI & marker signifikan
# ===============================
def ci95(arr):
    """
    Hitung mean dan 95% CI untuk array 1D (0/1).
    Menggunakan t-distribution (cocok untuk N kecil).
    """
    arr = np.asarray(arr, dtype=float)
    arr = arr[~np.isnan(arr)]
    N = len(arr)
    mean = arr.mean()
    if N < 2:
        return mean, math.nan, math.nan, N
    std = arr.std(ddof=1)
    se = std / math.sqrt(N)
    tcrit = stats.t.ppf(0.975, df=N-1)  # 95% CI two-sided
    lo = mean - tcrit * se
    hi = mean + tcrit * se
    return mean, lo, hi, N

def sig_marker(p):
    """
    Kembalikan *, **, *** tergantung nilai p.
    """
    if p is None or math.isnan(p):
        return ""
    if p < 0.001:
        return "***"
    if p < 0.01:
        return "**"
    if p < 0.05:
        return "*"
    return ""

# ===============================
# 3) Hitung mean & CI per metode
# ===============================
methods = {
    "Vector": "acc_vec",
    "API":    "acc_api",
    "Hybrid": "acc_hyb",
}

print("=== MEAN ACCURACY & 95% CI PER METODE ===")
for name, col in methods.items():
    mean, lo, hi, N = ci95(df[col])
    print(f"{name:6s}: mean={mean:.3f}, 95% CI=[{lo:.3f}, {hi:.3f}], N={N}")
print()

# ===============================
# 4) Paired t-test antar metode
# ===============================
pairs = [
    ("Hybrid", "API"),    # baseline utama
    ("Hybrid", "Vector"),
    ("API",    "Vector"),
]

print("=== PAIRED T-TEST & % IMPROVEMENT (Accuracy) ===")
for m_a, m_b in pairs:
    col_a = methods[m_a]
    col_b = methods[m_b]

    # Pastikan panjang sama & drop NaN kalau ada
    a = df[col_a].astype(float).to_numpy()
    b = df[col_b].astype(float).to_numpy()
    mask = ~np.isnan(a) & ~np.isnan(b)
    a = a[mask]
    b = b[mask]

    if len(a) < 2:
        print(f"{m_a} vs {m_b}: sampel terlalu sedikit, N={len(a)}")
        continue

    # Paired t-test
    t_stat, p_val = stats.ttest_rel(a, b)

    # Selisih per query
    diff = a - b
    d_mean, d_lo, d_hi, N = ci95(diff)

    # Mean accuracy per metode (di subset yang sama)
    mean_a, _, _, _ = ci95(a)
    mean_b, _, _, _ = ci95(b)

    # Improvement (karena accuracy: semakin besar semakin baik)
    abs_gain = mean_a - mean_b
    rel_impr = abs_gain / mean_b * 100 if mean_b != 0 else math.nan

    mark = sig_marker(p_val)

    print(f"{m_a} vs {m_b}:")
    print(f"  {m_a:6s} Acc = {mean_a:.3f}")
    print(f"  {m_b:6s} Acc = {mean_b:.3f}")
    print(f"  Δmean ({m_a} - {m_b}) = {d_mean:.3f}, "
          f"95% CI=[{d_lo:.3f}, {d_hi:.3f}], "
          f"p={p_val:.4f} {mark}")
    print(f"  Improvement of {m_a} over {m_b}: "
          f"{abs_gain:.3f} ({rel_impr:.1f}%)")
    print()
