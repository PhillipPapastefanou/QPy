import subprocess
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib import font_manager
import os
from datetime import datetime
from matplotlib.offsetbox import OffsetImage, AnnotationBbox

# --- Configuration & Paths ---
FONT_PATH = '/Net/Groups/Services/WWW/users/ppapastefanou/public_html/font/Sans/cmunss.ttf'
SAVE_PATH = "/Net/Groups/Services/WWW/users/ppapastefanou/public_html/cluster_report.png"

# Storage Configs
WORK_SCRATCH_QUOTA_DIR = "/Net/Groups/BSI/work_scratch/"
SCRATCH_QUOTA_DIR = "/Net/Groups/BSI/scratch/"
WORK_SCRATCH_TOTAL_STORAGE_B = 276969475584 
SCRATCH_TOTAL_STORAGE_B = 153871930880 
icon_path = "/Net/Groups/BSI/work_scratch/ppapastefanou/src/QPy/auxil/2545.png"

if os.path.exists(FONT_PATH):
    font_manager.fontManager.addfont(FONT_PATH)
    # Set CMU Sans Serif as primary, but DejaVu Sans as fallback for emojis
    plt.rcParams['font.family'] = ['CMU Sans Serif', 'DejaVu Sans', 'sans-serif']

# --- Utility Functions ---

def get_slurm_output(cmd):
    try:
        return subprocess.check_output(cmd, shell=True).decode('utf-8')
    except Exception as e:
        print(f"Error running command: {e}")
        return ""

def to_tb(size_str):
    size_str = str(size_str).upper().strip()
    try:
        multipliers = {'T': 1, 'G': 1024, 'M': 1024**2, 'K': 1024**3}
        for unit, div in multipliers.items():
            if unit in size_str:
                return float(size_str.replace(unit, '')) / div
        return float(size_str) / 1024 
    except (ValueError, TypeError):
        return 0.0

# --- Modular Plotting Functions ---

def plot_cluster_health(ax, df_part):
    p1 = ax.barh(df_part["Partition"], df_part["Allocated"], color='tab:red', label='Allocated')
    p2 = ax.barh(df_part["Partition"], df_part["Idle"], left=df_part["Allocated"], color='tab:blue', label='Idle')
    p3 = ax.barh(df_part["Partition"], df_part["Other"], left=df_part["Allocated"]+df_part["Idle"], color='#95a5a6', label='Other')

    ax.bar_label(p1, labels=[f'U: {v}' if v > 0 else '' for v in df_part["Allocated"]], label_type='center', color='white', fontweight='bold', fontsize=8)
    ax.bar_label(p2, labels=[f'I: {v}' if v > 0 else '' for v in df_part["Idle"]], label_type='center', color='white', fontweight='bold', fontsize=8)
    
    total_cores = df_part["Allocated"] + df_part["Idle"] + df_part["Other"]
    ax.bar_label(p3, labels=[fr'$\Sigma$: {val}' for val in total_cores], padding=8, fontweight='bold', fontsize=9)
    
    ax.set_title("Cluster Core Utilization", fontweight='bold')
    ax.set_title(f"Time: {datetime.now().strftime('%H:%M:%S')}", loc='left', fontsize=9, color='gray')
    ax.legend(loc='upper right', fontsize=8)

def plot_user_cores(ax, df_user_total):
    p_user = ax.barh(df_user_total.index, df_user_total.values, color='#3498db')
    ax.bar_label(p_user, labels=[f'{v}' if v >= 200 else '' for v in df_user_total.values], label_type='center', color='white', fontweight='bold', fontsize=8)
    ax.bar_label(p_user, labels=[f'{v}' if 0 < v < 200 else '' for v in df_user_total.values], label_type='edge', padding=5, fontsize=8)

    ax.set_title("Core Usage by User (All Partitions)", fontweight='bold')
    ax.set_xlim(0, df_user_total.values.max() * 1.2)

