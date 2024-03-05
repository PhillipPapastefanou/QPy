from enum import Enum

class PftQuincy(Enum):
    TrBE = 1 # broad leaved evergreen (rainforest)
    TeBE = 2 # broad leaved evergreen (xeric forest)
    TrBR = 3 # broad leaved deciduous (rain green)
    TeBS = 4 # broad leaved deciduous (summer green) & BBS: ?
    BNE  = 5 # needle-leaved evergreen & TeNE: ?
    BNS  = 6 #  needle-leaved deciduous
    TeH  = 7 # C3 grass & TeC: C3 crop ?
    TrH  = 8 # C4 grass & TrC: C4 crop ?

class PftListItem:
    def __init__(self):
        self.data = {i : 0.0 for i in PftQuincy}
    def __getitem__(self, key):
        return self.data[key]
    def __setitem__(self, key, value):
        self.data[key] = value
