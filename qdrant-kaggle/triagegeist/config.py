import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = Path(os.getenv("DATA_DIR", PROJECT_ROOT / "data"))
RESULTS_DIR = PROJECT_ROOT / "results"
RESULTS_DIR.mkdir(exist_ok=True)

# Data files (Kaggle competition dataset)
TRAIN_CSV = DATA_DIR / "train.csv"
TEST_CSV = DATA_DIR / "test.csv"
CHIEF_COMPLAINTS_CSV = DATA_DIR / "chief_complaints.csv"
PATIENT_HISTORY_CSV = DATA_DIR / "patient_history.csv"
SAMPLE_SUBMISSION_CSV = DATA_DIR / "sample_submission.csv"

# Qdrant
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
COLLECTION_NAME = os.getenv("QDRANT_COLLECTION", "triagegeist")

# Embedding model (Fastembed-native, strong on clinical text)
EMBEDDING_MODEL = "nomic-ai/nomic-embed-text-v1.5"
EMBEDDING_DIM = 768

# Search / prediction
K_NEIGHBORS = 15
DISTANCE_METRIC = "Cosine"

# Vitals columns (for text serialization)
VITALS_COLS = [
    "systolic_bp", "diastolic_bp", "heart_rate", "respiratory_rate",
    "temperature_c", "spo2", "gcs_total", "pain_score",
    "shock_index", "news2_score", "bmi",
]

# Demographic columns (for bias analysis)
DEMOGRAPHIC_COLS = ["age_group", "sex", "language", "insurance_type"]

# Triage context columns
CONTEXT_COLS = [
    "arrival_mode", "arrival_hour", "arrival_day", "arrival_season",
    "shift", "mental_status_triage", "chief_complaint_system",
    "pain_location", "transport_origin",
]

# History columns prefix
HISTORY_PREFIX = "hx_"

# Target
TARGET_COL = "triage_acuity"

# ESI labels for display
ESI_LABELS = {
    1: "Resuscitation",
    2: "Emergent",
    3: "Urgent",
    4: "Less Urgent",
    5: "Non-Urgent",
}
