# arxiv_website

To run:
```
streamlit run arxiv-classifier-app.py
```

## Setup

To install dependencies, run:
```
conda create -n arxiv_website
conda install python=3.12 conda-forge::streamlit conda-forge::bs4
pip install firebase-admin
```

Setting up firestore:
1. Create a new private key:
https://console.firebase.google.com/u/0/project/arxiv-website/settings/serviceaccounts/adminsdk
2. Download key locally to a destination outside the repo and create a softlink to `API_KEYS`
```
# in the repo root
mkdir API_KEYS
ln -s <absolute path to download destination> API_KEYS/certificate.json
```