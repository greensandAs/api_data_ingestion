import requests
import pandas as pd
from io import StringIO
from snowflake.connector import connect
from snowflake.connector.pandas_tools import write_pandas

conn = connect(
    user="ASLAM",
    password="Aslam@12345678",
    account="BAFXTND-WH77514",       
    warehouse="COMPUTE_WH",
    role="SYSADMIN",
    database="URL_DEMO",
    schema="DEV"
)

TABLE_NAME = "ORDERS"

# To Fetch exisiting batch IDs
def get_loaded_batches():
    cur = conn.cursor()
    cur.execute(f"SELECT DISTINCT BATCH_ID FROM {TABLE_NAME}")
    return {row[0] for row in cur.fetchall()}

# Get list of batch IDs from API
def get_batch_ids():
    r = requests.get("http://localhost:5000/api/batches/batch_list.csv")
    r.raise_for_status()
    # return r.json()["batch_ids"]
    df = pd.read_csv(StringIO(r.text))
    return df["batch_id"].astype(str).tolist() 

# Ingest batch 
def ingest_batch(batch_id):
    try:
        url = f"http://localhost:5000/api/batch_data/{batch_id}"
        r = requests.get(url)
        r.raise_for_status()
        
        df = pd.read_csv(StringIO(r.text))

        df.columns = [col.strip().upper() for col in df.columns]  
        df["BATCH_ID"] = int(batch_id)  

        write_pandas(conn, df[["BATCH_ID", "ORDER_ID", "AMOUNT"]], table_name=TABLE_NAME)
        print(f"Loaded batch {batch_id} with {len(df)} rows")

    except Exception as e:
        print(f"Error loading batch {batch_id}: {e}")

#  Main 
if __name__ == "__main__":
    loaded_batches = get_loaded_batches()
    print(f"Already loaded batch IDs: {loaded_batches}")

    for batch_id in get_batch_ids():
        if int(batch_id) in loaded_batches:
            print(f"Skipping batch {batch_id} (already loaded)")
        else:
            print(f"Ingesting batch {batch_id}")
            ingest_batch(batch_id)