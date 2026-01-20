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
            # ÖNCE KONTROL ET: Bu ID veritabanında var mı?
            existing = self.collection.get(ids=[doc_id])
            
            # Eğer ID bulunamazsa (ids listesi boşsa) False döndür
            if not existing['ids']:
                print(f"Delete Error: ID '{doc_id}' not found in DB.")
                return False

            # Varsa sil
            self.collection.delete(ids=[doc_id])
            return True
        except Exception as e:
            print(f"Delete Exception: {e}")
            return False
            
    def search_memory(self, query, n_results=3):
        try:
            results = self.collection.query(
                query_texts=[query], 
                n_results=n_results
            )
        
            found_memories = []
            if results['documents']:
                count = len(results['documents'][0])
                
                for i in range(count):
                    distance = results['distances'][0][i]
                    text = results['documents'][0][i]
                    doc_id = results['ids'][0][i]
                
                    # BURADA FİLTRE YOK!
                    # 1.4, 1.8, 2.5... Ne bulursa hepsini listeye ekliyor.
                    # Böylece main dosyasında hepsini ekrana basıp görebileceksin.
                    found_memories.append({
                        "id": doc_id, 
                        "text": text, 
                        "distance": distance
                    })
        
            return found_memories 
        except Exception as e:
            print(f"Search Error: {e}")
            return []