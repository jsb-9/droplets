import pandas as pd

def process_csv(file_path):
    
    df = pd.read_csv(file_path, index_col=False)
    print(df.columns)
    print(df['datetime'].head())
    print(type(df['datetime'].iloc[0]))
    df.drop(columns=['_id', 'exchange', 'tf', 'instrument'], inplace=True)

    df['datetime'] = df['datetime'].str.rstrip('Z')
    df['datetime'] = pd.to_datetime(df['datetime'], format='%Y-%m-%dT%H:%M:%S.%f')

    df['datetime'] = df['datetime'].dt.strftime('%Y-%m-%d %H:%M:%S')

    df = df.rename(columns={'o': 'open','h': 'high','l': 'low', 'c': 'close', 'v': 'volume'})
    print(df.head())
    return df


file_path = "/mnt/c/Users/jagjot/Downloads/spot/midcp.csv"
processed_df = process_csv(file_path)
# print(processed_df.head())

processed_df.to_csv(file_path, index=False)
