import numpy as np
from time import perf_counter
from src.forcing.site_derived.converter.settings import Settings, Verbosity


class Base_Parsing:

    def __init__(self, settings : Settings):
        self.settings = settings

    def round(self, x, n_figs):
        power = 10 ** np.floor(np.log10(np.abs(x).clip(1e-200)))
        rounded = np.round(x / power, n_figs - 1) * power
        return rounded


    def dprint(self, text , f: callable):
        if (self.settings.verbosity == Verbosity.Info) | (self.settings.verbosity == Verbosity.Full):
            print(text, end="")
            t1 = perf_counter()
        f()
        if (self.settings.verbosity == Verbosity.Info) | (self.settings.verbosity == Verbosity.Full):
            t2 = perf_counter()
            print(f"Done! ({np.round(t2 - t1, 1)} sec.)")