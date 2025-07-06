# Snowflake Serverless API Ingestion Pipeline

This project is a Proof of Concept (PoC) demonstrating a robust, serverless, and automated data ingestion pipeline that pulls batch data from an external REST API directly into a Snowflake table. The entire workflow is orchestrated by a single Python Stored Procedure, leveraging native Snowflake features and eliminating the need for external middleware or orchestration tools.

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Deployment Steps](#deployment-steps)
  - [Step 1: Create the Target Table](#step-1-create-the-target-table)
  - [Step 2: Configure External Access (Requires `ACCOUNTADMIN`)](#step-2-configure-external-access-requires-accountadmin)
  - [Step 3: Deploy the Stored Procedure](#step-3-deploy-the-stored-procedure)
- [Usage](#usage)
- [How It Works](#how-it-works)
- [Next Steps & Productionalization](#next-steps--productionalization)

## Overview

The primary goal of this project is to provide a reference implementation for a modern data ingestion pattern within Snowflake. It addresses the common challenge of fetching data from third-party APIs by containing all logic within the data platform itself. This approach significantly reduces architectural complexity, infrastructure costs, and operational overhead.

## Key Features

- **Serverless:** No external servers, containers, or functions to manage. The entire process runs on Snowflake's compute.
- **Automated:** The procedure handles the full end-to-end process from fetching data to loading it into a table.
- **Incremental Loading:** Intelligently checks for already-ingested data batches to prevent duplication and ensure idempotency.
- **Resilient:** Includes in-flight data validation and standardization to handle common API inconsistencies like case-sensitive column names.
- **Secure:** Uses Snowflake's `External Access Integration` framework for secure, auditable, and governed outbound network requests.
- **Scalable:** Leverages the performance of Snowpark and Snowflake's warehouse compute, which can scale as needed.

## Architecture

The solution architecture is composed entirely of native Snowflake objects:

1.  **External REST API:** The source system providing data.
2.  **Network Rule & External Access Integration:** Snowflake security objects that safely permit the Stored Procedure to connect to the allow-listed API endpoint.
3.  **Python Stored Procedure:** The "brain" of the operation. It orchestrates the workflow, fetches data using the `requests` library, transforms it with `pandas`, and loads it using the `Snowpark` API.
4.  **Snowflake Table:** The final destination for the ingested data.

## Prerequisites

Before deploying, you will need:
- A Snowflake account.
- A role with privileges to create tables and procedures (e.g., `SYSADMIN`).
- A user with the `ACCOUNTADMIN` role to execute the security-related steps (Step 2).
- The URL of the target API endpoint. For this PoC, we use `https://*.sisko.replit.dev`.

## Deployment Steps

Execute the following SQL statements in a Snowflake worksheet.

### Step 1: Create the Target Table

This table will store the final, ingested data.

```sql
-- Use an appropriate role, database, and schema
-- USE ROLE SYSADMIN;
-- USE WAREHOUSE MY_WAREHOUSE;
-- USE DATABASE MY_DB;
-- USE SCHEMA MY_SCHEMA;

CREATE OR REPLACE TABLE ORDERS (
    BATCH_ID NUMBER,
    ORDER_ID STRING,
    AMOUNT NUMBER(10, 2)
);
```
### Step 2: Configure External Access (Requires ACCOUNTADMIN)

These steps create the security objects that allow Snowflake to make outbound API calls.

```sql
-- This section MUST be run by a user with the ACCOUNTADMIN role
USE ROLE ACCOUNTADMIN;

-- 1. Create a Network Rule to allow-list the API's domain
CREATE OR REPLACE NETWORK RULE api_network_rule
  MODE = EGRESS
  TYPE = HOST_PORT
  VALUE_LIST = ('23330b7e-8c1a-4e75-ba37-25c8562a67de-00-15d7ouf65hn5.sisko.replit.dev');

-- 2. Create an External Access Integration that uses the Network Rule
CREATE OR REPLACE EXTERNAL ACCESS INTEGRATION batch_ingest_ext
  ALLOWED_NETWORK_RULES = (api_network_rule)
  ENABLED = TRUE;

-- 3. Grant the role that will run the procedure usage on the integration
GRANT USAGE ON INTEGRATION batch_ingest_ext TO ROLE SYSADMIN;
```
### Step 3: Deploy the Stored Procedure
This creates the procedure that contains all the ingestion logic.

```sql
-- Switch back to your primary working role
-- USE ROLE SYSADMIN;

CREATE OR REPLACE PROCEDURE INGEST_BATCH_FROM_API()
  RETURNS STRING
  LANGUAGE PYTHON
  RUNTIME_VERSION = '3.10'
  PACKAGES = ('pandas', 'requests', 'snowflake-snowpark-python')
  EXTERNAL_ACCESS_INTEGRATIONS = (batch_ingest_ext)
  HANDLER = 'main'
AS
$$
import pandas as pd
import requests
from io import StringIO
from snowflake.snowpark.session import Session
from snowflake.snowpark.exceptions import SnowparkClientException

def main(session: Session) -> str:
    base_url = "https://23330b7e-8c1a-4e75-ba37-25c8562a67de-00-15d7ouf65hn5.sisko.replit.dev"

    # Step 1: Fetch batch list
    try:
        resp = requests.get(f"{base_url}/api/batches/batch_list.csv")
        resp.raise_for_status()
        batch_df = pd.read_csv(StringIO(resp.text))
    except requests.exceptions.RequestException as e:
        return f"❌ Error fetching batch list: {e}"

    if "batch_id" not in batch_df.columns:
        return "❌ Missing 'batch_id' column in batch_list.csv"

    # Step 2: Fetch existing BATCH_IDs
    try:
        existing_batches = set(session.table("ORDERS").select("BATCH_ID").distinct().to_pandas()["BATCH_ID"].astype(str))
    except SnowparkClientException as e:
        return f"❌ Error fetching existing batch IDs from ORDERS table: {e}"

    # Step 3: Ingest new batches
    loaded, skipped = 0, 0
    total = len(batch_df["batch_id"])
    
    REQUIRED_COLS = {"ORDER_ID", "AMOUNT"}

    for batch_id in batch_df["batch_id"].astype(str):
        if batch_id in existing_batches:
            skipped += 1
            continue

        try:
            data_url = f"{base_url}/api/batch_data/{batch_id}"
            batch_resp = requests.get(data_url)
            batch_resp.raise_for_status()
            
            if not batch_resp.text:
                print(f"⚠️  Skipping batch {batch_id} because the API returned an empty file.")
                continue

            df = pd.read_csv(StringIO(batch_resp.text))
            
            original_columns = list(df.columns)
            df.columns = [col.strip().upper() for col in df.columns]

            if not REQUIRED_COLS.issubset(df.columns):
                print(f"⚠️  Skipping batch {batch_id} due to missing required columns. Required: {list(REQUIRED_COLS)}. Found: {original_columns}")
                continue
            
            df["BATCH_ID"] = int(batch_id)
            final_df = df[["BATCH_ID", "ORDER_ID", "AMOUNT"]]
            session.write_pandas(final_df, "ORDERS", auto_create_table=False)
            loaded += 1

        except Exception as e:
            print(f"⚠️  Skipping batch {batch_id} due to an unexpected error: {e}")
            continue

    return f"✅ Ingest complete — Processed: {total} | Loaded: {loaded} | Skipped (existing): {skipped}"
$$;
```
## Usage
Once deployed, you can execute the ingestion pipeline by simply calling the stored procedure.

#### Example Output (Initial Run):
✅ Ingest complete — Processed: 4 | Loaded: 4 | Skipped (existing): 0
#### Example Output (Second Run):
✅ Ingest complete — Processed: 4 | Loaded: 0 | Skipped (existing): 4

To view any logs or errors printed during execution, check the Query History in Snowsight for your CALL statement. The output from print() statements will be displayed there.

## How It Works

The procedure executes the following logic:

1.  **Fetches Batch Manifest:** It calls the `/api/batches/batch_list.csv` endpoint to get a list of all available batch IDs.
2.  **Checks for Existing Data:** It queries the `ORDERS` table to get a distinct list of `BATCH_ID`s that have already been loaded.
3.  **Iterates and Processes:** It loops through each batch ID from the manifest.
    - If a batch has already been loaded, it increments a `skipped` counter and moves on.
    - For new batches, it calls the `/api/batch_data/{batch_id}` endpoint.
4.  **Transforms and Validates:**
    - It reads the CSV data into a Pandas DataFrame.
    - **It standardizes all column names to uppercase** to prevent case-sensitivity errors.
    - It validates that required columns (`ORDER_ID`, `AMOUNT`) are present.
5.  **Loads Data:** It uses `session.write_pandas()` to append the cleaned DataFrame to the `ORDERS` table.
6.  **Reports Status:** Finally, it returns a summary string of the actions it took.

## Next Steps & Productionalization

This PoC provides a solid foundation. To move this pattern into a production environment, consider the following enhancements:

- **Parameterization:** Modify the procedure to accept arguments for the API URL and target table name to make it more reusable.
- **Scheduling:** Wrap the `CALL` statement in a [Snowflake Task](https://docs.snowflake.com/en/user-guide/tasks-intro) to run the ingestion on an automated schedule (e.g., every hour).
- **Error Alerting:** Configure [Snowflake Alerts](https://docs.snowflake.com/en/user-guide/alerts) to send notifications via email or other channels if the procedure fails.
- **CI/CD:** Integrate the SQL and Python code into a CI/CD pipeline for automated testing and deployment.
