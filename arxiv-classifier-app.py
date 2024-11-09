import json

import firebase_admin
import streamlit as st
from firebase_admin import credentials, firestore

# to generate private API key:
# https://console.firebase.google.com/u/0/project/arxiv-website/settings/serviceaccounts/adminsdk

# PermissionDenied: 403 Cloud Firestore API has not been used in project arxiv-website before or it is disabled. Enable it by visiting https://console.developers.google.com/apis/api/firestore.googleapis.com/overview?project=arxiv-website then retry. If you enabled this API recently, wait a few minutes for the action to propagate to our systems and retry. [links { description: "Google developers console API activation" url: "https://console.developers.google.com/apis/api/firestore.googleapis.com/overview?project=arxiv-website" } , reason: "SERVICE_DISABLED" domain: "googleapis.com" metadata { key: "service" value: "firestore.googleapis.com" } metadata { key: "consumer" value: "projects/arxiv-website" } ]
# https://console.cloud.google.com/apis/api/firestore.googleapis.com/metrics?project=arxiv-website
# https://console.firebase.google.com/u/0/project/arxiv-website/settings/serviceaccounts/adminsdk
# https://console.cloud.google.com/firestore/databases/-default-/data/panel/mod_queues/0?authuser=0&hl=en&project=arxiv-website

# from https://firebase.google.com/docs/firestore/query-data/get-data#python
if not firebase_admin._apps:
    # cred = credentials.Certificate('API_KEYS/arxiv-website-firebase-adminsdk-mkdbk-dc872d30e8.json')
    # point to soft link so that we don't have to modify this part of the code
    cred = credentials.Certificate('./API_KEYS/certificate.json')
    app = firebase_admin.initialize_app(cred)
db = firestore.client()

# Load data from Firestore collections
def load_moderation_queue(category_id):
    """Retrieve the list of paper IDs for the specified category from the mod_queues collection."""
    doc_ref = db.collection("mod_queues").document(str(category_id))
    doc = doc_ref.get()
    if doc.exists:
        return doc.to_dict().get(str(category_id), [])
    return []

def get_paper_info(paper_id):
    """Retrieve paper information from the paper_info collection."""
    doc_ref = db.collection("paper_info").document(paper_id)
    doc = doc_ref.get()
    if doc.exists:
        return doc.to_dict()
    return None

def submit_moderation_result(paper_id, category_id, email, decision_p, decision_s):
    """Submit moderation result to the mod_results collection."""
    # mod_result_ref = db.collection("mod_results").document(paper_id)
    # mod_result_ref.set({
    #     "id": paper_id,
    #     "my_cat": str(category_id),
    #     "in_my_cat": result
    #     # str(category_id): result
    # }, merge=False)

    # add result
    mod_results_ref = db.collection("mod_results")
    mod_results_ref.add({
        "paper_id": paper_id,
        "my_cat": str(category_id),
        "email": email,
        "my_cat_primary": decision_p,
        "my_cat_secondary": decision_s,
    })

    # remove paper from queue
    mod_queue_ref = db.collection("mod_queues").document(str(category_id))
    mod_queue_doc = mod_queue_ref.get()
    
    if mod_queue_doc.exists:
        queue_data = mod_queue_doc.to_dict()
        papers = queue_data.get(str(category_id), [])
        
        # Remove the paper_id if it's in the queue
        if paper_id in papers:
            papers.remove(paper_id)
            mod_queue_ref.update({str(category_id): papers})

# App UI
def main():
    st.title("ArXiv Paper Moderator")

    # Step 1: Select moderation category
    st.header("Select Moderation Category")
    category_id = st.selectbox("Choose your category", [0, 1, 2, 3, 59])  # Modify if there are more categories
    email = st.text_input(label="Please enter your email", value="jcl354@cornell.edu", key='email')
    # st.session_state["email"] = 
    
    if st.button("Start Moderation"):
        st.session_state["category_id"] = category_id
        st.session_state["paper_queue"] = load_moderation_queue(category_id)
        st.session_state["current_paper_idx"] = 0
 
        # st.experimental_rerun()
        st.rerun()

    # Step 2: Moderation Page
    if "category_id" in st.session_state:
        category_id = st.session_state["category_id"]
        paper_queue = st.session_state["paper_queue"]
        current_idx = st.session_state["current_paper_idx"]

        if current_idx < len(paper_queue):
            paper_id = paper_queue[current_idx]
            paper_info = get_paper_info(paper_id)

            if paper_info:
                st.header(f"Currently moderating category {category_id} using email {email}")

                st.subheader(f"Paper ID: {paper_info['id']}")
                st.write(f"[View Paper PDF]({paper_info['url']})")
                # st.write("Top Categories:", paper_info["top_5_cats"])

                # Moderation Decision
                # st.write("Does this paper belong to your category?")
                # if st.button("Yes"):
                #     submit_moderation_result(paper_id, category_id, True)
                #     st.session_state["current_paper_idx"] += 1
                #     # st.experimental_rerun()
                #     st.rerun()

                # elif st.button("No"):
                #     submit_moderation_result(paper_id, category_id, False)
                #     st.session_state["current_paper_idx"] += 1
                #     # st.experimental_rerun()
                #     st.rerun()
                decision_p = st.radio(
                    "How well does this paper fit the category as a primary category?",
                    ["Great fit (category should definitely be primary)", 
                     "Good fit (category is fine but other categories may be better)", 
                     "OK fit (category is ok if no other category fits)", 
                     "Bad fit (category should definitely not be primary)"],
                    key="decision_p"
                )

                decision_s = st.radio(
                    "If you selected Bad for primary, should the category still be secondary?",
                    ["Great fit (category should definitely be secondary)", 
                     "OK fit (I have no objection to listing the category as seocndary)", 
                     "Bad fit (category should definitely not be secondary)",],
                    key="decision_s"
                )
                if st.button("Submit Classification"):
                    submit_moderation_result(paper_id, category_id, email, decision_p, decision_s)
                    # submit_moderation_result(paper_id, category_id, st.session_state["email"], decision_p, decision_s)
                    st.session_state["current_paper_idx"] += 1
                    st.rerun()

            else:
                st.error("Paper information not found.")
        else:
            st.success("You have completed all papers in this category!")

if __name__ == "__main__":
    main()
