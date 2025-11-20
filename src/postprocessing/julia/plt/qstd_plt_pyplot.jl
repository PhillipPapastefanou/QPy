using NCDatasets
using Dates 
using CFTime
using DataFrames
using Statistics 
#using WGLMakie 
using ColorSchemes   

using PyCall
using PyPlot
#PyPlot.matplotlib.use("qt5agg")
#PyPlot.matplotlib.use("Agg")
PyPlot.matplotlib.use("pdf")

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

    nvars = length(file.vars)
    COLUMNS_PER_PAGE = plt_settings.ncols_per_page
    ROWS_PER_PAGE = plt_settings.nrows_per_page

    outfilename = joinpath(plot_folder, string(file.cat)*"_"* string(file.simulation_type)*".pdf")


    PdfPages = PyPlot.matplotlib.backends.backend_pdf.PdfPages
    pdf = PdfPages(outfilename)

    last_page = false
    first_page = true

    index_var = 1
    while !last_page

        fig = PyPlot.figure(figsize=(10, 12), layout="constrained")

        # On the first page we display header and footer information
        if first_page
            spec = fig.add_gridspec(ROWS_PER_PAGE + 2, COLUMNS_PER_PAGE)

                    # Print header information first
                    # ax = fig.add_subplot(spec[0, :])
                    # ax.text(x=0.0, y=0.5,
                    #         s=f"{self.Basic_info.sitename}, {self.Basic_info.pft}, {self.Basic_info.user}, {self.Basic_info.date} ",
                    #         size=18, transform=ax.transAxes, horizontalalignment='left', verticalalignment='center')
                    # ax.text(x=0.0, y=0.25,
                    #         s=f"Output time resolution: {time_res.name}, displayed time resolution: {time_res.name} ",
                    #         size=12, transform=ax.transAxes, horizontalalignment='left', verticalalignment='center')
                    # ax.text(x=1.0, y=0.5,
                    #         s=f"Output category: {output_cat_name}",
                    #         size=18, transform=ax.transAxes, horizontalalignment='right', verticalalignment='center')
                    # ax.text(x=1.0, y=0.25,
                    #         s=f"Output variant: All",
                    #         size=12, transform=ax.transAxes, horizontalalignment='right', verticalalignment='center')
                    # ax.axis('off')

                    # # Print footer information
                    # ax = fig.add_subplot(spec[self.ROWS_PER_PAGE + 1, :])
                    # ax.text(x=1.0, y=0.5, s=f"commit: {self.Basic_info.commit} -- branch: {self.Basic_info.branch} -- "
                    #                         f"status: {self.Basic_info.status}", size=12, transform=ax.transAxes,
                    #         horizontalalignment='right', verticalalignment='center')
                    # ax.axis('off')
        else 
            spec = fig.add_gridspec(ROWS_PER_PAGE + 2, COLUMNS_PER_PAGE)

        end

        for r in range(1, ROWS_PER_PAGE)
            for c in range(1, COLUMNS_PER_PAGE)

                if index_var <= nvars
                    
                    # On the first page we start with one row later because we
                    if first_page
                        ax = fig.add_subplot(spec[r + 1, c])
                    else
                        ax = fig.add_subplot(spec[r + 1, c])
                    end
                    
                    var = file.vars[index_var]

                    var_name = var.name
                    var_unit = var.unit

                    data = get_data(qout_collection, var.name, file.simulation_type)

                    if var.ndim == 1
                        ax.plot(data[1], data[2], lw=1)
                    end
                    if var.ndim == 2
                        dim2 = size(data[2], 1)    
                        for s in 1:dim2
                            ax.plot(data[1], data[2][s,:], lw=1)
                        end
                    end
                    ax.set_title(var_name)
                    ax.set_ylabel(var_unit)
                    #ax.set_xlabel(f'time (res: {time_res.name})')
                    index_var += 1              
                end
            end
        end

        #fig = PyPlot.gcf()
        pdf.savefig(fig, orientation="portrait")
        PyPlot.close(fig)
        first_page = false

                    
        if index_var > nvars
            last_page = true
            pdf.close()
        end
    end

    PyPlot.tight_layout()
    pdf.close()    
end


