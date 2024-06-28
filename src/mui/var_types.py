
class ForcingDataset:
    def __init__(self):
        self.name = ""
        self.offset = 0.25
        self.res = 0.5
        self.min_lon = -179.75
        self.min_lat = -89.75
        self.max_lon = -self.min_lon
        self.max_lat = -self.min_lat
        self.min_year = 1981
        self.max_year = 2022
class Gridcell:
    def __init__(self):
        self.name = ""
        self.lon_pts  = 0.0
        self.lat_pts = 0.0
        self.min_year = 1981
        self.max_year = 2022