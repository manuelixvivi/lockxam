import matplotlib.pyplot as plt
import numpy as np

# Data Evaluasi Kinerja (Contoh Ilustrasi untuk Laporan)
metrics = ["Akurasi Rubrik", "Konsistensi Nilai", "Kesesuaian Konteks Lokal", "Reduksi Halusinasi"]
before_rag = [75, 78, 45, 60]  # Kinerja Base Model (Qwen/Llama) tanpa RAG
after_rag = [92, 95, 96, 94]  # Kinerja Model setelah menggunakan RAG (Vector Search)

x = np.arange(len(metrics))
width = 0.35

fig, ax = plt.subplots(figsize=(10, 6))
rects1 = ax.bar(x - width / 2, before_rag, width, label="Sebelum RAG (Base Model)", color="#e74c3c")
rects2 = ax.bar(
    x + width / 2, after_rag, width, label="Setelah RAG (Equigrade AI)", color="#2ecc71"
)

# Add some text for labels, title and custom x-axis tick labels, etc.
ax.set_ylabel("Skor Persentase (%)", fontsize=12, fontweight="bold")
ax.set_title(
    "Peningkatan Kinerja Penilaian AI (Sebelum vs Setelah Implementasi RAG)",
    fontsize=14,
    fontweight="bold",
    pad=20,
)
ax.set_xticks(x)
ax.set_xticklabels(metrics, fontsize=11)
ax.legend(loc="lower right", fontsize=11)


# Attach a text label above each bar, displaying its height.
def autolabel(rects):
    """Attach a text label above each bar in *rects*, displaying its height."""
    for rect in rects:
        height = rect.get_height()
        ax.annotate(
            f"{height}%",
            xy=(rect.get_x() + rect.get_width() / 2, height),
            xytext=(0, 3),  # 3 points vertical offset
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontweight="bold",
        )


autolabel(rects1)
autolabel(rects2)

fig.tight_layout()

# Simpan grafik
output_file = "rag_evaluation_comparison.png"
plt.savefig(output_file, dpi=300)
print(f"Grafik berhasil disimpan sebagai {output_file}")
