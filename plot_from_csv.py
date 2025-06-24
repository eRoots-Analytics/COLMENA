import pandas as pd
import matplotlib.pyplot as plt

# Load the CSV
df = pd.read_csv("data_2.csv")

# Use the "Time [s]" column as the x-axis
time = df["Time [s]"]

# Define omega columns to plot
omega_cols = [f"omega GENROU {i}" for i in range(1, 11)]

# Check that all required columns are present
missing = [col for col in omega_cols if col not in df.columns]
if missing:
    raise ValueError(f"Missing columns in CSV: {missing}")

# Plot all omega GENROU time series
plt.figure(figsize=(12, 6))
for col in omega_cols:
    plt.plot(time, df[col], label=col)

plt.xlabel("Time [s]")
plt.ylabel("Omega")
plt.title("GENROU Omega Time Series (1–10)")
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.show()
