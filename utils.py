"""Helper functions for the app and data processing."""

import logging
from argparse import ArgumentParser
import requests
from bs4 import BeautifulSoup
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
from tenacity import retry, stop_after_attempt, wait_exponential
from enum import Enum
from joblib import Memory

memory = Memory("cachedir")

logger = logging.getLogger(__name__)


#
# Data utils
#
parser = ArgumentParser()
parser.add_argument(
    "--data_path",
    "-dp",
    type=str,
    default="data/mod-queue-all2023_v2-test-pos50-neg50.json",
    help="Path to moderator queues stored as a json file",
)


class PrimaryDecision(Enum):
    """Enum for primary category decision options."""

    GREAT_FIT = "Great fit (category should definitely be primary)"
    GOOD_FIT = "Good fit (category is fine but other categories may be better)"
    OK_FIT = "OK fit (category is ok if no other category fits)"
    BAD_FIT = "Bad fit (category should definitely not be primary)"

    def __str__(self):
        return self.value


class SecondaryDecision(Enum):
    """Enum for secondary category decision options."""

    GREAT_FIT = "Great fit (category should definitely be secondary)"
    OK_FIT = "OK fit (I have no objection to listing the category as seocndary)"
    BAD_FIT = "Bad fit (category should definitely not be secondary)"
    N_A = "N/A"

    def __str__(self):
        return self.value


#
# Firebase utils
#
MODERATOR_QUEUE_COLLECTION = "mod_queues_v5-all2023_v2-test-pos50-neg50"
PAPER_INFO_COLLECTION = "paper_info_v5-all2023_v2-test-pos50-neg50"
MODERATOR_RESULTS_COLLECTION = "mod_results-all2023_v2-test-pos50-neg50"


def get_firestore() -> firestore.client:
    """Get the firestore client

    Refs:
    from https://firebase.google.com/docs/firestore/query-data/get-data#python

    https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management
    https://docs.streamlit.io/develop/concepts/connections/secrets-management
    # NOTE: need change to secrets instead of json for deployment
    """
    if not firebase_admin._apps:
        # cred = credentials.Certificate('API_KEYS/arxiv-website-firebase-adminsdk-mkdbk-dc872d30e8.json')
        # point to soft link so that we don't have to modify this part of the code
        cred = credentials.Certificate("./API_KEYS/certificate.json")
        firebase_admin.initialize_app(cred)

    db = firestore.client()
    return db


def get_arxiv_details_from_id(paper_id: str) -> dict:
    """Get paper info from the arXiv abstract page.

    Args:
        paper_id (str): arXiv paper ID
    Returns:
        dict: arxiv details

    """
    try:
        # Construct the URL from the paper ID
        # TODO: get this information from the all2023_v2 split of the HF dataset

        url = f"https://export.arxiv.org/abs/{paper_id}"

        # Send a GET request to fetch the HTML content
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        # Parse the HTML content
        soup = BeautifulSoup(response.text, "html.parser")
        # import pdb; pdb.set_trace()

        # Extract the title
        title_element = soup.find("h1", {"class": "title mathjax"})
        if title_element:
            title = title_element.get_text(strip=True).replace("Title:", "")
        else:
            logger.warning(f"Title not found for paper at {url}")
            title = "Title not found"

        # Extract the authors
        author_elements = soup.find("div", {"class": "authors"})
        if author_elements:
            authors = author_elements.get_text(strip=True).replace("Authors:", "")
        else:
            logger.warning(f"Authors not found for paper at {url}")
            authors = "Authors not found"

        # Extract the abstract
        abstract_block = soup.find("blockquote", {"class": "abstract mathjax"})
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
            "url": f"https://ar5iv.org/html/{paper_id}",  # construct the ar5iv website url since this doesn't display the category
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"An error occurred while fetching the page: {e}")
        return {"Error": f"An error occurred while fetching the page: {e}"}


@memory.cache
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=15))
def has_ar5iv_page(paper_id: str) -> bool:
    """Check if the paper has an ar5iv page.

    Args:
        paper_id (str): arXiv paper ID
    Returns:
        bool: True if the paper has an ar5iv page, False otherwise

    """
    url = f"https://ar5iv.labs.arxiv.org/html/{paper_id}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    response = requests.get(url, headers=headers, allow_redirects=False)
    match response.status_code:
        case s if 200 <= s < 300:
            return True
        case s if 300 <= s < 400:
            return False
        case _:
            raise Exception(f"Unexpected status code: {response.status_code}")
