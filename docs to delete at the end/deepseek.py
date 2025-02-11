!pip install -q transformers sentencepiece accelerate sentence-splitter

from transformers import pipeline, AutoTokenizer, AutoModelForSeq2SeqLM
from sentence_splitter import SentenceSplitter
from tqdm import tqdm
import torch

# ====== 1. OCR CORRECTION SETUP ======
# Local FLAN-T5 model
ocr_tokenizer = T5Tokenizer.from_pretrained("./flan-t5-small")
ocr_model = T5ForConditionalGeneration.from_pretrained("./flan-t5-small", device_map="auto")

# ====== 2. SUMMARIZATION SETUP ======
sum_tokenizer = AutoTokenizer.from_pretrained("mrm8488/bert2bert_shared-spanish-finetuned-summarization")
sum_model = AutoModelForSeq2SeqLM.from_pretrained("mrm8488/bert2bert_shared-spanish-finetuned-summarization").to("cuda")

# ====== 3. TRANSLATION SETUP ======
translator = pipeline("translation_es_to_en", 
                     model="Helsinki-NLP/opus-mt-es-en",
                     device=0)

# ====== TEXT PROCESSING FUNCTIONS ======
splitter = SentenceSplitter(language='es')

def chunk_text(text, max_chars=1000):
    """Split text into meaningful chunks preserving sentence boundaries"""
    chunks = []
    current_chunk = []
    current_len = 0
    
    for sentence in splitter.split(text):
        sent_len = len(sentence)
        if current_len + sent_len > max_chars:
            chunks.append(" ".join(current_chunk))
            current_chunk = [sentence]
            current_len = sent_len
        else:
            current_chunk.append(sentence)
            current_len += sent_len
            
    if current_chunk:
        chunks.append(" ".join(current_chunk))
    return chunks

def correct_ocr_chunk(chunk):
    inputs = ocr_tokenizer(
        f"Corrige errores OCR en este texto histórico español preservando nombres y fechas: {chunk}",
        return_tensors="pt",
        max_length=512,
        truncation=True
    ).to(ocr_model.device)
    
    outputs = ocr_model.generate(
        inputs.input_ids,
        max_length=1024,
        num_beams=3,
        early_stopping=True
    )
    return ocr_tokenizer.decode(outputs[0], skip_special_tokens=True)

def summarize_text(text):
    inputs = sum_tokenizer(
        text,
        return_tensors="pt",
        max_length=1024,
        truncation=True
    ).to("cuda")
    
    outputs = sum_model.generate(
        inputs.input_ids,
        max_length=512,
        min_length=256,
        num_beams=4,
        early_stopping=True
    )
    return sum_tokenizer.decode(outputs[0], skip_special_tokens=True)

# ====== FULL PIPELINE ======
def process_article(text):
    try:
        # 1. Chunk and Correct OCR
        corrected_chunks = [correct_ocr_chunk(chunk) for chunk in chunk_text(text)]
        full_corrected = "\n".join(corrected_chunks)
        
        # 2. Summarize
        if len(full_corrected.split()) > 500:  # Only summarize long articles
            summary = summarize_text(full_corrected)
        else:
            summary = full_corrected
            
        # 3. Translate
        translated = translator(summary, max_length=600)[0]['translation_text']
        
        return {
            "corrected": full_corrected,
            "summary_es": summary,
            "summary_en": translated
        }
    
    except Exception as e:
        print(f"Processing failed: {str(e)}")
        return None

# ====== PROCESS SAMPLE FILE ======
with open("19470802_1.txt", "r", errors="ignore") as f:
    raw_text = f.read()

result = process_article(raw_text)

print("=== CORRECTED TEXT ===")
print(result["corrected"][:2000] + "...\n")

print("=== SPANISH SUMMARY ===")
print(result["summary_es"] + "\n")

print("=== ENGLISH TRANSLATION ===")
print(result["summary_en"])