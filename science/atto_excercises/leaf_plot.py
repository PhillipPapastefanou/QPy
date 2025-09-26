import pandas as pd
import matplotlib.pyplot as plt
import os

df = pd.read_csv(os.path.join("data", "atto_psi_leaf", "Day1.csv"),
                 sep=";", decimal=",",   index_col=0)
groups = [1, 2]  # group IDs based on spec_pl_1_* and spec_pl_2_*
fig, axes = plt.subplots(len(groups), 1, figsize=(8, 6), sharex=True)

if len(groups) == 1:  # make axes iterable if only one group
    axes = [axes]
# Convert index "HH:MM" → float hours
df.index = pd.to_datetime(df.index, format="%H:%M").hour + pd.to_datetime(df.index, format="%H:%M").minute / 60

for ax, g in zip(axes, groups):
    cols = [c for c in df.columns if f"spec_pl_{g}_" in c]
    mean, std = df[cols].mean(axis=1), df[cols].std(axis=1)

    ax.errorbar(df.index, mean, yerr=std, fmt='o', capsize=5, c= 'black')
    ax.set_title(f"Group {g}")
    ax.set_ylabel("Average Value")
    ax.grid(True)

axes[-1].set_xlabel("Time of Day")
plt.xticks(rotation=45)
plt.tight_layout()
plt.show()