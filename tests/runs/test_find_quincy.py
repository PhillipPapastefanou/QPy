import os
import sys
import unittest
from pathlib import Path

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(THIS_DIR, os.pardir, os.pardir))
from src.quincy.auxil.find_quincy_paths import QuincyPathFinder

class TestQuincyPathsExist(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.pf = QuincyPathFinder()

    def test_found_quincy_flag(self):
        self.assertTrue(self.pf.found_quincy, "Quincy directory was not found")

    def test_directories_exist(self):
        paths = [
            self.pf.quincy_root_path,
        ]

        for p in paths:
            p = Path(p)
            with self.subTest(path=p):
                self.assertTrue(p.exists(), f"Missing path: {p}")
                self.assertTrue(p.is_dir(), f"Not a directory: {p}")

    def test_required_files_exist(self):
        files = [
            Path(self.pf.lctlib_root_path),
            Path(self.pf.namelist_root_path),
            Path(self.pf.sel_out_var_root_path),
        ]

        for f in files:
            with self.subTest(file=f):
                self.assertTrue(f.exists(), f"Missing file: {f}")
                self.assertTrue(f.is_file(), f"Not a file: {f}")

    def test_chosen_path_is_a_candidate(self):
        pairs = [
            (self.pf.namelist_root_path, self.pf.namelist_paths),
            (self.pf.lctlib_root_path, self.pf.lctlib_paths),
            (self.pf.sel_out_var_root_path, self.pf.sel_out_var_paths),
        ]

        for chosen, candidates in pairs:
            with self.subTest(file=chosen):
                self.assertIsInstance(chosen, str)
                self.assertIn(chosen, candidates)

    def test_binary_exists(self):
        binary = self.pf.binary_path
        self.assertTrue(os.path.isfile(binary), f"QUINCY binary not found: {binary}. Compile QUINCY first.")
        self.assertTrue(os.access(binary, os.X_OK), f"QUINCY binary is not executable: {binary}")

    def test_binary_is_up_to_date(self):
        binary = self.pf.binary_path
        if not os.path.isfile(binary):
            self.skipTest("QUINCY binary not found")

        binary_time = os.path.getmtime(binary)
        src_dir = os.path.join(self.pf.quincy_root_path, 'src')
        newer = []
        for root, dirs, files in os.walk(src_dir):
            for name in files:
                if name.lower().endswith(('.f90', '.f', '.inc')):
                    path = os.path.join(root, name)
                    if os.path.getmtime(path) > binary_time:
                        newer.append(os.path.relpath(path, self.pf.quincy_root_path))

        self.assertEqual(sorted(newer), [],
                         f"Source files changed after {binary} was built, recompile QUINCY:\n  " + "\n  ".join(sorted(newer)))


if __name__ == "__main__":
    unittest.main()

