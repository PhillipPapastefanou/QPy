from src.quincy.IO.NamelistWriter import NamelistWriter
from src.quincy.base.Namelist import Namelist
from time import perf_counter

namelist = Namelist()

t1 = perf_counter()

nlm_writer = NamelistWriter(namelist)

nlm_writer.export("A.txt")

t2 = perf_counter()
print(f"Time elapsed: {(t2 - t1)*1000.0}ms")