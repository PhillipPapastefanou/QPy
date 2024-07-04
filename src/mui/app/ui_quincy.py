from src.mui.designs.ui_quincy_design import Ui_MainWindow
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import pyqtSlot, pyqtSignal, QThread, QObject
from src.mui.logging import MessageType
from src.mui.logging import MessageFormat


from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.backend_bases import MouseButton
import cartopy.crs as ccrs

import numpy as np
import pandas as pd
import os
from queue import Queue
from datetime import datetime
import time
import subprocess
import shutil

from src.mui.forcing_prep import ForcingSlicer
from src.mui.forcing_prep import ForcingGenerator
from src.mui.ui_settings import Ui_Settings
from src.mui.ui_model_run_interface import UI_ModelRunInterface
from src.mui.var_types import Gridcell
from src.mui.var_types import ForcingDataset
from src.mui.var_types import Scenario
import sys


class UI_Quincy(QtWidgets.QMainWindow, Ui_MainWindow):
    def __init__(self, settings: Ui_Settings):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.ui_settings = settings

        self.model_run_display = UI_ModelRunInterface(self.ui)
        self.model_run_display.setup_ui()

        self.splitDockWidget(self.ui.dockWidget_output_1, self.ui.dockWidget_output_2 ,QtCore.Qt.Horizontal)
        self.splitDockWidget(self.ui.dockWidget_output_3, self.ui.dockWidget_output_4 ,QtCore.Qt.Horizontal)
        self.init()


    def init(self):


        self.gridcell = Gridcell()
        self.forcing_dataset = ForcingDataset()
        self.scenario = Scenario(self.forcing_dataset)

        self.p1 = ccrs.PlateCarree()
        self.p2 = ccrs.PlateCarree()

        self.canvas_worldmap = FigureCanvas(Figure(tight_layout=True))
        self.ui.verticalLayout_worldmap_mpl.addWidget(self.canvas_worldmap)

        self.canvas_forcing = FigureCanvas(Figure(tight_layout=True))
        self.ui.verticalLayout_forcing_display.addWidget(self.canvas_forcing)

        #self.root_path_clim_forcing = os.path.join(self.ui_settings.directory_QPy, 'forcing', 'cru_jra_2.4')
        self.root_path_clim_forcing = os.path.join(self.ui_settings.directory_forcing, 'cru_jra_2.4')
        self.forcing_slicer = ForcingSlicer(root_path=self.root_path_clim_forcing)
        self.forcing_dataset = self.forcing_slicer.forc_dataset

        self.ui.lineEdit_offset.setText(str(self.forcing_dataset.offset))
        self.ui.lineEdit_resolution.setText(str(self.forcing_dataset.res))
        self.ui.lineEdit_first_year.setText(str(self.forcing_dataset.min_year))
        self.ui.lineEdit_last_year.setText(str(self.forcing_dataset.max_year))
        self.ui.comboBox_forcing_dataset.addItem("CRU_JRA_2.4")


        ax_temp = self.canvas_forcing.figure.add_subplot(111)
        ax2 = ax_temp.twinx()
        ax_temp.axes.set_xlabel('months')
        ax2.set_ylabel('Temperature [C]', color='red')
        ax_temp.axes.set_ylabel('Precipitation $[\mathrm{mm}$ $\mathrm{month}^{-1}]$', color='tab:blue')
        ax_temp.axes.yaxis.label.set_color('tab:blue')
        ax_temp.axes.tick_params(axis='y', colors='tab:blue')
        ax_temp.set_xticks([])
        # for minor ticks
        ax_temp.set_xticks([], minor=True)
        ax_temp.text(0.5, 0.5, "Please click on the above map\nto select a location", size=18,
                     horizontalalignment='center',
                     verticalalignment='center')
        ax2.spines['left'].set_color('tab:blue')
        ax2.spines['right'].set_color('red')
        ax2.yaxis.label.set_color('red')
        ax2.tick_params(axis='y', colors='red')
        self.canvas_forcing.draw_idle()
        self.draw_worldmap()

        self.canvas_worldmap.mpl_connect("button_press_event", self.on_press_worldmap)
        self.ui.lineEdit_lon.editingFinished.connect(self.text_changed_label_lon)
        self.ui.lineEdit_lat.editingFinished.connect(self.text_changed_label_lat)

        self.init_manip()
        self.init_run()

        self.model_run_display.init(self.ui_settings, self.gridcell, self.scenario)
        self.ui.lineEdit_nyear_spinup.setText(str(self.scenario.nyear_spinup))


        #Todo temporary: remove
        self.ui.lineEdit_lon.setText("-60.25")
        self.ui.lineEdit_lat.setText("-3.25")
        self.text_changed_label_lon()
        self.text_changed_label_lat()


    def onCountChanged(self, value):
        self.ui.progressBar_model_progress.setValue(value)

    def resetProgressBar(self, min, max):
        self.ui.progressBar_model_progress.setMinimum(min)
        self.ui.progressBar_model_progress.setMaximum(max)

    def init_manip(self):

        # self.ui.tab_temp = QtWidgets.QWidget()
        # self.ui.tab_temp.setObjectName("tab_temp")
        self.ui.tabWidget_manip_display.setTabText(self.ui.tabWidget_manip_display.indexOf(self.ui.tab_temp), "Temp")
        #self.tabWidget_manip_display.setTabText(self.tabWidget_manip_display.indexOf(self.tab_rain), _translate("MainWindow", "Rain"))
        #self.ui.tabWidget_manip_display.addTab(self.ui.tab_temp, "")


        self.ui.tabWidget_manip_display.setTabText(self.ui.tabWidget_manip_display.indexOf(self.ui.tab_rain), "Rain")

        self.ui.tab_co2 = QtWidgets.QWidget()
        self.ui.tab_co2.setObjectName("tab_co2")
        self.ui.tabWidget_manip_display.addTab(self.ui.tab_co2, "CO2")


        self.ui.tab_temp.layout = QtWidgets.QVBoxLayout()
        self.canvas_temp = FigureCanvas(Figure(tight_layout=True))
        self.ui.tab_temp.layout.addWidget(self.canvas_temp)
        self.ui.tab_temp.setLayout(self.ui.tab_temp.layout)
        self.ax_temp = self.canvas_temp.figure.add_subplot(111)
        self.ui.temp_data_base, = self.ax_temp.plot([], [])
        self.ui.temp_data_manip, = self.ax_temp.plot([], [])
        self.ui.horizontalSlider_temp_change.valueChanged.connect(self.update_temp_change)
        self.ax_temp.set_xticks([])
        self.ax_temp.set_yticks([])
        # for minor ticks
        self.ax_temp.set_xticks([], minor=True)
        self.ax_temp.text(0, 0, "Please click on the above map\nto select a location", size = 12, horizontalalignment='center',
             verticalalignment='center')
        self.first_time_selection = True


        self.ui.tab_rain.layout = QtWidgets.QVBoxLayout()
        self.canvas_rain = FigureCanvas(Figure(tight_layout=True))
        self.ui.tab_rain.layout.addWidget(self.canvas_rain)
        self.ui.tab_rain.setLayout(self.ui.tab_rain.layout)
        self.ax_rain = self.canvas_rain.figure.add_subplot(111)
        self.rain_data_base, = self.ax_rain.plot([], [])
        self.rain_data_manip, = self.ax_rain.plot([], [])
        self.ui.horizontalSlider_rain_change.valueChanged.connect(self.update_rain_change)
        self.ax_rain.set_xticks([])
        self.ax_rain.set_yticks([])
        # for minor ticks
        self.ax_rain.set_xticks([], minor=True)

        self.ui.lineEdit_temp_change.setText("0 \xb0C")
        self.ui.lineEdit_rain_change.setText("0 mm")
        self.ui.lineEdit_co2_change.setText("0 ppm")
        self.ui.lineEdit_temp_years.setText("10")
        self.ui.lineEdit_rain_years.setText("10")
        self.ui.lineEdit_co2_years.setText("10")

    def init_run(self):
        self.ui.pushButton_run_model.clicked.connect(self.run_model)
        self.ui.pushButton_stop_model.clicked.connect(self.stop_model)

    def draw_temp_plot(self):
        temp_change_slider = self.ui.horizontalSlider_temp_change.value()
        self.temp_change = temp_change_slider/4.0
        temp_year_range = int(self.ui.lineEdit_temp_years.text())

        self.df_manip['tmp'] = self.df_base['tmp']
        self.df_manip['add'] = 0.0
        index = self.df_manip.index.year > self.gridcell.max_year - temp_year_range
        self.df_manip.loc[index, 'add'] = np.arange(0, 12 * temp_year_range) / 12 / temp_year_range * self.temp_change
        self.df_manip['tmp'] += self.df_manip['add']


        self.temp_data_base.set_xdata(self.df_base.index)
        self.temp_data_base.set_ydata(self.df_base['tmp'] - 273.15)
        self.temp_data_manip.set_xdata(self.df_manip.index)
        self.temp_data_manip.set_ydata(self.df_manip['tmp'] - 273.15)

        self.ax_temp.relim()
        self.ax_temp.autoscale_view()
        self.canvas_temp.draw()
        self.canvas_temp.flush_events()
    def draw_rain_plot(self):
        rain_change_slider = self.ui.horizontalSlider_rain_change.value()
        self.rain_change = rain_change_slider
        rain_year_range = int(self.ui.lineEdit_rain_years.text())

        self.df_manip['pre'] = self.df_base['pre']
        self.df_manip['add'] = 0.0
        index = self.df_manip.index.year > self.gridcell.max_year - rain_year_range
        self.df_manip.loc[index, 'add'] = np.arange(0, 12 * rain_year_range)/ 12 / rain_year_range * self.rain_change
        self.df_manip['pre'] += self.df_manip['add']
        self.df_manip.loc[self.df_manip['pre'] < 0.0, 'pre'] = 0.0

        self.rain_data_base.set_xdata(self.df_base.index)
        self.rain_data_base.set_ydata(self.df_base['pre'])
        self.rain_data_manip.set_xdata(self.df_manip.index)
        self.rain_data_manip.set_ydata(self.df_manip['pre'])

        self.ax_rain.relim()
        self.ax_rain.autoscale_view()
        self.canvas_rain.draw()
        self.canvas_rain.flush_events()
    def update_temp_change(self):
        self.draw_temp_plot()
        self.ui.lineEdit_temp_change.setText(f'{self.temp_change} \xb0C')
        self.ui.tabWidget_manip_display.setCurrentIndex(0)
    def update_rain_change(self):
        self.draw_rain_plot()
        self.ui.lineEdit_rain_change.setText(f'{self.rain_change} mm')
        self.ui.tabWidget_manip_display.setCurrentIndex(1)
    def draw_worldmap(self):
        self.canvas_worldmap.axes = self.canvas_worldmap.figure.add_subplot(111, projection=self.p1)
        self.canvas_worldmap.axes.stock_img()
        self.canvas_worldmap.axes.set_global()
        self.canvas_worldmap.axes.gridlines()
        self.canvas_worldmap.axes.coastlines()
        self.canvas_worldmap.axes.scatter(x=self.gridcell.lon_pts,
                                          y=self.gridcell.lat_pts,
                                          color='red',
                                          edgecolors='black',
                                          transform=self.p1, zorder=1)
        self.canvas_worldmap.draw_idle()
    def draw_forcing(self, df):

        self.canvas_forcing.figure.clear()
        ax = self.canvas_forcing.figure.add_subplot(111)
        ax2 = ax.twinx()
        ax.axes.bar(np.arange(1, 13), df['pre'], zorder=2, color='tab:blue', alpha=0.75)
        ax2.plot(df['tmp'] - 273.15, 'red', zorder=1)
        ax.axes.set_xlabel('months')
        ax2.set_ylabel('Temperature [C]', color='red')
        ax.axes.set_ylabel('Precipitation $[\mathrm{mm}$ $\mathrm{month}^{-1}]$', color='tab:blue')
        ax.axes.yaxis.label.set_color('tab:blue')
        ax.axes.tick_params(axis='y', colors='tab:blue')
        ax2.spines['left'].set_color('tab:blue')
        ax2.spines['right'].set_color('red')
        ax2.yaxis.label.set_color('red')
        ax2.tick_params(axis='y', colors='red')
        self.canvas_forcing.draw_idle()
    def text_changed_label_lat(self):

        try:
            lat_new = float(self.ui.lineEdit_lat.text())
            if abs(lat_new - self.gridcell.lat_pts) < 1E-6:
                return
            self.gridcell.lat_pts = lat_new
        except:
            # Todo Write a statement
            # but nothing to do here
            dummy = 42

        self.gridcell.lat_pts = self.round_coordinate(self.gridcell.lat_pts, self.forcing_dataset.offset, self.forcing_dataset.res)
        self.gridcell.lat_pts = self.constrain(self.gridcell.lat_pts, self.forcing_dataset.min_lat, self.forcing_dataset.max_lat)
        self.ui.lineEdit_lat.setText(str(np.round(self.gridcell.lat_pts, 2)))

        self.draw_worldmap()
        self.df_base  = self.forcing_slicer.get_temp_prec_slice(self.gridcell.lon_pts, self.gridcell.lat_pts)
        df_monthly_avg =  self.df_base.groupby(self.df_base.index.month).mean()

        self.draw_forcing(df_monthly_avg)
    def text_changed_label_lon(self):
        try:
            lon_new = float(self.ui.lineEdit_lon.text())
            if abs(lon_new - self.gridcell.lon_pts) < 1E-6:
                return
            self.gridcell.lon_pts = lon_new
        except:
            # Todo Write a statement
            # but nothing to do here
            dummy = 42

        self.gridcell.lon_pts = self.round_coordinate(self.gridcell.lon_pts, self.forcing_dataset.offset, self.forcing_dataset.res)
        self.gridcell.lon_pts = self.constrain(self.gridcell.lon_pts, self.forcing_dataset.min_lon, self.forcing_dataset.max_lon)
        self.ui.lineEdit_lon.setText(str(np.round(self.gridcell.lon_pts, 2)))

        self.df_base = self.forcing_slicer.get_temp_prec_slice(self.gridcell.lon_pts, self.gridcell.lat_pts)
        self.df_manip = self.df_base.copy()
        df_monthly_avg = self.df_base.groupby(self.df_base.index.month).mean()
        self.draw_forcing(df_monthly_avg)

        if self.first_time_selection:
            self.ax_temp = self.canvas_temp.figure.add_subplot(111)
            self.temp_data_base, = self.ax_temp.plot([pd.to_datetime('2015-09-25')], [0], color='black', alpha=0.75,
                                                     label="base")
            self.temp_data_manip, = self.ax_temp.plot([pd.to_datetime('2015-09-25')], [0], color='tab:red', alpha=0.75,
                                                      label="manip")
            self.ax_temp.tick_params(axis='x', labelrotation=45)
            self.ax_temp.set_ylabel('Temperature [C]')
            self.ax_temp.legend(loc='lower left')

            self.ax_rain = self.canvas_rain.figure.add_subplot(111)
            self.rain_data_base, = self.ax_rain.plot([pd.to_datetime('2015-09-25')], [0], color='black', alpha=0.75,
                                                     label="base")
            self.rain_data_manip, = self.ax_rain.plot([pd.to_datetime('2015-09-25')], [0], color='tab:red', alpha=0.75,
                                                      label="manip")
            self.ax_rain.tick_params(axis='x', labelrotation=45)
            self.ax_rain.set_ylabel('Rainfall [mm]')
            self.ax_rain.legend(loc='lower left')

            self.first_time_selection = False

        self.draw_temp_plot()
        self.draw_rain_plot()
    def on_press_worldmap(self, event):
        lon, lat = self.p1.transform_point(event.xdata, event.ydata, self.p2)
        lon = self.round_coordinate(lon, offset = self.forcing_dataset.offset, res = self.forcing_dataset.res)
        lat = self.round_coordinate(lat, offset = self.forcing_dataset.offset, res = self.forcing_dataset.res)

        if event.button == MouseButton.LEFT:
            self.gridcell.lon_pts = lon
            self.gridcell.lat_pts = lat
            self.ui.lineEdit_lon.setText(str(np.round(lon,2)))
            self.ui.lineEdit_lat.setText(str(np.round(lat, 2)))
            self.draw_worldmap()
            self.df_base = self.forcing_slicer.get_temp_prec_slice(lon, lat)
            self.df_manip = self.df_base.copy()
            df_monthly_avg = self.df_base.groupby(self.df_base.index.month).mean()
            self.draw_forcing(df_monthly_avg)

            if self.first_time_selection:
                self.ax_temp = self.canvas_temp.figure.add_subplot(111)
                self.temp_data_base, = self.ax_temp.plot([pd.to_datetime('2015-09-25')], [0], color='black', alpha = 0.75, label="base")
                self.temp_data_manip, = self.ax_temp.plot([pd.to_datetime('2015-09-25')], [0], color='tab:red', alpha= 0.75, label="manip")
                self.ax_temp.tick_params(axis='x', labelrotation=45)
                self.ax_temp.set_ylabel('Temperature [C]')
                self.ax_temp.legend(loc='lower left')

                self.ax_rain = self.canvas_rain.figure.add_subplot(111)
                self.rain_data_base, = self.ax_rain.plot([pd.to_datetime('2015-09-25')], [0], color='black', alpha = 0.75, label="base")
                self.rain_data_manip, = self.ax_rain.plot([pd.to_datetime('2015-09-25')], [0], color='tab:red', alpha= 0.75, label="manip")
                self.ax_rain.tick_params(axis='x', labelrotation=45)
                self.ax_rain.set_ylabel('Rainfall [mm]')
                self.ax_rain.legend(loc='lower left')

                self.first_time_selection = False

            self.draw_temp_plot()
            self.draw_rain_plot()


    def run_model(self):
        if self.df_base.isnull().values.any():
            self.append_log("Nothing terrestrial is growing here! Selected different gridcell.", MessageType.WARN.value)
            return

        self.ui.pushButton_run_model.setEnabled(False)
        self.ui.pushButton_stop_model.setEnabled(True)

        # Start computation
        self.running_thread = ComputationThread(self)
        self.running_thread.finished.connect(self.on_thread_finished)
        self.running_thread.progressedChanged.connect(self.onCountChanged)
        self.running_thread.progressBarReset.connect(self.resetProgressBar)
        self.running_thread.sig_log.connect(self.append_log)
        self.running_thread.start()

    def stop_model(self):
        self.running_thread.stop()
        self.ui.pushButton_run_model.setEnabled(True)
        self.ui.pushButton_stop_model.setEnabled(False)
    def on_thread_finished(self):
        self.running_thread.deleteLater()
        self.ui.pushButton_run_model.setEnabled(True)
        self.ui.pushButton_stop_model.setEnabled(False)
    def result_ready(self, result):
        self.pB_run.setEnabled(True)
        self.pB_stop.setEnabled(False)
        self.running_thread = None
    def create_dirs(self):
        self.ui_settings.scenario_output_path = f"{self.gridcell.lon_pts}_{self.gridcell.lat_pts}"
        os.makedirs(self.ui_settings.scenario_output_path, exist_ok=True)
    def export_monthly_forcing(self):
        df_other = self.forcing_slicer.get_other_forcing(self.gridcell.lon_pts, self.gridcell.lat_pts)
        df_other['tmp'] = self.df_manip['tmp']
        df_other['pre'] = self.df_manip['pre']
        df_other.to_csv(os.path.join(self.ui_settings.scenario_output_path,"monthly_forcing.csv"))

        df_site_data = pd.DataFrame()
        df_site_data['lon'] = [self.gridcell.lon_pts]
        df_site_data['lat'] = [self.gridcell.lat_pts]
        df_site_data['min_year'] = [self.gridcell.min_year]
        df_site_data['max_year'] = [self.gridcell.max_year]
        df_site_data.to_csv(os.path.join(self.ui_settings.scenario_output_path,"site_data.csv"), index=False)

    def generate_subdaily_forcing(self):
        generator = ForcingGenerator(settings=self.ui_settings)
        generator.generate_subdaily_forcing(os.path.join(self.ui_settings.root_ui_directory,self.ui_settings.scenario_output_path))
        generator.generate_additional_quincy_forcing(self.gridcell.lon_pts, self.gridcell.lat_pts, self.ui_settings.scenario_output_path)


    def generate_namelist(self):
        from src.quincy.IO.NamelistReader import NamelistReader
        from src.quincy.IO.NamelistWriter import NamelistWriter
        from src.quincy.base.NamelistTypes import ForcingMode
        from src.quincy.base.NamelistTypes import OutputIntervalPool
        from src.quincy.base.NamelistTypes import OutputIntervalFlux
        from src.quincy.base.PFTTypes import PftQuincy

        reader = NamelistReader(self.ui_settings.quincy_namelist_path)
        namelist = reader.parse()
        # Dynamic changes

        namelist.base_ctl.output_end_last_day_year  = self.gridcell.max_year - self.gridcell.min_year + 1
        namelist.base_ctl.forcing_file_start_yr = self.gridcell.min_year
        namelist.base_ctl.forcing_file_last_yr = self.gridcell.max_year
        namelist.jsb_forcing_ctl.simulation_length_number  = self.gridcell.max_year - self.gridcell.min_year + 1
        namelist.jsb_forcing_ctl.transient_simulation_start_year = self.scenario.first_year_transient
        namelist.jsb_forcing_ctl.forcing_mode = self.scenario.forcing_mode
        namelist.jsb_forcing_ctl.transient_spinup_years = self.scenario.nyear_spinup
        namelist.grid_ctl.latitude = self.gridcell.lat_pts
        namelist.grid_ctl.longitude = self.gridcell.lon_pts



        from src.quincy.base.NamelistTypes import VegBnfScheme
        from src.quincy.base.NamelistTypes import BiomassAllocScheme

        #Static changes from usecase 80:
        namelist.vegetation_ctl.veg_bnf_scheme = VegBnfScheme.UNLIMITED
        namelist.vegetation_ctl.biomass_alloc_scheme = BiomassAllocScheme.DYNAMIC

        namelist.assimilation_ctl.flag_t_jmax_acclimation = True
        namelist.assimilation_ctl.flag_t_resp_acclimation = True

        namelist.phenology_ctl.lai_max = 6.0
        namelist.spq_ctl.nsoil_energy = 15
        namelist.spq_ctl.nsoil_water = 15

        from src.quincy.base.NamelistTypes import SbModelScheme
        from src.quincy.base.NamelistTypes import SbNlossScheme
        from src.quincy.base.NamelistTypes import SbBnfScheme
        from src.quincy.base.NamelistTypes import SbAdsorbScheme

        namelist.soil_biogeochemistry_ctl.sb_model_scheme = SbModelScheme.SIMPLE_1D
        namelist.soil_biogeochemistry_ctl.sb_nloss_scheme = SbNlossScheme.DYNAMIC
        namelist.soil_biogeochemistry_ctl.sb_bnf_scheme = SbBnfScheme.DYNAMIC

        namelist.soil_biogeochemistry_ctl.sb_adsorp_scheme = SbAdsorbScheme.ECA_FULL
        namelist.soil_biogeochemistry_ctl.flag_sb_prescribe_po4 = True

        # To be parsed
        namelist.vegetation_ctl.plant_functional_type_id = PftQuincy[self.ui.comboBox_PFT.currentText()].value

        print(namelist.vegetation_ctl.plant_functional_type_id )

        namelist.spq_ctl.soil_depth = 9.5
        namelist.spq_ctl.soil_awc_prescribe = 231
        namelist.spq_ctl.soil_sand = 0.33
        namelist.spq_ctl.soil_silt = 0.34
        namelist.spq_ctl.soil_clay = 0.33
        namelist.spq_ctl.bulk_density = 1300.285

        namelist.soil_biogeochemistry_ctl.usda_taxonomy_class = 57
        namelist.soil_biogeochemistry_ctl.nwrb_taxonomy_class = 44
        namelist.soil_biogeochemistry_ctl.soil_ph = 6.5
        namelist.soil_biogeochemistry_ctl.soil_p_labile = 62.209
        namelist.soil_biogeochemistry_ctl.soil_p_slow = 30.4341
        namelist.soil_biogeochemistry_ctl.soil_p_occluded = 124.4217
        namelist.soil_biogeochemistry_ctl.soil_p_primary = 271.834
        namelist.soil_biogeochemistry_ctl.qmax_org_fine_particle = 3.666


        namelist.jsb_forcing_ctl.n_deposition_scheme = "dynamic"
        namelist.jsb_forcing_ctl.p_deposition_scheme = "dynamic"

        namelist.jsb_forcing_ctl.flag_read_dC13 = True
        namelist.jsb_forcing_ctl.flag_read_DC14 = True




        #Static changes
        namelist.jsb_forcing_ctl.transient_spinup_start_year = self.gridcell.min_year
        namelist.jsb_forcing_ctl.transient_spinup_end_year = 2002
        namelist.base_ctl.output_interval_flux_spinup = OutputIntervalFlux.WEEKLY
        namelist.base_ctl.output_interval_pool_spinup = OutputIntervalPool.WEEKLY
        namelist.base_ctl.output_start_first_day_year = 1


        #namelist.base_ctl.include_nitrogen = False
        #namelist.base_ctl.include_nitrogen15 = False
        #namelist.base_ctl.include_phosphorus = False

        writer = NamelistWriter(namelist= namelist)
        writer.export(os.path.join(self.ui_settings.root_ui_directory,self.ui_settings.scenario_output_path,"namelist.slm"))


    def generate_lctlib(self):
        #Todo modifiy lctlib file
        shutil.copy(self.ui_settings.quincy_lctlib_path, os.path.join(self.ui_settings.root_ui_directory,self.ui_settings.scenario_output_path))
    def start_quincy_simulation(self):
        self.process_q = subprocess.Popen(self.ui_settings.binary_quincy,
                                          cwd=os.path.join(self.ui_settings.root_ui_directory,self.ui_settings.scenario_output_path))


    def round_coordinate(self, value, offset, res):
        return np.round((value + offset) * 4.0 * res) / (4.0 * res) - offset
    def constrain(self, value, min_b, max_b):
        return max(min(value, max_b), min_b)

    @pyqtSlot(str, int)
    def append_log(self, text, message_type ):
        self.ui.textBrowser_logger.moveCursor(QtGui.QTextCursor.End)

        # Pragmatic solution to not print whitespaces and newlines
        if len(text) < 2:
            return

        date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        text_with_date = f"{date_str} {text}"

        if message_type == MessageType.INFO.value:
            text_with_date = MessageFormat.INFO.format(text_with_date)
        if message_type == MessageType.WARN.value:
            text_with_date = MessageFormat.WARN.format(text_with_date)
        if message_type == MessageType.ERROR.value:
            text_with_date = MessageFormat.ERROR.format(text_with_date)
        if message_type == MessageType.SUCCESS.value:
            text_with_date = MessageFormat.SUCCESS.format(text_with_date)

        self.ui.textBrowser_logger.append( text_with_date )


