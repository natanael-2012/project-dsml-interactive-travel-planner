# %%
from dotenv import load_dotenv
import os

# from google.colab import userdata
# HF_TOKEN = userdata.get('HF_TOKEN')
# userdata.get('OPENAI_API_KEY')

load_dotenv()
# huggingface_token = os.getenv("HUGGINGFACE_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# %%
from google.colab import drive
import os
import zipfile
from tqdm import tqdm
# from dotenv import load_dotenv
from openai import OpenAI
from transformers import pipeline, AutoTokenizer, AutoModelForSeq2SeqLM

# %%
# ========== Mount Google Drive ==========
drive.mount('/content/drive')

# ========== Path Configuration ==========
# Update these paths according to your Google Drive structure
DRIVE_BASE = '/content/drive/MyDrive/'
ZIP_PATH = "./data/elmundo_chunked_es_page1_40years.zip"
EXTRACT_DIR = '/tmp/extracted'  # Using tmp for faster I/O
OUTPUT_DIR = os.path.join(DRIVE_BASE, 'cleaned_articles1')

# Create directories
os.makedirs(EXTRACT_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)


# %%
ZIP_PATH = "./data/elmundo_chunked_es_page1_40years.zip"
EXTRACT_DIR = '/tmp/extracted'  # Using tmp for faster I/O
os.makedirs(EXTRACT_DIR, exist_ok=True)

# %%
# ========== File Extraction ==========
def extract_files():
    with zipfile.ZipFile(ZIP_PATH, 'r') as zip_ref:
        # Extract nested structure
        for file in zip_ref.namelist():
            if file.endswith('.txt'):
                print(f"{file} extracted")
    print("*" * 50)
    print(f"Extracted files to: {EXTRACT_DIR}")

# %% [markdown]
# 1. Extract zip file
# 2. open the folder
# 3. For each file in folder, 
#     read the content and extract the text
#     <!-- chunk the text into 1000 words -->
#     <!-- pass chunks to the model so it can fix the spelling -->
#     translate the corrected text to english
#     <!-- add the file name and the corrected text to a dictionary -->
#     save the corrected text to a new file
# 4. Save the dictionary to a pkl file
# 5. 
# 

# %%
from openai import OpenAI
client = OpenAI(
    api_key=OPENAI_API_KEY
)

def correct_with_openai(text, filename, just_text = True, max_completion_tokens = 2048, temperature = 1, top_p = 1, frequency_penalty=0, presence_penalty=0,**kwargs):
  response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
      {
        "role": "user",
        "content": [
          {
            "type": "text",
            "text": f"Eres un experto en documentos históricos de Puerto Rico. El texto en español son noticias del siglo XX y contiene muchos errores a causa del OCR. Descifra el contenido y tradúcelo al inglés:\n1. Preserva nombres propios (ej: Mayagüez, Caguas)\n2. Ignora el \"header\" (ej:\n```EL MUNDO\nPRONOSTICOS DEL TIEMPO PARA LA ISLA, HOY: Mayormente nublado, con aguaceros dispersos temprano en la mafiana. EN SAN JUAN. AYER: Temperatura máxima. 80; mínima, 77. Presión barométrica al nivel del mar, a las 4:80 de la tarde. 38.88 pulgadas de mercurio. No hay indicios de disturbio tropical.\n40 páginas 5/\nDIARIO DE LA MARANA\nAÑO XXVIII\nEntered aa second clsss matter, Post Office, San Juan, P. R.)```\n3. Ignora los anuncios\n4. Solo mantén contenido relacionado a Puerto Rico (especialmente sobre ciudades, locaciones o eventos históricos)\n5. Traduce el texto a inglés. Solo mantén los datos mas importantes\n6.  Lista las ciudades o locaciones de Puerto Rico mencionadas\n7. Escribe solo en texto (no uses **negrillas** ni *itálicas* ni nada en markdown)\n8. return it as a JSON object with two fields:\n    - 'metadata': un diccionario con la siguiente informacion: 'filename' (nombre del articulo), 'date' (fecha del articulo), 'locations' (lista de las ciudades o locaciones de Puerto Rico mencionadas).\n    - 'text': the corrected and summarized text in English.\n8. No digas nada mas ni preguntes más. El nombre del articulo es {filename}. Usa el siguiente texto: {text}"
          }
        ]
      }
    ],
    response_format={
      "type": "json_object"
    },
    temperature=temperature,
    max_completion_tokens=max_completion_tokens,
    top_p=top_p,
    frequency_penalty=frequency_penalty,
    presence_penalty=presence_penalty,
    **kwargs
  )
  if just_text:
    return response.choices[0].message.content
  
  return response

# %%
from datetime import datetime
import pickle as pkl

def save_progress(data, filename="all_docs.pkl"):
    """ Save the current state of data to Google Drive. """
    save_path = os.path.join(OUTPUT_DIR, filename)
    
    with open(save_path, 'wb') as f:
        pkl.dump(data, f)
    
    print(f"Progress saved at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} to {save_path}")

# %%
# ========== Processing Pipeline ==========
import json
import pickle as pkl
from langchain.docstore.document import Document
import time

# Save progress every 30 minutes
interval_minutes = 30

def process_files():
    extract_files()

    all_docs = []

    # Track when the last save occurred
    last_save_time = time.time()

    # Get all text files from nested directory
    base_dir = os.path.join(EXTRACT_DIR, "elmundo_chunked_es_page1_40years")
    txt_files = [f for f in os.listdir(base_dir) if f.endswith('.txt')]

    for filename in tqdm(txt_files, desc="Processing files"):
        input_path = os.path.join(base_dir, filename)
        output_path = os.path.join(OUTPUT_DIR, f"cleaned_{filename}")

        with open(input_path, 'r', encoding='utf-8', errors='ignore') as f:
            raw_text = f.read()

        try:
            # cleaned text is a JSON object with 'metadata' and 'text' fields:
            json_object = json.loads(correct_with_openai(raw_text, filename))  # OpenAI version
            cleaned_text = json_object.get('text')

            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(cleaned_text.get('text'))

            print(f"Processed: {filename} -> Saved to Drive")

            doc = Document(
                page_content=json_object['text'],
                metadata=json_object['metadata']
            )
            all_docs.append(doc)

        except Exception as e:
            print(f"Error processing {filename}: {str(e)}")
            continue

        current_time = time.time()
        if (current_time - last_save_time) >= (interval_minutes * 60):
            save_progress(all_docs)
            last_save_time = current_time  # Update the last save time

    # Save all_docs as pkl file
    with open(os.path.join(OUTPUT_DIR, "all_docs.pkl"), 'wb') as f:
        pkl.dump(all_docs, f)

    with open("all_docs.pkl", 'wb') as f:
        pkl.dump(all_docs, f)

    return all_docs

# %%
all_docs = process_files()

# %%
## ========== Chroma ==========


