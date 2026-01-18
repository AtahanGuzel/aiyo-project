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

--- MEMORY ACTIONS (STRICT) ---

1. [SAVE] (Auto-Memory):
   - TRIGGER: ONLY when the user EXPLICITLY states a NEW fact about themselves, their preferences, or the project in the CURRENT message.
   - SOURCE TRUTH: You must ONLY extract facts that are physically written in the 'USER' input. 
   - FORBIDDEN: 
     - NEVER save facts based on your own output/response.
     - NEVER save general knowledge or definitions (e.g., "The sky is blue").
     - NEVER save answers to questions the user asked.
   - Syntax: [SAVE: User likes Linux Kernel development]

2. [FORGET] (Manual-Cleanup ONLY):
   - TRIGGER: ONLY when the user EXPLICITLY asks to "delete", "remove", or "forget" a specific information.
   - RULE: NEVER auto-delete conflicting information. Only delete when commanded.
   - Syntax: [FORGET: ID_OF_THE_TARGET_MEMORY]

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
            # ------------- Input & Commands -------------
            user_input = input(f"\n{Colors.GREEN}You:{Colors.ENDC} ")
            if not user_input.strip(): continue # Empty input check
            
            if user_input.lower() in ['exit', 'quit']: break # Exit
            
            # Slash Commands (Clear Context)
            if user_input.strip() in ['/new', '/reset', '.']:
                # Reset messages list but keep system prompt
                messages = [{'role': 'system', 'content': SYSTEM_PROMPT}]
                print(f"{Colors.YELLOW}✨ Conversation context cleared.{Colors.ENDC}")
                continue
            
            # Manual Memory Delete Command
            if user_input.startswith("/del"):
                try:
                    tid = user_input.split()[1] # Split for 'del' and 'id'
                    if memory_bank.delete_memory(tid):
                        print(f"{Colors.RED}Memory {tid} destroyed.{Colors.ENDC}")
                    else: print(f"{Colors.GREY}ID not found.{Colors.ENDC}")
                except: print("Usage: /del <id>")
                continue
            # --------------------------------------------
            
            # ------------- RAG Retrieval Logic -------------
            # take the current user input for retrieval
            search_query = user_input
            
            # Store user input
            messages.append({'role': 'user', 'content': user_input})
            # Prepare temporary payload messages
            payload_messages = list(messages) 

            # Scan Memory for Relevant Context
            print(f"{Colors.GREY}Scanning archives...{Colors.ENDC}", end="\r")
            retrieved_list = memory_bank.search_memory(search_query) 
            
            if retrieved_list:
                print(f"{Colors.YELLOW}Recall:{Colors.ENDC} {Colors.GREY}Found {len(retrieved_list)} memories.{Colors.ENDC}")
                context_str_list = [] 
                for m in retrieved_list:
                    print(f"   {Colors.YELLOW}[DEBUG] Dist: {m['distance']:.4f} | ID: {m['id']} | Found: '{m['text']}'{Colors.ENDC}")
                    context_str_list.append(f"[ID: {m['id']}] {m['text']}") # Format the data for Aiyo
                
                full_context = "\n".join(context_str_list) # Combine all retrieved memories
                # Augment the last user message with CONTEXT
                augmented_prompt = f"CONTEXT (Use these facts if relevant):\n{full_context}\n\nUSER: {user_input}"
                # Replace the last user message with the augmented one
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

            # Check for [FORGET:...] Tag
            if "[FORGET:" in full_content:
                forget_match = re.search(r'\[FORGET:(.*?)\]', full_content)
                if forget_match:
                    target_id = forget_match.group(1).strip()
                    success = memory_bank.delete_memory(target_id)
                    system_note = f"\n{Colors.RED}[Auto-Prune]: Conflicting memory removed.{Colors.ENDC}" if success else f"\n{Colors.GREY}[Auto-Prune]: ID not found.{Colors.ENDC}"
                    clean_output = full_content.replace(forget_match.group(0), "").strip()
                    full_content = clean_output

            # Check for [SAVE:...] Tag
            if "[SAVE:" in full_content:
                save_match = re.search(r'\[SAVE:(.*?)\]', full_content)
                if save_match:
                    fact = save_match.group(1).strip()
                    
                    # HALLUCINATION CHECK (Don't save if asking a question)
                    is_asking_question = "?" in clean_output
                    
                    if is_asking_question:
                         system_note = f"\n{Colors.GREY}[Safety]: Blocked hallucinated save during question.{Colors.ENDC}"
                    else:
                        new_id = memory_bank.add_memory(fact, category="auto")
                        if new_id:
                            last_saved_id = new_id
                            prefix = system_note + "\n" if system_note else "\n"
                            system_note = f"{prefix}{Colors.GREY}[Auto-Save]: '{fact}'{Colors.ENDC}"
                        else:
                            prefix = system_note + "\n" if system_note else "\n"
                            system_note = f"{prefix}{Colors.GREY}[Memory]: I already knew that.{Colors.ENDC}"
                    
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