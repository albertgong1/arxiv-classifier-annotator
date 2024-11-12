# TODO load data into mod_queues and papaer_info automatically
from argparse import ArgumentParser
parser = ArgumentParser()
parser.add_argument("--data_path", type=str, default="data/mod-queue-default-test-pos10-neg10.json")
args, _ = parser.parse_known_args()

data_path = args.data_path

# firebase imports
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
# standard imports
import json

# read data from json file
with open(data_path, 'r') as f:
    queues = json.load(f)

# push the data into the firestore table: mod_queues

# from https://firebase.google.com/docs/firestore/query-data/get-data#python
if not firebase_admin._apps:
    # cred = credentials.Certificate('API_KEYS/arxiv-website-firebase-adminsdk-mkdbk-dc872d30e8.json')
    # point to soft link so that we don't have to modify this part of the code
    cred = credentials.Certificate('./API_KEYS/certificate.json')
    app = firebase_admin.initialize_app(cred)

db = firestore.client()

# Create a write batch
batch = db.batch()

for name, queue in list(queues.items()):
    # Set the data for the 'users' collection
    doc_ref = db.collection('mod_queues').document(name)
    # any existing data will be overwritten by the new data
    batch.set(doc_ref, {'queue' : queue})
    # to update the data instead of overwriting it, use the update method

batch.commit()
