# ---
# jupyter:
#   jupytext:
#     cell_metadata_filter: -all
#     custom_cell_magics: kql
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.11.2
#   kernelspec:
#     display_name: arxiv-classifier
#     language: python
#     name: python3
# ---

# %%
"""Script to update the `paper_info` collection on Firestore with the data from each paper's arxiv abstract page.

Example usage:
```bash
python update_paper_info.py -dp data/mod-queue-all2023_v2-test-pos10-neg10.json
```
"""
import json
from tqdm import tqdm
import requests
from bs4 import BeautifulSoup
import logging
from utils import parser, get_firestore, PAPER_INFO_COLLECTION

args, _ = parser.parse_known_args()
data_path = args.data_path

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def get_arxiv_details_from_id(paper_id):
    try:
        # Construct the URL from the paper ID
        # TODO: get this information from the all2023_v2 split of the HF dataset

        
        url = f"https://export.arxiv.org/abs/{paper_id}"
        
        # Send a GET request to fetch the HTML content
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        # Parse the HTML content
        soup = BeautifulSoup(response.text, 'html.parser')
        # import pdb; pdb.set_trace()
        
        # Extract the title
        title_element = soup.find('h1', {'class': 'title mathjax'})
        if title_element:
            title = title_element.get_text(strip=True).replace("Title:", "") 
        else:
            logger.warning(f"Title not found for paper at {url}")
            title = "Title not found"
        
        # Extract the authors
        author_elements = soup.find('div', {'class': 'authors'})
        if author_elements:
            authors = author_elements.get_text(strip=True).replace("Authors:", "")
        else:
            logger.warning(f"Authors not found for paper at {url}")
            authors = "Authors not found"
        
        # Extract the abstract
        abstract_block = soup.find('blockquote', {'class': 'abstract mathjax'})
        if abstract_block:
            abstract = abstract_block.get_text(strip=True).replace("Abstract:", "")
        else:
            logger.warning(f"Abstract not found for paper at {url}")
            abstract = "Abstract not found"
        
        # Return results as a dictionary
        return {
            "title": title,
            "authors": authors,
            "abstract": abstract,
            "url": f"https://ar5iv.org/html/{paper_id}" # construct the ar5iv website url since this doesn't display the category
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"An error occurred while fetching the page: {e}")
        return {"Error": f"An error occurred while fetching the page: {e}"}

logger.info(f"Loading data from {data_path}")
with open(data_path, 'r') as f:
    queues = json.load(f)

logger.info("Getting all paper ids in queues")
paper_ids = set()
for queue in queues.values():
    paper_ids.update(queue)
papers_ids = list(paper_ids)

logger.info("Updating paper_info collection")
db = get_firestore()
# Create a write batch
batch = db.batch()
pbar = tqdm(enumerate(papers_ids), desc="Updating paper_info collection")
for i, paper_id in pbar:
    # Set the data for the 'users' collection
    doc_ref = db.collection(PAPER_INFO_COLLECTION).document(paper_id)
    # get paper info from arxiv abstract page
    paper_info = get_arxiv_details_from_id(paper_id)
    # NOTE: any existing data will be overwritten by the new data
    # to update the data instead of overwriting it, use the update method
    batch.set(doc_ref, paper_info)
    # to update the data instead of overwriting it, use the update method
    pbar.set_description(f"Updated paper_info collection ({i+1} / {len(papers_ids)})")
# commit the batch
batch.commit()
logger.info("Done!")
