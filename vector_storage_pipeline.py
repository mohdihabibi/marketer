"""
Vector Storage & RAG Pipeline - Days 3-4
Process your scraped emails and create embeddings for Pinecone
"""

import json
import pandas as pd
import openai
from pinecone import Pinecone, ServerlessSpec
import time
from typing import List, Dict
import re
from datetime import datetime

# =============================================================================
# CONFIGURATION
# =============================================================================

# Set your API keys
OPENAI_API_KEY = st.secrets["openai"]["api_key"]
PINECONE_API_KEY = st.secrets["pinecone"]["api_key"]
PINECONE_ENVIRONMENT = "your_pinecone_environment"  # e.g., "us-west1-gcp"

# Initialize APIs
openai.api_key = OPENAI_API_KEY

# =============================================================================
# 1. EMAIL SCRAPING FUNCTIONS
# =============================================================================

class EmailRAGPipeline:
    def __init__(self, index_name: str = "email-campaigns"):
        self.index_name = index_name
        self.pc = Pinecone(api_key=PINECONE_API_KEY)
        self.dimension = 1536  # OpenAI embedding dimension
        self.emails_df = None
        self.embeddings = []
        
    def load_scraped_emails(self, json_file: str = "email_templates.json") -> pd.DataFrame:
        """Load the emails you just scraped"""
        print(f"📂 Loading emails from {json_file}...")
        
        with open(json_file, 'r', encoding='utf-8') as f:
            emails = json.load(f)
        
        print(f"✅ Loaded {len(emails)} emails")
        
        # Convert to DataFrame and clean
        df = pd.DataFrame(emails)
        df = self.clean_email_data(df)
        
        self.emails_df = df
        return df
    
    def clean_email_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean and prepare email data for embedding"""
        print("🧹 Cleaning email data...")
        
        # Clean text content
        df['subject'] = df['subject'].fillna('').astype(str).apply(self.clean_text)
        df['body'] = df['body'].fillna('').astype(str).apply(self.clean_text)
        
        # Create combined content for embedding
        df['full_content'] = df['subject'] + ' ' + df['body']
        
        # Add useful metadata
        df['subject_length'] = df['subject'].str.len()
        df['body_length'] = df['body'].str.len()
        df['word_count'] = df['full_content'].str.split().str.len()
        
        # Extract features
        df['has_emoji'] = df['full_content'].str.contains(r'[🎉🚀📧💎🌟✨🔥📱⚡️💰🎯]', regex=True)
        df['has_urgency'] = df['full_content'].str.contains(r'\b(urgent|limited|now|today|hurry|act fast|don\'t miss)\b', case=False, regex=True)
        df['has_discount'] = df['full_content'].str.contains(r'\b(\d+%|discount|save|off|deal|free|promo)\b', case=False, regex=True)
        df['has_cta'] = df['full_content'].str.contains(r'\[(.*?)\]|get started|learn more|sign up|download|try|buy', case=False, regex=True)
        
        # Remove empty content
        df = df[df['full_content'].str.strip() != ''].copy()
        
        print(f"✅ Cleaned data: {len(df)} emails ready for embedding")
        return df
    
    def clean_text(self, text: str) -> str:
        """Clean individual text content"""
        if not isinstance(text, str):
            return ""
        
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text.strip())
        
        # Remove placeholder text
        text = re.sub(r'\[.*?\]', '[CTA]', text)  # Keep CTA structure but simplify
        text = re.sub(r'\{.*?\}', '', text)  # Remove variables like {name}
        
        return text
    
    def generate_embeddings(self) -> List[List[float]]:
        """Generate embeddings for all emails"""
        if self.emails_df is None:
            raise ValueError("Load emails first using load_scraped_emails()")
        
        print("🔮 Generating embeddings with OpenAI...")
        
        texts = self.emails_df['full_content'].tolist()
        embeddings = []
        
        # Process in batches to handle rate limits
        batch_size = 50
        total_batches = (len(texts) + batch_size - 1) // batch_size
        
        for i in range(0, len(texts), batch_size):
            batch_num = i // batch_size + 1
            batch = texts[i:i + batch_size]
            
            print(f"📊 Processing batch {batch_num}/{total_batches} ({len(batch)} emails)...")
            
            try:
                response = openai.embeddings.create(
                    input=batch,
                    model="text-embedding-ada-002"
                )
                
                batch_embeddings = [item.embedding for item in response.data]
                embeddings.extend(batch_embeddings)
                
                print(f"✅ Generated {len(batch_embeddings)} embeddings")
                
                # Rate limiting - OpenAI free tier
                if batch_num < total_batches:
                    time.sleep(1)
                
            except Exception as e:
                print(f"❌ Error in batch {batch_num}: {e}")
                # Add zero embeddings as fallback
                zero_embedding = [0.0] * self.dimension
                embeddings.extend([zero_embedding] * len(batch))
        
        self.embeddings = embeddings
        print(f"🎉 Total embeddings generated: {len(embeddings)}")
        
        return embeddings
    
    def setup_pinecone_index(self):
        """Create Pinecone index if it doesn't exist"""
        print(f"🌲 Setting up Pinecone index: {self.index_name}")
        
        # Check if index exists
        existing_indexes = [index.name for index in self.pc.list_indexes()]
        
        if self.index_name not in existing_indexes:
            print(f"📝 Creating new index: {self.index_name}")
            
            self.pc.create_index(
                name=self.index_name,
                dimension=self.dimension,
                metric="cosine",
                spec=ServerlessSpec(
                    cloud="aws",
                    region="us-east-1"
                )
            )
            
            # Wait for index to be ready
            print("⏳ Waiting for index to be ready...")
            time.sleep(10)
            
        else:
            print(f"✅ Index {self.index_name} already exists")
        
        return self.pc.Index(self.index_name)
    
    def upload_to_pinecone(self):
        """Upload emails and embeddings to Pinecone"""
        if not self.embeddings:
            raise ValueError("Generate embeddings first using generate_embeddings()")
        
        print("📤 Uploading to Pinecone...")
        
        index = self.setup_pinecone_index()
        
        # Prepare vectors for upload
        vectors = []
        for i, (_, row) in enumerate(self.emails_df.iterrows()):
            vector = {
                "id": f"email_{i}",
                "values": self.embeddings[i],
                "metadata": {
                    "subject": row['subject'][:1000],  # Pinecone metadata size limit
                    "body": row['body'][:1000],
                    "brand": str(row.get('brand', ''))[:100],
                    "category": str(row.get('category', ''))[:50],
                    "source": str(row.get('source', ''))[:100],
                    "subject_length": int(row['subject_length']),
                    "body_length": int(row['body_length']),
                    "word_count": int(row['word_count']),
                    "has_emoji": bool(row['has_emoji']),
                    "has_urgency": bool(row['has_urgency']),
                    "has_discount": bool(row['has_discount']),
                    "has_cta": bool(row['has_cta'])
                }
            }
            vectors.append(vector)
        
        # Upload in batches
        batch_size = 100
        total_batches = (len(vectors) + batch_size - 1) // batch_size
        
        for i in range(0, len(vectors), batch_size):
            batch_num = i // batch_size + 1
            batch = vectors[i:i + batch_size]
            
            print(f"📤 Uploading batch {batch_num}/{total_batches}...")
            
            try:
                index.upsert(batch)
                print(f"✅ Uploaded {len(batch)} vectors")
                time.sleep(1)  # Rate limiting
                
            except Exception as e:
                print(f"❌ Error uploading batch {batch_num}: {e}")
        
        # Get index stats
        time.sleep(2)
        stats = index.describe_index_stats()
        print(f"🎯 Pinecone index stats: {stats.total_vector_count} vectors stored")
        
        return index
    
    def test_similarity_search(self, query: str, top_k: int = 5):
        """Test similarity search functionality"""
        print(f"\n🔍 Testing similarity search for: '{query}'")
        print("-" * 50)
        
        # Generate embedding for query
        response = openai.embeddings.create(
            input=[query],
            model="text-embedding-ada-002"
        )
        query_embedding = response.data[0].embedding
        
        # Search Pinecone
        index = self.pc.Index(self.index_name)
        results = index.query(
            vector=query_embedding,
            top_k=top_k,
            include_metadata=True
        )
        
        print(f"Found {len(results.matches)} similar emails:")
        
        for i, match in enumerate(results.matches):
            score = match.score
            subject = match.metadata.get('subject', 'No subject')
            category = match.metadata.get('category', 'Unknown')
            
            print(f"\n{i+1}. Similarity: {score:.3f}")
            print(f"   Subject: {subject[:80]}...")
            print(f"   Category: {category}")
        
        return results
    
    def run_complete_pipeline(self, json_file: str = "email_templates.json"):
        """Run the complete pipeline from scraped emails to Pinecone"""
        print("🚀 RUNNING COMPLETE VECTOR STORAGE PIPELINE")
        print("=" * 55)
        
        try:
            # Step 1: Load scraped emails
            df = self.load_scraped_emails(json_file)
            
            # Step 2: Generate embeddings
            embeddings = self.generate_embeddings()
            
            # Step 3: Upload to Pinecone
            index = self.upload_to_pinecone()
            
            print("\n✅ PIPELINE COMPLETE!")
            print(f"📊 Processed {len(df)} emails")
            print(f"🔮 Generated {len(embeddings)} embeddings")
            print(f"📤 Uploaded to Pinecone index: {self.index_name}")
            
            # Test with some sample queries
            test_queries = [
                "product launch announcement",
                "new feature update",
                "company partnership news",
                "special discount offer"
            ]
            
            print("\n🧪 Testing similarity search...")
            for query in test_queries:
                self.test_similarity_search(query, top_k=3)
                print()
            
            return True
            
        except Exception as e:
            print(f"❌ Pipeline failed: {e}")
            print(f"Exception type: {type(e).__name__}")
            return False

