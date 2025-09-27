import pandas as pd
import matplotlib.pyplot as plt
import os

tree_id = '232'

# Read CSV
df = pd.read_csv(
    os.path.join("data", "atto_psi_leaf", "LeafWaterPotential_0926_0927.csv"),
    decimal=",", sep=";", index_col=0
)
df.columns = df.columns.str.strip()

# Convert Collected time -> fractional hours
df["time_float"] = pd.to_datetime(df["Collected time"], format="%H:%M").dt.hour + \
                   pd.to_datetime(df["Collected time"], format="%H:%M").dt.minute / 60

# Filter for given TreeID
tree_df = df[df["TreeID"].astype(str) == tree_id]

# Group only by time (all leaves combined)
grouped = tree_df.groupby("time_float").agg(
    avg=("Leaf water potential", "mean"),
    std=("Leaf water potential", "std")
).reset_index()

# Plot
plt.figure(figsize=(10, 6))
plt.errorbar(
    grouped["time_float"],
    grouped["avg"],
    yerr=grouped["std"],
    capsize=4,
    marker="o",
    linestyle="--",
    color="tab:blue",
    label=f"Tree {tree_id}"
)

plt.xlabel("Time of Day (hours)")
plt.ylabel("Leaf water potential")
plt.title(f"Tree {tree_id} - Leaf Water Potential with Std Error Bars (all leaves)")
plt.legend()
plt.tight_layout()
plt.show()
