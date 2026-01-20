import ollama
import sys
import time
import os
import re
from memory import AiyoMemory

# ------------- Configuration -------------
MODEL_NAME = "gemma2:9b"
# -----------------------------------------

# ------------- System Prompt -------------
SYSTEM_PROMPT = """
You are Aiyo, a witty and helpful local AI assistant.

--- CORE INSTRUCTIONS ---
1. You have access to a vector memory (CONTEXT). Use it to answer questions.
2. The Context formats memories as: [ID: uuid] Memory Text...
3. IF you do not find the answer in the CONTEXT or conversation history:
   - DO NOT GUESS.
   - Simply ask the user for the information.

--- MEMORY PROCESS (CRITICAL) ---
Every time the user sends a message, you must mentally perform these steps:
1. **Analyze**: Does the user mention a specific FACT about themselves (Hobby, Preference, Location, Plan)?
2. **Check**: Is this a question? (If yes, DO NOT SAVE).
3. **Action**: If it is a new fact, output the [SAVE: ...] tag immediately.

--- MEMORY ACTIONS (STRICT) ---

1. [SAVE] (Auto-Memory):
   - TRIGGER: When the user states a NEW fact or preference.
   - SOURCE TRUTH: Extract facts ONLY from the 'USER' input.
   - SYNTAX: [SAVE: User likes Linux Kernel development]
   - RULE: Use Third Person ("User is...", "User likes...").

2. [FORGET] (Manual-Cleanup):
   - PROCESS: 
     1. Analyze user input for keywords: "forget", "delete", "remove", "wrong".
     2. Search the current CONTEXT block for the specific fact the user refers to.
     3. Extract the exact [ID] associated with that fact.
     4. Generate the tag: [FORGET: INSERT_ID_HERE].
   - EXAMPLES:
     * Context: "[ID: 12ab] User likes apples" -> User: "I hate apples, delete that." -> Aiyo: "[FORGET: 12ab] Deleted."
     * Context: "[ID: 56cd] User lives in Ankara" -> User: "Forget where I live." -> Aiyo: "[FORGET: 56cd] Location removed."
   - TRIGGER: When the user wants to correct or remove information.
--- FEW-SHOT EXAMPLES (FOLLOW THESE PATTERNS) ---

Example 1 (Fact Statement):
User: "I live in Istanbul."
Aiyo: [SAVE: User lives in Istanbul] Oh, Istanbul is a beautiful city! Which side do you live on?

Example 2 (Preference in Conversation):
User: "I am more into metal music usually."
Aiyo: [SAVE: User prefers metal music] Metal is awesome! Do you have a favorite band?

Example 3 (Correction):
User: "Actually, I don't like mushrooms."
Aiyo: [SAVE: User dislikes mushrooms] Got it, I'll remember that for future recipes.

Example 4 (Question - NO SAVE):
User: "Do you know where I live?"
Aiyo: (NO SAVE TAG) I don't know that yet. Can you tell me?

--- CONFLICT HANDLING ---
IF the Context contains conflicting facts (e.g., ID_A says "Red", User says "Blue"):
   - Action: Just [SAVE: User's favorite color is Blue].
   - DO NOT auto-delete ID_A. 
"""
# -----------------------------------------

