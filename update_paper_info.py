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

# %%
from util import parser, get_firestore
args, _ = parser.parse_known_args()
data_path = args.data_path

# %%
# standard imports
import json
from tqdm import tqdm
import requests
from bs4 import BeautifulSoup

# %%
def get_arxiv_details_from_id(paper_id):
    try:
        # Construct the URL from the paper ID
        url = f"https://arxiv.org/abs/{paper_id}"
        
        # Send a GET request to fetch the HTML content
        response = requests.get(url)
        response.raise_for_status()
        
        # Parse the HTML content
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract the title
        title_element = soup.find('h1', {'class': 'title mathjax'})
        title = title_element.get_text(strip=True).replace("Title:", "") if title_element else "Title not found"
        
        # Extract the authors
        author_elements = soup.find('div', {'class': 'authors'})
        authors = author_elements.get_text(strip=True).replace("Authors:", "") if author_elements else "Authors not found"
        
        # Extract the abstract
        abstract_block = soup.find('blockquote', {'class': 'abstract mathjax'})
        abstract = abstract_block.get_text(strip=True).replace("Abstract:", "") if abstract_block else "Abstract not found"
        
        # Return results as a dictionary
        return {
            "title": title,
            "authors": authors,
            "abstract": abstract,
            "url": f"https://ar5iv.org/html/{paper_id}" # construct the ar5iv website url since this doesn't display the category
        }
    except requests.exceptions.RequestException as e:
        return {"Error": f"An error occurred while fetching the page: {e}"}

# %%
# read data from json file
with open(data_path, 'r') as f:
    queues = json.load(f)

# %%
# get all paper ids in queues
paper_ids = set()
for queue in queues.values():
    paper_ids.update(queue)
papers_ids = list(paper_ids)

# %%
db = get_firestore()
# Create a write batch
batch = db.batch()
pbar = tqdm(enumerate(papers_ids), desc="Updating paper_info collection")
for i, paper_id in pbar:
    # Set the data for the 'users' collection
    doc_ref = db.collection('paper_info').document(paper_id)
    # get paper info from arxiv abstract page
    paper_info = get_arxiv_details_from_id(paper_id)
    # NOTE: any existing data will be overwritten by the new data
    # to update the data instead of overwriting it, use the update method
    batch.set(doc_ref, paper_info)
    # to update the data instead of overwriting it, use the update method
    pbar.set_description(f"Updated paper_info collection ({i+1} / {len(papers_ids)})")
# commit the batch
batch.commit()
