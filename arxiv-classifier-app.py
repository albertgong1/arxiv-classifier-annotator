"""Streamlit app for annotating arXiv papers
Example usage:
```bash
streamlit run arxiv-classifier-app.py
```
"""

import pandas as pd
import streamlit as st
import logging
import firebase_admin
from firebase_admin import credentials, firestore

from utils import MODERATOR_QUEUE_COLLECTION, PAPER_INFO_COLLECTION

logging.basicConfig(level=logging.DEBUG)


if not firebase_admin._apps:
    # Get the credentials from secrets.toml
    cred = credentials.Certificate(dict(st.secrets["firebase"]))
    firebase_admin.initialize_app(cred)
db = firestore.client()

# Load data from Firestore collections
def load_moderation_queue(mod_name, current_cat):
    """Retrieve the list of paper IDs for the specified category from the MODERATOR_QUEUE_COLLECTION collection."""
    mod_queue_id = str(mod_name)+":"+current_cat.split(":")[0]
    logging.debug(f"Entered load mod queue for {mod_queue_id}")
    doc_ref = db.collection(MODERATOR_QUEUE_COLLECTION).document(mod_queue_id)
    doc = doc_ref.get()
    logging.debug(f"Document data: {doc.to_dict()}")
    if doc.exists:
        return doc.to_dict().get('queue', [])
    else:
        return []

def get_paper_info(paper_id):
    """Retrieve paper information from the paper_info collection."""
    doc_ref = db.collection(PAPER_INFO_COLLECTION).document(paper_id)
    doc = doc_ref.get()
    if doc.exists:
        return doc.to_dict()
    return None

def submit_moderation_result(paper_id, current_cat, mod_name, decision_p, decision_s):
    """Submit moderation result to the mod_results collection."""
    # mod_result_ref = db.collection("mod_results").document(paper_id)
    # mod_result_ref.set({
    #     "id": paper_id,
    #     "my_cat": str(category_id),
    #     "in_my_cat": result
    #     # str(category_id): result
    # }, merge=False)

    # add result
    mod_results_ref = db.collection("mod_results").document(document_id=mod_name+"_"+current_cat.split(":")[0]+"_"+paper_id)
    mod_results_ref.set({
        "name": mod_name,
        "category": str(current_cat),
        "paper_id": paper_id,
        "primary_decision": decision_p,
        "secondary_decision": decision_s,
    })

    # remove paper from queue
    ref = str(mod_name)+":"+current_cat.split(":")[0]
    mod_queue_ref = db.collection(MODERATOR_QUEUE_COLLECTION).document(ref)
    mod_queue_doc = mod_queue_ref.get()

    if mod_queue_doc.exists:
        queue_data = mod_queue_doc.to_dict()
        papers = queue_data.get("queue", [])
        
        # Remove the paper_id if it's in the queue
        if paper_id in papers:
            papers.remove(paper_id)
            mod_queue_ref.update({"queue": papers})

# App UI
def main():
    st.title("ArXiv Paper Moderator")
    mod_cats = pd.read_csv("data/mod_cats.csv")
    # mod_emails = pd.read_csv("data/mod_emails.csv")
    mod_cats["name"] = mod_cats["First name"] + ' ' + mod_cats["Last name"]

    # Step 1: Select moderation category
    st.header("Select Moderation Category")
    current_cat = st.selectbox("Choose your category", set(mod_cats["Category"].to_list()))  # Modify if there are more categories
    _name = st.selectbox('Select your name or "Other" then input your name below', mod_cats[mod_cats['Category']==current_cat]["name"].tolist()+["Other"], placeholder="Johann Lee")
    if _name == "Other":
        newName = st.text_input("Please enter your name")
    mod_name = _name if _name != "Other" else newName

    if st.button("Start Moderation"):
        st.session_state["current_cat"] = current_cat
        st.session_state["paper_queue"] = load_moderation_queue(mod_name, current_cat)
        st.session_state["current_paper_idx"] = 0
 
        # st.experimental_rerun()
        st.rerun()

    # Step 2: Moderation Page
    if "current_cat" in st.session_state:
        current_cat = st.session_state["current_cat"]
        paper_queue = st.session_state["paper_queue"]
        current_idx = st.session_state["current_paper_idx"]

        if current_idx < len(paper_queue):
            paper_id = paper_queue[current_idx]
            paper_info = get_paper_info(paper_id)

            if paper_info:
                # st.subheader(f"Paper ID: {paper_info['id']}")
                st.write(f"**Title**: {paper_info['title']}")
                st.write(f"**Authors**: {paper_info['authors']}")
                st.write(f"**Abstract**: {paper_info['abstract']}")
                st.write(f"[View Paper HTML]({paper_info['url']})")
                # st.write("Top Categories:", paper_info["top_5_cats"])

                decision_p = st.radio(
                    f"How well does {current_cat} fit this paper as the primary category?",
                    ["Great fit (category should definitely be primary)", 
                     "Good fit (category is fine but other categories may be better)", 
                     "OK fit (category is ok if no other category fits)", 
                     "Bad fit (category should definitely not be primary)"],
                    key="decision_p"
                )

                decision_s = "N/A"
                if(decision_p == "Bad fit (category should definitely not be primary)"):
                    decision_s = st.radio(
                        f"If you selected Bad for primary, should {current_cat} still be a secondary on this paper?",
                        ["Great fit (category should definitely be secondary)", 
                        "OK fit (I have no objection to listing the category as seocndary)", 
                        "Bad fit (category should definitely not be secondary)",],
                        key="decision_s"
                    )

                if st.button("Submit Classification"):
                    submit_moderation_result(paper_id, current_cat, mod_name, decision_p, decision_s)
                    # submit_moderation_result(paper_id, category_id, st.session_state["email"], decision_p, decision_s)
                    st.session_state["current_paper_idx"] += 1
                    st.rerun()

                st.write(f"Currently moderating **{current_cat}** under **{mod_name}**")
                st.write(f"Currently finished moderating **{current_idx}** papers out of a total of **{len(paper_queue)}**")

                # instead of Tom's #7 i want to do change cateogry and go to prev paper
                # i think it makes sense to decouple submission and movement


            else:
                st.error("Paper information not found.")
        else:
            st.success("You have completed all papers in this category!")

if __name__ == "__main__":
    main()
