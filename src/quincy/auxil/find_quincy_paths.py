import os
import sys
from pathlib import Path
import json

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(THIS_DIR, os.pardir, os.pardir))

class QuincyPathFinder:
    def __init__(self):
        
        WORK_SCRATCH_DIR = "/Net/Groups/BSI/work_scratch"
        LOCAL_RES_DIR = os.path.join(THIS_DIR, os.pardir,os.pardir, os.pardir, "local")
        
        paths= {}            
        if os.path.exists(os.path.join(LOCAL_RES_DIR, "paths.json")):
            print("Found saved local QUINCY dir!")
            with open(os.path.join(LOCAL_RES_DIR, "paths.json")) as f:
                paths = json.load(f)
                self.quincy_root_path =  paths['quincy_root_path']                                 
                if os.path.exists(self.quincy_root_path):                    
                    self.found_quincy = True
                    self.set_derived_path()
                else:
                    print("Found local paths, but the QUINCY dir does not exit")
                    print("Please fix paths.json")
                    exit(99)
            return   
                    
        
        # Check if QUINCY is already in the env variables
        self.found_quincy = False
        if 'QUINCYs' in os.environ:        
            self.quincy_root_path = os.environ.get("QUINCY")
            self.found_quincy = True
            self.set_derived_path()
            return
        
        # Try to find QUINCY in the work_scratch directory if were on the clsuter
        user = os.environ.get("USER")       
        if not os.path.exists(WORK_SCRATCH_DIR):
            print("You seem to be not on the BGC cluster as the cluster dirs are unavailable")
            print("Please set a QUINCY environmental variable")
            self.found_quincy = False 
            return
        
        rt_user_path = os.path.join(WORK_SCRATCH_DIR, user)       
        pot_quincy_paths = self.find_dirs_with_file(rt_user_path, "compile_quincy.sh")
        
        if len(pot_quincy_paths) == 0:
            print("Could not find QUINCY source code folder")
            print("Please set a QUINCY environmental variable")
            self.found_quincy = False 
            return
        
        if len(pot_quincy_paths) > 1:
            print("Error: Multiple instances of QUINCY source code found...")
            print("Please set a QUINCY environmental variable")
            self.found_quincy = False 
            return            
            
        print(f"Found QUINCTY at {pot_quincy_paths[0]} ")
        self.quincy_root_path =  pot_quincy_paths[0]     
        self.found_quincy = True   
        self.set_derived_path()
        
        os.makedirs(LOCAL_RES_DIR, exist_ok=True)        
        out_paths = {}
        out_paths['quincy_root_path'] = self.quincy_root_path
        with open(os.path.join(LOCAL_RES_DIR, "paths.json"), "w") as f:
            json.dump(out_paths, f, indent=2,  cls=PathEncoder)
        
               
    def find_dirs_with_file(self, start_dir, filename, max_depth=3):
        start_dir = Path(start_dir)
        results = []

        for path in start_dir.rglob(filename):
            # Limit directory depth
            if len(path.relative_to(start_dir).parts) <= max_depth:
                results.append(path.parent)

        return results
    
    def set_derived_path(self):
        self.namelist_root_path = os.path.join(self.quincy_root_path,'contrib','namelist', 'namelist.slm')
        self.lctlib_root_path = os.path.join(self.quincy_root_path,'data', 'lctlib_quincy_nlct14.def')
        self.sel_out_var_root_path = os.path.join(self.quincy_root_path,
                                                                        'data', 
                                                                        'basic_output_variables.txt')


class PathEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Path):
            return str(obj)
        return super().default(obj)