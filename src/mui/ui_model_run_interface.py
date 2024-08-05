import os
import pandas as pd
import numpy as np
from datetime import datetime
from src.mui.designs.ui_quincy_design import Ui_MainWindow
from src.mui.ui_settings import Ui_Settings
from src.mui.ui_settings import ModelOutputPlottingType
from src.mui.output_plot_interface import OutputPlotInterface
from src.mui.var_types import Gridcell
from src.mui.var_types import Scenario
from src.mui.logging import MessageType
from PyQt5 import QtCore, QtGui, QtWidgets
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from src.quincy.base.PFTTypes import PftQuincy


class UI_ModelRunInterface:

    def __init__(self, ui : Ui_MainWindow):
        self.ui = ui
        self.output_variables_str = ['NPP', 'GPP', 'Transpiration', 'Evaporation', 'LAI', 'BetaSoilGS','Total_C', 'HeartWood_C', 'Leaf_C']
        self.filename_vars = {}
        self.filename_vars['NPP'] = 'vegfluxC'
        self.filename_vars['GPP'] = 'vegfluxC'
        self.filename_vars['Transpiration'] = 'vegfluxH2O'
        self.filename_vars['Evaporation'] = 'vegfluxH2O'
        self.filename_vars['LAI'] = 'veg_diagnostics'
        self.filename_vars['BetaSoilGS'] = 'veg_diagnostics'
        self.filename_vars['Total_C'] = 'vegpoolC'
        self.filename_vars['Leaf_C'] = 'vegpoolC'
        self.filename_vars['HeartWood_C'] = 'vegpoolC'

        self.output_resolution_str_list = [s.name for s in ModelOutputPlottingType]

        self.output_plt_spinup_interface = {}
        self.output_plt_transient_interface = {}


    def setup_ui(self):

        self.ui.dockWidget_status_bar.setFloating(False)
        self.ui.dockWidget_status_bar.setContextMenuPolicy(QtCore.Qt.PreventContextMenu)
        x  = QtWidgets.QWidget()
        x.setMinimumSize(0,0)
        self.ui.dockWidget_status_bar.setTitleBarWidget(x)

        self.ui.dockWidget_logger.setFloating(False)
        self.ui.dockWidget_logger.setContextMenuPolicy(QtCore.Qt.PreventContextMenu)
        x  = QtWidgets.QWidget()
        x.setMinimumSize(0,0)
        self.ui.dockWidget_logger.setTitleBarWidget(x)


    def init(self,
             ui_settings    : Ui_Settings,
             gridcell       : Gridcell,
             scenario       : Scenario):

        self.scenario = scenario
        self.gridcell = gridcell
        self.ui_settings = ui_settings
        self.axis = []

        self.lines_spinup= []
        self.lines_trans_b = []
        self.lines_trans_a = []

        self.canvas_output_mpl_1 = FigureCanvas(Figure(tight_layout=True))
        self.canvas_output_mpl_2 = FigureCanvas(Figure(tight_layout=True))
        self.canvas_output_mpl_3 = FigureCanvas(Figure(tight_layout=True))
        self.canvas_output_mpl_4 = FigureCanvas(Figure(tight_layout=True))

        self.ui.mpl_container_1.addWidget(self.canvas_output_mpl_1)
        self.ui.mpl_container_2.addWidget(self.canvas_output_mpl_2)
        self.ui.mpl_container_3.addWidget(self.canvas_output_mpl_3)
        self.ui.mpl_container_4.addWidget(self.canvas_output_mpl_4)

        self.axis.append(self.canvas_output_mpl_1.figure.add_subplot(111))
        self.axis.append(self.canvas_output_mpl_2.figure.add_subplot(111))
        self.axis.append(self.canvas_output_mpl_3.figure.add_subplot(111))
        self.axis.append(self.canvas_output_mpl_4.figure.add_subplot(111))

        for i in range(4):
            self.axis[i].tick_params(axis='x', labelrotation=45)
            self.line_0, = self.axis[i].plot([pd.to_datetime('2015-09-25')], [0], color='black')
            self.line_b, = self.axis[i].plot([pd.to_datetime('2015-09-25')], [0], color='orange')
            self.line_a, = self.axis[i].plot([pd.to_datetime('2015-09-25')], [0], color='tab:red')
            self.lines_trans_b.append(self.line_b)
            self.lines_trans_a.append(self.line_a)
            self.lines_spinup.append(self.line_0)

        self.ui.cB_output_1.addItems(self.output_variables_str)
        self.ui.cB_output_2.addItems(self.output_variables_str)
        self.ui.cB_output_3.addItems(self.output_variables_str)
        self.ui.cB_output_4.addItems(self.output_variables_str)

        self.ui.cB_output_1.currentTextChanged.connect(self.change_cb1)

        self.selected_vars = []
        self.selected_vars.append(self.output_variables_str[0])
        self.selected_vars.append(self.output_variables_str[2])
        self.selected_vars.append(self.output_variables_str[4])
        self.selected_vars.append(self.output_variables_str[6])
        self.ui.cB_output_1.setCurrentText(self.selected_vars[0])
        self.ui.cB_output_2.setCurrentText(self.selected_vars[1])
        self.ui.cB_output_3.setCurrentText(self.selected_vars[2])
        self.ui.cB_output_4.setCurrentText(self.selected_vars[3])

        self.selected_output_resolution_list = []
        self.selected_output_resolution_list.append(ModelOutputPlottingType.Weekly)
        self.selected_output_resolution_list.append(ModelOutputPlottingType.Weekly)
        self.selected_output_resolution_list.append(ModelOutputPlottingType.Weekly)
        self.selected_output_resolution_list.append(ModelOutputPlottingType.Weekly)
        self.ui.cB_res_1.addItems(self.output_resolution_str_list)
        self.ui.cB_res_2.addItems(self.output_resolution_str_list)
        self.ui.cB_res_3.addItems(self.output_resolution_str_list)
        self.ui.cB_res_4.addItems(self.output_resolution_str_list)
        self.ui.cB_res_1.setCurrentText(self.selected_output_resolution_list[0].name)
        self.ui.cB_res_2.setCurrentText(self.selected_output_resolution_list[1].name)
        self.ui.cB_res_3.setCurrentText(self.selected_output_resolution_list[2].name)
        self.ui.cB_res_4.setCurrentText(self.selected_output_resolution_list[3].name)

        self.ui.cB_res_1.currentTextChanged.connect(self.change_cb1)

        self.output_df_transient_achange = {}
        self.output_df_transient_bchange = {}

        self.load_spinup_data = False
        self.have_spinup_data = False
        self.have_transient_data = False

        for pft in PftQuincy:
            self.ui.comboBox_PFT.addItem(pft.name)

    def change_cb1(self):
        index = 0
        self.selected_vars[index] = self.ui.cB_output_1.currentText()
        self.selected_output_resolution_list[index] = ModelOutputPlottingType[self.ui.cB_res_1.currentText()]
        try:
            self._update_single_plot(index)
            self.canvas_output_mpl_1.draw_idle()
            self.canvas_output_mpl_1.flush_events()

        except Exception as err:
            print(f"Unexpected {err=}, {type(err)=}", MessageType.ERROR.value)
            self.canvas_output_mpl_1.draw_idle()
            self.canvas_output_mpl_1.flush_events()
            return


    def init_quincy_config(self):

        dir_name = os.path.join(self.ui_settings.root_ui_directory,self.ui_settings.scenario_output_path)
        test = os.listdir(dir_name)

        for item in test:
            if item.endswith(".txt"):
                os.remove(os.path.join(dir_name, item))

        from src.quincy.base.NamelistTypes import OutputIntervalFlux
        from src.quincy.base.NamelistTypes import ForcingMode

        self.output_time_res = OutputIntervalFlux.WEEKLY

        nyears_change = np.max([ int(self.ui.lineEdit_temp_years.text()),  int(self.ui.lineEdit_rain_years.text())])
        nyear_spinup = int(self.ui.lineEdit_nyear_spinup.text())
        nyear_transient = self.scenario.forcing_dataset.max_year - self.scenario.forcing_dataset.min_year  + 1

        self.scenario.nyear_spinup = nyear_spinup
        self.scenario.parse_datetime_multiplier(self.output_time_res)
        self.scenario.parse_simulation_length(nyear_spinup, nyear_transient, nyears_change)
        self.scenario.parse_simulation_years()

        self.current_year = self.scenario.first_year_spinup

        if self.scenario.forcing_mode == ForcingMode.STATIC:
            self.load_spinup_data = False
            self.have_spinup_data = False
            self.have_transient_data = True
        else:
            self.load_spinup_data = True
            self.have_spinup_data = True
            self.have_transient_data = False

    def update_output_plots(self, sig_log):

        output_res = "weekly"
        mult = self.scenario.time_multiplier
        self.output_df_transient_achange = {}
        self.output_df_transient_bchange = {}
        self.output_df_spinup = {}

        for df_str in self.ui_settings.list_text_output_cats:
            if self.have_spinup_data & self.load_spinup_data:
                try:
                    self.output_plt_spinup_interface[df_str] = OutputPlotInterface(self.ui_settings,
                                        self.scenario,
                                        df_str,
                                        output_res,
                                        is_spinup = True)

                    self.output_plt_spinup_interface[df_str].load_data()
                    self.current_year = int(self.output_plt_spinup_interface[df_str].n_ts * mult / 365.0) + self.scenario.first_year_spinup

                except Exception as err:
                    sig_log.emit(f"Unexpected {err=}, {type(err)=}", MessageType.ERROR)
                    return
            else:
                try:
                    self.output_plt_transient_interface[df_str] = OutputPlotInterface(self.ui_settings,
                                        self.scenario,
                                        df_str,
                                        output_res,
                                        is_spinup = False)

                    self.output_plt_transient_interface[df_str].load_data()
                    self.current_year = int(self.output_plt_transient_interface[df_str].n_ts * mult / 365.0) + self.scenario.first_year_transient

                except Exception as err:
                    sig_log.emit(f"Unexpected {err=}, {type(err)=}", MessageType.ERROR)
                    return

        if self.current_year >= self.scenario.first_year_change:
            sig_log.emit(f"Simulating manipulation year: {self.current_year}", MessageType.INFO)
        elif self.current_year >= self.scenario.first_year_transient:
            sig_log.emit(f"Simulating transient year: {self.current_year}", MessageType.INFO)
        else:
            sig_log.emit(f"Simulating spinup year: {self.current_year}", MessageType.INFO)

        for i in range(len(self.selected_vars)):
            self._update_single_plot(i)

        self.canvas_output_mpl_1.draw_idle()
        self.canvas_output_mpl_1.flush_events()
        self.canvas_output_mpl_2.draw_idle()
        self.canvas_output_mpl_2.flush_events()
        self.canvas_output_mpl_3.draw_idle()
        self.canvas_output_mpl_3.flush_events()
        self.canvas_output_mpl_4.draw_idle()
        self.canvas_output_mpl_4.flush_events()

        # Check if the transient data exists
        # if so we do not reload the spinup data
        if self.load_spinup_data:
            if os.path.exists(f"{self.ui_settings.root_ui_directory}/"
                f"{self.ui_settings.scenario_output_path}/{df_str}_{output_res}.txt"):
                self.load_spinup_data = False
                self.have_transient_data = True

        return self.current_year - self.scenario.first_year_spinup


    def _update_single_plot(self, plot_window_index):
        i = plot_window_index
        var = self.selected_vars[i]
        file_contains_var = self.filename_vars[var]

        if self.have_spinup_data:
            self.output_plt_spinup_interface[file_contains_var].update_plot(
                self.selected_output_resolution_list[i],
                var,
                self.lines_spinup[i])

        if self.have_transient_data:
            self.output_plt_transient_interface[file_contains_var].update_plot_scenario(
                self.selected_output_resolution_list[i],
                var,
                self.scenario.first_year_change - 1,
                self.lines_trans_b[i],
                self.lines_trans_a[i])

        self.axis[i].set_ylabel(var)
        self.axis[i].relim()
        self.axis[i].autoscale()

        if self.have_spinup_data:
            xmin = np.min(self.output_plt_spinup_interface[file_contains_var].dfs["datetime"])
            xmax = np.max(self.output_plt_spinup_interface[file_contains_var].dfs["datetime"])

        if self.have_transient_data:
            xmax = self.output_plt_transient_interface[file_contains_var].max_year

        if self.have_spinup_data:
            self.axis[i].set_xlim(xmin, xmax)