import os
import getpass
import json

THIS_DIR = os.path.dirname(os.path.abspath(__file__))

WORK_SCRATCH_DIR = "/Net/Groups/BSI/work_scratch"
LOCAL_RES_DIR = os.path.normpath(os.path.join(THIS_DIR, os.pardir, os.pardir, os.pardir, "local"))
LOCAL_PATHS_FILE = os.path.join(LOCAL_RES_DIR, "paths.json")
MARKER_FILE = "compile_quincy.sh"


class QuincyPathFinder:
    """Locates the QUINCY source directory.
    """

    @classmethod
    def from_root(cls, quincy_root_path):
        """Paths of a given QUINCY directory, without searching for one."""
        finder = cls.__new__(cls)
        finder._reset()
        finder._set_root(quincy_root_path)
        return finder

    def __init__(self):
        self._reset()

        # 1. Environment variable
        env_path = os.environ.get("QUINCY")
        if env_path:
            if os.path.isdir(env_path):
                self._set_root(env_path)
                return
            print(f"QUINCY environment variable points to {env_path}, which does not exist. Ignoring it.")

        # 2. Cached path from a previous search
        cached_path = self._read_cached_path()
        if cached_path:
            if os.path.isdir(cached_path):
                print("Found saved local QUINCY dir!")
                self._set_root(cached_path)
                return
            print(f"Saved QUINCY dir {cached_path} does not exist anymore. Searching again...")

        self._search_work_scratch()

    def _reset(self):
        self.found_quincy = False
        self.quincy_root_path = None
        self.namelist_root_path = None
        self.lctlib_root_path = None
        self.sel_out_var_root_path = None
        self.namelist_paths = []
        self.lctlib_paths = []
        self.sel_out_var_paths = []
        self.binary_path = None

    def _search_work_scratch(self):
        # 3. Search the work_scratch directory if we are on the cluster
        if not os.path.isdir(WORK_SCRATCH_DIR):
            print("You seem to be not on the BGC cluster as the cluster dirs are unavailable")
            print("Please set a QUINCY environmental variable")
            return

        user = os.environ.get("USER") or getpass.getuser()
        rt_user_path = os.path.join(WORK_SCRATCH_DIR, user)
        pot_quincy_paths = self.find_dirs_with_file(rt_user_path, MARKER_FILE)

        if len(pot_quincy_paths) == 0:
            print("Could not find QUINCY source code folder")
            print("Please set a QUINCY environmental variable")
            return

        if len(pot_quincy_paths) > 1:
            print("Error: Multiple instances of QUINCY source code found:")
            for p in pot_quincy_paths:
                print(f"  {p}")
            print("Please set a QUINCY environmental variable")
            return

        print(f"Found QUINCY at {pot_quincy_paths[0]}")
        self._set_root(pot_quincy_paths[0])
        self._write_cached_path(self.quincy_root_path)

    def find_dirs_with_file(self, start_dir, filename, max_depth=3):
        """Return dirs below start_dir containing filename.

        max_depth counts path components of the file relative to start_dir, i.e.
        max_depth=3 finds start_dir/a/b/filename. Traversal is pruned at that depth
        and hidden directories are skipped.
        """
        start_dir = os.path.abspath(start_dir)
        if not os.path.isdir(start_dir):
            return []

        start_depth = start_dir.rstrip(os.sep).count(os.sep)
        results = []
        for root, dirs, files in os.walk(start_dir, onerror=lambda e: None):
            depth = root.rstrip(os.sep).count(os.sep) - start_depth
            if filename in files:
                results.append(root)
            if depth + 1 >= max_depth:
                dirs[:] = []
            else:
                dirs[:] = [d for d in dirs if not d.startswith('.')]

        return sorted(results)

    def set_derived_path(self):
        # *_paths lists every matching file, *_root_path is the one that gets used
        namelist_dir = os.path.join(self.quincy_root_path, 'contrib', 'namelist')
        lctlib_dir = os.path.join(self.quincy_root_path, 'data')
        sel_out_var_dir = os.path.join(self.quincy_root_path, 'contrib', 'netcdf_output')

        self.namelist_paths = self.find_files(namelist_dir, ['namelist', 'nlm'])
        self.lctlib_paths = self.find_files(lctlib_dir, ['lctlib'])
        self.sel_out_var_paths = self.find_files(sel_out_var_dir, ['output_variables'])

        self.namelist_root_path = self.pick_file(self.namelist_paths, namelist_dir)
        self.lctlib_root_path = self.pick_file(self.lctlib_paths, lctlib_dir, prefer='14')
        self.sel_out_var_root_path = self.pick_file(self.sel_out_var_paths, sel_out_var_dir)

        # Compiled model, not checked here since QUINCY might not be compiled yet
        self.binary_path = os.path.join(self.quincy_root_path, 'x86_64-gfortran', 'bin', 'qs.bin')

    def find_files(self, folder, keywords):
        """Return all files in folder whose name contains one of the keywords."""
        if not os.path.isdir(folder):
            return []
        files = []
        for name in sorted(os.listdir(folder)):
            path = os.path.join(folder, name)
            if os.path.isfile(path) and any(k in name.lower() for k in keywords):
                files.append(path)
        return files

    def pick_file(self, files, folder, prefer=None):
        """Return the only file in files. If there are several and prefer is given,
        only the ones containing prefer are kept. Raises if not exactly one is left."""
        if len(files) > 1 and prefer is not None:
            preferred = [f for f in files if prefer in os.path.basename(f)]
            if preferred:
                files = preferred

        if len(files) == 0:
            raise FileNotFoundError(f"No matching file found in {folder}")

        if len(files) > 1:
            names = "\n  ".join(files)
            raise ValueError(f"Multiple matching files found in {folder}, keep only one:\n  {names}")

        return files[0]

    def _set_root(self, path):
        self.quincy_root_path = str(path)
        self.found_quincy = True
        self.set_derived_path()

    @staticmethod
    def _read_cached_path():
        if not os.path.exists(LOCAL_PATHS_FILE):
            return None
        try:
            with open(LOCAL_PATHS_FILE) as f:
                return json.load(f).get('quincy_root_path')
        except (OSError, ValueError, AttributeError) as e:
            print(f"Could not read {LOCAL_PATHS_FILE}: {e}")
            return None

    @staticmethod
    def _write_cached_path(path):
        try:
            os.makedirs(LOCAL_RES_DIR, exist_ok=True)
            with open(LOCAL_PATHS_FILE, "w") as f:
                json.dump({'quincy_root_path': str(path)}, f, indent=2)
        except OSError as e:
            print(f"Could not save QUINCY path to {LOCAL_PATHS_FILE}: {e}")
