from src.mui.designs.quincy_ui_desin import Ui_MainWindow
from src.mui.ui_settings import Ui_Settings
from src.mui.var_types import Gridcell
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import pyqtSlot, pyqtSignal, QThread, QObject
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import pandas as pd
import numpy as np

class ModelRunDisplay:

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

        self.output_dfs = {}

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


    def init(self, ui_settings: Ui_Settings, gridcell: Gridcell):
        self.gridcell = gridcell
        self.ui_settings = ui_settings
        self.axis = []
        self.lines_b = []
        self.lines_a = []
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
            self.line_b, = self.axis[i].plot([pd.to_datetime('2015-09-25')], [0], color='black')
            self.line_a, = self.axis[i].plot([pd.to_datetime('2015-09-25')], [0], color='tab:red')
            self.lines_b.append(self.line_b)
            self.lines_a.append(self.line_a)

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


    def change_cb1(self):
        self.selected_vars[0] = self.ui.cB_output_1.currentText()

        self.lines_b[0].set_xdata(self.output_df_b[self.filename_vars[ self.selected_vars[0]]]["datetime"])
        self.lines_b[0].set_ydata(self.output_df_b[self.filename_vars[ self.selected_vars[0]]][ self.selected_vars[0]])

        self.lines_a[0].set_xdata(self.output_df_a[self.filename_vars[ self.selected_vars[0]]]["datetime"])
        self.lines_a[0].set_ydata(self.output_df_a[self.filename_vars[ self.selected_vars[0]]][ self.selected_vars[0]])

        self.axis[0].relim()
        self.axis[0].autoscale()
        self.axis[0].set_ylabel(self.selected_vars[0])

        self.canvas_output_mpl_1.draw_idle()
        self.canvas_output_mpl_1.flush_events()

    def prepare_plots(self):

        self.nyears_change = np.max([ int(self.ui.lineEdit_temp_years.text()),  int(self.ui.lineEdit_rain_years.text())])
        self.nyears = self.gridcell.max_year - self.gridcell.min_year + 1

        self.year_change = self.gridcell.max_year - self.nyears_change

    def update_output_plots(self):

        self.output_df_a = {}
        self.output_df_b = {}

        for df_str in ['vegfluxC', 'vegfluxH2O', 'veg_diagnostics', 'vegpoolC']:
            self.output_dfs[df_str] = pd.read_csv(f"{self.ui_settings.root_ui_directory}/{self.ui_settings.scenario_output_path}/{df_str}_weekly.txt", sep='\s+')
            n_current_stamps = self.output_dfs[df_str].shape[0]
            self.output_dfs[df_str]["datetime"] = pd.to_datetime(f"{self.gridcell.min_year}-01-01")
            self.output_dfs[df_str]["datetime"]  = self.output_dfs[df_str]["datetime"] + pd.to_timedelta(np.arange(0, n_current_stamps) * 7  + 7,unit="D")
            self.output_dfs[df_str]["year"]  = pd.DatetimeIndex(self.output_dfs[df_str]["datetime"]).year


        for df_str in ['vegfluxC', 'vegfluxH2O', 'veg_diagnostics','vegpoolC']:
            index_a = self.output_dfs[df_str]["year"] > self.year_change
            index_b = self.output_dfs[df_str]["year"] <= self.year_change
            self.output_df_a[df_str] = self.output_dfs[df_str].loc[index_a]
            self.output_df_b[df_str] = self.output_dfs[df_str].loc[index_b]

        # df_4 = pd.read_csv(f"{self.ui_settings.root_ui_directory}/{self.ui_settings.scenario_output_path}/veg_diagnostics_weekly.txt", sep='\s+')
        # self.df = pd.concat([self.df, df_2, df_3, df_4])
        # n_current_stamps = self.df.shape[0]



        for i in range(len(self.selected_vars)):

            var =  self.selected_vars[i]

            self.lines_b[i].set_xdata(self.output_df_b[self.filename_vars[var]]["datetime"])
            self.lines_b[i].set_ydata(self.output_df_b[self.filename_vars[var]][var])

            self.lines_a[i].set_xdata(self.output_df_a[self.filename_vars[var]]["datetime"])
            self.lines_a[i].set_ydata(self.output_df_a[self.filename_vars[var]][var])

            self.axis[i].set_ylabel(var)
            self.axis[i].relim()
            self.axis[i].autoscale()

        self.canvas_output_mpl_1.draw_idle()
        self.canvas_output_mpl_1.flush_events()
        self.canvas_output_mpl_2.draw_idle()
        self.canvas_output_mpl_2.flush_events()
        self.canvas_output_mpl_3.draw_idle()
        self.canvas_output_mpl_3.flush_events()
        self.canvas_output_mpl_4.draw_idle()
        self.canvas_output_mpl_4.flush_events()

        return n_current_stamps