def plot_storage_usage(ax, quota_file, total_bytes, title_label):
    """Generic storage plotter with a special Zen highlight for szaehle."""
    total_capacity_tb = total_bytes / (1024**3)
    try:
        df = pd.read_csv(quota_file, sep=r'\s+', engine='python')
        df['Size_TB'] = df['CurSize'].apply(to_tb)
        
        df_users = df[~df['Name'].str.contains('BSI', case=False, na=False)].copy()
        top_10 = df_users.sort_values(by='Size_TB', ascending=False).head(10)
        
        # Determine colors: Default based on partition, but Gold for the Zen Master
        colors = []
        base_color = 'teal' if 'Work' in title_label else 'orchid'
        for name in top_10['Name']:
            colors.append(base_color)

        bars = ax.bar(top_10['Name'], top_10['Size_TB'], color=colors)
        ax.set_title(f"{title_label} Top 10", fontweight='bold')
        ax.set_ylabel("Usage (TB)")
        ax.tick_params(axis='x', rotation=45, labelsize=9)
        
        # Standard labels (Usage strings like '20T')
        labels_outside = [row['CurSize'] if row['Name'] != 'szaehle' else '' for _, row in top_10.iterrows()]
        ax.bar_label(bars, labels=labels_outside, padding=3, fontsize=8)
        
        
        for bar, name, size in zip(bars, top_10['Name'], top_10['CurSize']):
            if name == 'szaehle':
                # Calculate position: center of bar, slightly below the top edge
                x_pos = bar.get_x() + bar.get_width() / 2
                y_pos = bar.get_height() * 0.9  # 90% of the height (just inside the top)
                
                ax.text(x_pos, y_pos, size, 
                        ha='center', va='top', 
                        fontsize=8, color='white', fontweight='bold')

    # Find the 'szaehle' bar and highlight it
        for bar, name in zip(bars, top_10['Name']):
            if name == 'szaehle':
                
                # Load and place the icon
                try:
                    img = plt.imread(icon_path)
                    imagebox = OffsetImage(img, zoom=0.1) # Adjust zoom as needed
                    # Place icon at the top of the bar
                    ab = AnnotationBbox(imagebox, (bar.get_x() + bar.get_width()/2, bar.get_height()),
                                        frameon=False, box_alignment=(0.5, -0.1))
                    ax.add_artist(ab)
                except Exception as e:
                    print(f"Could not load image: {e}")
        # -----------------------------

        # Summary box (Total vs Avail)
        bsi_row = df[df['Name'] == 'BSI']
        if not bsi_row.empty:
            bsi_usage_tb = to_tb(bsi_row['CurSize'].values[0])
            avail_tb = total_capacity_tb - bsi_usage_tb
            stats_text = (f"Total: {bsi_usage_tb:.1f} / {total_capacity_tb:.1f} TB\n"
                          f"Avail: {avail_tb:.1f} TB ({(avail_tb/total_capacity_tb)*100:.1f}%)")
            ax.text(0.95, 0.95, stats_text, transform=ax.transAxes, verticalalignment='top', horizontalalignment='right',
                    bbox=dict(boxstyle='round', facecolor='white', alpha=0.7), fontsize=8, fontweight='bold')
            
    except Exception:
        ax.text(0.5, 0.5, "Data Unavailable", ha='center', va='center')
# --- Main Logic ---

def main():
    # 1. Fetch Slurm Data
    user_cmd = "squeue -h -o '%u %P %T %C' | awk '$3 == \"RUNNING\" {key=$1\" \"$2; cores[key]+=$4} END {for (k in cores) print k, cores[k]}' | sort"
    sinfo_cmd = "sinfo -o '%20P %.10c %.15C %.10D %.15F'"
    
    # Process Sinfo
    sinfo_out = get_slurm_output(sinfo_cmd)
    sinfo_rows = []
    for line in sinfo_out.strip().split('\n')[1:]:
        parts = line.split()
        if len(parts) >= 3:
            counts = parts[2].split('/')
            sinfo_rows.append({'Partition': parts[0].strip('*'), 'Allocated': int(counts[0]), 'Idle': int(counts[1]), 'Other': int(counts[2])})
    df_part = pd.DataFrame(sinfo_rows)

    # Process User Cores
    user_out = get_slurm_output(user_cmd)
    user_rows = [line.split() for line in user_out.strip().split('\n') if line.strip()]
    df_user = pd.DataFrame(user_rows, columns=['User', 'Partition', 'Cores'])
    df_user['Cores'] = df_user['Cores'].astype(int)
    df_user_total = df_user.groupby("User")["Cores"].sum().sort_values()

    # 2. Setup Figure
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(14, 8))
    
    # Core Plots
    plot_cluster_health(ax1, df_part)
    plot_user_cores(ax2, df_user_total)
    
    # Storage Plots (Modular usage)
    date_str = datetime.now().strftime('%Y_%m_%d')
    
    # Work_Scratch (AX3)
    work_file = os.path.join(WORK_SCRATCH_QUOTA_DIR, f"QUOTA_{date_str}.txt")
    plot_storage_usage(ax3, work_file, WORK_SCRATCH_TOTAL_STORAGE_B, "Work_Scratch")
    
    # Scratch (AX4)
    scratch_file = os.path.join(SCRATCH_QUOTA_DIR, f"QUOTA_{date_str}.txt")
    plot_storage_usage(ax4, scratch_file, SCRATCH_TOTAL_STORAGE_B, "Scratch")

    plt.tight_layout()
    plt.savefig(SAVE_PATH, dpi=150)
    print(f"Success: Report generated at {SAVE_PATH}")

if __name__ == "__main__":
    main()