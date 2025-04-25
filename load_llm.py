from transformers import AutoTokenizer, AutoModelForCausalLM
import os
from huggingface_hub import login
from dotenv import load_dotenv
load_dotenv()
huggingface_token = os.environ.get("HUGGINGFACE_TOKEN")
login(token=huggingface_token)
model_id = "google/gemma-7b-it"  # ví dụ model

local_dir = "./models/gemma-7b-it"  # thư mục lưu model

# Tải model và lưu local (nếu chưa có)
tokenizer = AutoTokenizer.from_pretrained(model_id, cache_dir=local_dir)
model = AutoModelForCausalLM.from_pretrained(model_id, cache_dir=local_dir)

