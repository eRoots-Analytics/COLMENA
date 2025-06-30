import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import matplotlib.colors as mcolors

# Load the CSV
df = pd.read_csv("data_2.csv")
# Use the "Time [s]" column as the x-axis
time = df["Time [s]"]

# Define omega columns to plot
omega_cols = [f"omega GENROU {i}" for i in range(1, 5)]

# Check that all required columns are present
missing = [col for col in omega_cols if col not in df.columns]
if missing:
    raise ValueError(f"Missing columns in CSV: {missing}")

plt.figure(figsize=(14, 6))
num_lines = len(omega_cols)
colors = cm.get_cmap('tab10', num_lines) 
for i, col in enumerate(omega_cols):
    plt.plot(time, df[col], label=col, color=colors(i), linewidth=1.5)

plt.xlabel("Time [s]", fontsize=12)
plt.ylabel("Frequency [Hz]", fontsize=12)
plt.title("Generator Frequency Time Series", fontsize=14)
plt.grid(True, alpha=0.3)

# Move legend outside
plt.legend(title="Generators", bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=10)
plt.tight_layout(rect=[0, 0, 0.85, 1])  # leave space on right for legend
plt.show()