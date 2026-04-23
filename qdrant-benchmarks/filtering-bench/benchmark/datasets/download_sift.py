from __future__ import annotations

import logging
import tarfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import numpy as np

log = logging.getLogger(__name__)

HDF5_URL = "http://ann-benchmarks.com/sift-128-euclidean.hdf5"
HDF5_PATH = Path(__file__).parent / "sift-128-euclidean.hdf5"

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
        base = np.array(f["train"], dtype=np.float32)
        queries = np.array(f["test"], dtype=np.float32)
        gt = np.array(f["neighbors"], dtype=np.int32)

    log.info(f"Loaded: {base.shape[0]} base, {queries.shape[0]} queries, {gt.shape[0]} gt")
    return SIFTDataset(base_vectors=base, query_vectors=queries, ground_truth=gt)


def read_fvecs(path: Path) -> np.ndarray:
    data = np.fromfile(str(path), dtype=np.int32)
    dim = data[0]
    return data.reshape(-1, dim + 1)[:, 1:].view(np.float32).copy()


def read_ivecs(path: Path) -> np.ndarray:
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
    log.info(f"Loaded: {base.shape[0]} base, {queries.shape[0]} queries, {gt.shape[0]} gt")
    return SIFTDataset(base_vectors=base, query_vectors=queries, ground_truth=gt)


def load_sift() -> SIFTDataset:
    try:
        dataset = _load_from_hdf5()
    except Exception as e:
        log.warning(f"HDF5 load failed ({e}), falling back to fvecs...")
        dataset = _load_from_fvecs()

    assert dataset.base_vectors.shape == (1_000_000, 128)
    assert dataset.query_vectors.shape == (10_000, 128)
    assert dataset.ground_truth.shape[0] == 10_000
    return dataset


def compute_recall(
    result_ids: list[int],
    ground_truth_ids: np.ndarray,
    top_k: int = 10,
) -> float:
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
