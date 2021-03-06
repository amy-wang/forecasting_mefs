import os
import pandas as pd
import numpy as np

'''
	Get generation and load forecast data 
	Input:  
		Generation by fuel type and load forecast for 2016 and 2017 
		Data source: PJM data miner 
		Link: https://dataminer2.pjm.com
	Output: 
		actual_fossil_gen: actual fossile fuel gen for 2016 and 2017
		generation_data: DF with PJM load forecast, fossil generation, renewable generation (there's a column for each 
			hour of day) and weekly nuclear generation as well as the previous week's nuclear generation 
'''

DATA_DIR = 'raw_data'
DATE_COL = 'date'
HOUR_COL = 'hour'

LOAD_FORECAST_FILES = [os.path.join(DATA_DIR, 'load_forecast_2017.csv'), os.path.join(DATA_DIR, 'load_forecast_2016.csv')]
LOAD_FORECAST_COLS =['date', 'area', 'pjm_load_forecast']
FINAL_LOAD_FORECAST_COLS = ['year', 'month', 'week', 'day', 'hour', 'pjm_load_forecast']
# rows with this label represent load forecast for all of PJM (other labels are just a sub section of PJM)
AREA_ALL_PJM = 'RTO' 

GEN_BY_FUEL_TYPE_FILES = [os.path.join(DATA_DIR, 'gen_by_fuel_type2017.csv'), os.path.join(DATA_DIR, 'gen_by_fuel_type2016.csv')]
NUCLEAR = 'Nuclear'
FUEL_TYPE_COL = 'fuel_type'
GEN_COLS = ['datetime_beginning_utc', 'mw']

WEEKLY_GROUPING = ['year', 'week']
DAILY_GROUPING = ['year', 'month', 'week', 'day']

NUCLEAR_COL_NAME = 'nuclear_gen'
NUCLEAR_LAST_WEEK = 'nuclear_gen_prev_week'

FOSSIL_FUEL = ['Coal', 'Gas', 'Multiple Fuels', 'Oil']
FOSSIL_COL_NAME = 'fossil_gen'

RENEWABLES = ['Hydro', 'Solar', 'Wind']
RENEWABLES_COL_NAME = 'renewable_gen'


def main():
	# Read files 
	load_forecast_df = pd.concat(map(pd.read_csv, LOAD_FORECAST_FILES))
	gen_by_fuel_type_df = pd.concat(map(pd.read_csv, GEN_BY_FUEL_TYPE_FILES))

	# Clean load forecast and fossil fuel gen
	formatted_load_forecast = get_load_forecasts(load_forecast_df)
	fossil_gen_simple_dispatch = fossil_gen_for_simple_dispatch(gen_by_fuel_type_df)

	# Save generation data by year 
	actual_fossil_gen_2017 = fossil_gen_simple_dispatch[fossil_gen_simple_dispatch['date'].dt.year == 2017]
	actual_fossil_gen_2017.set_index('date').sort_index().to_csv('actual_fossil_gen_2017.csv')
	actual_fossil_gen_2016 = fossil_gen_simple_dispatch[fossil_gen_simple_dispatch['date'].dt.year == 2016]
	actual_fossil_gen_2016.set_index('date').sort_index().to_csv('actual_fossil_gen_2016.csv')

	formatted_fossil_gen = fossil_gen_by_hour(fossil_gen_simple_dispatch)
	formatted_renewables = get_wind_solar_hydro(gen_by_fuel_type_df)
	formatted_nuclear = get_nuclear_gen(gen_by_fuel_type_df)

	# Combine into one df 
	df_merged = formatted_load_forecast
	df_merged = df_merged.merge(formatted_fossil_gen, how='inner', left_index=True, right_index=True)
	df_merged = df_merged.merge(formatted_renewables, how='inner', left_index=True, right_index=True).reset_index()
	
	df_merged = df_merged.merge(formatted_nuclear, how='inner', on=['year', 'week'])
	df_merged.set_index(DAILY_GROUPING, inplace=True)
	
	df_merged.to_csv('generation_data.csv')


