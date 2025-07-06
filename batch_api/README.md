# Flask Batch Data API

This is a simple Flask-based web service that exposes a REST API to serve batch data from CSV files. It allows users to retrieve a list of available batch IDs and then download the corresponding data file for a specific batch.

## Features

-   **List Batches**: Provides an endpoint to get a CSV list of all available batch IDs.
-   **Serve Batch Data**: Serves the specific data CSV file for a given batch ID.
-   **Error Handling**: Returns a `404 Not Found` error if a requested batch ID does not exist.
-   **Lightweight**: Built with Flask, making it minimal and easy to run.

## Project Structure

For the API to function correctly, your project must follow this directory structure. You will need to create the `data` directory and the `batch_list.csv` file.

```
.
├── app.py          # The main Flask application file
├── batch_list.csv  # List of all batch IDs
├── data/           # Directory to store individual batch data files
│   ├── batch_A01.csv
│   ├── batch_B02.csv
│   └── ...
├── requirements.txt # Project dependencies
└── README.md       # This file
```

### Sample Data Files

**1. `batch_list.csv`**
This file should contain a header `batch_id` and a list of all available batch identifiers.

```csv
batch_id
batch_A01
batch_B02
batch_C03
```
**2. `data/batch_A01.csv`**
Each file inside the `data/` directory should be named after its batch_id and contain the relevant data.
```csv
timestamp,value,metric
2023-10-27T10:00:00Z,10.5,temperature
2023-10-27T10:01:00Z,10.6,temperature
2023-10-27T10:02:00Z,10.5,temperature
```

## API Endpoints

### 1. Get Batch List

Retrieves a CSV file containing a list of all available batch IDs. This list is sourced from the `batch_list.csv` file on the server.

-   **URL**: `/api/batches/batch_list.csv`
-   **Method**: `GET`
-   **URL Parameters**: None
-   **Success Response**:
    -   **Code**: `200 OK`
    -   **Content-Type**: `text/csv`
    -   **Body**: The raw content of the `batch_list.csv` file.

    **Example Response Body:**
    ```csv
    batch_id
    batch_A01
    batch_B02
    batch_C03
    ```

### 2. Get Batch Data

Retrieves the data CSV file for a specified `batch_id`. The server looks for a file named `<batch_id>.csv` inside the `data/` directory.

-   **URL**: `/api/batch_data/<batch_id>`
-   **Method**: `GET`
-   **URL Parameters**:
    -   `batch_id` (string, **required**): The unique identifier for the batch (e.g., `batch_A01`).
-   **Success Response**:
    -   **Code**: `200 OK`
    -   **Content-Type**: `text/csv`
    -   **Body**: The raw content of the corresponding batch data file (e.g., `data/batch_A01.csv`).

    **Example Response Body for `/api/batch_data/batch_A01`:**
    ```csv
    timestamp,value,metric
    2023-10-27T10:00:00Z,10.5,temperature
    2023-10-27T10:01:00Z,10.6,temperature
    2023-10-27T10:02:00Z,10.5,temperature
    ```

-   **Error Response**:
    -   **Condition**: The requested `batch_id` does not correspond to an existing file on the server.
    -   **Code**: `404 Not Found`
    -   **Content-Type**: `application/json`
    -   **Body**: A JSON object describing the error.

    **Example Error Response Body:**
    ```json
    {
        "description": "Batch data not found",
        "name": "Not Found"
    }
    ```

    
