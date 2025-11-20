using NCDatasets
using Dates 
using CFTime
using DataFrames
using Statistics 
#using WGLMakie 
using CairoMakie
using PDFIO
using Makie
using ColorSchemes   

include("../core/qoutput.jl")
include("../core/qtypes.jl")
include("../core/qsite_reader.jl")

include("qplt_settings.jl")

function create_std_plt_single_output(output_folder, plot_folder, plt_settings::QPlotSettings)

    
    println("Plotting std output...")
    qout_collection = read_quincy_site_output(output_folder)

    if length(qout_collection.cats) == 0
        println("No output categories found in folder... Skipping.")
        return
    end

    if plt_settings.verbose
        len = length(qout_collection.cats)
        println("Found $len categories.")
        print("Found: ")        
        for s in qout_collection.sim_type_times
            print(String(s) * " ")
        end
        println(" simulations types.")
    end

    for simtype in qout_collection.sim_type_times
        for cat in qout_collection.cats
            file = qout_collection.data[simtype][cat]
            print("Processing $simtype and $cat ..." )
            time_passed = @elapsed create_std_plt_file(qout_collection, file, plot_folder, plt_settings)
            time_passed = round(time_passed, digits = 1)
            println(" Done! ($time_passed s).")
        end
    end

    println("All plots finished!")
end

function create_std_plt_file(qout_collection::QOutputCollection, file::QOutputFile, plot_folder::String, plt_settings::QPlotSettings)


    if !isdir(plot_folder)
        mkdir(plot_folder)
    end

    nrows_max = plt_settings.nrows_per_page
    ncols_max = plt_settings.ncols_per_page
    nrows = nrows_max
    nplot_per_cat = length(file.vars)

    axes = Matrix{Axis}(undef, nrows_max, ncols_max)
    ip = 1
    npages = Int(ceil(nplot_per_cat/nrows_max/ncols_max))
    fnames = []

    for p in 1:npages
        f = Figure(size=(plt_settings.width_px, plt_settings.height_px))

        for i in 1:nrows_max
            for j in 1:ncols_max

                if ip == nplot_per_cat
                    nrows = i
                    break
                end

                var = file.vars[ip]
                var_name = var.name
                var_unit = var.unit
                data = get_data(qout_collection, var.name, file.simulation_type)

                x_data_for_plot_numeric = Dates.datetime2unix.(data[1])

                axes[i, j] = Axis(f[i, j],
                    title = var_name, # Title for each subplot
                    xlabel = "time",
                    ylabel = "["* var_unit*"]"
                )

                if var.ndim == 1
                    lines!(axes[i,j], x_data_for_plot_numeric, data[2], color = :blue)
                end

                if var.ndim == 2
                    dim2 = size(data[2], 1)    
                    colors = ColorSchemes.tab20[1:dim2]     
                    for s in 1:dim2
                        lines!(axes[i,j], x_data_for_plot_numeric, data[2][s,:], color = colors[s])
                    end
                end                

                axes[i, j].xticklabelrotation = 30 * pi / 180.0
                axes[i, j].xticklabelsize = 12
                axes[i, j].yticklabelsize = 12
                axes[i, j].ylabelsize = 12
                axes[i, j].xlabelsize = 12
                nyear_ticks = file.last_year-file.first_year
                if nyear_ticks > 10
                    nyear_ticks = 10
                end
                axes[i, j].xticks = Makie.LinearTicks(nyear_ticks)
                axes[i, j].xtickformat = values -> [Dates.format(Dates.unix2datetime(x), "yyyy-mm") for x in values]
            
                ip += 1
            end
        end
        if npages > 1
            ps = "_"*string(p)
        else
            ps = ""
        end
        outfilename = joinpath(plot_folder, string(file.cat)*"_"* string(file.simulation_type)*ps*".pdf")
        save(outfilename, f)
        push!(fnames, outfilename)
    end



    # if npages > 1
    #     output_pdf_filename = string(file.cat)*"_"* string(file.simulation_type)*".pdf"
    #     PDFIO.write(output_pdf_filename) do doc_writer
        
    #         for p in 1:npages
    #             pdf_file_single = PDFIO.read(fnames[p])

    #             PDFIO.add_page!(doc_writer, pdf_file_single.pages[1])

    #             PDFIO.close(pdf_file_single)
    #         end
        
    #     end
    # end
    
end

