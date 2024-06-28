from src.mui.designs.quincy_ui_desin import Ui_MainWindow
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import pyqtSlot, pyqtSignal, QThread, QObject


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
from src.mui.model_run_display import ModelRunDisplay
from src.mui.var_types import Gridcell
from src.mui.var_types import ForcingDataset
import sys


class UI_Quincy(QtWidgets.QMainWindow, Ui_MainWindow):
    def __init__(self, settings: Ui_Settings):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.ui_settings = settings

        self.model_run_display = ModelRunDisplay(self.ui)
        self.model_run_display.setup_ui()

        self.splitDockWidget(self.ui.dockWidget_output_1, self.ui.dockWidget_output_2 ,QtCore.Qt.Horizontal)
        self.splitDockWidget(self.ui.dockWidget_output_3, self.ui.dockWidget_output_4 ,QtCore.Qt.Horizontal)
        self.init()


    def init(self):


        self.gridcell = Gridcell()
        self.forcing_dataset = ForcingDataset()

        self.p1 = ccrs.PlateCarree()
        self.p2 = ccrs.PlateCarree()

        self.canvas_worldmap = FigureCanvas(Figure(tight_layout=True))
        self.ui.verticalLayout_worldmap_mpl.addWidget(self.canvas_worldmap)

        self.canvas_forcing = FigureCanvas(Figure(tight_layout=True))
        self.ui.verticalLayout_forcing_display.addWidget(self.canvas_forcing)

        self.root_path_clim_forcing = os.path.join(self.ui_settings.root_qpy_directory,'forcing','cru_jra_2.4')
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

        self.model_run_display.init(self.ui_settings, self.gridcell)

        self.new_line_logger = True

        #Todo temporary: remove
        self.ui.lineEdit_lon.setText("9.75")
        self.ui.lineEdit_lat.setText("3.75")
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
        self.ui.lineEdit_temp_years.setText("5")
        self.ui.lineEdit_rain_years.setText("5")
        self.ui.lineEdit_co2_years.setText("5")

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
            print("Nothings terrestrial growing here! Selected different gridcell.")
            return

        self.ui.pushButton_run_model.setEnabled(False)
        self.ui.pushButton_stop_model.setEnabled(True)



        # Start computation
        self.running_thread = ComputationThread(self)
        self.running_thread.finished.connect(self.on_thread_finished)
        self.running_thread.progressedChanged.connect(self.onCountChanged)
        self.running_thread.progressBarReset.connect(self.resetProgressBar)
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

        reader = NamelistReader(self.ui_settings.quincy_namelist_path)

        namelist = reader.parse()
        namelist.base_ctl.output_start_first_day_year = 1
        namelist.base_ctl.output_end_last_day_year  = self.gridcell.max_year - self.gridcell.min_year + 1
        namelist.base_ctl.forcing_file_start_yr = self.gridcell.min_year
        namelist.base_ctl.forcing_file_last_yr = self.gridcell.max_year
        namelist.jsb_forcing_ctl.simulation_length_number  = self.gridcell.max_year - self.gridcell.min_year + 1

        writer = NamelistWriter(namelist= namelist)
        writer.export(os.path.join(self.ui_settings.root_ui_directory,self.ui_settings.scenario_output_path,"namelist.slm"))


    def generate_lctlib(self):
        #Todo modifiy lctlib file
        shutil.copy(self.ui_settings.quincy_lctlib_path, os.path.join(self.ui_settings.root_ui_directory,self.ui_settings.scenario_output_path))
    def start_quincy_simulation(self):
        self.process_q = subprocess.Popen(self.ui_settings.quincy_binary_path,
                                          cwd=os.path.join(self.ui_settings.root_ui_directory,self.ui_settings.scenario_output_path))


    def round_coordinate(self, value, offset, res):
        return np.round((value + offset) * 4.0 * res) / (4.0 * res) - offset
    def constrain(self, value, min_b, max_b):
        return max(min(value, max_b), min_b)

    @pyqtSlot(str)
    def append_text(self,text):
        self.ui.textBrowser_logger.moveCursor(QtGui.QTextCursor.End)

        if self.new_line_logger:
            date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            text_with_date = f"{date_str} {text}"
        else:
            text_with_date = f"{text}"

        if '\n' in text:
            self.new_line_logger = True
        else:
            self.new_line_logger = False

        self.ui.textBrowser_logger.insertPlainText( text_with_date )


class ComputationThread(QThread):

    # setup a signal, which takes a single object as parameter
    finished = pyqtSignal()
    progressedChanged = pyqtSignal(int)
    progressBarReset = pyqtSignal(int, int)

    def __init__(self, qg: UI_Quincy):
        QThread.__init__(self)
        self.qg = qg
        # mark the thread is alive
        self.alive = True

    # called when the thread starts running
    def run(self):
        print("Creating directories...")
        self.qg.create_dirs()
        print("Exporting monthly forcing...")
        self.qg.export_monthly_forcing()
        print("Applying weather generator...")
        self.qg.generate_subdaily_forcing()
        print("Generate lctlib file...")
        self.qg.generate_lctlib()
        print("Generate namelist file...")
        self.qg.generate_namelist()
        print("Starting QUINCY")
        self.qg.start_quincy_simulation()
        print("Process ID of subprocess %s" % self.qg.process_q.pid)

        min_progress = 0
        max_progress = (self.qg.gridcell.max_year - self.qg.gridcell.min_year) * int(365/7)
        self.progressBarReset.emit(min_progress, max_progress)

        self.qg.model_run_display.prepare_plots()

        while self.alive:
            time.sleep(1.0)
            progress_steps = self.qg.model_run_display.update_output_plots()
            self.progressedChanged.emit(progress_steps)
            poll = self.qg.process_q.poll()
            if not poll is None:
                break

        self.finished.emit()
        print("Finished QUINCY")

        if not self.alive:
            print("Thread :: Computation cancelled")
            return
        # emit result to the AppWidget

    def stop(self):
        # # Send SIGTER (on Linux)
        self.qg.process_q.terminate()
        # # Wait for process to terminate
        returncode = self.qg.process_q.wait()
        print (f"Returncode of subprocess: {returncode}")
        # mark this thread as not alive
        self.alive = False
        # wait for it to really finish
        self.wait()

