import os
import sys
import unittest
from pathlib import Path

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(THIS_DIR, os.pardir, os.pardir))
from src.quincy.auxil.find_quincy_paths import QuincyPathFinder

path_finder = QuincyPathFinder()

class TestQuincyPathsExist(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.pf = QuincyPathFinder()

    def test_found_quincy_flag(self):
        self.assertTrue(self.pf.found_quincy, "Quincy directoy was not found")

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
            Path(self.pf.namelist_root_path)
        ]

        for f in files:
            with self.subTest(file=f):
                self.assertTrue(f.exists(), f"Missing file: {f}")
                self.assertTrue(f.is_file(), f"Not a file: {f}")


if __name__ == "__main__":
    unittest.main()

