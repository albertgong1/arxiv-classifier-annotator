"""Script to collect results from the mod_results collection on Firestore and save them to a csv file.

Example usage:
```bash
python pull_results.py
```
"""

import os
from datetime import datetime
import pandas as pd
from utils import get_firestore, MODERATOR_RESULTS_COLLECTION


# get all the documents in the mod_results collection
db = get_firestore()
mod_results_ref = db.collection(MODERATOR_RESULTS_COLLECTION)
mod_results_docs = mod_results_ref.stream()

# convert the documents to a pandas dataframe
mod_results_df = pd.DataFrame([doc.to_dict() for doc in mod_results_docs])

# save the dataframe to a csv file
results_dir = "data/results"
os.makedirs(results_dir, exist_ok=True)
save_path = os.path.join(
    results_dir, f"mod_results-{datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}.csv"
)
mod_results_df.to_csv(save_path, index=False)
