import chromadb
import os
import uuid
import datetime

# Absolute paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# database path
DB_PATH = os.path.join(BASE_DIR, "storage", "chroma_db")
# Tag for collection
COLLECTION_NAME = "aiyo_knowledge"

class AiyoMemory:
    def __init__(self):
        try:
            # Persistent Client Creation (not on RAM, but on disk)
            self.client = chromadb.PersistentClient(path=DB_PATH)
            # Get or Create Collection
            self.collection = self.client.get_or_create_collection(
                name=COLLECTION_NAME,
                # Chosen distance metric is Cosine similarity
                metadata={"hnsw:space": "cosine"}
            )
        except Exception as e:
            print(f"Memory Error: {e}")

    def add_memory(self, text, source="user", category="general"):
        try:
            # 1. DUPLICATE CHECK
            existing = self.collection.query(query_texts=[text], n_results=1)

            if existing['documents'] and len(existing['documents'][0]) > 0:
                existing_distance = existing['distances'][0][0]
                # Benzerlik eşiği: 0.25'ten küçükse kaydetme (Aynısı var demektir)
                if existing_distance < 0.25: 
                    return None

            # 2. SAVE
            doc_id = str(uuid.uuid4()) # Unique ID
            timestamp = datetime.datetime.now().isoformat() # ISO Timestamp
            
            self.collection.add(
                documents=[text],
                metadatas=[{"source": source, "category": category, "timestamp": timestamp}],
                ids=[doc_id]
            )
            return doc_id 

        except Exception as e:
            return None

    def delete_memory(self, doc_id):
        try:
            self.collection.delete(ids=[doc_id])
            return True
        except:
            return False

    def search_memory(self, query, n_results=5):
        try:
            results = self.collection.query(
                query_texts=[query], 
                n_results=n_results
            )
        
            found_memories = []
            if results['documents']:
                for i in range(len(results['documents'][0])):
                    distance = results['distances'][0][i]
                    text = results['documents'][0][i]
                    doc_id = results['ids'][0][i]
                
                    # [DEĞİŞİKLİK] Eşik değerini (1.4) GEÇİCİ OLARAK KALDIRIYORUZ.
                    # Neden gelmediğini görmek için her şeyi (mesafesi 2.0 olsa bile) getirsin.
                    # if distance < 1.4:  <-- Yorum satırı yap veya sil
                    found_memories.append({"id": doc_id, "text": text, "distance": distance})
        
            return found_memories 
        except Exception as e:
            print(f"Search Error: {e}")
            return []