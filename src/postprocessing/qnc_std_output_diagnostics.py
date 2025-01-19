import pandas as pd
import numpy as np
from src.postprocessing.qnc_defintions import  *

class QNC_diagnostics:

    def __init__(self, output_path,
                 output_format,
                 available_outputs,
                 basic_info):
        self.output_path = output_path
        self.output_format = output_format
        self.available_outputs = available_outputs
        self.basic_info = basic_info


