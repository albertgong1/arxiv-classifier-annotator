"""Streamlit app for annotating arXiv papers

Example usage for local development:
```bash
streamlit run arxiv-classifier-app-dev.py
```
"""

import pandas as pd
import streamlit as st
import logging
import random
import firebase_admin
from firebase_admin import credentials, firestore
from firebase_admin.firestore import FieldFilter
from utils import (
    PrimaryDecision,
    SecondaryDecisionUponGoodOK,
    SecondaryDecisionUponBad,
)

if False:
    MODERATOR_QUEUE_COLLECTION = (
        "mod_queues_v5-all2023_v2-test-pos50-neg50-ar5iv-develop-0909"
    )
    PAPER_INFO_COLLECTION = (
        "paper_info_v5-all2023_v2-test-pos50-neg50-ar5iv-develop-0909"
    )
    MODERATOR_RESULTS_COLLECTION = (
        "mod_results-all2023_v2-test-pos50-neg50-ar5iv-develop-0909"
    )
else:
    MODERATOR_QUEUE_COLLECTION = (
        "mod_queues_v5-all2023_v2-test-pos50-neg50-ar5iv-develop-1001"
    )
    PAPER_INFO_COLLECTION = (
        "paper_info_v5-all2023_v2-test-pos50-neg50-ar5iv-develop-1001"
    )
    MODERATOR_RESULTS_COLLECTION = (
        "mod_results-all2023_v2-test-pos50-neg50-ar5iv-develop-1001"
    )

logging.basicConfig(level=logging.INFO)
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
    logger.info(f"Getting queue for {mod_queue_id=}")
    doc = db.collection(MODERATOR_QUEUE_COLLECTION).document(mod_queue_id).get()
    if doc.exists:
        full_queue = doc.to_dict().get("queue", [])
        logger.info(f"Loaded queue with {len(full_queue)} papers")
        # Query the MODERATOR_RESULTS_COLLECTION where "name" == mod_name and "category" == current_cat
        results = (
            db.collection(MODERATOR_RESULTS_COLLECTION)
            .where(filter=FieldFilter("name", "==", mod_name))
            .where(filter=FieldFilter("category", "==", current_cat))
            .get()
        )
        if results:
            results_ids = [result.to_dict().get("paper_id") for result in results]
            logger.info(
                f"Found {len(results_ids)} existing results for {mod_name=} and {current_cat=}"
            )
            remaining_queue = [
                paper_id for paper_id in full_queue if paper_id not in results_ids
            ]
            logger.info(f"Returning queue with {len(remaining_queue)} remaining papers")
        else:
            logger.info(f"No existing results found for {mod_name=} and {current_cat=}")
            remaining_queue = full_queue

        # We shuffle the remaining_queue in place to randomize the order in which
        # papers are presented to the moderator. The random seed is set using a
        # string based on the moderator's name and current category to ensure that
        # the order is consistent (deterministic) for each moderator-category pair
        # across sessions. However, if the moderator submits a paper and refreshes
        # the page, the order will be randomized again.
        random.seed(f"{mod_name}_{current_cat}")
        random.shuffle(remaining_queue)
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


def delete_moderation_result(
    paper_id: str,
    current_cat: str,
    mod_name: str,
) -> None:
    """Delete moderation result from the MODERATOR_RESULTS_COLLECTION collection on Firestore."""
    logger.warning(
        f"Deleting moderation result for {paper_id=} with {current_cat=} under {mod_name=}"
    )
    doc_id = format_mod_results_id(mod_name, current_cat, paper_id)
    db.collection(MODERATOR_RESULTS_COLLECTION).document(doc_id).delete()


def submit_moderation_result(
    paper_id: str,
    current_cat: str,
    mod_name: str,
    decision_p: PrimaryDecision,
    decision_s: SecondaryDecisionUponGoodOK | SecondaryDecisionUponBad | None,
) -> None:
    """Submit moderation result to the MODERATOR_RESULTS_COLLECTION collection on Firestore.

    Args:
        paper_id (str): arXiv paper ID
        current_cat (str): category
        mod_name (str): name of the moderator
        decision_p (PrimaryDecision): primary decision
        decision_s (SecondaryDecisionUponGoodOK | SecondaryDecisionUponBad | None): secondary decision
            None if the primary decision is Great Fit

    """
    logger.warning(
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
            "primary_decision": decision_p.value,
            "secondary_decision": decision_s.value if decision_s else None,
        }
    )


