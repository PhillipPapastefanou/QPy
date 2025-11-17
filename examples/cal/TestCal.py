import numpy as np
import pandas as pd
from datetime import timedelta, datetime
p = pd.period_range('2012', '2017', freq='W')
from time import perf_counter


df = pd.DataFrame()
df['dt'] = p


p1 = perf_counter()

first_date = datetime(1500, 1, 1)
last_date = datetime(9999, 9, 20)
x = 7
dates = np.arange(np.datetime64('1500-01-01'), np.datetime64('5509-01-01'), 7)
m = dates.astype('datetime64[M]').astype(int) % 12 + 1
y = dates.astype('datetime64[Y]').astype(int) + 1970

# create the dataframee
df = pd.DataFrame({'dates': dates})

df['z'] = np.arange(0, df.shape[0], 1)
df['m'] = m
df['y'] = y

#t = df.drop(['dates'], axis =1).groupby(by=["y", "m"]).mean().reset_index()
t = df.drop(['dates'], axis =1).groupby(by=["y"]).mean().reset_index()

#k = [np.datetime64(datetime(t['y'][i], t['m'][i], 1)) for i in range(t.shape[0])]
k = [np.datetime64(datetime(t['y'][i], 1, 1)) for i in range(t.shape[0])]

t['dates'] =k
import matplotlib.pyplot as plt

plt.scatter(t['dates'], t['z'], color='blue')
plt.show()

p2 = perf_counter()

print (p2-p1)