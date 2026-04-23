from __future__ import annotations

import logging
import tarfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import numpy as np

log = logging.getLogger(__name__)

# Fast HDF5 download from ann-benchmarks
HDF5_URL = "http://ann-benchmarks.com/sift-128-euclidean.hdf5"
HDF5_PATH = Path(__file__).parent / "sift-128-euclidean.hdf5"

# Fallback: original fvecs from IRISA
SIFT_FTP_URL = "ftp://ftp.irisa.fr/local/texmex/corpus/sift.tar.gz"
CACHE_DIR = Path(__file__).parent / "sift"
ARCHIVE_PATH = Path(__file__).parent / "sift.tar.gz"


@dataclass
class SIFTDataset:
    base_vectors: np.ndarray  # (1_000_000, 128) float32
    query_vectors: np.ndarray  # (10_000, 128) float32
    ground_truth: np.ndarray  # (10_000, 100) int32


def _download_with_progress(url: str, dest: Path) -> None:
    log.info(f"Downloading {url} -> {dest}")

    def _reporthook(block_num: int, block_size: int, total_size: int) -> None:
        downloaded = block_num * block_size
        if total_size > 0 and block_num % 500 == 0:
            pct = downloaded * 100 / total_size
            log.info(f"  {pct:.0f}% ({downloaded / 1e6:.1f}MB / {total_size / 1e6:.1f}MB)")

    urllib.request.urlretrieve(url, str(dest), reporthook=_reporthook)
    log.info(f"  Download complete: {dest.stat().st_size / 1e6:.1f}MB")


def _load_from_hdf5() -> SIFTDataset:
    import h5py

    if not HDF5_PATH.exists():
        HDF5_PATH.parent.mkdir(parents=True, exist_ok=True)
        _download_with_progress(HDF5_URL, HDF5_PATH)

    log.info(f"Loading SIFT-1M from {HDF5_PATH}...")
    with h5py.File(str(HDF5_PATH), "r") as f:
        # ann-benchmarks format: "train" = base vectors, "test" = queries
        # "neighbors" = ground truth indices, "distances" = ground truth distances
        base = np.array(f["train"], dtype=np.float32)
        queries = np.array(f["test"], dtype=np.float32)
        gt = np.array(f["neighbors"], dtype=np.int32)

    log.info(
        f"Loaded: {base.shape[0]} base vectors, "
        f"{queries.shape[0]} queries, "
        f"{gt.shape[0]} ground truth entries"
    )

    return SIFTDataset(base_vectors=base, query_vectors=queries, ground_truth=gt)


def read_fvecs(path: Path) -> np.ndarray:
    """Read .fvecs binary format. Returns (N, dim) float32 array."""
    data = np.fromfile(str(path), dtype=np.int32)
    dim = data[0]
    return data.reshape(-1, dim + 1)[:, 1:].view(np.float32).copy()


def read_ivecs(path: Path) -> np.ndarray:
    """Read .ivecs binary format. Returns (N, k) int32 array."""
    data = np.fromfile(str(path), dtype=np.int32)
    dim = data[0]
    return data.reshape(-1, dim + 1)[:, 1:].copy()


def _load_from_fvecs() -> SIFTDataset:
    base_path = CACHE_DIR / "sift_base.fvecs"

    if not base_path.exists():
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        if not ARCHIVE_PATH.exists():
            _download_with_progress(SIFT_FTP_URL, ARCHIVE_PATH)

        log.info(f"Extracting {ARCHIVE_PATH}...")
        with tarfile.open(str(ARCHIVE_PATH), "r:gz") as tar:
            for member in tar.getmembers():
                if member.isfile():
                    member.name = Path(member.name).name
                    tar.extract(member, path=str(CACHE_DIR))

    log.info("Loading SIFT-1M from fvecs...")
    base = read_fvecs(CACHE_DIR / "sift_base.fvecs")
    queries = read_fvecs(CACHE_DIR / "sift_query.fvecs")
    gt = read_ivecs(CACHE_DIR / "sift_groundtruth.ivecs")

    log.info(
        f"Loaded: {base.shape[0]} base vectors, "
        f"{queries.shape[0]} queries, "
        f"{gt.shape[0]} ground truth entries"
    )

    return SIFTDataset(base_vectors=base, query_vectors=queries, ground_truth=gt)


def load_sift() -> SIFTDataset:
    """Download (if needed) and load SIFT-1M into memory. Tries HDF5 first."""
    try:
        dataset = _load_from_hdf5()
    except Exception as e:
        log.warning(f"HDF5 load failed ({e}), falling back to fvecs...")
        dataset = _load_from_fvecs()

    assert dataset.base_vectors.shape == (1_000_000, 128), (
        f"Unexpected base shape: {dataset.base_vectors.shape}"
    )
    assert dataset.query_vectors.shape == (10_000, 128), (
        f"Unexpected query shape: {dataset.query_vectors.shape}"
    )
    assert dataset.ground_truth.shape[0] == 10_000, (
        f"Unexpected ground truth rows: {dataset.ground_truth.shape[0]}"
    )

    return dataset


def compute_recall(
    result_ids: list[int],
    ground_truth_ids: np.ndarray,
    top_k: int = 10,
) -> float:
    """Compute recall@k: fraction of top-k ground truth found in results."""
    gt_set = set(ground_truth_ids[:top_k].tolist())
    result_set = set(result_ids[:top_k])
    if not gt_set:
        return 0.0
    return len(gt_set & result_set) / len(gt_set)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    dataset = load_sift()
    print(f"Base: {dataset.base_vectors.shape}")
    print(f"Queries: {dataset.query_vectors.shape}")
    print(f"Ground truth: {dataset.ground_truth.shape}")
