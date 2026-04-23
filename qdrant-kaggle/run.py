"""Quick local run: load data, embed, index, predict, evaluate."""

import time

from sklearn.model_selection import train_test_split

from triagegeist.config import COLLECTION_NAME, K_NEIGHBORS
from triagegeist.data_loader import load_train
from triagegeist.embedder import create_collection, embed_and_upload, get_client
from triagegeist.evaluate import (
    bias_analysis,
    evaluate_predictions,
    plot_bias_summary,
    plot_confusion_matrix,
)
from triagegeist.predict import predict_acuity


def main():
    # Load
    print("loading data...")
    train = load_train()
    print(f"train shape: {train.shape}")

    # Split
    train_idx, val_idx = train_test_split(
        train.index, test_size=0.2, stratify=train["triage_acuity"], random_state=42
    )
    index_df = train.loc[train_idx].reset_index(drop=True)
    query_df = train.loc[val_idx].reset_index(drop=True)
    print(f"index: {len(index_df)}, query: {len(query_df)}")

    # Index
    client = get_client()
    create_collection(client)
    embed_and_upload(client, index_df)

    # Predict
    pred_df = predict_acuity(client, query_df)

    # Evaluate
    merged = query_df[["patient_id", "triage_acuity", "age_group", "sex", "language", "insurance_type"]].merge(
        pred_df, on="patient_id"
    )
    evaluate_predictions(merged["triage_acuity"], merged["predicted_acuity"])
    plot_confusion_matrix(merged["triage_acuity"], merged["predicted_acuity"])

    bias_results = bias_analysis(merged)
    plot_bias_summary(bias_results)

    print("\ndone. results saved to results/")


if __name__ == "__main__":
    main()
