import re
import string
import logging
import unicodedata
import pandas as pd
from etnltk import Amharic

# --- Setup logging ---
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# --- Precompiled regex ---
RE_LATIN_PUNCTUATION = re.compile(r'[!"#$%&\'()*+,\-./:;<=>?@[\\\]^_`{|}~]')
RE_REPEAT_SYMBOLS = re.compile(r'(\W)(\1{2,})')
RE_WHITESPACE = re.compile(r'\s+')
RE_EMOJI = re.compile("["
    u"\U0001F600-\U0001F64F"  # emoticons
    u"\U0001F300-\U0001F5FF"  # symbols & pictographs
    u"\U0001F680-\U0001F6FF"  # transport & map symbols
    u"\U0001F1E0-\U0001F1FF"  # flags
    u"\U00002500-\U00002BEF"  # Chinese char and symbols
    u"\U00002702-\U000027B0"
    u"\U000024C2-\U0001F251"
    u"\U0001f926-\U0001f937"
    u"\U00010000-\U0010ffff"
    u"\u2640-\u2642" 
    u"\u2600-\u2B55"
    u"\u200d"
    u"\u23cf"
    u"\u23e9"
    u"\u231a"
    u"\ufe0f"  # dingbats
    u"\u3030"
    "]+", flags=re.UNICODE)

# --- Stopwords and punctuation ---
AMHARIC_STOPWORDS = set([
    'እኔ', 'አንተ', 'እሱ', 'እሷ', 'እኛ', 'እናንተ', 'እነሱ',
    'ነኝ', 'ነህ', 'ናት', 'ነው', 'ነን', 'ናችሁ', 'ናቸው',
    'ወደ', 'ከ', 'በ', 'ለ', 'እንደ',
    'እንጂ', 'እንኳን', 'ደግሞ', 'ነገር', 'ግን', 'ምክንያት',
    'ያለ', 'ያልኩ', 'እየ', 'እንደዚህ', 'ያህዌ'
])

PUNCTUATION_SET = set(string.punctuation) | {'።', '፤', '…', '‘', '’', '“', '”'}

# --- Manual normalization ---
def manual_normalize_amharic(text):
    """Normalize common Amharic letter variants"""
    replacements = {
        'ሃ': 'ሀ', 'ኅ': 'ሀ', 'ኃ': 'ሀ', 'ሐ': 'ሀ', 'ሓ': 'ሀ',
        'ኻ': 'ሀ', 'ሃ': 'ሀ', 'ኸ': 'ሀ',
        'ዐ': 'አ', 'ኣ': 'አ', 'ዓ': 'አ',
        'ዑ': 'ኡ',
        'ዒ': 'ኢ',
        'ዔ': 'ኤ',
        'ዕ': 'እ',
        'ዖ': 'ኦ',
        'ጸ': 'ፀ',
        'ሴ': 'ሰ',
        'ሺ': 'ሰ',
    }
    for src, tgt in replacements.items():
        text = text.replace(src, tgt)
    return text

# --- Remove stopwords and punctuation ---
def remove_amharic_stopwords(tokens):
    """Remove Amharic stopwords and punctuation tokens"""
    return [
        token for token in tokens
        if token not in AMHARIC_STOPWORDS and token not in PUNCTUATION_SET and not RE_EMOJI.match(token)
    ]

# --- Clean text fallback ---
def clean_text_basic(text):
    """Basic cleaning if etnltk fails"""
    text = unicodedata.normalize('NFKC', text)
    text = RE_REPEAT_SYMBOLS.sub(r'\1', text)
    text = RE_LATIN_PUNCTUATION.sub('', text)
    text = RE_EMOJI.sub('', text)
    text = RE_WHITESPACE.sub(' ', text)
    return text.strip()

# --- Normalize Amharic text ---
def normalize_amharic(text):
    """Full normalization pipeline for Amharic text"""
    if not text or pd.isna(text):
        return ""
    
    text = unicodedata.normalize('NFKC', text)
    
    try:
        doc = Amharic(text)
        norm = getattr(doc, 'get_normalized', lambda: getattr(doc, 'normalized_text', text))()
    except Exception as e:
        logger.warning(f"Normalization failed for: {text[:50]}... Error: {e}")
        norm = clean_text_basic(text)

    norm = RE_EMOJI.sub('', norm)
    norm = manual_normalize_amharic(norm)
    return norm

# --- Tokenization pipeline ---
def tokenize_amharic(text):
    """Tokenize Amharic text using etnltk with fallback"""
    if not text or pd.isna(text):
        return []

    try:
        doc = Amharic(text)
        tokens = getattr(doc, 'get_tokens', lambda: getattr(doc, 'tokens', text.split()))()
    except Exception as e:
        logger.warning(f"Tokenization failed for: {text[:50]}... Error: {e}")
        tokens = text.split()
    
    return remove_amharic_stopwords(tokens)

# --- DataFrame processing ---
def clean_and_tokenize_dataframe(df):
    """
    Clean and tokenize Amharic messages in a DataFrame.

    Args:
        df (pd.DataFrame): Must contain a 'message' column.

    Returns:
        pd.DataFrame: with new columns 'cleaned_message' and 'tokens'
    """
    if 'message' not in df.columns:
        raise ValueError("DataFrame must contain 'message' column")
    
    df['cleaned_message'] = df['message'].fillna("").apply(normalize_amharic)
    df['tokens'] = df['cleaned_message'].apply(tokenize_amharic)
    return df
