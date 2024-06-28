set(headers
        auxil.h
        gwgen.h
        gridcell.h
        simple_daily_lpj.h
        simple_diurnal_manon.h
        vars.h
        csv_reader.h
        csv_writer.h
        forcing_reader.h
        gridcell_setting_reader.h
        )

set(source
        auxil.cpp
        simple_diurnal_manon.cpp
        gwgen.cpp
        simple_daily_lpj.cpp
        csv_reader.cpp
        csv_writer.cpp
        forcing_reader.cpp
        gridcell_setting_reader.cpp
        )

include(add_model_sources)