import numpy as np

class QNC_Variable:
    def __init__(self, name, cat = ""):
        self.name = name
        self.cat = cat
        self.unit_str = ""

class QNC_Obs_Model_Variable_Pair:
    def __init__(self,  name):
        self.model_vars_plus = []
        self.obs_vars_plus = []

        self.model_vars_minus = []
        self.obs_vars_minus = []
        self.name = name

    def Plus_model_var(self, var):
        self.model_vars_plus.append(var)

    def Substract_model_var(self, var):
        self.model_vars_minus.append(var)

    def Plus_obs_var(self, var):
        self.obs_vars_plus.append(var)

    def Substract_obs_var(self, var):
        self.obs_vars_minus.append(var)
    def Update_availability(self, found_model_var, found_obs_var):
        self.model_var.found = found_model_var
        self.obs_var.found = found_obs_var


class Obs_Model_Var_List:
    def __init__(self):
        self.Target_variables = []

    def Add(self, Obs_Model_Variable_Pair):
        self.Target_variables.append(Obs_Model_Variable_Pair)

    def Get_obs_var_list(self):
        plist = []
        for pair in self.Target_variables:
            list = []
            for var in pair.obs_vars_plus:
                list.append(var.name)
            for var in pair.obs_vars_minus:
                list.append(var.name)
            plist.append(list)
        return plist

    def Get_model_var_list(self):
        plist = []
        for pair in self.Target_variables:
            list = []
            for var in pair.model_vars_plus:
                list.append((var.cat, var.name))
            for var in pair.model_vars_minus:
                list.append((var.cat, var.name))
            plist.append(list)
        return plist

    def Reduce_available_variables(self, founds_model_list, found_obs_list):


        positions = np.full((len(founds_model_list)), True)

        for i in range(len(founds_model_list)):
            if False in founds_model_list[i]:
                positions[i] = False
            if False in found_obs_list[i]:
                positions[i] = False


        self.Available_variables = list(np.array(self.Target_variables)[positions])


