"""Script to update the mod_queues collection on Firestore with the data from the json file.

Example usage:
```bash
python update_mod_queues.py -dp data/mod-queue-all2023_v2-test-pos10-neg10.json
```
"""

import logging
import json
from tqdm import tqdm

from utils import parser, get_firestore, MODERATOR_QUEUE_COLLECTION

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
args = parser.parse_args()
data_path = args.data_path

logger.info(f"Loading data from {data_path}")
with open(data_path, 'r') as f:
    queues = json.load(f)

logger.info(f"Updating Firestore with {len(queues)} queues")
db = get_firestore()
# Create a write batch
batch = db.batch()
for name, queue in tqdm(list(queues.items())):
    # Set the data for the 'users' collection
    doc_ref = db.collection(MODERATOR_QUEUE_COLLECTION).document(name)
    # any existing data will be overwritten by the new data
    batch.set(doc_ref, {'queue' : queue})
    # to update the data instead of overwriting it, use the update method

batch.commit()
logger.info("Done!")
# to check that the data has been loaded correctly into the firestore database
# go to the following website:
# https://console.firebase.google.com/project/arxiv-website/firestore/databases/-default-/data/
