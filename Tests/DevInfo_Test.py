from src.quincy.IO.NamelistDevinfo import NamelistDevinfo
from src.quincy.base.Namelist import Namelist

namelist = Namelist()

devInfo = NamelistDevinfo(namelist)

devInfo.parse()