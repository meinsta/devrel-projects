"""KNN triage prediction via Qdrant vector search."""

import time
from collections import Counter

import numpy as np
import pandas as pd
from qdrant_client import QdrantClient, models
from tqdm import tqdm

from triagegeist.config import COLLECTION_NAME, EMBEDDING_MODEL, K_NEIGHBORS
from triagegeist.data_loader import serialize_patient


def predict_acuity(
    client: QdrantClient,
    df: pd.DataFrame,
    k: int = K_NEIGHBORS,
    collection_name: str = COLLECTION_NAME,
    weighted: bool = True,
) -> pd.DataFrame:
    """Predict triage acuity for each patient using KNN over Qdrant.

    Args:
        client: Qdrant client
        df: DataFrame with patient features
        k: Number of neighbors to retrieve
        collection_name: Qdrant collection to search
        weighted: If True, weight votes by inverse distance

    Returns:
        DataFrame with patient_id, predicted_acuity, confidence, neighbor_acuities
    """
    from fastembed import TextEmbedding

    model = TextEmbedding(model_name=EMBEDDING_MODEL)

    print(f"predicting acuity for {len(df)} patients (k={k})...")
    texts = [serialize_patient(row) for _, row in df.iterrows()]

    results = []
    t0 = time.perf_counter()

    # Embed in batches, search one at a time
    embeddings = list(model.embed(texts, batch_size=128))

    for i, (embedding, (_, row)) in enumerate(
        tqdm(zip(embeddings, df.iterrows()), total=len(df), desc="predict")
    ):
        hits = client.query_points(
            collection_name=collection_name,
            query=embedding.tolist(),
            limit=k,
            with_payload=True,
            # Exclude self if this patient is in the collection
            query_filter=models.Filter(
                must_not=[
                    models.FieldCondition(
                        key="patient_id",
                        match=models.MatchValue(value=row["patient_id"]),
                    )
                ]
            ),
        )

        neighbor_acuities = []
        neighbor_scores = []
        for hit in hits.points:
            acuity = hit.payload.get("triage_acuity")
            if acuity is not None:
                neighbor_acuities.append(int(acuity))
                neighbor_scores.append(hit.score)

        if not neighbor_acuities:
            predicted = 3  # default to urgent
            confidence = 0.0
        elif weighted and neighbor_scores:
            # Inverse distance weighting (cosine similarity is already 0-1)
            weights = np.array(neighbor_scores)
            acuity_votes = {}
            for acuity, weight in zip(neighbor_acuities, weights):
                acuity_votes[acuity] = acuity_votes.get(acuity, 0) + weight
            predicted = max(acuity_votes, key=acuity_votes.get)
            total_weight = sum(acuity_votes.values())
            confidence = acuity_votes[predicted] / total_weight if total_weight > 0 else 0.0
        else:
            counts = Counter(neighbor_acuities)
            predicted = counts.most_common(1)[0][0]
            confidence = counts[predicted] / len(neighbor_acuities)

        results.append({
            "patient_id": row["patient_id"],
            "predicted_acuity": predicted,
            "confidence": round(confidence, 3),
            "neighbor_acuities": neighbor_acuities,
            "neighbor_scores": [round(s, 4) for s in neighbor_scores],
        })

    elapsed = time.perf_counter() - t0
    print(f"predicted {len(results)} patients in {elapsed:.1f}s")

    return pd.DataFrame(results)


def explain_prediction(
    client: QdrantClient,
    row: pd.Series,
    k: int = 5,
    collection_name: str = COLLECTION_NAME,
) -> list[dict]:
    """Return the K most similar cases for a single patient, for explainability."""
    from fastembed import TextEmbedding

    model = TextEmbedding(model_name=EMBEDDING_MODEL)
    text = serialize_patient(row)
    embedding = list(model.embed([text]))[0]

    hits = client.query_points(
        collection_name=collection_name,
        query=embedding.tolist(),
        limit=k,
        with_payload=True,
    )

    explanations = []
    for hit in hits.points:
        explanations.append({
            "patient_id": hit.payload.get("patient_id"),
            "score": round(hit.score, 4),
            "acuity": hit.payload.get("triage_acuity"),
            "chief_complaint": hit.payload.get("chief_complaint_raw"),
            "disposition": hit.payload.get("disposition"),
            "age_group": hit.payload.get("age_group"),
        })

    return explanations
