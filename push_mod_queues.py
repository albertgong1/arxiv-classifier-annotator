"""Script to update the mod_queues collection on Firestore with the data from the json file.

NOTE: we only push papers with ar5iv pages to the mod_queues collection.

To check that the data has been loaded correctly into the firestore database, go to the following website:
https://console.firebase.google.com/project/arxiv-website/firestore/databases/-default-/data/

Example usage:
```bash
python push_mod_queues.py -dp data/mod-queue-all2023_v2-test-pos10-neg10.json
```
"""

import logging
import json
from tqdm import tqdm
import os
from utils import parser, get_firestore, MODERATOR_QUEUE_COLLECTION, has_ar5iv_page

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
args = parser.parse_args()
data_path = args.data_path

basename = os.path.basename(data_path)

logger.info(f"Loading data from {data_path}")
with open(data_path, "r") as f:
    queues = json.load(f)

logger.info(f"Updating Firestore with {len(queues)} queues")
db = get_firestore()
# Create a write batch
batch = db.batch()
queues_with_ar5iv_pages = {}
queues_without_ar5iv_pages = {}
# NOTE: some papers throw a 503 error when fetching the ar5iv page
IGNORE = [
    "2308.16495",
    "2308.10736",
    "2308.07589",
    "2308.06380",
    "2308.06232",
    "2307.08856",
    "2310.17336",
]
for name, queue in tqdm(list(queues.items())):
    logger.info(f"Processing queue for {name}...")
    filtered_queue = []
    for paper_id in queue:
        if paper_id in IGNORE:
            logger.warning(f"Paper {paper_id} is in the ignore list, skipping...")
            continue
        if has_ar5iv_page(paper_id):
            filtered_queue.append(paper_id)
        else:
            logger.warning(
                f"Paper {paper_id} does not have an ar5iv page, removing from queue"
            )
    logger.info(f"Papers with ar5iv pages: {len(filtered_queue)} / {len(queue)}")
    queues_with_ar5iv_pages[name] = filtered_queue
    queues_without_ar5iv_pages[name] = [
        paper_id for paper_id in queue if paper_id not in filtered_queue
    ]
    doc_ref = db.collection(MODERATOR_QUEUE_COLLECTION).document(name)
    # NOTE: any existing data will be overwritten by the new data
    # to update the data instead of overwriting it, use the update method
    batch.set(doc_ref, {"queue": filtered_queue})

batch.commit()

save_path = f"ar5iv-{basename}"
logger.info(f"Saving queues with ar5iv pages to {save_path}...")
with open(save_path, "w") as f:
    json.dump(queues_with_ar5iv_pages, f, indent=4)

save_path = f"no-ar5iv-{basename}"
logger.info(f"Saving queues without ar5iv pages to {save_path}...")
with open(save_path, "w") as f:
    json.dump(queues_without_ar5iv_pages, f, indent=4)

save_path = f"ignore-{basename}"
logger.info(f"Saving ignore list to {save_path}...")
with open(save_path, "w") as f:
    json.dump(IGNORE, f, indent=4)

logger.info("Done!")
