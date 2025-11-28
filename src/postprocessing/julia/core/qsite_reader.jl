include("qtypes.jl")
include("qoutput.jl")

using NCDatasets
using Dates

function read_quincy_site_output(folder)
    folder_path = folder
    all_entries = readdir(folder_path)

    nc_files = String[] # Initialize an empty array to store file names
    for entry in all_entries
        full_path = joinpath(folder_path, entry) # Construct the full path
        if isfile(full_path) && endswith(full_path, ".nc")
            push!(nc_files, entry)
        end
    end

    cats = []
    sim_type_times = []
    for file in nc_files
        if file[1:2] == "Q_"
            parts = split(file, '_')
            push!(cats, "Q_"*parts[2])
            sim_type = parts[3]
            time = parts[4][1:end-3]    
            push!(sim_type_times,  sim_type*"_"*time)
        else
            parts = split(file, '_')
            push!(cats, parts[1])
            sim_type = parts[2]
            time = parts[3][1:end-3]
            push!(sim_type_times,  sim_type*"_"*time)
        end
    end

    cats = unique(cats)
    sim_type_times = unique(sim_type_times)
    qcollection = QOutputCollection()
    qcollection.root_folder = folder_path
    
    qcollection.sim_type_times = sim_type_times
    qcollection.cats = cats

    time_data = Vector{DateTimeNoLeap}()
    parsed_variables = false
    for sim_type_t in sim_type_times
        parsed_time = false
        qcollection.data[sim_type_t] = Dict{String, QOutputFile}()
        
        for cat in cats

            filename = joinpath(folder_path, cat*"_"*sim_type_t*".nc")        
            ds = NCDataset(filename, "r")
            
            # We do need to parse the time only once as it will be the same across all cats
            if !parsed_time
                time_data = ds["time"][:]

                time_data = [
                Dates.DateTime(
                    year(dt),
                    month(dt),
                    day(dt),
                    hour(dt),
                    minute(dt),
                    second(dt)
                ) for dt in time_data
                            ]
                parsed_time = true
            end

            hlp1 = split(sim_type_t, '_')
            time_str = hlp1[2]
            simtype_str = hlp1[1]
            
            time_enum = convert_to_output_time_dim(time_str) 
            simtype_enum = convert_to_output_simumation_type(simtype_str)
            
            variables = keys(ds)
            qvariables = Vector{QOutputVariable}()
            for varname in variables            
                if varname == "time"
                    continue
                end
                if varname == "soil_depth"
                    continue
                end
                ndim = ndims(ds[varname])

                unit = ds[varname].attrib["units"]      
                push!(qvariables, QOutputVariable(ndim, unit, varname))   
                
                push!(qcollection.var_names, varname)  
                push!(qcollection.var_cats, cat)  
                push!(qcollection.var_sim_types, simtype_enum) 
                push!(qcollection.var_time_types, time_enum) 
                
            end
            outputfile = QOutputFile(time_enum, simtype_enum, cat, filename, time_data, qvariables)

            qcollection.data[sim_type_t][cat] = outputfile

            close(ds)
        end
        parsed_variables = true
    end
    return qcollection;
end

function get_variables(qcollection::QOutputCollection)
    return unique(qcollection.var_names)
end

function get_data(qcollection::QOutputCollection, varname::String, sim_type::QOutputSimulationType)
    
    indexes_var = findall(isequal(varname), qcollection.var_names)
    if indexes_var === nothing
        println("$varname not found in output variables")
        return
    end

    indexes_sim_type = findall(isequal(sim_type), qcollection.var_sim_types)
    if indexes_sim_type === nothing
        println("$varname not found in output variables")
        return
    end

    index = intersect(indexes_var, indexes_sim_type)
    if length(index) > 1
        println("The output variables are ambigious")
        return
    end

    if length(index) == 0
        println("Output variable not found in indexes")
        return
    end
    index = index[1]

    cat = qcollection.var_cats[index]
    sim_type = qcollection.var_sim_types[index]
    time_type = qcollection.var_time_types[index]

    

    simtime_type = lowercase(string(sim_type))*"_"*lowercase(string(time_type))
    fname = qcollection.data[simtime_type][cat].filename

    ds = NCDataset(fname, "r")

    nd = ndims(ds[varname])

    if nd == 1
         data_raw = Array(ds[varname])
    elseif nd ==2
         data_raw = ds[varname][:,:]
    else
        print("Unsupported dimensionality $nd")
        close(ds)
        exit(99)
    end
    close(ds)
    return [qcollection.data[simtime_type][cat].time_points, data_raw]
end
