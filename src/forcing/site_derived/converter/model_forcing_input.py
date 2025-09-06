class SW_Input_Parser:
    def __init__(self, file_unit):

        self.target_units = ["Wm-2", "W/m2"]

        if file_unit in self.target_units:
            dummy = 3
        else:
            raise Exception("Unsupported SW radiation unit")

    def convert(self, data):
        return data


class LW_Input_Parser:
    def __init__(self, file_unit):

        self.target_units = ["Wm-2", "W/m2"]
        if file_unit in self.target_units:
            dummy = 3
        else:
            raise Exception("Unsupported LW radiation unit")

    def convert(self, data):
        return data

class Tair_Input_Parser:
    def __init__(self, file_unit):

        self.DEGREE_C_TO_K = 273.15
        self.target_unit = "K"

        if file_unit == "K":
            self.offset = 0.0
        elif file_unit == "C":
            self.offset = self.DEGREE_C_TO_K
        else:
            raise Exception("Unsupported temperature unit")

    def convert(self, data):
        return data + self.offset


class Qair_Input_Parser:
    def __init__(self, file_unit):

        self.G_TO_KG = 1000.0
        self.target_unit = "g/kg"

        if file_unit in ['kg/kg', 'g/g', '1', '-']:
            self.factor = self.G_TO_KG
        elif file_unit in ['g/kg']:
            self.factor = 1.0
        else:
            raise Exception("Unsupported QAir unit")

    def convert(self, data):
        return data * self.factor


class Pressure_Input_Parser:
    def __init__(self, file_unit):
        self.target_unit = "hPa"

        if file_unit in ['Pa','Pascal']:
            self.factor = 1.0 / 100.0
        elif file_unit in ['kPa']:
            self.factor = 10.0
        elif file_unit in ['hPa']:
            self.factor = 1.0
        else:
            raise Exception("Unsupported pressure unit")

    def convert(self, data):
        return data * self.factor

class Precipitation_Input_Parser:
    def __init__(self, file_unit):
        self.target_unit = "mm/day"
        self.Seconds_In_Day = 86400.0;

        if file_unit in ['mm/day', 'mm day-1']:
            self.factor = 1.0
        elif file_unit in ['kg/m2/s']:
            self.factor = self.Seconds_In_Day
        else:
            raise Exception("Unsupported rainfall unit")

    def convert(self, data):
        return data * self.factor

class Windspeed_Input_Parser:
    def __init__(self, file_unit):
        self.target_unit = "m/s"
        self.KM_P_H_To_M_P_S = 3600.0 / 1000.0

        if file_unit in ['m/s', 'm s-1']:
            self.factor = 1.0
        elif file_unit in ['km/h', 'km h-1']:
            self.factor = 1.0 / self.KM_P_H_To_M_P_S
        else:
            raise Exception("Unsupported windseed unit")

    def convert(self, data):
        return data * self.factor