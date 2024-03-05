from src.quincy.IO.NamelistReader import NamelistReader
from time import perf_counter

t1 = perf_counter()

NLReader = NamelistReader(filepath="namelist_example.txt")
namelist = NLReader.parse()

t2 = perf_counter()
print(f"Time elapsed: {(t2 - t1)*1000.0}ms")