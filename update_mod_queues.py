"""Script to update the mod_queues collection on Firestore with the data from the json file.

Example usage:
```bash
python update_mod_queues.py -dp data/mod-queue-all2023_v2-test-pos10-neg10.json
```
"""

from util import parser, get_firestore
args = parser.parse_args()
data_path = args.data_path

# standard imports
import json
from tqdm import tqdm

# read data from json file
with open(data_path, 'r') as f:
    queues = json.load(f)

db = get_firestore()
# Create a write batch
batch = db.batch()
for name, queue in tqdm(list(queues.items())):
    # Set the data for the 'users' collection
    doc_ref = db.collection('mod_queues').document(name)
    # any existing data will be overwritten by the new data
    batch.set(doc_ref, {'queue' : queue})
    # to update the data instead of overwriting it, use the update method

batch.commit()

# to check that the data has been loaded correctly into the firestore database
# go to the following website:
# https://console.firebase.google.com/project/arxiv-website/firestore/databases/-default-/data/