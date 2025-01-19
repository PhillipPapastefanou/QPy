from src.postprocessing.qnc_ncdf_reader import QNC_ncdf_reader
from src.postprocessing.qnc_defintions import Output_Time_Res
from src.postprocessing.qnc_basic_Information_parser import Basic_information_parser
from src.postprocessing.qnc_defintions import *

import matplotlib.pyplot as plt
from time import perf_counter
from matplotlib.backends.backend_pdf import PdfPages

import numpy as np
import pandas as pd
from matplotlib.dates import DateFormatter
import os
import traceback
import re
from matplotlib.lines import Line2D

class QNC_std_output_plotting:
    def __init__(self, output_path,
                 post_processing_path,
                 output_format,
                 available_outputs,
                 basic_info):

        self.output_path = output_path
        self.output_format = output_format
        self.post_processing_path = post_processing_path
        self.Available_outputs = available_outputs
        self.Basic_info = basic_info


        # Settings -------------------------
        # How many variables belong to the time could also be 10...
        self.TIME_VARIABLE_OFFSET = 3;

        self.COLUMNS_PER_PAGE = 2
        self.ROWS_PER_PAGE = 5
        # End of settings ------------------

        self.MAX_PLOTS_PER_PAGE = self.COLUMNS_PER_PAGE * self.ROWS_PER_PAGE

    def Plot_all_1D(self):

        nc_outputs = []
        time_res = Output_Time_Res.Invalid

        for identifier in self.Available_outputs:
            output_file = self.Available_outputs[identifier]

            cats = output_file.Target_categories
            sim_type = output_file.Simulation_type
            time_res = output_file.Time_resolution

            nc_output = QNC_ncdf_reader(self.output_path,
                                        cats,
                                        identifier,
                                        time_res
                                        )

            nc_output.Parse_env_and_variables()
            nc_output.Read_all_1D()
            nc_output.Close()
            nc_outputs.append(nc_output)


        # Ploting routine
        for output_cat_name in nc_output.output_cat_names:
            print(f"     Plotting {output_cat_name} variables... ", end='')
            t1_start = perf_counter()

            export_filename = os.path.join(self.post_processing_path, f"{output_cat_name}_all.pdf")

            #if self.output_model_type == 'both':
            #    data_set_spin = qoutput_spin.Datasets_1D[output_cat_name]
                #data_set_spin = data_set_spin.groupby(pd.Grouper(key='date', freq='1W')).mean().reset_index()

            nvars_total = nc_outputs[0].Datasets_1D[output_cat_name].shape[1]
            unit_set = nc_outputs[0].Units_1D[output_cat_name]

            # Substract time variables from dataset
            nvars = nvars_total - self.TIME_VARIABLE_OFFSET;

            index_start = self.TIME_VARIABLE_OFFSET
            index_running = index_start
            index_var = 0
            index_end = index_start + self.MAX_PLOTS_PER_PAGE

            pdf = PdfPages(export_filename)

            last_page = False
            first_page = True
            while not last_page:

                fig = plt.figure(figsize=(10, 12), layout="constrained")

                # On the first page we display header and footer information
                if first_page:
                    # We have two more rows, one for header one for footer
                    spec = fig.add_gridspec(self.ROWS_PER_PAGE + 2, self.COLUMNS_PER_PAGE)

                    # Print header information first
                    ax = fig.add_subplot(spec[0, :])
                    ax.text(x=0.0, y=0.5,
                            s=f"{self.Basic_info.sitename}, {self.Basic_info.pft}, {self.Basic_info.user}, {self.Basic_info.date} ",
                            size=18, transform=ax.transAxes, horizontalalignment='left', verticalalignment='center')
                    ax.text(x=0.0, y=0.25,
                            s=f"Output time resolution: {time_res.name}, displayed time resolution: {time_res.name} ",
                            size=12, transform=ax.transAxes, horizontalalignment='left', verticalalignment='center')
                    ax.text(x=1.0, y=0.5,
                            s=f"Output category: {output_cat_name}",
                            size=18, transform=ax.transAxes, horizontalalignment='right', verticalalignment='center')
                    ax.text(x=1.0, y=0.25,
                            s=f"Output variant: All",
                            size=12, transform=ax.transAxes, horizontalalignment='right', verticalalignment='center')
                    ax.axis('off')

                    # Print footer information
                    ax = fig.add_subplot(spec[self.ROWS_PER_PAGE + 1, :])
                    ax.text(x=1.0, y=0.5, s=f"commit: {self.Basic_info.commit} -- branch: {self.Basic_info.branch} -- "
                                            f"status: {self.Basic_info.status}", size=12, transform=ax.transAxes,
                            horizontalalignment='right', verticalalignment='center')
                    ax.axis('off')

                else:
                    # All other pages do not need to have the extra rows for header and footer
                    spec = fig.add_gridspec(self.ROWS_PER_PAGE, self.COLUMNS_PER_PAGE)

                for r in range(0, self.ROWS_PER_PAGE):
                    for c in range(0, self.COLUMNS_PER_PAGE):

                        if index_var < nvars:


                            # On the first page we start with one row later because we
                            if first_page:
                                ax = fig.add_subplot(spec[r + 1, c])
                            else:
                                ax = fig.add_subplot(spec[r, c])


                            # Get the slice of the data containing only the variable we are interested in
                            for nc_out in nc_outputs:
                                data_set = nc_out.Datasets_1D[output_cat_name]
                                datetimes = nc_output.times_np_64
                                #data_set = data_set.groupby(
                                #    pd.Grouper(key='date', freq='1y')).mean().reset_index()

                                slice = data_set.iloc[:, index_running]

                                # Plot the slice of the data y = slice and x = the date string
                                #ax.plot(data_set['date'], slice, lw=1)
                                ax.plot(datetimes, slice, lw=1)


                            var_name = data_set.columns[index_running]
                            ax.set_title(var_name)
                            ax.set_ylabel(unit_set[var_name])
                            ax.set_xlabel(f'time (res: {time_res.name})')

                            index_running += 1
                            index_var += 1

                pdf.savefig(fig, orientation='portrait')
                plt.close(fig)
                first_page = False

                if index_end >= nvars:
                    last_page = True
                    pdf.close()
                else:
                    index_start += self.MAX_PLOTS_PER_PAGE
                    index_end += self.MAX_PLOTS_PER_PAGE

            t_stop = perf_counter()
            print(f"Done! ({np.round(t_stop - t1_start, 1)} sec.)")

    def Plot_single_1D(self):

        for identifier in self.Available_outputs:

            print(f"Performing 1D {identifier} variables... ")
            output_file = self.Available_outputs[identifier]

            cats = output_file.Target_categories
            sim_type = output_file.Simulation_type
            time_res = output_file.Time_resolution

            nc_output = QNC_ncdf_reader(self.output_path,
                                        cats,
                                        identifier,
                                        time_res
                                        )



            self.parsing_success = nc_output.Parse_env_and_variables()
            if not self.parsing_success:
                return
            nc_output.Read_all_1D()
            nc_output.Close()

            # Ploting routine
            for output_cat_name in nc_output.output_cat_names:

                print(f"     Plotting {output_cat_name} variables... ", end='')
                t1_start = perf_counter()
                export_filename = os.path.join(self.post_processing_path, f"{output_cat_name}_{identifier}.pdf")

                # if self.output_model_type == 'both':
                #    data_set_spin = qoutput_spin.Datasets_1D[output_cat_name]
                # data_set_spin = data_set_spin.groupby(pd.Grouper(key='date', freq='1W')).mean().reset_index()

                nvars_total = nc_output.Datasets_1D[output_cat_name].shape[1]
                unit_set = nc_output.Units_1D[output_cat_name]

                # Substract time variables from dataset
                nvars = nvars_total - self.TIME_VARIABLE_OFFSET;

                index_start = self.TIME_VARIABLE_OFFSET
                index_running = index_start
                index_var = 0
                index_end = index_start + self.MAX_PLOTS_PER_PAGE

                pdf = PdfPages(export_filename)

                last_page = False
                first_page = True
                while not last_page:

                    fig = plt.figure(figsize=(10, 12), layout="constrained")

                    # On the first page we display header and footer information
                    if first_page:
                        # We have two more rows, one for header one for footer
                        spec = fig.add_gridspec(self.ROWS_PER_PAGE + 2, self.COLUMNS_PER_PAGE)

                        # Print header information first
                        ax = fig.add_subplot(spec[0, :])
                        ax.text(x=0.0, y=0.5,
                                s=f"{self.Basic_info.sitename}, {self.Basic_info.pft}, {self.Basic_info.user}, {self.Basic_info.date} ",
                                size=18, transform=ax.transAxes, horizontalalignment='left',
                                verticalalignment='center')
                        ax.text(x=0.0, y=0.25,
                                s=f"Output time resolution: {time_res.name}, displayed time resolution: {time_res.name} ",
                                size=12, transform=ax.transAxes, horizontalalignment='left',
                                verticalalignment='center')
                        ax.text(x=1.0, y=0.5,
                                s=f"Output category: {output_cat_name}",
                                size=18, transform=ax.transAxes, horizontalalignment='right',
                                verticalalignment='center')
                        ax.text(x=1.0, y=0.25,
                                s=f"Output variant: All",
                                size=12, transform=ax.transAxes, horizontalalignment='right',
                                verticalalignment='center')
                        ax.axis('off')

                        # Print footer information
                        ax = fig.add_subplot(spec[self.ROWS_PER_PAGE + 1, :])
                        ax.text(x=1.0, y=0.5,
                                s=f"commit: {self.Basic_info.commit} -- branch: {self.Basic_info.branch} -- "
                                  f"status: {self.Basic_info.status}", size=12, transform=ax.transAxes,
                                horizontalalignment='right', verticalalignment='center')
                        ax.axis('off')

                    else:
                        # All other pages do not need to have the extra rows for header and footer
                        spec = fig.add_gridspec(self.ROWS_PER_PAGE, self.COLUMNS_PER_PAGE)

                    for r in range(0, self.ROWS_PER_PAGE):
                        for c in range(0, self.COLUMNS_PER_PAGE):

                            if index_var < nvars:
                                # On the first page we start with one row later because we
                                if first_page:
                                    ax = fig.add_subplot(spec[r + 1, c])
                                else:
                                    ax = fig.add_subplot(spec[r, c])

                                data_set = nc_output.Datasets_1D[output_cat_name]

                                slice = data_set.iloc[:, index_running]
                                var_name = data_set.columns[index_running]


                                ax.plot(data_set['date'], slice, lw=1)
                                ax.set_title(var_name)
                                ax.set_ylabel(unit_set[var_name])
                                ax.set_xlabel(f'time (res: {time_res.name})')
                                ax.tick_params(labelrotation=45)

                                index_running += 1
                                index_var += 1

                    pdf.savefig(fig, orientation='portrait')
                    plt.close(fig)
                    first_page = False

                    if index_end >= nvars:
                        last_page = True
                        pdf.close()
                    else:
                        index_start += self.MAX_PLOTS_PER_PAGE
                        index_end += self.MAX_PLOTS_PER_PAGE

                t_stop = perf_counter()
                print(f"Done! ({np.round(t_stop - t1_start, 1)} sec.)")
            print(f"Done with 1D {identifier} variables.")

    def plot_2d(self):

        for identifier in self.Available_outputs:

            print(f"Performing 2D {identifier} variables... ")

            output_file = self.Available_outputs[identifier]

            cats = output_file.Target_categories
            sim_type = output_file.Simulation_type
            time_res = output_file.Time_resolution

            nc_output = QNC_ncdf_reader(self.output_path,
                                        cats,
                                        identifier,
                                        time_res
                                        )

            nc_output.Parse_env_and_variables()

            for output_cat_name in nc_output.output_cat_names:

                # Ploting routine
                print(f"     Plotting {output_cat_name} variables... ", end='')
                t1_start = perf_counter()

                var_names = nc_output.Dataset_Names_2D[output_cat_name]
                unit_names = nc_output.Units_2D[output_cat_name]
                nvars = len(var_names)


                # In case we do not have any 2D output available skip this file
                if nvars == 0:
                    continue

                export_filename = os.path.join(self.post_processing_path, f"{output_cat_name}_{identifier}_2D.pdf")

                index_start = self.TIME_VARIABLE_OFFSET
                index_running = index_start
                index_var = 0
                index_end = index_start + self.MAX_PLOTS_PER_PAGE

                pdf = PdfPages(export_filename)

                last_page = False
                first_page = True
                while not last_page:

                    fig = plt.figure(figsize=(10, 12), layout="constrained")

                    # On the first page we display header and footer information
                    if first_page:
                        # We have two more rows, one for header one for footer
                        spec = fig.add_gridspec(self.ROWS_PER_PAGE + 2, self.COLUMNS_PER_PAGE)

                        # Print header information first
                        ax = fig.add_subplot(spec[0, :])
                        ax.text(x=0.0, y=0.5,
                                s=f"{self.Basic_info.sitename}, {self.Basic_info.pft}, {self.Basic_info.user}, {self.Basic_info.date} ",
                                size=18, transform=ax.transAxes, horizontalalignment='left', verticalalignment='center')
                        ax.text(x=0.0, y=0.25,
                                s=f"Output time resolution: {time_res.name}, displayed time resolution: {time_res.name} ",
                                size=12, transform=ax.transAxes, horizontalalignment='left', verticalalignment='center')
                        ax.text(x=1.0, y=0.5,
                                s=f"Output category: {output_cat_name}",
                                size=18, transform=ax.transAxes, horizontalalignment='right', verticalalignment='center')
                        ax.text(x=1.0, y=0.25,
                                s=f"Output variant: {self.output_format.name}",
                                size=12, transform=ax.transAxes, horizontalalignment='right', verticalalignment='center')
                        ax.axis('off')

                        # Print footer information
                        ax = fig.add_subplot(spec[self.ROWS_PER_PAGE + 1, :])
                        ax.text(x=1.0, y=0.5, s=f"commit: {self.Basic_info.commit} -- branch: {self.Basic_info.branch} -- "
                                                f"status: {self.Basic_info.status}", size=12, transform=ax.transAxes,
                                horizontalalignment='right', verticalalignment='center')
                        ax.axis('off')

                    else:
                        # All other pages do not need to have the extra rows for header and footer
                        spec = fig.add_gridspec(self.ROWS_PER_PAGE, self.COLUMNS_PER_PAGE)

                    for r in range(0, self.ROWS_PER_PAGE):
                        for c in range(0, self.COLUMNS_PER_PAGE):

                            if index_var < nvars:

                                var_name = var_names[index_var]

                                # Load the 2D data directly
                                slice = nc_output.read_2D(output_cat_name, var_name)


                                for sub_index in range(0,2):
                                    # On the first page we start with one row later because we
                                    if first_page:
                                        ax = fig.add_subplot(spec[r + 1, c])
                                    else:
                                        ax = fig.add_subplot(spec[r, c])

                                    ndim2 = slice.shape[1] - self.TIME_VARIABLE_OFFSET + 1;

                                    for dim2 in range(0, ndim2):
                                        # Plot the slice of the data y = slice and x = the date string
                                        #ax.plot(slice['date'], slice[str(dim2)], lw=1)
                                        ax.plot(slice['date'],  slice[str(dim2)], lw=1)

                                ax.set_title(var_name)
                                ax.set_ylabel(unit_names[var_name])
                                ax.set_xlabel(f'time (res: {time_res.name})')
                                ax.tick_params(labelrotation=45)

                                index_running += 1
                                index_var += 1

                    pdf.savefig(fig, orientation='portrait')
                    plt.close(fig)
                    first_page = False

                    if index_end >= nvars:
                        last_page = True
                        pdf.close()
                    else:
                        index_start += self.MAX_PLOTS_PER_PAGE
                        index_end += self.MAX_PLOTS_PER_PAGE

                t_stop = perf_counter()
                print(f"Done! ({np.round(t_stop - t1_start, 1)} sec.)")
            print(f"Done with performing 2D {identifier} variables.")

            nc_output.Close()


    def Plot_2d_split(self):
        for identifier in self.Available_outputs:
            output_file = self.Available_outputs[identifier]

            print(f"Performing 2D {identifier} variables... ")

            cats = output_file.Target_categories
            sim_type = output_file.Simulation_type
            time_res = output_file.Time_resolution

            nc_output = QNC_ncdf_reader(self.output_path,
                                        cats,
                                        identifier,
                                        time_res
                                        )

            nc_output.Parse_env_and_variables()

            for output_cat_name in nc_output.output_cat_names:

                # Ploting routine
                print(f"     Plotting {output_cat_name} variables... ", end='')
                t1_start = perf_counter()

                var_names = nc_output.Dataset_Names_2D[output_cat_name]
                unit_names = nc_output.Units_2D[output_cat_name]
                nvars = len(var_names)

                nplots = nvars

                # We have soil layers
                if len(nc_output.soil_depths) != 0:
                    nplots  *= 2
                # We have canopy layers
                else:
                    nplots *= 2


                # In case we do not have any 2D output available skip this file
                if nvars == 0:
                    continue

                export_filename = os.path.join(self.post_processing_path, f"{output_cat_name}_{identifier}_2D.pdf")

                index_start = self.TIME_VARIABLE_OFFSET
                index_running = index_start
                index_var = 0
                index_end = index_start + self.MAX_PLOTS_PER_PAGE

                pdf = PdfPages(export_filename)

                last_page = False
                first_page = True
                while not last_page:

                    fig = plt.figure(figsize=(10, 12), layout="constrained")

                    # On the first page we display header and footer information
                    if first_page:
                        # We have two more rows, one for header one for footer
                        spec = fig.add_gridspec(self.ROWS_PER_PAGE + 2, self.COLUMNS_PER_PAGE)

                        # Print header information first
                        ax = fig.add_subplot(spec[0, :])
                        ax.text(x=0.0, y=0.5,
                                s=f"{self.Basic_info.sitename}, {self.Basic_info.pft}, {self.Basic_info.user}, {self.Basic_info.date} ",
                                size=18, transform=ax.transAxes, horizontalalignment='left', verticalalignment='center')
                        ax.text(x=0.0, y=0.25,
                                s=f"Output time resolution: {time_res.name}, displayed time resolution: {time_res.name} ",
                                size=12, transform=ax.transAxes, horizontalalignment='left', verticalalignment='center')
                        ax.text(x=1.0, y=0.5,
                                s=f"Output category: {output_cat_name}",
                                size=18, transform=ax.transAxes, horizontalalignment='right', verticalalignment='center')
                        ax.text(x=1.0, y=0.25,
                                s=f"Output variant: {self.output_format.name}",
                                size=12, transform=ax.transAxes, horizontalalignment='right', verticalalignment='center')
                        ax.axis('off')

                        # Print footer information
                        ax = fig.add_subplot(spec[self.ROWS_PER_PAGE + 1, :])
                        ax.text(x=1.0, y=0.5, s=f"commit: {self.Basic_info.commit} -- branch: {self.Basic_info.branch} -- "
                                                f"status: {self.Basic_info.status}", size=12, transform=ax.transAxes,
                                horizontalalignment='right', verticalalignment='center')
                        ax.axis('off')

                        cmap = plt.get_cmap("tab10")
                        if nc_output.Second_dim == Second_dim_type.Canopy_layer:

                            custom_lines_left = [Line2D([0], [0], color=cmap(i), lw=4) for i in range(0, int(nc_output.Nsecond_dim / 2))]
                            custom_lines_right = [Line2D([0], [0], color=cmap(i- int(nc_output.Nsecond_dim / 2)), lw=4) for i in range(int(nc_output.Nsecond_dim / 2), int(nc_output.Nsecond_dim))]

                            legend1 = plt.legend(custom_lines_left, range(0, int(nc_output.Nsecond_dim / 2)), loc=(0.05, 1.0), ncol = 3)
                            legend2 = plt.legend(custom_lines_right, range(int(nc_output.Nsecond_dim / 2), int(nc_output.Nsecond_dim)),loc=(0.6, 1.0), ncol = 3)
                            ax.add_artist(legend1)
                            ax.add_artist(legend2)
                    else:
                        # All other pages do not need to have the extra rows for header and footer
                        spec = fig.add_gridspec(self.ROWS_PER_PAGE, self.COLUMNS_PER_PAGE)

                    for r in range(0, self.ROWS_PER_PAGE):

                            if index_var < nvars:

                                var_name = var_names[index_var]

                                # Load the 2D data directly
                                slice = nc_output.read_2D(output_cat_name, var_name)

                                for sub_index in range(0, 2):
                                    # On the first page we start with one row later because we
                                    if first_page:
                                        ax = fig.add_subplot(spec[r + 1, sub_index])
                                    else:
                                        ax = fig.add_subplot(spec[r, sub_index])

                                    ndim2 = slice.shape[1] - self.TIME_VARIABLE_OFFSET + 1;
                                    ndim2 /= 2
                                    ndim2 = int(ndim2)
                                    for dim2 in range(ndim2 * sub_index, ndim2*(sub_index+1)):
                                        # Plot the slice of the data y = slice and x = the date string
                                        #ax.plot(slice['date'], slice[str(dim2)], lw=1)

                                        ax.plot(slice['date'], slice[str(dim2)], lw=1)

                                    if nc_output.Second_dims_2D[var_name] == "soil_layer":
                                        title_layer_str = "SL"
                                    else:
                                        title_layer_str = "CL"

                                    ax.set_title(var_name + " " +title_layer_str +"(" + str(ndim2 * sub_index) +"-"+str(ndim2*(sub_index+1))+")")
                                    ax.set_ylabel(unit_names[var_name])
                                    ax.set_xlabel(f'time (res: {time_res.name})')

                                    ax.tick_params(labelrotation=45)

                                index_running += 1
                                index_var += 1

                    pdf.savefig(fig, orientation='portrait')
                    plt.close(fig)
                    first_page = False

                    if index_end >= nplots:
                        last_page = True
                        pdf.close()
                    else:
                        index_start += self.MAX_PLOTS_PER_PAGE
                        index_end += self.MAX_PLOTS_PER_PAGE

                t_stop = perf_counter()
                print(f"Done! ({np.round(t_stop - t1_start, 1)} sec.)")
            print(f"Done with performing 2D {identifier}.")

            nc_output.Close()











