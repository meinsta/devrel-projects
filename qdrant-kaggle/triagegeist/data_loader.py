"""Load and merge Triagegeist competition data into embeddable patient records."""

import pandas as pd

from triagegeist.config import (
    CHIEF_COMPLAINTS_CSV,
    CONTEXT_COLS,
    HISTORY_PREFIX,
    PATIENT_HISTORY_CSV,
    SAMPLE_SUBMISSION_CSV,
    TEST_CSV,
    TRAIN_CSV,
    VITALS_COLS,
)


def load_train() -> pd.DataFrame:
    return _load_and_merge(TRAIN_CSV)


def load_test() -> pd.DataFrame:
    return _load_and_merge(TEST_CSV)


def load_sample_submission() -> pd.DataFrame:
    return pd.read_csv(SAMPLE_SUBMISSION_CSV)


def _load_and_merge(main_csv) -> pd.DataFrame:
    df = pd.read_csv(main_csv)
    complaints = pd.read_csv(CHIEF_COMPLAINTS_CSV)
    history = pd.read_csv(PATIENT_HISTORY_CSV)

    df = df.merge(complaints, on="patient_id", how="left")
    df = df.merge(history, on="patient_id", how="left")
    return df


def serialize_patient(row: pd.Series) -> str:
    """Convert a patient row into a natural language string for embedding.

    Combines chief complaint, vitals, context, and history into a single
    text representation that medical embedding models can process.
    """
    parts = []

    # Chief complaint (most important signal)
    cc = row.get("chief_complaint_raw")
    if pd.notna(cc) and str(cc).strip():
        parts.append(f"Chief complaint: {cc.strip()}")

    complaint_system = row.get("chief_complaint_system")
    if pd.notna(complaint_system):
        parts.append(f"System: {complaint_system}")

    # Mental status
    mental = row.get("mental_status_triage")
    if pd.notna(mental):
        parts.append(f"Mental status: {mental}")

    # Vitals as natural language
    vitals_parts = []
    vitals_map = {
        "systolic_bp": "systolic BP {:.0f}",
        "diastolic_bp": "diastolic BP {:.0f}",
        "heart_rate": "heart rate {:.0f}",
        "respiratory_rate": "respiratory rate {:.0f}",
        "temperature_c": "temperature {:.1f}C",
        "spo2": "SpO2 {:.0f}%",
        "gcs_total": "GCS {:.0f}",
        "pain_score": "pain {:.0f}/10",
        "shock_index": "shock index {:.2f}",
        "news2_score": "NEWS2 {:.0f}",
        "bmi": "BMI {:.1f}",
    }
    for col, fmt in vitals_map.items():
        val = row.get(col)
        if pd.notna(val) and val != -1:
            vitals_parts.append(fmt.format(val))
    if vitals_parts:
        parts.append(f"Vitals: {', '.join(vitals_parts)}")

    # Context
    context_map = {
        "arrival_mode": "Arrival: {}",
        "pain_location": "Pain location: {}",
        "transport_origin": "Transport from: {}",
    }
    for col, fmt in context_map.items():
        val = row.get(col)
        if pd.notna(val):
            parts.append(fmt.format(val))

    # Demographics (for context, not bias)
    age = row.get("age")
    sex = row.get("sex")
    if pd.notna(age) and pd.notna(sex):
        parts.append(f"{int(age)} year old {sex}")

    # Active medical history
    hx_cols = [c for c in row.index if c.startswith(HISTORY_PREFIX)]
    active_hx = [c.replace(HISTORY_PREFIX, "").replace("_", " ") for c in hx_cols if row.get(c) == 1]
    if active_hx:
        parts.append(f"History: {', '.join(active_hx)}")

    # Prior utilization
    prior_ed = row.get("num_prior_ed_visits_12m")
    prior_admit = row.get("num_prior_admissions_12m")
    if pd.notna(prior_ed) and prior_ed > 0:
        parts.append(f"{int(prior_ed)} ED visits in past year")
    if pd.notna(prior_admit) and prior_admit > 0:
        parts.append(f"{int(prior_admit)} admissions in past year")

    num_meds = row.get("num_active_medications")
    if pd.notna(num_meds) and num_meds > 0:
        parts.append(f"{int(num_meds)} active medications")

    return ". ".join(parts)


def build_payloads(df: pd.DataFrame) -> list[dict]:
    """Build Qdrant payload dicts from dataframe rows."""
    payload_cols = (
        ["patient_id", "chief_complaint_raw", "chief_complaint_system",
         "mental_status_triage", "disposition", "ed_los_hours",
         "triage_acuity"]
        + VITALS_COLS
        + CONTEXT_COLS
        + ["age", "age_group", "sex", "language", "insurance_type",
           "num_prior_ed_visits_12m", "num_prior_admissions_12m",
           "num_active_medications", "num_comorbidities"]
    )
    # Only include columns that exist in the dataframe
    payload_cols = [c for c in payload_cols if c in df.columns]

    payloads = []
    for _, row in df.iterrows():
        payload = {}
        for col in payload_cols:
            val = row[col]
            if pd.notna(val):
                payload[col] = val if not isinstance(val, float) or val != int(val) else int(val)
            else:
                payload[col] = None
        payloads.append(payload)
    return payloads
