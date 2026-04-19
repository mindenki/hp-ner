# Load model directly
from transformers import AutoModel, AutoTokenizer
# model = AutoModel.from_pretrained("microsoft/deberta-v3-base", dtype="auto")
tokenizer = AutoTokenizer.from_pretrained("microsoft/deberta-v3-base", dtype="auto")

# model.save_pretrained("./bert")
tokenizer.save_pretrained("./bert")