def fossil_gen_by_hour(df):
	df = _extract_date(df, DATE_COL)

	df = df[['year', 'month', 'week','day', 'hour', 'fossil_gen']]
	df = _pivot_hourly(df, DAILY_GROUPING).dropna()
	return df 


def get_load_forecasts(df):
	df = df.copy(deep=True)
	df.columns = LOAD_FORECAST_COLS

	# RTO columns represent the load forecast for all of PJM
	df = df.loc[df['area'] == AREA_ALL_PJM]

	# There are multiple forecasts provided per hour so take the first one 
	df = df.groupby([DATE_COL]).first().reset_index()

	df[DATE_COL] = pd.to_datetime(df[DATE_COL])
	df = _extract_date(df, DATE_COL)
	df = df[FINAL_LOAD_FORECAST_COLS]

	df = _pivot_hourly(df, DAILY_GROUPING).dropna()

	return df 


def get_nuclear_gen(df):
	df = df.copy(deep=True)
	nuclear = df.loc[df[FUEL_TYPE_COL] == NUCLEAR]

	# Select columns and update the names 
	nuclear = nuclear[GEN_COLS]
	nuclear.columns = [DATE_COL, NUCLEAR_COL_NAME]

	# get date attributes from datetime col 
	nuclear[DATE_COL] = pd.to_datetime(nuclear[DATE_COL])
	nuclear = _extract_date(nuclear, DATE_COL)

	nuclear_weekly = nuclear.groupby(WEEKLY_GROUPING).mean().reset_index()
	nuclear_weekly = nuclear_weekly[['year', 'week', 'nuclear_gen']]
	nuclear_weekly.set_index(['year', 'week'], inplace=True)

	nuclear_weekly[NUCLEAR_LAST_WEEK] = nuclear_weekly[NUCLEAR_COL_NAME].shift(1)
	nuclear_weekly.dropna(inplace=True)

	return nuclear_weekly


def fossil_gen_for_simple_dispatch(df):
	df = df.copy(deep=True)
	df = df.loc[df[FUEL_TYPE_COL].isin(FOSSIL_FUEL)]

	# Select columns and update the names 
	df = df[GEN_COLS]
	df.columns = [DATE_COL, FOSSIL_COL_NAME]

	# groupby so each hour has one row 
	df = df.groupby([DATE_COL]).sum().reset_index()

	df[DATE_COL] = pd.to_datetime(df[DATE_COL])
	return df 


def get_wind_solar_hydro(df):
	df = df.copy(deep=True)
	df = df.loc[df[FUEL_TYPE_COL].isin(RENEWABLES)]

	# Select columns and update the names 
	df = df[GEN_COLS]
	df.columns = [DATE_COL, RENEWABLES_COL_NAME]

	df = df.groupby(DATE_COL).sum().reset_index()

	# get date attributes from datetime col 
	df[DATE_COL] = pd.to_datetime(df[DATE_COL])
	df = _extract_date(df, DATE_COL)

	df = df[['year', 'month', 'week','day', 'hour', 'renewable_gen']]
	df = _pivot_hourly(df, DAILY_GROUPING).dropna()

	return df 


def _extract_date(df, date_col):
	df.copy(deep=True)
	df['hour'] = df[date_col].dt.hour
	df['week'] = df[date_col].dt.week
	df['month'] = df[date_col].dt.month
	df['year'] = df[date_col].dt.year
	df['day'] = df[date_col].dt.dayofyear
	return df


def _pivot_hourly(df, time_index_arr):
	df.copy(deep=True)

	df = df.pivot_table(index = time_index_arr, columns=HOUR_COL, values=df.columns)
	df.columns = df.columns.map('{0[0]}|{0[1]}'.format)
	return df 


if __name__=='__main__':
    main()