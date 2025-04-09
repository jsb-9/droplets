import pandas as pd
import os
import asyncio
import datetime as dt
import polars as pl

folder_path = 'droplets/NIFTY All 0DTE 1sec data'

from .fetching_from_local_db.fetch_from_db import fetch_data

def resample(
    data: pl.DataFrame, timeframe, offset: dt.timedelta | None = None
) -> pl.DataFrame:
    return (
        data.set_sorted("datetime")
        .group_by_dynamic(
            index_column="datetime",
            every=timeframe,
            period=timeframe,
            label="left",
            offset=offset,
        )
        .agg(
            [
                pl.col("o").first().alias("o"),
                pl.col("h").max().alias("h"),
                pl.col("l").min().alias("l"),
                pl.col("c").last().alias("c"),
                pl.col("v").sum().alias("v"),
            ]
        )
    )

async def fetch():

    list_of_refetch_contracts: list[dict] = []

    for file_name in os.listdir(folder_path):
        if file_name.endswith('.parquet'):
            file_path = os.path.join(folder_path, file_name)
            print(file_name)
            df = pd.read_parquet(file_path)
            df = df.dropna(subset='datetime')
            # print(df.head())
            # print(index)
            # break
            new_data = resample(pl.DataFrame(df), '1m')
            new_data = new_data.to_pandas()
            print(len(new_data))
            if len(new_data) > 120:
                filename_ = file_name.split('.')[0]
                
                index='nifty'
                strike = int(df['strike'][0])
                expiry = pd.to_datetime(df['expiry'][0]).date()
                asset_class = df['asset_class'][0][0:-1]
                
                print(index, strike, expiry, asset_class)

                data = await fetch_data(
                    index=index,
                    start_date=expiry,
                    end_date=expiry,
                    start_time=dt.time(9, 15),
                    end_time=dt.time(15, 30),
                    expiry=expiry,
                    strike=strike,
                    asset_class='C' if df['asset_class'][0] == 'CE' else 'P'
                )
                # print(data)
                # print(len(data))
                if data is None:
                    continue
                data = data.to_pandas()

                # data.to_csv(f'DB_data_{filename_}.csv')
                # Merging df and new_data on the 'datetime' column
                merged_df = pd.merge(data, new_data, on='datetime', how='outer', suffixes=('_from_db', '_one_sec_resampled'))

                # Display the merged DataFrame
                # print(merged_df)

                merged_df['open_diff'] = merged_df['o_from_db'] - merged_df['o_one_sec_resampled']
                merged_df['high_diff'] = merged_df['h_from_db'] - merged_df['h_one_sec_resampled']
                merged_df['low_diff'] = merged_df['l_from_db'] - merged_df['l_one_sec_resampled']
                merged_df['close_diff'] = merged_df['c_from_db'] - merged_df['c_one_sec_resampled']
                merged_df['volume_diff'] = merged_df['v_from_db'] - merged_df['v_one_sec_resampled']

                open_diff = abs(merged_df['open_diff']).max()
                high_diff = abs(merged_df['high_diff']).max()
                low_diff = abs(merged_df['low_diff']).max()
                close_diff = abs(merged_df['close_diff']).max()

                final_diff = max(open_diff, high_diff, low_diff, close_diff)
                print(f'Max Diff : {final_diff}')

                if (final_diff > 2):
                    new_dict = {
                        "index": index,
                        "strike": strike,
                        "asset_class": asset_class,
                        "expiry": expiry,
                        "reason": "Values Mismatch"
                    }
                    list_of_refetch_contracts.append(new_dict)
                    merged_df.to_csv(f'Update Files 1sec Data/{filename_}.csv')
                elif (len(data) != len(new_data)):
                    new_dict = {
                        "index": index,
                        "strike": strike,
                        "asset_class": asset_class,
                        "expiry": expiry,
                        "reason": "Length Mismatch"
                    }
                    list_of_refetch_contracts.append(new_dict)
                    merged_df.to_csv(f'Update Files 1sec Data/{filename_}.csv')

                # break

    refetch_df = pd.DataFrame(list_of_refetch_contracts)
    refetch_df.to_csv('Refetch NIFTY.csv', index=False)

if __name__ == '__main__':
    asyncio.run(fetch())