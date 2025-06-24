# interpret_model.py
from transformers import AutoTokenizer, AutoModelForTokenClassification
from transformers import pipeline
import shap
import torch

# Load model and tokenizer
model_path = "masakhane/afroxlmr-large-ner-masakhaner-1.0_2.0"
model = AutoModelForTokenClassification.from_pretrained(model_path)
tokenizer = AutoTokenizer.from_pretrained(model_path)

# Inference pipeline
nlp_ner = pipeline("ner", model=model, tokenizer=tokenizer, aggregation_strategy="simple")

# Sample text for explanation
text = "በአዲስ አበባ የሚገኙ ሻይ እና አብራሪ ቤቶች ሽያጭ በቅናሽ በቀድሞ ዋጋ እየቀሩ ናቸው።"

print("NER Predictions:")
print(nlp_ner(text))

# SHAP for interpretability
explainer = shap.Explainer(nlp_ner)
shap_values = explainer([text])
shap.plots.text(shap_values[0])
