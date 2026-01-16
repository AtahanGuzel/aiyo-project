import ollama
import sys
import time
import os
import re
from memory import AiyoMemory

MODEL_NAME = "gemma2:9b"

# --- SYSTEM PROMPT (APPEND-ONLY & STRICT SAVE) ---
SYSTEM_PROMPT = """
You are Aiyo, a witty and helpful local AI assistant.

--- CORE INSTRUCTIONS ---
1. You have access to a vector memory (CONTEXT). Use it to answer questions.
2. The Context formats memories as: [ID: uuid] Memory Text...
3. IF you do not find the answer in the CONTEXT or conversation history:
   - DO NOT GUESS.
   - Simply ask the user for the information.

--- MEMORY ACTIONS (STRICT) ---

1. [SAVE] (Auto-Memory):
   - TRIGGER: When the user states a NEW fact about themselves, preferences, or the project.
   - QUALITY RULE: The content inside [SAVE: ...] must be a STANDALONE fact. Use specific nouns, not pronouns.
     - BAD: [SAVE: He likes it] (Ambiguous)
     - GOOD: [SAVE: User likes Linux Kernel development]
   - DUPLICATE RULE: DO NOT [SAVE] if the fact is already explicitly stated in the CONTEXT.

2. [FORGET] (Manual-Cleanup ONLY):
   - TRIGGER: ONLY when the user EXPLICITLY asks to "delete", "remove", or "forget" a specific information.
   - RULE: NEVER auto-delete conflicting information. Only delete when commanded.
   - Syntax: [FORGET: ID_OF_THE_TARGET_MEMORY]

--- CONFLICT HANDLING ---
IF the Context contains conflicting facts (e.g., ID_A says "Red", User says "Blue"):
   - Action: Just [SAVE: User's favorite color is Blue].
   - DO NOT auto-delete ID_A. 
   - You may simply inform the user that you updated your memory.
"""

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

# --- [YENİ] LLM Judge Function ---
def check_is_related(history_text, new_input):
    """
    Gemma'ya sorar: Bu yeni girdi, eskisiyle alakalı mı?
    Sadece 'YES' veya 'NO' döndürür. OOM yemez (Sequential).
    """
    prompt = f"""
    [INST] Analyze if the NEW INPUT is a continuation or follow-up to the HISTORY.
    
    HISTORY: "{history_text}"
    NEW INPUT: "{new_input}"
    
    Rules:
    1. If input refers to history (it, that, he, details) -> YES
    2. If input completely changes topic -> NO
    
    Reply ONLY with 'YES' or 'NO'. [/INST]
    """
    
    try:
        response = ollama.generate(
            model=MODEL_NAME, 
            prompt=prompt, 
            options={
                "num_predict": 2,     # Hız için sadece 2 token
                "temperature": 0.0,   # Robot gibi kesin cevap
                "num_ctx": 2048
            }
        )
        answer = response['response'].strip().upper()
        return "YES" in answer
    except:
        return False # Hata durumunda ayır

