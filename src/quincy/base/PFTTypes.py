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
    
class PftFluxnet(Enum):
    TrBE = 0
    TeBE = 1
    TrBR = 2
    TeBS = 3
    BBS  = 4
    BNE  = 5
    TeNE = 6
    BNS  = 7
    TeH  = 8
    TeC  = 9
    TrH  = 10
    TrC  = 11
    
def GetQuincyPFTfromFluxnetPFT(fpft : PftFluxnet):
    if fpft == PftFluxnet.TrBE:
        return PftQuincy.BEM  
    elif fpft == PftFluxnet.TeBE:
        return PftQuincy.BED
    elif fpft == PftFluxnet.TrBR:
        return PftQuincy.BDR
    elif fpft == PftFluxnet.TeBS:
        return PftQuincy.BDS      
    elif fpft == PftFluxnet.BBS:
        return PftQuincy.BDS   
    elif fpft == PftFluxnet.BNE:
        return PftQuincy.NE
    elif fpft == PftFluxnet.TeNE:
        return PftQuincy.NE
    elif fpft == PftFluxnet.BNS:
        return PftQuincy.NS
    elif fpft == PftFluxnet.TeH:
        return PftQuincy.TeH
    elif fpft == PftFluxnet.TeC:
        return PftQuincy.TeH
    elif fpft == PftFluxnet.TrH:
        return PftQuincy.TrH
    elif fpft == PftFluxnet.TrC:
        return PftQuincy.TrH
    else:
        print(f"Invalid PFT: {fpft}")
        exit(99)
    
        
class PftListItem:
    def __init__(self):
        self.data = {i : 0.0 for i in PftQuincy}
    def __getitem__(self, key):
        return self.data[key]
    def __setitem__(self, key, value):
        self.data[key] = value
