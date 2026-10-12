import io
import os
import sys
import unittest
from contextlib import redirect_stdout

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(THIS_DIR, os.pardir, os.pardir))

from src.quincy.auxil.find_quincy_paths import QuincyPathFinder
from src.quincy.IO.NamelistReader import NamelistReader
from src.quincy.IO.LctlibReader import LctlibReader
from src.quincy.base.Lctlib import Lctlib_Item
from src.quincy.base.NamelistTypes import NamelistItem
from src.quincy.base.PFTTypes import PftQuincy


def parse_and_capture(reader):
    """Parse with the reader and return (result, list of messages the reader printed).
    The readers report problems by printing instead of raising."""
    buf = io.StringIO()
    with redirect_stdout(buf):
        result = reader.parse()
    return result, buf.getvalue().splitlines()


class Test_QuincyFilesParsing(unittest.TestCase):
    """Opens the namelist and lctlib of the local QUINCY checkout and checks that
    QPy knows every parameter in them and that every QPy parameter is in them."""

    @classmethod
    def setUpClass(cls):
        cls.pf = QuincyPathFinder()
        if not cls.pf.found_quincy:
            raise unittest.SkipTest("QUINCY directory not found")

        cls.nlm_reader = NamelistReader(cls.pf.namelist_root_path)
        cls.namelist, cls.nlm_messages = parse_and_capture(cls.nlm_reader)

        cls.lct_reader = LctlibReader(cls.pf.lctlib_root_path)
        cls.lctlib, cls.lct_messages = parse_and_capture(cls.lct_reader)

    def test_namelist_parses_without_errors(self):
        # Unknown categories/variables or unparseable values end up here
        self.assertEqual(self.nlm_messages, [],
                         f"Problems parsing {self.pf.namelist_root_path}:\n  " + "\n  ".join(self.nlm_messages))

    def test_namelist_has_all_qpy_parameters(self):
        missing = []
        for cat_str in vars(self.namelist):
            cat = getattr(self.namelist, cat_str)
            for var_str, item in vars(cat).items():
                if isinstance(item, NamelistItem) and not item.parsed:
                    missing.append(f"{cat_str}.{var_str}")

        self.assertEqual(missing, [],
                         f"QPy parameters not found in {self.pf.namelist_root_path}:\n  " + "\n  ".join(missing))

    def test_lctlib_parses_without_errors(self):
        # Rows with the wrong number of PFTs or unknown variables end up here
        self.assertEqual(self.lct_messages, [],
                         f"Problems parsing {self.pf.lctlib_root_path}:\n  " + "\n  ".join(self.lct_messages))

    def test_lctlib_has_all_qpy_parameters(self):
        # NLCT is read from the header line, name is set from the PFT
        qpy_vars = set(vars(Lctlib_Item(PftQuincy.BED))) - {'name', 'NLCT'}
        file_vars = {line.split()[0] for line in self.lct_reader.raw_input_lines if "NLCT" not in line}

        missing = sorted(qpy_vars - file_vars)
        self.assertEqual(missing, [],
                         f"QPy parameters not found in {self.pf.lctlib_root_path}:\n  " + "\n  ".join(missing))

    def test_lctlib_header(self):
        self.assertIn("NLCT", self.lctlib.title_string)
        nlct = int(self.lctlib.title_string.split()[1])
        self.assertEqual(nlct, len(PftQuincy),
                         f"lctlib has {nlct} PFTs, QPy expects {len(PftQuincy)}")


if __name__ == "__main__":
    unittest.main()
