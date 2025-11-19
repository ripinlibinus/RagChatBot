import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.metrics import confusion_matrix

# ============================================================
# 1. LOAD DATA
# ============================================================
# File hasil evaluasi yang sudah kamu punya
reca = pd.read_excel("eval/recap.xlsx")      # PCA, Strict, CPR, NR per query
recap = pd.read_excel("eval/recap1.xlsx")   # acc_vec, acc_api, acc_hyb per query

# ------------------------------------------------------------
# 2. BAR CHART: SUMMARY METRICS PER PIPELINE
#    (PCA, Strict Success, CPR, No Result, Accuracy)
# ------------------------------------------------------------

# Hitung mean per metric per pipeline dari data yang ada
metrics = ["PCA", "Strict", "CPR", "NR", "Acc"]
pipelines = ["Vector", "API", "Hybrid"]

mean_values = {
    "Vector": [],
    "API": [],
    "Hybrid": [],
}

# PCA
mean_values["Vector"].append(reca["PCA_vec"].mean(skipna=True))
mean_values["API"].append(reca["PCA_api"].mean(skipna=True))
mean_values["Hybrid"].append(reca["PCA_hyb"].mean(skipna=True))

# Strict Success
mean_values["Vector"].append(reca["SS_vec"].mean(skipna=True))
mean_values["API"].append(reca["SS_api"].mean(skipna=True))
mean_values["Hybrid"].append(reca["SS_hyb"].mean(skipna=True))

# CPR
mean_values["Vector"].append(reca["CPR_vec"].mean(skipna=True))
mean_values["API"].append(reca["CPR_api"].mean(skipna=True))
mean_values["Hybrid"].append(reca["CPR_hyb"].mean(skipna=True))

# No Result Score
mean_values["Vector"].append(reca["NR_vec"].mean(skipna=True))
mean_values["API"].append(reca["NR_api"].mean(skipna=True))
mean_values["Hybrid"].append(reca["NR_hyb"].mean(skipna=True))

# Accuracy dari recap1
mean_values["Vector"].append(recap["acc_vec"].mean())
mean_values["API"].append(recap["acc_api"].mean())
mean_values["Hybrid"].append(recap["acc_hyb"].mean())

# Plot grouped bar chart
x = np.arange(len(metrics))   # posisi group
width = 0.25                  # lebar bar

fig, ax = plt.subplots()
ax.bar(x - width, mean_values["Vector"], width, label="Vector")
ax.bar(x,          mean_values["API"],   width, label="API")
ax.bar(x + width,  mean_values["Hybrid"],width, label="Hybrid")

ax.set_xticks(x)
ax.set_xticklabels(metrics)
ax.set_ylabel("Score")
ax.set_ylim(0, 1.05)
ax.set_title("Summary metrics per pipeline")
ax.legend()
ax.grid(axis="y", linestyle="--", alpha=0.4)

plt.tight_layout()
plt.show()

# ------------------------------------------------------------
# 3. BOX PLOT: DISTRIBUSI PCA PER PIPELINE
# ------------------------------------------------------------
pca_vec = reca["PCA_vec"].dropna()
pca_api = reca["PCA_api"].dropna()
pca_hyb = reca["PCA_hyb"].dropna()

fig, ax = plt.subplots()
ax.boxplot([pca_vec, pca_api, pca_hyb], labels=["Vector", "API", "Hybrid"])

ax.set_ylabel("PCA score")
ax.set_title("PCA distribution per pipeline")
ax.grid(axis="y", linestyle="--", alpha=0.4)

plt.tight_layout()
plt.show()

# ------------------------------------------------------------
# 4. CONFUSION MATRIX HEATMAP UNTUK SETIAP PIPELINE
# ------------------------------------------------------------
"""
Bagian ini BUTUH file tambahan, misalnya 'cm_data.xlsx', dengan kolom:
- y_true       : label gold (0/1)
- y_pred_vec   : prediksi pipeline Vector (0/1)
- y_pred_api   : prediksi pipeline API (0/1)
- y_pred_hyb   : prediksi pipeline Hybrid (0/1)

Contoh isi:
query_id | y_true | y_pred_vec | y_pred_api | y_pred_hyb
1        |   1    |     1      |     1      |     0
2        |   0    |     1      |     0      |     0
...

Kalau file ini sudah kamu buat, aktifkan kode di bawah.
"""

try:
    cm_df = pd.read_excel("eval/cm_data.xlsx")

    def plot_cm(y_true, y_pred, title):
        cm = confusion_matrix(y_true, y_pred)  # shape (2,2) untuk binary class
        fig, ax = plt.subplots()
        im = ax.imshow(cm)  # pakai colormap default

        ax.set_title(title)
        ax.set_xlabel("Predicted label")
        ax.set_ylabel("True label")
        ax.set_xticks([0, 1])
        ax.set_yticks([0, 1])

        # tulis angka di tiap sel
        for i in range(cm.shape[0]):
            for j in range(cm.shape[1]):
                ax.text(j, i, str(cm[i, j]),
                        ha="center", va="center")

        plt.tight_layout()
        plt.show()

    # Confusion matrix per pipeline
    plot_cm(cm_df["y_true"], cm_df["y_pred_vec"], "Confusion Matrix - Vector")
    plot_cm(cm_df["y_true"], cm_df["y_pred_api"], "Confusion Matrix - API")
    plot_cm(cm_df["y_true"], cm_df["y_pred_hyb"], "Confusion Matrix - Hybrid")

except FileNotFoundError:
    print("cm_data.xlsx tidak ditemukan. Buat dulu file ini untuk confusion matrix heatmap.")
