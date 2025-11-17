from src.quincy.base.Lctlib import Lctlib
from src.quincy.IO.LctlibReader import LctlibReader

lctlib = Lctlib()

# lctlib[PftQuincy.TeBE].ps_pathway = PsPathway.IC3PHOT
#
# lctlib.set_row("LctNumber", range(1, 9))
# landcover_ints = [3, 3, 3, 3, 3, 3, 4, 4]
# lctlib.set_row("LandcoverClass", landcover_ints)
# growthform_ints = [1, 1, 1, 1, 1, 1, 2, 2]
# lctlib.set_row("growthform", growthform_ints)

from time import perf_counter

reader = LctlibReader(filepath="lctlib_example.txt")
lctlib = reader.parse()

t1 = perf_counter()

# for i in range(1000):
#     lctlib[PftQuincy.TeBE].g0 = i / 1000.0
#     writer = LctlibWriter(lctlib=lctlib)
#     writer.export(f"out/{i}B.txt")
t2 = perf_counter()
print(f"Time elapsed: {(t2 - t1)*1000.0}ms")