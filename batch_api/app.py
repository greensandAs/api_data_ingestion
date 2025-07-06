from flask import Flask, jsonify, send_file, abort
import pandas as pd
import os

app = Flask(__name__)
DATA_DIR = "data"
BATCH_CSV = "batch_list.csv"

# Endpoint 1: List of batch IDs
@app.route("/api/batches/batch_list.csv", methods=["GET"])
def get_batch_ids():
    # df = pd.read_csv(BATCH_CSV)
    # return jsonify({"batch_ids": df["batch_id"].tolist()})
    return send_file(BATCH_CSV, mimetype="text/csv")

# Endpoint 2: Data CSV for a specific batch
@app.route("/api/batch_data/<batch_id>", methods=["GET"])
def get_batch_data(batch_id):
    file_path = os.path.join(DATA_DIR, f"{batch_id}.csv")
    if not os.path.isfile(file_path):
        return abort(404, description="Batch data not found")
    return send_file(file_path, mimetype="text/csv")