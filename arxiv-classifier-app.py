import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import pandas as pd
from datetime import datetime
import json

# Initialize Firebase Admin (you'll need to replace this with your own credentials)
if not firebase_admin._apps:
    cred = credentials.Certificate("path/to/your/serviceAccountKey.json")
    firebase_admin.initialize_app(cred)

db = firestore.client()

class PaperClassificationApp:
    def __init__(self):
        st.set_page_config(page_title="arXiv Paper Classification", layout="wide")
        
        # Initialize session state
        if 'user_category' not in st.session_state:
            st.session_state.user_category = None
        if 'current_paper_index' not in st.session_state:
            st.session_state.current_paper_index = 0
            
    def load_papers(self):
        """Load papers from Firestore that haven't been classified by the current user"""
        papers_ref = db.collection('papers')
        query = papers_ref.where('classified_by', 'array_does_not_contain', 
                               st.session_state.user_category)
        docs = query.get()
        return [doc.to_dict() for doc in docs]

    def save_classification(self, paper_id, classification_data):
        """Save classification results to Firestore"""
        paper_ref = db.collection('papers').document(paper_id)
        
        # Update the document
        paper_ref.update({
            'classifications': firestore.ArrayUnion([{
                'category': st.session_state.user_category,
                'decision': classification_data['decision'],
                'secondary_categories': classification_data.get('secondary_categories', []),
                'timestamp': datetime.now(),
            }]),
            'classified_by': firestore.ArrayUnion([st.session_state.user_category])
        })

    def render_login(self):
        """Render the category selection interface"""
        st.title("arXiv Paper Classification")
        
        categories = [
            "cs.AI", "cs.CL", "cs.CV", "cs.LG", "cs.NE",
            "stat.ML", "math.ST", "physics.comp-ph"
        ]
        
        selected_category = st.selectbox(
            "Select your arXiv category:",
            options=categories,
            key="category_selector"
        )
        
        if st.button("Start Classification"):
            st.session_state.user_category = selected_category
            st.experimental_rerun()

    def render_classification_interface(self, papers):
        """Render the main classification interface"""
        if not papers:
            st.write("No more papers to classify!")
            return

        current_paper = papers[st.session_state.current_paper_index]
        
        # Display paper information
        st.title("Paper Classification")
        st.write(f"Papers remaining: {len(papers) - st.session_state.current_paper_index}")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.header("Paper Details")
            st.write(f"**Title:** {current_paper['title']}")
            st.write(f"**Abstract:** {current_paper['abstract']}")
            if 'pdf_url' in current_paper:
                st.markdown(f"[View PDF]({current_paper['pdf_url']})")

        with col2:
            st.header("Classification")
            
            # Primary classification
            decision = st.radio(
                "How well does this paper fit the category?",
                ["Great fit", "Good fit", "Poor fit", "Reject"],
                key="decision"
            )
            
            # Secondary categories
            st.write("**Secondary Categories (if any):**")
            secondary_categories = st.multiselect(
                "Select secondary categories:",
                options=[cat for cat in current_paper.get('possible_categories', [])
                        if cat != st.session_state.user_category],
                key="secondary_categories"
            )
            
            # Submit button
            if st.button("Submit Classification"):
                self.save_classification(
                    current_paper['id'],
                    {
                        'decision': decision,
                        'secondary_categories': secondary_categories
                    }
                )
                
                if st.session_state.current_paper_index < len(papers) - 1:
                    st.session_state.current_paper_index += 1
                    st.experimental_rerun()
                else:
                    st.success("You've classified all available papers!")

    def run(self):
        """Main app execution"""
        if not st.session_state.user_category:
            self.render_login()
        else:
            papers = self.load_papers()
            self.render_classification_interface(papers)

if __name__ == "__main__":
    app = PaperClassificationApp()
    app.run()
