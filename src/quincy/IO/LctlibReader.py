from src.quincy.base.Lctlib import Lctlib
from src.quincy.base.PFTTypes import PftQuincy
class LctlibReader:
    def __init__(self, filepath):
        self.filepath = filepath
        self.raw_input_lines = self.iread(filepath=filepath)

    def parse(self):
        return self.iparse(self.raw_input_lines)

    def iread(self, filepath):
        raw_input_lines = []
        file = open(filepath, "r")
        while True:
            line = file.readline()
            if not line:
                break
            # Treat each line individually

            # Remove whitespaces
            line = line.strip()
            # Ignore all lines with a comment and no content at all
            if len(line) > 0:
                if (line[0] != '#'):
                    raw_input_lines.append(line)
        file.close()
        return raw_input_lines

    def iparse(self, raw_input_lines):
        lctlib = Lctlib()

        for line in raw_input_lines:

            if "NLCT" in line:
                lctlib.title_string = line
                continue

            # Spilt by whitspace
            raw_str_array = line.split(" ")

            if len(raw_str_array) != len(PftQuincy) + 1:
                print(f"Can't parse: {raw_str_array}. Unequal lenghts.")
                continue

            var_name = raw_str_array[0]
            values = raw_str_array[1:]

            try:
                lctlib.set_row(var_name, values)
            except Exception as error:
                print(f"Can't parse: {raw_str_array}. Error message:")
                print(error)

        return lctlib



