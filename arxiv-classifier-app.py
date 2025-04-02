"""Streamlit app for annotating arXiv papers

Example usage for local development:
```bash
streamlit run arxiv-classifier-app.py
```
"""

import pandas as pd
import streamlit as st
import logging
import firebase_admin
from firebase_admin import credentials, firestore
from firebase_admin.firestore import FieldFilter
from utils import (
    MODERATOR_QUEUE_COLLECTION,
    PAPER_INFO_COLLECTION,
    MODERATOR_RESULTS_COLLECTION,
)

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


if not firebase_admin._apps:
    # Get the credentials from secrets.toml
    cred = credentials.Certificate(dict(st.secrets["firebase"]))
    firebase_admin.initialize_app(cred)

db = firestore.client()


def load_moderation_queue(
    mod_name: str, current_cat: str
) -> tuple[list[str], list[str]]:
    """Retrieve the list of unannotated papers for the specified category and moderator.

    1. Get the full list of papers from the MODERATOR_QUEUE_COLLECTION
    2. Remove papers that are already in MODERATOR_RESULTS_COLLECTION
    3. Return the list of remaining papers

    NOTE: some moderators belong to multiple categories.

    Args:
        mod_name (str): name of the moderator
        current_cat (str): category
    Returns:
        full_queue (list[str]): full list of papers
        remaining_queue (list[str]): list of papers that have not been annotated

    """

    def format_mod_queue_id(mod_name: str, current_cat: str) -> str:
        """Format the moderation queue document ID.

        Args:
            mod_name (str): name of the moderator
            current_cat (str): category
        Returns:
            str: formatted moderation queue document ID

        """
        return f"{mod_name}:{current_cat.split(':')[0]}"

    mod_queue_id = format_mod_queue_id(mod_name, current_cat)
    logger.debug(f"Getting queue for {mod_queue_id=}")
    doc = db.collection(MODERATOR_QUEUE_COLLECTION).document(mod_queue_id).get()
    if doc.exists:
        full_queue = doc.to_dict().get("queue", [])
        logger.debug(f"Loaded queue with {len(full_queue)} papers")
        # Query the MODERATOR_RESULTS_COLLECTION where "name" == mod_name and "category" == current_cat
        results = (
            db.collection(MODERATOR_RESULTS_COLLECTION)
            .where(filter=FieldFilter("name", "==", mod_name))
            .where(filter=FieldFilter("category", "==", current_cat))
            .get()
        )
        if results:
            results_ids = [result.to_dict().get("paper_id") for result in results]
            logger.debug(
                f"Found {len(results_ids)} existing results for {mod_name=} and {current_cat=}"
            )
            remaining_queue = [
                paper_id for paper_id in full_queue if paper_id not in results_ids
            ]
            logger.debug(
                f"Returning queue with {len(remaining_queue)} remaining papers"
            )
        else:
            logger.debug(
                f"No existing results found for {mod_name=} and {current_cat=}"
            )
            remaining_queue = full_queue
        return full_queue, remaining_queue
    else:
        logger.warning(
            f"Document {mod_queue_id=} does not exist in `{MODERATOR_QUEUE_COLLECTION}`"
        )
        return [], []


def get_paper_info(paper_id: str) -> dict | None:
    """Retrieve paper information from the paper_info collection.

    Args:
        paper_id (str): arXiv paper ID
    Returns:
        dict of paper information if found, otherwise None

    """
    doc = db.collection(PAPER_INFO_COLLECTION).document(paper_id).get()
    if doc.exists:
        return doc.to_dict()
    return None


def submit_moderation_result(
    paper_id: str, current_cat: str, mod_name: str, decision_p: str, decision_s: str
) -> None:
    """Submit moderation result to the MODERATOR_RESULTS_COLLECTION collection on Firestore.

    Args:
        paper_id (str): arXiv paper ID
        current_cat (str): category
        mod_name (str): name of the moderator
        decision_p (str): primary decision
        decision_s (str): secondary decision

    """

    def format_mod_results_id(mod_name: str, current_cat: str, paper_id: str) -> str:
        """Format the moderation result document ID.

        Args:
            mod_name (str): name of the moderator
            current_cat (str): category
            paper_id (str): arXiv paper ID
        Returns:
            str: formatted moderation result document ID

        """
        return f"{mod_name}_{current_cat.split(':')[0]}_{paper_id}"

    logger.info(
        f"Submitting moderation result for {paper_id=} with {current_cat=} under {mod_name=}"
    )
    # add result
    mod_results_ref = db.collection(MODERATOR_RESULTS_COLLECTION).document(
        document_id=format_mod_results_id(mod_name, current_cat, paper_id)
    )
    mod_results_ref.set(
        {
            "name": mod_name,
            "category": str(current_cat),
            "paper_id": paper_id,
            "primary_decision": decision_p,
            "secondary_decision": decision_s,
        }
    )


