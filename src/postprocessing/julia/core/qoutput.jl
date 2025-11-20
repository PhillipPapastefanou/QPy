include("qtypes.jl")
using Dates 

mutable struct QOutputVariable
    ndim::Int 
    unit::String
    name::String
end

mutable struct QOutputFile
    time_dim::QOutputTimeDim 
    simulation_type::QOutputSimulationType
    cat::String
    filename::String
    first_year::Int
    last_year::Int
    time_points::Vector{DateTime}
    vars::Vector{QOutputVariable}
end
function QOutputFile(time_dim, simulation_type, cat, filename, time_data, qvariables)
    if length(time_data) > 0
        QOutputFile(time_dim, simulation_type, cat, filename,
         Dates.year(time_data[1]), Dates.year(time_data[end]), time_data, qvariables)
    else
        QOutputFile(time_dim, simulation_type, cat, filename,
         0, 0, time_data, qvariables)  
    end
end

mutable struct QOutputCollection
    data::Dict{String, Dict{String, QOutputFile}}
    root_folder::String
    _var_names::Vector{String}
    _var_cats::Vector{String}
    _var_sim_types::Vector{QOutputSimulationType}
    _var_time_types::Vector{QOutputTimeDim}
    sim_type_times::Vector{String}
    cats::Vector{String}

    function QOutputCollection()
        new(
            Dict{String, Dict{String, QOutputFile}}(), # data
            "",                                        # root_folder
            String[],                                  # _var_names
            String[],                                  # _var_cats
            QOutputSimulationType[],                   # _var_sim_types
            QOutputTimeDim[],                          # _var_time_types
            String[],                                  # sim_type_times
            String[],                                  # cats  
        )
    end
end
mutable struct QMultiRunCollections
    output::Vector{QOutputCollection}
    idstr::Vector{String}
end



