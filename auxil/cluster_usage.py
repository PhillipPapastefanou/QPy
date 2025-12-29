import subprocess
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib import font_manager
import io
import os
from datetime import datetime

font_path = '/Net/Groups/Services/WWW/users/ppapastefanou/public_html/font/Sans/cmunss.ttf'
font_manager.fontManager.addfont(font_path)

# Set it as the global font using the font's internal name
# CMU Sans Serif's internal name is usually 'CMU Sans Serif'
plt.rcParams['font.family'] = 'CMU Sans Serif'


def get_slurm_output(cmd):
    """Executes a shell command and returns the string output."""
    try:
        return subprocess.check_output(cmd, shell=True).decode('utf-8')
    except Exception as e:
        print(f"Error running command: {e}")
        return ""

def to_tb(size_str):
    """Converts cluster size strings (20T, 125G, 500M) to numeric TB."""
    size_str = str(size_str).upper().strip()
    try:
        if 'T' in size_str:
            return float(size_str.replace('T', ''))
        elif 'G' in size_str:
            return float(size_str.replace('G', '')) / 1024
        elif 'M' in size_str:
            return float(size_str.replace('M', '')) / (1024**2)
        elif 'K' in size_str:
            return float(size_str.replace('K', '')) / (1024**3)
        return float(size_str) / 1024 # Assume GB if no unit provided
    except (ValueError, TypeError):
        return 0.0


# 1. Define the commands exactly as you provided them
user_cmd = (
    "squeue -h -o '%u %P %T %C' | "
    "awk '$3 == \"RUNNING\" {key=$1\" \"$2; cores[key]+=$4} "
    "END {for (k in cores) print k, cores[k]}' | sort"
)

sinfo_cmd = "sinfo -o '%20P %.10c %.15C %.10D %.15F'"

# 2. Get the data
user_output = get_slurm_output(user_cmd)
sinfo_output = get_slurm_output(sinfo_cmd)

# 3. Parse User Data (Format: User Partition Cores)
user_rows = []
for line in user_output.strip().split('\n'):
    if line.strip():
        parts = line.split()
        if len(parts) == 3:
            user_rows.append([parts[0], parts[1], int(parts[2])])
df_user = pd.DataFrame(user_rows, columns=['User', 'Partition', 'Cores'])

# 4. Parse Sinfo Data (Format: PARTITION CPUS CPUS(A/I/O/T) ...)
sinfo_rows = []
for line in sinfo_output.strip().split('\n'):
    # Skip header or empty lines
    if "PARTITION" in line or not line.strip():
        continue
    parts = line.split()
    if len(parts) >= 3:
        p_name = parts[0].strip('*')
        # Split the A/I/O/T string (Allocated/Idle/Other/Total)
        counts = parts[2].split('/')
        if len(counts) == 4:
            sinfo_rows.append({
                'Partition': p_name,
                'Allocated': int(counts[0]),
                'Idle': int(counts[1]),
                'Other': int(counts[2]),
                'Total': int(counts[3])
            })
df_part = pd.DataFrame(sinfo_rows)

# 5. Aggregate and Plot
df_user_total = df_user.groupby("User")["Cores"].sum().sort_values(ascending=True)

today = datetime.now().strftime("%Y_%m_%d")
file_dir = "/Net/Groups/BSI/work_scratch/" # Update this path
file_name = f"QUOTA_{today}.txt"
quota_file = os.path.join(file_dir, file_name)

total_b = 276969475584
total_tb = total_b / (1024**3)




fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(12, 8))

try:
    df = pd.read_csv(quota_file, sep=r'\s+', engine='python')
