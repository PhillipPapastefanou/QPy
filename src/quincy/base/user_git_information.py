import git
import os
import re
import datetime
from enum import Enum

class QUINCY_BUILD_SYSTEM(Enum):   
    DEFAULT = 0
    CMAKE = 1

class UserGitInformation:
    def __init__(self, quincy_root_path, folder, site):
        self.quincy_root_path = quincy_root_path
        self.folder = folder
        self.site = site
        
    def Generate(self):
        self.get_compiler_information()
        self.get_git_info()
        self.generate_binary_sinfo_file()
        self.write_binary_sinfo_file()        
        self.write_exp_info_file()

        
    def write_binary_sinfo_file(self):
        with open(os.path.join(self.folder, "binary_sinfo.txt"), "w") as file:
            for item in self.binary_sinfo_file_str:
                file.write(item + "\n")
        
        
    def get_compiler_information(self):
        
        quincy_standard_comp_opts = os.path.join(self.quincy_root_path, "build", "make_compile-options.incl")
        
        config = {}
        try:
            with open(quincy_standard_comp_opts, 'r') as file:
                for line in file:
                    line = line.strip() 
                    if line.startswith('#') or line == '': 
                        continue
                    match = re.match(r'(\w+)\s*=\s*(.*)', line) # Regex to capture key and value
                    if match:
                        key, value = match.groups()
                        config[key] = value
        except FileNotFoundError:
            print(f"Error: File not found at {quincy_standard_comp_opts}")
            
        self.compiler_str = config['COMP']
        
        if "gfortran" in self.compiler_str:
            self.compiler_short_str = "gfortran"
        else: 
            self.compiler_short_str = self.compiler_str    
        
        fc_str = config['F_C']
        
        if "__QUINCY_WITH_NETCDF__" in fc_str:
            self.compiled_with_netcdf = "TRUE"
        else:
            self.compiled_with_netcdf = "FALSE"
                
        quincy_potential_path = os.path.join(self.quincy_root_path, self.compiler_str, "bin", "land.x")
        
        if os.path.exists(quincy_potential_path):
            self.quincy_binary_path = quincy_potential_path
            self.quincy_build_syste = QUINCY_BUILD_SYSTEM.DEFAULT
            
        else:
            print("Could not determine QUINCY build system")
            print("So far only DEFAULT is supported")
            exit(99)
            
        
    def get_git_info(self):
        try:
            repo = git.Repo(self.quincy_root_path) 

            self.branch_name = repo.active_branch.name
            self.commit_hash = repo.head.commit.hexsha[:7] 
            self.author_name = repo.head.commit.author.name
            self.author_email = repo.head.commit.author.email
            self.git_status  = "modified"


        except git.InvalidGitRepositoryError:
            return {"error": "Not a Git repository"}
        except Exception as e:
            return {"error": str(e)}
    
    def generate_binary_sinfo_file(self):
        self.binary_sinfo_file_str = []        
        self.binary_sinfo_file_str.append("commit branch status:")
        self.binary_sinfo_file_str.append(f"{self.commit_hash} {self.branch_name} {self.git_status}")
        self.binary_sinfo_file_str.append("compiled with netcdf-libraries:")
        self.binary_sinfo_file_str.append(self.compiled_with_netcdf)
        self.binary_sinfo_file_str.append("compiler:")
        self.binary_sinfo_file_str.append(self.compiler_short_str)
        
    def write_exp_info_file(self):
        self.user = os.getlogin()
        self.site = self.site
        current_date = datetime.date.today()
        self.formatted_date = current_date.strftime("%Y-%m-%d")  # Year-month-day    
        self.exp_info_file = []         
        self.exp_info_file.append("sitename user date")
        self.exp_info_file.append(f"{self.site} {self.user} {self.formatted_date}")
        
        with open(os.path.join(self.folder, "exp_info.txt"), "w") as file:
            for item in self.exp_info_file:
                file.write(item + "\n")
        