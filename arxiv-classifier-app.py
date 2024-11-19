import json

import firebase_admin
import pandas as pd
import streamlit as st
from firebase_admin import credentials, firestore
import requests
from bs4 import BeautifulSoup

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
def load_moderation_queue(mod_name, current_cat):
    """Retrieve the list of paper IDs for the specified category from the mod_queues collection."""
    # print(str(mod_name)+":"+current_cat.split(":")[0])
    doc_ref = db.collection("mod_queues").document(str(mod_name)+":"+current_cat.split(":")[0])
    doc = doc_ref.get()
    # print(doc.to_dict())
    if doc.exists:
        return doc.to_dict().get('queue', [])
    else:
        return []

def get_paper_info(paper_id):
    """Retrieve paper information from the paper_info collection."""
    doc_ref = db.collection("paper_info").document(paper_id)
    doc = doc_ref.get()
    if doc.exists:
        return doc.to_dict()
    return None

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
            "abstract": abstract
        }
    except requests.exceptions.RequestException as e:
        return {"Error": f"An error occurred while fetching the page: {e}"}

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
    mod_queue_ref = db.collection("mod_queues").document(ref)
    mod_queue_doc = mod_queue_ref.get()
    # print(mod_queue_doc.to_dict())

    if mod_queue_doc.exists:
        queue_data = mod_queue_doc.to_dict()
        papers = queue_data.get("queue", [])
        # print(papers)
        # print(paper_id)
        
        # Remove the paper_id if it's in the queue
        if paper_id in papers:
            papers.remove(paper_id)
            # print(papers)
            mod_queue_ref.update({"queue": papers})

# App UI
def main():
    st.title("ArXiv Paper Moderator")
    mod_cats = pd.read_csv("data/mod_cats.csv")
    # mod_emails = pd.read_csv("data/mod_emails.csv")
    mod_cats["name"] = mod_cats["First name"] + ' ' + mod_cats["Last name"]

    # Step 1: Select moderation category
    st.header("Select Moderation Category")
    current_cat = st.selectbox("Choose your category", mod_cats["Category"].to_list())  # Modify if there are more categories
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
            paper_details = get_arxiv_details_from_id(paper_id)

            if paper_info:
                st.subheader(f"Paper ID: {paper_info['id']}")
                st.write(f"Title: {paper_details['title']}")
                st.write(f"Authors: {paper_details['authors']}")
                st.write(f"Abstract: {paper_details['abstract']}")
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
                    submit_moderation_result(paper_id, current_cat, mod_name, decision_p, decision_s)
                    # submit_moderation_result(paper_id, category_id, st.session_state["email"], decision_p, decision_s)
                    st.session_state["current_paper_idx"] += 1
                    st.rerun()

                st.write(f"Currently moderating **{current_cat}** under **{mod_name}**")

                # instead of Tom's #7 i want to do change cateogry and go to prev paper
                # i think it makes sense to decouple submission and movement


            else:
                st.error("Paper information not found.")
        else:
            st.success("You have completed all papers in this category!")

if __name__ == "__main__":
    main()
