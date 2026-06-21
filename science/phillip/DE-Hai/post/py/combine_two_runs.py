import os
import shutil

source_dir = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/2023_bench/71_run_transient_3days_new_mort_new_phen_fix/output"       
dest_dir = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/2023_bench/temp/"   
OFFSET = 40000

# 1. Gather and sort all numeric folders to guarantee sequential execution order
numeric_folders = [f for f in os.listdir(source_dir) if os.path.isdir(os.path.join(source_dir, f)) and f.isdigit()]
numeric_folders.sort(key=int)  # Orders them strictly: 0, 1, 2... 39999

# 2. SAFETY FIRST: Run a pre-check to ensure NOTHING will be overridden
print("Running safety collision checks...")
collisions = []
for folder in numeric_folders:
    new_name = str(int(folder) + OFFSET)
    dest_path = os.path.join(dest_dir, new_name)
    if os.path.exists(dest_path):
        collisions.append(f"{folder} -> {new_name}")

if collisions:
    print("\n❌ ABORTING: Collision detected! The following target folders already exist:")
    for c in collisions[:10]:  # Print first 10 collisions
        print(f"  {c}")
    if len(collisions) > 10:
        print(f"  ... and {len(collisions) - 10} more.")
    print("\nNo files were moved.")
    exit(1) # Stop script execution immediately
else:
    print("✅ Clear! No collisions found. Proceeding with sequential move...\n")

# 3. Safe, ordered execution
for folder in numeric_folders:
    source_path = os.path.join(source_dir, folder)
    new_name = str(int(folder) + OFFSET)
    destination_path = os.path.join(dest_dir, new_name)
    
    print(f"Moving: {folder} ➡️ {new_name}")
    shutil.move(source_path, destination_path)

print("\n🎉 Ordered batch transfer complete with zero overrides!")