# =============================================================================
# QUICK SETUP VERIFICATION
# =============================================================================

def verify_setup():
    """Verify API keys and basic setup"""
    print("🔧 VERIFYING SETUP...")
    
    # Test OpenAI
    try:
        response = openai.embeddings.create(
            input=["test"],
            model="text-embedding-ada-002"
        )
        print("✅ OpenAI API working")
    except Exception as e:
        print(f"❌ OpenAI API error: {e}")
        return False
    
    # Test Pinecone
    try:
        pc = Pinecone(api_key=PINECONE_API_KEY)
        indexes = pc.list_indexes()
        print("✅ Pinecone API working")
    except Exception as e:
        print(f"❌ Pinecone API error: {e}")
        return False
    
    # Check if email file exists
    import os
    if os.path.exists("email_templates.json"):
        print("✅ Email templates file found")
    else:
        print("❌ Email templates file not found - run the scraper first!")
        return False
    
    print("🎉 Setup verification complete!")
    return True

# =============================================================================
# MAIN FUNCTION
# =============================================================================

def main():
    """Main function to run the vector storage pipeline"""
    
    # Verify setup first
    if not verify_setup():
        print("❌ Setup verification failed. Please fix the issues above.")
        return False
    
    # Run the pipeline
    pipeline = EmailRAGPipeline()
    success = pipeline.run_complete_pipeline()
    
    if success:
        print("\n🎯 NEXT STEPS:")
        print("✅ Your emails are now stored in Pinecone!")
        print("✅ Ready for Days 5-7: Build the Streamlit app")
        print("✅ Test query: Try similarity search with different product descriptions")
    
    return success

if __name__ == "__main__":
    # Remember to set your API keys at the top of the file!
    main()