# ------------- UI Utilities -------------
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    GREY = '\033[90m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    ENDC = '\033[0m'

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def type_effect(text):
    for char in text:
        print(char, end="", flush=True)
        time.sleep(0.005)
    print()
# ----------------------------------------


def chat_session():

    # ------------- Memory Connection -------------
    print(f"{Colors.YELLOW}Linking Neural Pathways...{Colors.ENDC}", end="")
    try:
        memory_bank = AiyoMemory() # access memory system
        print(f" {Colors.GREEN}[LINKED]{Colors.ENDC}")
    except:
        print(f" {Colors.RED}[FAIL]{Colors.ENDC}")
        return

    print(f"{Colors.CYAN}Aiyo v0.2 (Fast-Track RAG) Initialized.{Colors.ENDC}")
    print("-" * 50)
    # ---------------------------------------------

    # Initial Message from System
    messages = [{'role': 'system', 'content': SYSTEM_PROMPT}]
    
    # Last data saved to memory (for delete purposes, for accidental saves)
    last_saved_id = None

    # ------------- Main Interaction Loop -------------
    while True:
        try:
            # ------------- 1. Input & Commands -------------
            user_input = input(f"\n{Colors.GREEN}You:{Colors.ENDC} ")
            if not user_input.strip(): continue # Boş girdi kontrolü
            
            if user_input.lower() in ['exit', 'quit']: break # Çıkış
            
            # Slash Komutları (Context Temizleme)
            if user_input.strip() in ['/new', '/reset', '.']:
                messages = [{'role': 'system', 'content': SYSTEM_PROMPT}]
                print(f"{Colors.YELLOW}✨ Conversation context cleared.{Colors.ENDC}")
                continue
            
            # Manuel Hafıza Silme Komutu (/del)
            if user_input.startswith("/del"):
                try:
                    tid = user_input.split()[1]
                    if memory_bank.delete_memory(tid):
                        print(f"{Colors.RED}🗑️ Memory {tid} destroyed.{Colors.ENDC}")
                    else: 
                        print(f"{Colors.GREY}⚠️ ID not found.{Colors.ENDC}")
                except: print("Usage: /del <id>")
                continue
            # -----------------------------------------------

            # ------------- 2. Retrieval Logic -------------
            
            # Arama sorgusunu kullanıcı girdisine eşitle
            search_query = user_input

            # [MUTABIK KALDIĞIMIZ KISIM] Query Transformation
            # "me/my" kelimelerini "User/User's" yaparak veritabanı eşleşmesini artır.
            # (Bunu az önce konuşup onayladığımız için tuttum, istersen silebilirsin)
            search_query = re.sub(r'\b(my)\b', "User's", search_query, flags=re.IGNORECASE)
            search_query = re.sub(r'\b(me|i|myself)\b', "User", search_query, flags=re.IGNORECASE)
            
            # Kullanıcı mesajını sohbet geçmişine ekle
            messages.append({'role': 'user', 'content': user_input})
            payload_messages = list(messages) 

            # C) Scan Memory (Hafıza Tarama)
            # --- C) Scan Memory (Hibrit Yaklaşım) ---
            print(f"{Colors.GREY}🔍 Scanning archives...{Colors.ENDC}", end="\r")
            
            # 1. Önce Normal Vektör Araması Yap
            retrieved_list = memory_bank.search_memory(search_query) 
            
            context_str_list = []
            ids_in_context = [] # Çakışmayı önlemek için eklenen ID'leri tutacağız

            # 2. [ÖNCELİK 1] Son Kaydedilen Veriyi (Injection) Ekle
            # Kullanıcı "Bunu sil" derse, büyük ihtimalle son ekleneni kastediyordur.
            if last_saved_id:
                try:
                    # Veriyi ID ile doğrudan çek
                    recent_mem = memory_bank.collection.get(ids=[last_saved_id])
                    if recent_mem['documents']:
                         rec_text = recent_mem['documents'][0]
                         rec_id = recent_mem['ids'][0]
                         
                         # Listeye ekle (Başına [LATEST] yazarak modele ipucu ver)
                         entry = f"[LATEST MEMORY] [ID: {rec_id}] {rec_text}"
                         context_str_list.append(entry)
                         ids_in_context.append(rec_id) # Bu ID'yi not et
                         
                         print(f"   🚀 {Colors.CYAN}[DEBUG] Injected Last Save: '{rec_text}'{Colors.ENDC}")
                except:
                    pass # Hata olursa (örn silinmişse) devam et

            # 3. [ÖNCELİK 2] Vektörden Gelenleri Ekle
            if retrieved_list:
                print(f"{Colors.YELLOW}💡 Recall (Top 3):{Colors.ENDC}")
                
                for m in retrieved_list:
                    dist = m['distance']
                    rec_id = m['id']
                    
                    # Eşik Değeri
                    THRESHOLD = 1.5
                    
                    # Görsel Renklendirme
                    if dist < THRESHOLD: color = Colors.GREEN
                    else: color = Colors.RED
                    
                    print(f"   🎯 {color}[DEBUG] Dist: {dist:.4f} | ID: {rec_id} | Found: '{m['text']}'{Colors.ENDC}")
                    
                    # Mantıksal Ekleme
                    if dist < THRESHOLD:
                        # KONTROL: Bu ID'yi az önce "Last Save" olarak ekledik mi?
                        if rec_id not in ids_in_context:
                            context_str_list.append(f"[ID: {rec_id}] {m['text']}")
                            ids_in_context.append(rec_id) # Listeye eklendi işaretle

            # 4. Context'i Hazırla
            if context_str_list:
                full_context = "\n".join(context_str_list)
                # Prompt'a göm
                augmented_prompt = f"CONTEXT (Use these facts if relevant):\n{full_context}\n\nUSER: {user_input}"
                payload_messages[-1] = {'role': 'user', 'content': augmented_prompt}
            else:
                print(" " * 30, end="\r")
            # -----------------------------------------------

            # ------------- AI Inference (Generation) -------------
            print(f"{Colors.BLUE}Aiyo:{Colors.ENDC} ", end="", flush=True)
            start_time = time.time()
            
            response = ollama.chat(
                model=MODEL_NAME, 
                messages=payload_messages,
                options={"num_ctx": 4096} 
            )
            
            full_content = response['message']['content']
            end_time = time.time()
            # -----------------------------------------------------

            # ------------- Response Post-Processing -------------
            # Cleaning HTML Tags if any
            full_content = re.sub(r'<[^>]+>', '', full_content)

            clean_output = full_content
            system_note = ""

            # Check for [FORGET:...] Tags (Döngüsel Kontrol)
            while "[FORGET:" in full_content:
                forget_match = re.search(r'\[FORGET:(.*?)\]', full_content)
                if forget_match:
                    target_id = forget_match.group(1).strip()
                    
                    # Silme işlemi
                    if memory_bank.delete_memory(target_id):
                        prefix = system_note + "\n" if system_note else "\n"
                        system_note = f"{prefix}{Colors.RED}🗑️ [Auto-Prune]: Memory {target_id[:8]}... deleted.{Colors.ENDC}"
                    else:
                        prefix = system_note + "\n" if system_note else "\n"
                        system_note = f"{prefix}{Colors.GREY}⚠️ [Auto-Prune]: ID {target_id[:8]}... not found.{Colors.ENDC}"
                    
                    # Etiketi temizle ve döngüye devam et (başka var mı diye)
                    full_content = full_content.replace(forget_match.group(0), "").strip()
                else:
                    break
            
            # Temizlenmiş çıktıyı hazırla
            clean_output = full_content
            # Save Action - SADECE SORU İŞARETİ KONTROLÜ
            if "[SAVE:" in full_content:
                save_match = re.search(r'\[SAVE:(.*?)\]', full_content)
                if save_match:
                    fact = save_match.group(1).strip()
                    
                    # TEK KURAL: Kullanıcı mesajında '?' varsa kaydetme.
                    if "?" in user_input:
                         prefix = system_note + "\n" if system_note else "\n"
                         system_note = f"{prefix}{Colors.GREY}[Safety]: Save blocked (User asked a question).{Colors.ENDC}"
                    else:
                        # Soru işareti yoksa doğrudan kaydet
                        new_id = memory_bank.add_memory(fact, category="auto")
                        if new_id:
                            last_saved_id = new_id
                            prefix = system_note + "\n" if system_note else "\n"
                            system_note = f"{prefix}{Colors.GREY}[Auto-Save]: '{fact}'{Colors.ENDC}"
                        else:
                            prefix = system_note + "\n" if system_note else "\n"
                            system_note = f"{prefix}{Colors.GREY}[Memory]: I already knew that.{Colors.ENDC}"
                    
                    # Etiketi çıktıdan temizle
                    clean_output = full_content.replace(save_match.group(0), "").strip()
            # ----------------------------------------------------
                    
            # ------------- User Interface Output -------------
            type_effect(clean_output)
            if system_note: print(system_note)
            print(f"{Colors.HEADER}   (⏱️ {end_time - start_time:.2f}s){Colors.ENDC}")

            messages.append({'role': 'assistant', 'content': clean_output})
            # -------------------------------------------------

        except KeyboardInterrupt:
            print("\nInterrupted.")
            break
        except Exception as e:
            print(f"\n{Colors.RED}Error: {e}{Colors.ENDC}")
    # -------------------------------------------------

if __name__ == "__main__":
    clear_screen()
    chat_session()