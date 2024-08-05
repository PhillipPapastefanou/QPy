class extract_variables():
    def __init__(self, ds):
        self.ds = ds

    def extract_to_dict(self):
        import xarray as xr
        variables_ds = {}
        for var_name, data_array in self.ds.data_vars.items():
            if 'units' in data_array.attrs:
                variables_ds[var_name] = data_array.attrs['units']
        return(variables_ds)

class netcdf_to_pandas():
    def __init__(self, ds, var1, var2):
        self.ds = ds
        self.var1 = var1
        self.var2 = var2

    def quincy_to_pandas(self):
        import xarray as xr
        import pandas as pd
         # Export one column to a pandas dataframe
        df = self.ds[self.var1].to_dataframe()
         # Add another variable
        df[self.var2] = self.ds[self.var2]
        # Convert the NetCDF time index to a pandas time index
        dates = self.ds.indexes['time'].to_datetimeindex();
        # Save the pandas time index as another column using .to_datetime
        df['date'] = pd.to_datetime(dates)
        # Then reset index such that the original time column is retained but not an index
        df.reset_index(inplace=True)
        # Remove the old time column that we dont need
        df.drop(['time'], axis=1, inplace=True)
        # Not sure what this does
        df.groupby(['date'])
        return df

    def obs_to_pandas(self):
        import xarray as xr
        import pandas as pd
        df = self.ds[self.var1].to_dataframe()
        df.reset_index(inplace=True)
        df['date'] = pd.to_datetime(df['time'])
        df.drop(['time'], axis=1, inplace=True)
        df.drop(['latitude'], axis=1, inplace=True)
        df.drop(['longitude'], axis=1, inplace=True)
        return df

class netcdf_to_pandas_with_list():
    def __init__(self, ds, var1, list_vars):
        self.ds = ds
        self.var1 = var1
        self.list_vars = list_vars

    def quincy_to_pandas(self):
        import xarray as xr
        import pandas as pd
         # Export one column to a pandas dataframe
        df = self.ds[self.var1].to_dataframe()
         # Loop through the list of variables and add each as a new column
        for i in self.list_vars:
            df[i] = self.ds[i]
        # Convert the NetCDF time index to a pandas time index
        dates = self.ds.indexes['time'].to_datetimeindex();
        # Save the pandas time index as another column using .to_datetime
        df['date'] = pd.to_datetime(dates)
        # Then reset index such that the original time column is retained but not an index
        df.reset_index(inplace=True)
        # Remove the old time column that we dont need
        df.drop(['time'], axis=1, inplace=True)
        # Not sure what this does
        df.groupby(['date'])
        return df

    def obs_to_pandas(self):
        import xarray as xr
        import pandas as pd
        df = self.ds[self.var1].to_dataframe()
        for i in self.list_vars:
            df[i] = self.ds[i].to_dataframe()
        df.reset_index(inplace=True)
        df['date'] = pd.to_datetime(df['time'])
        df.drop(['time'], axis=1, inplace=True)
        df.drop(['latitude'], axis=1, inplace=True)
        df.drop(['longitude'], axis=1, inplace=True)
        return df

class StatMeasures():
    def __init__(self, y_mod, y_obs):
        self.y_mod=y_mod
        self.y_obs=y_obs

    def rmse(self):
        import numpy as np
        rmse= np.sqrt(np.sum((self.y_mod - self.y_obs) ** 2) / self.y_obs.shape[0])
        return(rmse)

class Plotting():
    def __init__(self, index, y_mod, y_obs, y_mod_label,y_obs_label, plot_title, x_label, y_label):
        self.y_mod = y_mod
        self.y_obs = y_obs
        self.y_mod_label = y_mod_label
        self.y_obs_label = y_obs_label
        self.index = index
        self.plot_title = plot_title
        self.x_label = x_label
        self.y_label = y_label

    def basic_plot(self):
        import matplotlib.cm as cm
        import matplotlib.pyplot as plt
        # Set default plotting fonts
        plt.rcParams['font.family'] = 'serif'  # or 'sans-serif', 'cursive', etc.
        plt.rcParams['font.size'] = 12
        plt.rcParams['font.serif'] = ['Times New Roman']  # Example of a specific font
        plt.rcParams['axes.titlesize'] = 16
        plt.rcParams['axes.labelsize'] = 14
        plt.rcParams['legend.fontsize'] = 12
        #Start the actual plot
        cividis = cm.get_cmap('cividis')
        plt.figure(figsize=(10, 6))
        plt.plot(self.index, self.y_mod, label=self.y_mod_label, color=cividis(0.1),
                 linestyle='--')
        plt.plot(self.index, self.y_obs, label=self.y_obs_label, color=cividis(0.9))
        plt.title(self.plot_title, fontsize=14)
        plt.xlabel(self.x_label, fontsize=11)
        plt.ylabel(self.y_label, fontsize=11)
        plt.legend(loc='best', fontsize=12)
        plt.show