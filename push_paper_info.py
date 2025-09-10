"""Script to update the `paper_info` collection on Firestore with the data from each paper's arxiv abstract page.

Example usage:
```bash
python push_paper_info.py -dp data/mod-queue-all2023_v2-test-pos10-neg10.json
```
"""

import json
from tqdm import tqdm
import logging
from datasets import load_dataset
from utils import parser, get_firestore, PAPER_INFO_COLLECTION

parser.add_argument(
    "--paper_info_collection",
    "-pic",
    type=str,
    default=PAPER_INFO_COLLECTION,
    help="Firestore collection to update",
)
args, _ = parser.parse_known_args()
data_path = args.data_path
paper_info_collection = args.paper_info_collection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info("Loading data from HF")
ds = load_dataset("kilian-group/arxiv-classifier", name="all2023_v2", split="test")
map = {x["paper_id"]: x for x in tqdm(ds, desc="Constructing lookup table")}


def get_arxiv_details_from_id_hf(paper_id: str) -> dict:
    """Get the paper info from the HF dataset.

    Args:
        paper_id (str): arXiv paper ID
    Returns:
        dict: arxiv details

    """
    # import pdb; pdb.set_trace()
    paper = map.get(paper_id, None)
    if paper is None:
        raise ValueError(f"Paper not found for id {paper_id}")
    return {
        "title": paper["title"],
        "authors": paper["authors"],
        "abstract": paper["abstract"],
        "url": f"https://ar5iv.org/html/{paper_id}",
    }


logger.info(f"Loading data from {data_path}")
with open(data_path, "r") as f:
    queues = json.load(f)

logger.info("Getting all paper ids in queues")
paper_ids = set()
for queue in queues.values():
    paper_ids.update(queue)
papers_ids = list(paper_ids)

logger.info(f"Updating collection: {paper_info_collection}")
db = get_firestore()

# Define a reasonable batch size (e.g., 250 documents per batch)
BATCH_SIZE = 250

for i in range(0, len(papers_ids), BATCH_SIZE):
    # Create a new batch for each chunk
    batch = db.batch()

    # Get the current chunk of paper_ids
    chunk = papers_ids[i : i + BATCH_SIZE]

    # Process each paper in the current chunk
    for paper_id in tqdm(chunk, desc=f"Processing batch {i // BATCH_SIZE + 1}"):
        doc_ref = db.collection(paper_info_collection).document(paper_id)
        paper_info = get_arxiv_details_from_id_hf(paper_id)
        batch.set(doc_ref, paper_info)

    # Commit the current batch
    logger.info(f"Committing batch {i // BATCH_SIZE + 1}")
    batch.commit()

logger.info("Done!")
