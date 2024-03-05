import enum
import numpy
from datetime import datetime
from src.quincy.base.Namelist import Namelist

class NamelistWriter:
    def __init__(self, namelist : Namelist):
        self.namelist  = namelist

    def export(self, filename):
        self.lines = []
        t_string = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        self.iadd_comment("Instruction file generate with QPy generator.", False)
        self.iadd_comment(f"File created on {t_string}.", False)

        for cat_str in vars(self.namelist):
            cat = getattr(self.namelist, cat_str)
            self.iadd_category(cat)

        with open(filename, 'w') as f:
            for line in self.lines:
                f.write(line)
                f.write('\n')

    def iadd_comment(self, str, is_inline):
        if is_inline:
            self.lines.append(f"  ! {str}")
        else:
            self.lines.append(f"! {str}")
    def iadd_category(self, instance):

        # Beginning string
        str_start = f"&{type(instance).__name__}"
        self.lines.append(str_start)

        if len(vars(instance)) == 0:
            self.iadd_comment("nothing here yet", True)

        for var_str in vars(instance):
            value = getattr(instance, var_str)
            var_type =  type(value)

            if (var_type is float) | (var_type is numpy.float64) :
                self.iadd_string(f"{var_str}={value}")

            elif (var_type is int) | (var_type is numpy.int64) :
                self.iadd_string(f"{var_str}={value}")

            elif var_type is str:
                self.iadd_string(f"{var_str}=\"{value}\"")

            elif var_type is bool:
                b_value = ".TRUE." if value else ".FALSE."
                self.iadd_string(f"{var_str}={b_value}")

            elif isinstance(value, enum.Enum):
                 self.iadd_string(f"{var_str}=\"{str(value.name).lower()}\"")

            else:
                print(f"Unsupported type {var_type} of variable {var_str}")

        # End string
        str_end = "/"
        self.lines.append(str_end)

    def iadd_string(self, str):
        self.lines.append(f"  {str}")


