from enum import Enum

class PftQuincy(Enum):
    BEM = 1 # moist broadleaved evergreen
    BED = 2 # dry broadleaved evergreen
    BDR = 3 # rain green broadleaved deciduous
    BDS = 4 # summer green broadleaved deciduous
    NE  = 5 # needle-leaved evergreen & TeNE: ?
    NS  = 6 #  needle-leaved deciduous
    TeH  = 7 # C3 grass
    TrH  = 8 # C4 grass
    TeP  = 9 # C3 pasture
    TrP  = 10 # C4 pasture
    TeC  = 11 # C3 crop
    TrC  = 12 # C4 crop
    BSO  = 13 # bare soil
    UAR  = 14 # urban area

class PftListItem:
    def __init__(self):
        self.data = {i : 0.0 for i in PftQuincy}
    def __getitem__(self, key):
        return self.data[key]
    def __setitem__(self, key, value):
        self.data[key] = value
