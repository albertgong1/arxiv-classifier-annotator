"""
Utils for the arxiv-classifier project
"""
from argparse import ArgumentParser
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore

# 
# Data utils
# 
parser = ArgumentParser()
parser.add_argument("--data_path", "-dp", type=str, 
                    default="data/mod-queue-all2023_v2-test-pos10-neg10.json",
                    help='Path to moderator queues stored as a json file')

# 
# Firebase utils
# 
MODERATOR_QUEUE_COLLECTION = "mod_queues_v5"
PAPER_INFO_COLLECTION = "paper_info_v5-export"

def get_firestore():
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
        cred = credentials.Certificate('./API_KEYS/certificate.json')
        app = firebase_admin.initialize_app(cred)

    db = firestore.client()
    return db
