include("qtypes.jl")
using Dates 
import Base: getindex

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
    var_names::Vector{String}
    var_cats::Vector{String}
    var_sim_types::Vector{QOutputSimulationType}
    var_time_types::Vector{QOutputTimeDim}
    sim_type_times::Vector{String}
    cats::Vector{String}

    function QOutputCollection()
        new(
            Dict{String, Dict{String, QOutputFile}}(), # data
            "",                                        # root_folder
            String[],                                  # var_names
            String[],                                  # var_cats
            QOutputSimulationType[],                   # var_sim_types
            QOutputTimeDim[],                          # var_time_types
            String[],                                  # sim_type_times
            String[],                                  # cats  
        )
    end
end
mutable struct QMultiRunCollections
    output::Vector{QOutputCollection}
    idstr::Vector{String}
end

function getindex(m::QMultiRunCollections, ids::AbstractVector{<:AbstractString})
    
    pos = Dict(s => i for (i, s) in pairs(m.idstr))  # String -> index
    idx = Vector{Int}(undef, length(ids))

    for (k, id) in pairs(ids)
        i = get(pos, id, 0)
        i == 0 && error("Unknown id: $id")
        idx[k] = i
    end

    return QMultiRunCollections(m.output[idx], m.idstr[idx])
end