# Apply the TB conversion
    df['Size_TB'] = df['CurSize'].apply(to_tb)
       
    df_users = df[~df['Name'].str.contains('BSI', case=False, na=False)].copy()

    bsi_row = df[df['Name'] == 'BSI']
     
    # Sort descending and take top 10
    top_10 = df_users.sort_values(by='Size_TB', ascending=False).head(10)
    # Plotting to ax3
    ax3.clear()
    # Using a horizontal bar chart (barh) is often better for many users
    bars = ax3.bar(top_10['Name'], top_10['Size_TB'], color='teal')
    
    ax3.set_title(f"Top 10 Storage Users ({datetime.now().strftime("%d/%m/%Y")})", fontweight='bold', fontsize=12)
    ax3.set_ylabel("Usage (TB)", fontweight='bold')
    ax3.tick_params(axis='x', rotation=45)
    
    # Add the original text labels (like '20T') on top of bars for clarity
    ax3.bar_label(bars, labels=top_10['CurSize'], padding=3, fontsize=8)
        
    if not bsi_row.empty:
        bsi_usage_tb = to_tb(bsi_row['CurSize'].values[0])
        available_tb = total_tb - bsi_usage_tb
        available_pc = available_tb/total_tb*100.0

        stats_text = (f"BSI: {bsi_usage_tb:.1f} TB used out of {total_tb:.1f} TB\n"
                  f"Available: {available_tb:.1f} TB ({available_pc:.1f}%)")
    
        # Add this text to your plot (e.g., in the corner of ax3 or a separate title)
        ax3.text(0.95, 0.95, stats_text, transform=ax3.transAxes, 
                verticalalignment='top', horizontalalignment='right',
                bbox=dict(boxstyle='round', facecolor='white', alpha=0.5),
                fontsize=10, fontweight='bold')
except FileNotFoundError:
    print(f"Error: The file {quota_file} does not exist yet for today.")

# --- Plot 1: Cluster Health ---
p1 = ax1.barh(df_part["Partition"], df_part["Allocated"], color='tab:red', label='Allocated')
p2 = ax1.barh(df_part["Partition"], df_part["Idle"], left=df_part["Allocated"], color='tab:blue', label='Idle')
p3 = ax1.barh(df_part["Partition"], df_part["Other"], left=df_part["Allocated"]+df_part["Idle"], color='#95a5a6', label='Other')

# Define custom label lists: Only show if value > 0
labels_p1 = [f'U: {v}' if v > 0 else '' for v in df_part["Allocated"]]
labels_p2 = [f'I: {v}' if v > 0 else '' for v in df_part["Idle"]]
labels_p3 = [f'O: {v}' if v > 0 else '' for v in df_part["Other"]]

# Apply the labels to the center of each stack
ax1.bar_label(p1, labels=labels_p1, label_type='center', color='white', fontweight='bold', fontsize=9)
ax1.bar_label(p2, labels=labels_p2, label_type='center', color='white', fontweight='bold', fontsize=9)
ax1.bar_label(p3, labels=labels_p3, label_type='center', color='black', fontsize=9)

# Add the TOTAL (Sum) at the very end of the bar
total_cores = df_part["Allocated"] + df_part["Idle"] + df_part["Other"]
ax1.bar_label(p3, labels=[fr'$\Sigma$: {val}' for val in total_cores], padding=8, fontweight='bold')
timestamp = datetime.now().strftime("%H-%M-%S")
ax1.set_title("Cluster Core Utilization", fontweight='bold', loc='center')
ax1.set_title(f"Time: {timestamp}", loc='left', fontsize=10, color='gray') # Added datestring to left
ax1.set_xlabel("Cores")
ax1.legend(loc='upper right')


# --- Plot 2: Top Users ---
p_user = ax2.barh(df_user_total.index, df_user_total.values, color='#3498db')

# 1. Labels for large bars: Place INSIDE
# Only show if value >= 200
labels_inside = [f'{v}' if v >= 200 else '' for v in df_user_total.values]
ax2.bar_label(p_user, labels=labels_inside, label_type='center', color='white', fontweight='bold')

# 2. Labels for small bars: Place OUTSIDE
# Only show if 0 < value < 200
labels_outside = [f'{v}' if 0 < v < 200 else '' for v in df_user_total.values]
ax2.bar_label(p_user, labels=labels_outside, label_type='edge', padding=5, color='black')

ax2.set_title("Core Usage by User (All Partitions)", fontweight='bold')
ax2.set_xlabel("Cores")

# Ensure the X-axis has enough room for the outside labels
ax2.set_xlim(0, df_user_total.values.max() * 1.1)

plt.tight_layout()
#plt.show()
plt.savefig("/Net/Groups/Services/WWW/users/ppapastefanou/public_html/cluster_report.png", dpi= 150)
#print("Report saved to cluster_report.png")