# App UI
def main() -> None:
    """Main function to run the Streamlit app."""
    st.title("ArXiv Paper Moderator")
    mod_cats = pd.read_csv("data/mod_cats.csv")
    # mod_emails = pd.read_csv("data/mod_emails.csv")
    mod_cats["name"] = mod_cats["First name"] + " " + mod_cats["Last name"]

    # Step 1: Select moderation category
    st.header("Select Moderation Category")
    current_cat = st.selectbox("Choose your category", mod_cats["Category"].tolist())
    _name = st.selectbox(
        'Select your name or "Other" then input your name below',
        mod_cats[mod_cats["Category"] == current_cat]["name"].tolist() + ["Other"],
        placeholder="Johann Lee",
    )
    if _name == "Other":
        newName = st.text_input("Please enter your name")
        # TODO: check that newName is not already in the list
    mod_name = _name if _name != "Other" else newName

    if st.button("Start Moderation"):
        st.session_state.current_cat = current_cat
        st.session_state.full_queue, st.session_state.remaining_queue = (
            load_moderation_queue(mod_name, current_cat)
        )
        st.session_state.current_paper_idx = 0
        st.rerun()

    # Step 2: Moderation Page
    if "decision_p" not in st.session_state:
        st.session_state.decision_p = None
    if "decision_s" not in st.session_state:
        st.session_state.decision_s = None

    if "current_cat" in st.session_state:
        current_cat = st.session_state.current_cat
        full_queue = st.session_state.full_queue
        remaining_queue = st.session_state.remaining_queue
        current_paper_idx = st.session_state.current_paper_idx

        if current_paper_idx < len(remaining_queue):
            paper_id = remaining_queue[current_paper_idx]
            if paper_info := get_paper_info(paper_id):
                # NOTE: uncomment to reveal paper ID to moderator
                # st.subheader(f"Paper ID: {paper_info['id']}")
                st.write(f"**Title**: {paper_info['title']}")
                st.write(f"**Authors**: {paper_info['authors']}")
                st.write(f"**Abstract**: {paper_info['abstract']}")
                st.write(f"[View Paper HTML]({paper_info['url']})")
                # NOTE: uncomment to reveal the top-5 predicted categories from the model to the moderator
                # st.write("Top Categories:", paper_info["top_5_cats"])

                decision_p = st.radio(
                    f"How well does {current_cat} fit this paper as the primary category?",
                    [
                        "Great fit (category should definitely be primary)",
                        "Good fit (category is fine but other categories may be better)",
                        "OK fit (category is ok if no other category fits)",
                        "Bad fit (category should definitely not be primary)",
                    ],
                    key="decision_p",
                )
                if decision_p == "Bad fit (category should definitely not be primary)":
                    decision_s = st.radio(
                        f"If you selected Bad for primary, should {current_cat} still be a secondary on this paper?",
                        [
                            "Great fit (category should definitely be secondary)",
                            "OK fit (I have no objection to listing the category as seocndary)",
                            "Bad fit (category should definitely not be secondary)",
                        ],
                        key="decision_s",
                    )
                else:
                    decision_s = "N/A"

                if st.button("Submit Classification") and decision_p is not None:
                    submit_moderation_result(
                        paper_id, current_cat, mod_name, decision_p, decision_s
                    )
                    st.session_state.current_paper_idx += 1
                    # remove radio buttons
                    del st.session_state.decision_p
                    del st.session_state.decision_s
                    st.rerun()

                st.write(f"Currently moderating **{current_cat}** under **{mod_name}**")
                st.write(
                    f"Currently finished moderating **{current_paper_idx + len(full_queue) - len(remaining_queue)}** papers out of a total of **{len(full_queue)}**"
                )

            else:
                st.error("Paper information not found.")

        else:
            st.success("You have completed all papers in this category!")


if __name__ == "__main__":
    main()
