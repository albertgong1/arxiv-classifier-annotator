"""Script to collect results from the mod_results collection on Firestore and save them to a csv file.

Example usage:
```bash
python pull_results.py
```
"""

import pandas as pd
from utils import get_firestore, MODERATOR_RESULTS_COLLECTION


# get all the documents in the mod_results collection
db = get_firestore()
mod_results_ref = db.collection(MODERATOR_RESULTS_COLLECTION)
mod_results_docs = mod_results_ref.stream()

# convert the documents to a pandas dataframe
mod_results_df = pd.DataFrame([doc.to_dict() for doc in mod_results_docs])

# save the dataframe to a csv file
mod_results_df.to_csv("mod_results.csv", index=False)
