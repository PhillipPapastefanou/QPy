from src.quincy.base.NamelistTypes import ForcingMode
from src.quincy.base.NamelistTypes import OutputIntervalPool
from src.quincy.base.NamelistTypes import OutputIntervalFlux

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
class Scenario:
    def __init__(self, forcing_dataset: ForcingDataset):
        self.forcing_dataset = forcing_dataset
        self.focing_mode = ForcingMode.STATIC
        self.nyear_spinup = 100
        self.nyear_transient = 0
        self.nyear_total = 0
        self.first_year_spinup = 0
        self.last_year_spinup = 0
        self.first_year_transient = 0
        self.last_year_transient = 0

        self.first_year_change = 0
        self.last_year_change = 0

        self.has_spinup = False
        self.time_res = OutputIntervalFlux.WEEKLY
        self.time_multiplier = 1.0

    def parse_datetime_multiplier(self, output_interval : OutputIntervalFlux):
        self.time_res = output_interval

        if self.time_res == OutputIntervalFlux.DAILY:
            self.time_multiplier = 1.0
        elif self.time_res == OutputIntervalFlux.WEEKLY:
            self.time_multiplier = 7.0
        elif self.time_res == OutputIntervalFlux.YEARLY:
            self.time_multiplier = 365
        else:
            print("Not support output resolution selected")
            exit(99)

    def parse_simulation_length(self, nyear_spinup, nyear_transient, nyear_change):
        if nyear_spinup == 0:
            self.forcing_mode = ForcingMode.STATIC
        else:
            self.forcing_mode = ForcingMode.TRANSIENT
        self.nyear_spinup = nyear_spinup
        self.nyear_total = nyear_spinup + nyear_transient
        self.nyear_change = nyear_change
    def parse_simulation_years(self):
        self.first_year_transient = self.forcing_dataset.min_year
        self.last_year_transient = self.forcing_dataset.max_year
        self.first_year_spinup = self.forcing_dataset.min_year - self.nyear_spinup
        self.last_year_spinup = self.first_year_transient - 1
        self.last_year_change = self.last_year_transient
        self.first_year_change = self.last_year_transient - self.nyear_change +  1