def main() -> None:
    """Main function to run the Streamlit app."""
    st.title("ArXiv Paper Moderator")
    mod_cats = pd.read_csv("data/mod_cats.csv")
    mod_cats["name"] = mod_cats["First name"] + " " + mod_cats["Last name"]

    #
    # Step 1: Select moderation category
    #
    if "current_cat" not in st.session_state:
        st.header("Select Moderation Category")
        current_cat = st.selectbox(
            "Choose your category", mod_cats["Category"].unique().tolist()
        )
        _name = st.selectbox(
            'Select your name or "Other" then input your name below',
            mod_cats[mod_cats["Category"] == current_cat]["name"].tolist() + ["Other"],
            placeholder="Johann Lee",
        )
        if _name == "Other":
            # set value=None so that the user has to enter something
            newName = st.text_input("Please enter your name", value=None)
        st.session_state.mod_name = _name if _name != "Other" else newName

        if st.button("Start Moderation"):
            st.session_state.current_cat = current_cat
            st.session_state.full_queue, st.session_state.remaining_queue = (
                load_moderation_queue(st.session_state.mod_name, current_cat)
            )
            st.session_state.current_paper_idx = 0
            st.rerun()

    #
    # Step 2: Moderation Page
    #
    # Initialize session state variables so that `del st.session_state.decision_p`
    # and `del st.session_state.decision_s` are always well-defined even if the
    # user never clicks on the radio buttons
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
                logger.debug(f"Paper ID: {paper_id}")
                st.write(f"**Title**: {paper_info['title']}")
                # TODO: render mathjax in the abstract
                st.write(f"**Authors**: {paper_info['authors']}")
                logger.debug(f"Abstract: {paper_info['abstract']}")
                st.write(f"**Abstract**: {paper_info['abstract']}")
                st.write(f"[View Paper HTML]({paper_info['url']})")
                # NOTE: uncomment to reveal the top-5 predicted categories from the model to the moderator
                # st.write("Top Categories:", paper_info["top_5_cats"])

                st.markdown(
                    f"""
                <h3 style='font-size: 20px; font-weight: bold; margin-bottom: 0px; padding-bottom: 0px;'>
                How well does {current_cat} fit this paper as the primary category?
                </h3>
                <style>
                div[data-testid="stRadio"] > div {{
                    margin-top: -20px;
                }}
                </style>
                """,
                    unsafe_allow_html=True,
                )
                decision_p = st.radio(
                    "",
                    [
                        PrimaryDecision.GREAT_FIT,
                        PrimaryDecision.GOOD_FIT,
                        PrimaryDecision.OK_FIT,
                        PrimaryDecision.BAD_FIT,
                    ],
                    key="decision_p",
                    index=None,
                )
                if decision_p in [PrimaryDecision.GOOD_FIT, PrimaryDecision.OK_FIT]:
                    st.markdown(
                        f"""
                    <h3 style='font-size: 20px; font-weight: bold; margin-bottom: 0px; padding-bottom: 0px;'>
                    Should {current_cat} still be a secondary on this paper?
                    </h3>
                    <style>
                    div[data-testid="stRadio"] > div {{
                        margin-top: -20px;
                    }}
                    </style>
                    """,
                        unsafe_allow_html=True,
                    )
                    decision_s = st.radio(
                        "",
                        [
                            SecondaryDecisionUponGoodOK.GOOD_FIT,
                            SecondaryDecisionUponGoodOK.OK_FIT,
                            SecondaryDecisionUponGoodOK.BAD_FIT,
                        ],
                        key="decision_s",
                        index=None,
                    )
                elif decision_p == PrimaryDecision.BAD_FIT:
                    st.markdown(
                        f"""
                    <h3 style='font-size: 20px; font-weight: bold; margin-bottom: 0px; padding-bottom: 0px;'>
                    Should {current_cat} still be a secondary on this paper?
                    </h3>
                    <style>
                    div[data-testid="stRadio"] > div {{
                        margin-top: -20px;
                    }}
                    </style>
                    """,
                        unsafe_allow_html=True,
                    )
                    decision_s = st.radio(
                        "",
                        [
                            SecondaryDecisionUponBad.GREAT_FIT,
                            SecondaryDecisionUponBad.OK_FIT,
                            SecondaryDecisionUponBad.BAD_FIT,
                        ],
                        key="decision_s",
                        index=None,
                    )
                else:
                    decision_s = None

                is_valid_submission = not (
                    decision_p is None
                    or (decision_p != PrimaryDecision.GREAT_FIT and decision_s is None)
                )

                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Submit Classification"):
                        if is_valid_submission:
                            submit_moderation_result(
                                paper_id,
                                current_cat,
                                st.session_state.mod_name,
                                decision_p,
                                decision_s,
                            )
                            st.session_state.current_paper_idx += 1
                            # remove radio buttons so that they are uninitialized for the next paper
                            del st.session_state.decision_p
                            del st.session_state.decision_s
                            st.rerun()
                        else:
                            st.error("Please make a selection.")
                with col2:
                    if st.session_state.current_paper_idx > 0:
                        if st.button("Back"):
                            # reverse the effects of the previous submission
                            previous_paper_idx = st.session_state.current_paper_idx - 1
                            paper_id_to_delete = remaining_queue[previous_paper_idx]
                            delete_moderation_result(
                                paper_id_to_delete,
                                current_cat,
                                st.session_state.mod_name,
                            )
                            st.session_state.current_paper_idx -= 1
                            st.rerun()

                st.write(
                    f"Currently moderating **{current_cat}** under **{st.session_state.mod_name}**"
                )
                num_finished_papers = (
                    current_paper_idx + len(full_queue) - len(remaining_queue)
                )
                st.write(
                    f"Currently finished moderating **{num_finished_papers}** papers out of a total of **{len(full_queue)}**"
                )

            else:
                st.error("Paper information not found.")

        else:
            #
            # Step 3: Return to moderation category selection
            #
            st.success("You have completed all papers in this category!")

            if st.button("Moderate Another Category"):
                del st.session_state.current_cat
                st.rerun()


if __name__ == "__main__":
    main()