def chat_session():
    print(f"{Colors.YELLOW}🧠 Linking Neural Pathways...{Colors.ENDC}", end="")
    try:
        memory_bank = AiyoMemory()
        print(f" {Colors.GREEN}[LINKED]{Colors.ENDC} ✅")
    except:
        print(f" {Colors.RED}[FAIL]{Colors.ENDC}")
        return

    print(f"{Colors.CYAN}🤖 Aiyo v3.1 (Multi-Memory RAG) Initialized.{Colors.ENDC}")
    print("-" * 50)

    messages = [{'role': 'system', 'content': SYSTEM_PROMPT}]
    last_saved_id = None
    last_user_input_raw = "" 

    while True:
        try:
            # 1. Input Alma
            user_input = input(f"\n{Colors.GREEN}👤 Architect:{Colors.ENDC} ")
            if not user_input.strip(): continue
            
            # 2. Manuel Komutlar (Python Level)
            if user_input.lower() in ['exit', 'quit']: break
            
            # Slash Komutları (Context'i manuel temizler)
            if user_input.strip() in ['/new', '/reset', '.']:
                last_user_input_raw = ""
                print(f"{Colors.YELLOW}✨ Conversation context cleared.{Colors.ENDC}")
                continue
            
            # Admin Silme
            if user_input.startswith("/del"):
                try:
                    tid = user_input.split()[1]
                    if memory_bank.delete_memory(tid):
                        print(f"{Colors.RED}🗑️ Memory {tid} destroyed.{Colors.ENDC}")
                    else: print(f"{Colors.GREY}⚠️ ID not found.{Colors.ENDC}")
                except: print("Usage: /del <id>")
                continue

            # 3. [OPTIMIZASYON] Akıllı Context Merge
            search_query = user_input
            
            # Eğer geçmiş varsa, Gemma'ya sor (Her durumda)
            if last_user_input_raw:
                print(f"{Colors.GREY}🤔 Analyzing flow...{Colors.ENDC}", end="\r")
                
                is_connected = check_is_related(last_user_input_raw, user_input)
                
                if is_connected:
                    print(f"{Colors.GREY}🔗 Context merged (Topic Linked).    {Colors.ENDC}")
                    search_query = f"{last_user_input_raw} {user_input}"
                else:
                    print(f"{Colors.GREY}🆕 New Topic detected.               {Colors.ENDC}")
            
            # --- RAG AKIŞI ---
            
            messages.append({'role': 'user', 'content': user_input})
            payload_messages = list(messages) 

            # Hafıza Tarama
            print(f"{Colors.GREY}🔍 Scanning archives...{Colors.ENDC}", end="\r")
            retrieved_list = memory_bank.search_memory(search_query) 
            
            if retrieved_list:
                print(f"{Colors.YELLOW}💡 Recall:{Colors.ENDC} {Colors.GREY}Found {len(retrieved_list)} memories.{Colors.ENDC}")
                context_str_list = []
                for m in retrieved_list:
                    print(f"   🎯 {Colors.YELLOW}[DEBUG] Dist: {m['distance']:.4f} | ID: {m['id']} | Found: '{m['text']}'{Colors.ENDC}")
                    context_str_list.append(f"[ID: {m['id']}] {m['text']}")
                
                full_context = "\n".join(context_str_list)
                augmented_prompt = f"CONTEXT (Use these facts if relevant):\n{full_context}\n\nUSER: {user_input}"
                payload_messages[-1] = {'role': 'user', 'content': augmented_prompt}
            else:
                print(" " * 30, end="\r")

            # Cevap Üretme
            print(f"{Colors.BLUE}🤖 Aiyo:{Colors.ENDC} ", end="", flush=True)
            start_time = time.time()
            
            response = ollama.chat(
                model=MODEL_NAME, 
                messages=payload_messages,
                options={"num_ctx": 4096} 
            )
            
            full_content = response['message']['content']
            end_time = time.time()

            # --- PROCESSOR (Temizlik ve Aksiyonlar) ---
            
            # HTML Temizliği
            full_content = re.sub(r'<[^>]+>', '', full_content)

            clean_output = full_content
            system_note = ""

            # Forget Action
            if "[FORGET:" in full_content:
                forget_match = re.search(r'\[FORGET:(.*?)\]', full_content)
                if forget_match:
                    target_id = forget_match.group(1).strip()
                    success = memory_bank.delete_memory(target_id)
                    system_note = f"\n{Colors.RED}🗑️ [Auto-Prune]: Conflicting memory removed.{Colors.ENDC}" if success else f"\n{Colors.GREY}⚠️ [Auto-Prune]: ID not found.{Colors.ENDC}"
                    clean_output = full_content.replace(forget_match.group(0), "").strip()
                    full_content = clean_output

            # Save Action
            if "[SAVE:" in full_content:
                save_match = re.search(r'\[SAVE:(.*?)\]', full_content)
                if save_match:
                    fact = save_match.group(1).strip()
                    
                    # [YENİ] HALLUCINATION CHECK
                    # Eğer model cümlesinde soru işareti kullanıyorsa (Kullanıcıya soru soruyorsa)
                    # Genellikle o sırada yeni bir bilgi öğrenmemiştir, uyduruyordur.
                    is_asking_question = "?" in clean_output
                    
                    if is_asking_question:
                         # Soru sorarken kaydetmeyi engelle
                         # Ancak loga düşelim ki neyi engellediğimizi görelim
                         system_note = f"\n{Colors.GREY}🛡️ [Safety]: Blocked hallucinated save during question.{Colors.ENDC}"
                    
                    else:
                        # Güvenli, kaydet.
                        new_id = memory_bank.add_memory(fact, category="auto")
                        if new_id:
                            last_saved_id = new_id
                            prefix = system_note + "\n" if system_note else "\n"
                            system_note = f"{prefix}{Colors.GREY}💾 [Auto-Save]: '{fact}'{Colors.ENDC}"
                        else:
                            prefix = system_note + "\n" if system_note else "\n"
                            system_note = f"{prefix}{Colors.GREY}🧠 [Memory]: I already knew that.{Colors.ENDC}"
                    
                    # Her durumda etiketi temizle
                    clean_output = full_content.replace(save_match.group(0), "").strip()
                    
            # Output Basma
            type_effect(clean_output)
            if system_note: print(system_note)
            print(f"{Colors.HEADER}   (⏱️ {end_time - start_time:.2f}s){Colors.ENDC}")

            messages.append({'role': 'assistant', 'content': clean_output})
            last_user_input_raw = user_input # Loop sonu güncelleme

        except KeyboardInterrupt:
            print("\n🛑 Interrupted.")
            break
        except Exception as e:
            print(f"\n{Colors.RED}Error: {e}{Colors.ENDC}")

if __name__ == "__main__":
    clear_screen()
    chat_session()