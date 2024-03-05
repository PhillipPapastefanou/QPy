import enum
from datetime import datetime
from src.quincy.base.Lctlib import Lctlib
from src.quincy.base.PFTTypes import PftQuincy
class LctlibWriter:
    def __init__(self, lctlib : Lctlib):
        self.lctlib  = lctlib

    def export(self, filename):
        self.lines = []
        t_string = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        self.iadd_comment("Lctlib file generate with QPy generator.")
        self.iadd_comment(f"File created on {t_string}.")

        self.iadd_string(self.lctlib.title_string)

        self.iadd_lctlib(self.lctlib)

        with open(filename, 'w') as f:
            for line in self.lines:
                f.write(line)
                f.write('\n')

    def iadd_comment(self, str):
        self.lines.append(f"# {str}")
    def iadd_lctlib(self, instance):

        first_pft = instance[PftQuincy.TeBE]

        for var_str in vars(first_pft):

            # The name var string is just for demon
            if var_str == "name":
                continue

            for pft in PftQuincy:

                data_pft = instance[pft]
                value = getattr(data_pft, var_str)
                var_type =  type(value)

                if pft.value == 1:
                    line = var_str

                if (var_type is float) | (var_type is int) :
                    line += (f" {value}" )
                elif isinstance(value, enum.Enum):
                    line += (f" {value.value}")
                else:
                    print(f"Unsupported type {var_type} of variable {var_str}")
            self.iadd_string(line)

    def iadd_string(self, str):
        self.lines.append(f"{str}")