class ComputationThread(QThread):

    # setup a signal, which takes a single object as parameter
    finished = pyqtSignal()
    sig_log = pyqtSignal(str, int)
    progressedChanged = pyqtSignal(int)
    progressBarReset = pyqtSignal(int, int)

    def __init__(self, qg: UI_Quincy):
        QThread.__init__(self)
        self.qg = qg
        # mark the thread is alive
        self.alive = True

    # called when the thread starts running
    def run(self):

        try:
            self.sig_log.emit("Creating directories...", MessageType.INFO.value)
            self.qg.create_dirs()

            self.sig_log.emit("Init forcing setup...", MessageType.INFO.value)
            self.qg.model_run_display.init_quincy_config()
            min_progress = 0
            max_progress = self.qg.model_run_display.scenario.nyear_total
            self.progressBarReset.emit(min_progress, max_progress)

            self.sig_log.emit("Exporting monthly forcing...", MessageType.INFO.value)
            self.qg.export_monthly_forcing()

            self.sig_log.emit("Applying weather generator...", MessageType.INFO.value)
            self.qg.generate_subdaily_forcing()

            self.sig_log.emit("Generating lctlib file...", MessageType.INFO.value)
            self.qg.generate_lctlib()

            self.sig_log.emit("Generating namelist file...", MessageType.INFO.value)
            self.qg.generate_namelist()

            self.sig_log.emit("Starting QUINCY...", MessageType.INFO.value)
            self.qg.start_quincy_simulation()

            while self.alive:
                time.sleep(1.0)
                progress_steps = self.qg.model_run_display.update_output_plots(self.sig_log)
                self.progressedChanged.emit(progress_steps)
                poll = self.qg.process_q.poll()
                if not poll is None:
                    break

            self.finished.emit()
            self.sig_log.emit("Finished QUINCY simulation!", MessageType.SUCCESS.value)

            if not self.alive:
                self.sig_log.emit("Thread :: Computation cancelled", MessageType.WARN.value)
                return

        except Exception as err:
            self.sig_log.emit(f"Unexpected {err=}, {type(err)=}", MessageType.ERROR.value)
            return
        # emit result to the AppWidget

    def stop(self):

        if  hasattr(self.qg, 'process_q'):

            # # Send SIGTER (on Linux)
            self.qg.process_q.terminate()
            # # Wait for process to terminate
            returncode = self.qg.process_q.wait()
            # mark this thread as not alive
            self.alive = False
            # wait for it to really finish
            self.wait()



