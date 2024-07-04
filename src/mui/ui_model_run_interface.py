import os
import pandas as pd
import numpy as np
from src.mui.designs.ui_quincy_design import Ui_MainWindow
from src.mui.ui_settings import Ui_Settings
from src.mui.var_types import Gridcell
from src.mui.var_types import Scenario
from src.mui.logging import MessageType
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import pyqtSlot, pyqtSignal, QThread, QObject
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure


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
        self.output_dfs_transient = {}
        self.output_dfs_spinup = {}

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


    def init(self, ui_settings: Ui_Settings, gridcell: Gridcell, scenario : Scenario):
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

        self.output_df_transient_achange = {}
        self.output_df_transient_bchange = {}
        self.output_df_spinup = {}

        self.load_spinup_data = False
        self.have_spinup_data = False
        self.have_transient_data = False

    def change_cb1(self):
        self.selected_vars[0] = self.ui.cB_output_1.currentText()

        if self.have_transient_data:
            self.lines_trans_b[0].set_xdata(self.output_df_transient_bchange[self.filename_vars[ self.selected_vars[0]]]["datetime"])
            self.lines_trans_b[0].set_ydata(self.output_df_transient_bchange[self.filename_vars[ self.selected_vars[0]]][ self.selected_vars[0]])

            self.lines_trans_a[0].set_xdata(self.output_df_transient_achange[self.filename_vars[ self.selected_vars[0]]]["datetime"])
            self.lines_trans_a[0].set_ydata(self.output_df_transient_achange[self.filename_vars[ self.selected_vars[0]]][ self.selected_vars[0]])

        if self.have_spinup_data:
            self.lines_spinup[0].set_xdata(self.output_df_spinup[self.filename_vars[self.selected_vars[0]]]["datetime"])
            self.lines_spinup[0].set_ydata(self.output_df_spinup[self.filename_vars[self.selected_vars[0]]][self.selected_vars[0]])


        self.axis[0].relim()
        self.axis[0].autoscale()
        self.axis[0].set_ylabel(self.selected_vars[0])

        if self.have_spinup_data:
            xmin = np.min(self.output_df_spinup[self.filename_vars[self.selected_vars[0]]]["datetime"])
            xmax = np.max(self.output_df_spinup[self.filename_vars[self.selected_vars[0]]]["datetime"])

            self.axis[0].set_xlim(xmin, xmax)

        if self.have_transient_data:
            xmax = np.max(self.output_dfs_transient[self.filename_vars[self.selected_vars[0]]]["datetime"])
            self.axis[0].set_xlim(xmin, xmax)

        self.canvas_output_mpl_1.draw_idle()
        self.canvas_output_mpl_1.flush_events()


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

        for df_str in ['vegfluxC', 'vegfluxH2O', 'veg_diagnostics', 'vegpoolC']:
            if self.have_spinup_data & self.load_spinup_data:
                try:


                    self.output_dfs_spinup[df_str] = pd.read_csv(f"{self.ui_settings.root_ui_directory}/{self.ui_settings.scenario_output_path}/{df_str}_spinup_{output_res}.txt", sep='\s+')
                    n_current_stamps = self.output_dfs_spinup[df_str].shape[0]

                    dates = np.array(f"{self.scenario.first_year_spinup}-01-01", 'datetime64[D]') + np.linspace(0,
                                                                                                             7 * n_current_stamps,
                                                                                                             n_current_stamps,
                                                                                                             dtype='timedelta64[D]')
                    self.output_dfs_spinup[df_str]["datetime"]  = dates

                    self.output_dfs_spinup[df_str]["year"]  = dates.astype('datetime64[Y]').astype(int) + 1970
                    # for i in range(0, n_current_stamps):
                    #     self.output_dfs_spinup[df_str].loci] = d0 + np.timedelta64(int(i * mult + mult),'D')

                    #times_np_64 = np.empty(n_current_stamps, dtype='datetime64[s]')
                    # for i in range(0, n_current_stamps):
                    #     self.output_dfs_spinup[df_str]["datetime"] = np.datetime64(f"{self.scenario.first_year_spinup}-01-01")
                    #     self.output_dfs_spinup[df_str]["datetime"] = self.output_dfs_spinup[df_str]["datetime"]
                    #
                    #     times_np_64[i] = np.datetime64(self.dF['date'][i])
                    #     np.datetime64()
                    #
                    # self.output_dfs_spinup[df_str]["datetime"] = pd.to_datetime(f"{self.scenario.first_year_spinup}-01-01")
                    # self.output_dfs_spinup[df_str]["datetime"]  = self.output_dfs_spinup[df_str]["datetime"] + pd.to_timedelta(np.arange(0, n_current_stamps) * mult + mult, unit="D")
                    #self.output_dfs_spinup[df_str]["year"]  = pd.DatetimeIndex(self.output_dfs_spinup[df_str]["datetime"]).year
                    self.current_year = int(n_current_stamps * mult / 365.0) + self.scenario.first_year_spinup

                except Exception as err:
                    sig_log.emit(f"Unexpected {err=}, {type(err)=}", MessageType.ERROR)
                    return
            else:
                try:
                    self.output_dfs_transient[df_str] = pd.read_csv(f"{self.ui_settings.root_ui_directory}/{self.ui_settings.scenario_output_path}/{df_str}_{output_res}.txt", sep='\s+')
                    n_current_stamps = self.output_dfs_transient[df_str].shape[0]
                    # self.output_dfs_transient[df_str]["datetime"] = pd.to_datetime(f"{self.scenario.first_year_transient}-01-01")
                    # self.output_dfs_transient[df_str]["datetime"]  = self.output_dfs_transient[df_str]["datetime"] + pd.to_timedelta(np.arange(0, n_current_stamps) * mult + mult, unit="D")
                    # self.output_dfs_transient[df_str]["year"]  = pd.DatetimeIndex(self.output_dfs_transient[df_str]["datetime"]).year
                    dates = np.array(f"{self.scenario.first_year_transient}-01-01", 'datetime64[D]') + np.linspace(0,
                                                                                                             7 * n_current_stamps,
                                                                                                             n_current_stamps,
                                                                                                             dtype='timedelta64[D]')
                    self.output_dfs_transient[df_str]["datetime"]  = dates
                    self.output_dfs_transient[df_str]["year"] = dates.astype('datetime64[Y]').astype(int) + 1970
                    self.current_year = int(n_current_stamps * mult / 365.0)+ self.scenario.first_year_transient

                except Exception as err:
                    sig_log.emit(f"Unexpected {err=}, {type(err)=}", MessageType.ERROR)
                    return

        if self.current_year >= self.scenario.first_year_change:
            sig_log.emit(f"Simulating manipulation year: {self.current_year}", MessageType.INFO)
        elif self.current_year >= self.scenario.first_year_transient:
            sig_log.emit(f"Simulating transient year: {self.current_year}", MessageType.INFO)
        else:
            sig_log.emit(f"Simulating spinup year: {self.current_year}", MessageType.INFO)


        if self.have_spinup_data:
            for df_str in ['vegfluxC', 'vegfluxH2O', 'veg_diagnostics','vegpoolC']:
                self.output_df_spinup[df_str] = self.output_dfs_spinup[df_str]

        if self.have_transient_data:
            for df_str in ['vegfluxC', 'vegfluxH2O', 'veg_diagnostics','vegpoolC']:
                index_a = self.output_dfs_transient[df_str]["year"] >= self.scenario.first_year_change
                index_b = self.output_dfs_transient[df_str]["year"] <  self.scenario.first_year_change
                self.output_df_transient_achange[df_str] = self.output_dfs_transient[df_str].loc[index_a]
                self.output_df_transient_bchange[df_str] = self.output_dfs_transient[df_str].loc[index_b]

        for i in range(len(self.selected_vars)):
            var = self.selected_vars[i]
            if self.have_spinup_data:
                self.lines_spinup[i].set_xdata(self.output_df_spinup[self.filename_vars[var]]["datetime"])
                self.lines_spinup[i].set_ydata(self.output_df_spinup[self.filename_vars[var]][var])

            if self.have_transient_data:
                self.lines_trans_b[i].set_xdata(self.output_df_transient_bchange[self.filename_vars[var]]["datetime"])
                self.lines_trans_b[i].set_ydata(self.output_df_transient_bchange[self.filename_vars[var]][var])

                self.lines_trans_a[i].set_xdata(self.output_df_transient_achange[self.filename_vars[var]]["datetime"])
                self.lines_trans_a[i].set_ydata(self.output_df_transient_achange[self.filename_vars[var]][var])

            self.axis[i].set_ylabel(var)
            self.axis[i].relim()
            self.axis[i].autoscale()

            xmin = np.min(self.output_df_spinup[self.filename_vars[var]]["datetime"])
            xmax = np.max(self.output_df_spinup[self.filename_vars[var]]["datetime"])

            if self.have_spinup_data:
                self.axis[i].set_xlim(xmin, xmax)

            if self.have_transient_data:
                xmax = np.max(self.output_dfs_transient[self.filename_vars[var]]["datetime"])
                self.axis[i].set_xlim(xmin, xmax)


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
