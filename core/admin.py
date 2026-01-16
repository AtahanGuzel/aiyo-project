import chromadb
import os
import sys

# --- UI COLORS ---
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

# --- CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "storage", "chroma_db")
COLLECTION_NAME = "aiyo_knowledge"

def connect_db():
    try:
        client = chromadb.PersistentClient(path=DB_PATH)
        collection = client.get_or_create_collection(name=COLLECTION_NAME)
        return collection
    except Exception as e:
        print(f"{Colors.RED}🔥 Connection Error: {e}{Colors.ENDC}")
        sys.exit(1)

def list_memories():
    collection = connect_db()
    count = collection.count()
    
    print(f"\n{Colors.HEADER}🧠 NEURAL ARCHIVE DUMP ({count} Memories){Colors.ENDC}")
    print("-" * 60)
    
    # Get all data
    data = collection.get()
    
    if count == 0:
        print(f"{Colors.YELLOW}The brain is empty.{Colors.ENDC}")
        return

    ids = data['ids']
    documents = data['documents']
    metadatas = data['metadatas']
    
    for i in range(len(ids)):
        print(f"{Colors.CYAN}ID:{Colors.ENDC} {ids[i]}")
        print(f"{Colors.GREEN}Date:{Colors.ENDC} {metadatas[i].get('timestamp', 'Unknown')}")
        print(f"{Colors.YELLOW}Data:{Colors.ENDC} {documents[i]}")
        print("-" * 60)

def delete_memory(memory_id):
    collection = connect_db()
    try:
        collection.delete(ids=[memory_id])
        print(f"{Colors.GREEN}✅ Memory [{memory_id}] successfully deleted.{Colors.ENDC}")
    except Exception as e:
        print(f"{Colors.RED}❌ Error deleting memory: {e}{Colors.ENDC}")

def wipe_all():
    collection = connect_db()
    try:
        # Get all IDs first
        all_ids = collection.get()['ids']
        if all_ids:
            collection.delete(ids=all_ids)
            print(f"{Colors.RED}☢️  ALL MEMORIES WIPED! Aiyo is essentially reborn.{Colors.ENDC}")
        else:
            print("Nothing to delete.")
    except Exception as e:
        print(f"Error: {e}")

# --- MENU LOOP ---
if __name__ == "__main__":
    while True:
        print(f"\n{Colors.BLUE}--- AIYO ADMIN CONSOLE ---{Colors.ENDC}")
        print("1. List All Memories")
        print("2. Delete Specific Memory (Need ID)")
        print("3. Wipe EVERYTHING (Reset Brain)")
        print("4. Exit")
        
        choice = input(f"\n{Colors.GREEN}Select Option:{Colors.ENDC} ")
        
        if choice == '1':
            list_memories()
        elif choice == '2':
            target_id = input("Paste ID here: ").strip()
            delete_memory(target_id)
        elif choice == '3':
            confirm = input(f"{Colors.RED}Are you SURE? This cannot be undone. (yes/no):{Colors.ENDC} ")
            if confirm.lower() == 'yes':
                wipe_all()
        elif choice == '4':
            print("Exiting Admin Console.")
            break
        else:
            print("Invalid option.")