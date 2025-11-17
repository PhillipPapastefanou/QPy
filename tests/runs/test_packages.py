# check_packages.py

import importlib
import unittest


def check_required_packages():
    """
    Check whether required packages are installed.
    Returns:
        {
            "installed": [...],
            "missing": [...]
        }
    """
    required = ["pandas", "numpy", "matplotlib", "mpi4py"]
    missing = []
    installed = []

    # Check basic packages
    for pkg in required:
        try:
            importlib.import_module(pkg)
            installed.append(pkg)
        except ImportError:
            missing.append(pkg)

    # Check netCDF support
    netcdf_ok = False
    for pkg in ("netCDF4", "xarray"):
        try:
            importlib.import_module(pkg)
            installed.append(pkg)
            netcdf_ok = True
            break
        except ImportError:
            pass

    if not netcdf_ok:
        missing.append("netCDF support (netCDF4 or xarray)")

    return {"installed": installed, "missing": missing}


# -------------------------------------------------------------------
# Unit test function
# -------------------------------------------------------------------

class TestRequiredPackages(unittest.TestCase):

    def test_no_missing_packages(self):
        """ Required packages should all be installed. """
        result = check_required_packages()
        self.assertEqual(
            result["missing"], 
            [],
            msg="Missing required packages: " + ", ".join(result["missing"])
        )

    def test_return_structure(self):
        """ Function should return a dict with correct keys and types. """
        result = check_required_packages()

        self.assertIsInstance(result, dict)
        self.assertIn("installed", result)
        self.assertIn("missing", result)
        self.assertIsInstance(result["installed"], list)
        self.assertIsInstance(result["missing"], list)


# Allow running tests directly from the file
if __name__ == "__main__":
    unittest.main()