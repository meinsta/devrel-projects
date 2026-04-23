from __future__ import annotations

import difflib
import json
import os
import re
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from qdrant_client import QdrantClient, models


STAGE_KEYS = {
    1: "stage1_search",
    2: "stage2_article",
    3: "stage3_lookup",
    4: "stage4_compare",
}

# Canonical tool name mapping (old -> new)
TOOL_ALIASES = {
    "search": "search_corpus",
    "lookup": "text_search",
    "prune_documents": "prune_chunks",
}


def build_qdrant_client(timeout: int = 15) -> QdrantClient:
    load_dotenv()
    return QdrantClient(
        url=os.getenv("QDRANT_URL"),
        api_key=os.getenv("QDRANT_API_KEY"),
        timeout=timeout,
    )


def get_preindexed_collection_ids(timeout: int = 15, require_nonempty: bool = False) -> set[str]:
    qdrant = build_qdrant_client(timeout=timeout)
    collections = qdrant.get_collections().collections
    fr_collections = {col.name for col in collections if col.name.startswith("fr_")}

    if not require_nonempty:
        return fr_collections

    # Slower path: verify each collection has points (use for eval, not training)
    nonempty = set()
    for name in fr_collections:
        try:
            info = qdrant.get_collection(name)
            if info.points_count and info.points_count > 0:
                nonempty.add(name)
        except Exception:
            pass
    return nonempty


_STAGE_DATA: dict[str, list[int]] | None = None


def _get_stage_data() -> dict[str, list[int]]:
    global _STAGE_DATA
    if _STAGE_DATA is not None:
        return _STAGE_DATA

    stage_path = Path(__file__).with_name("frames_stages.json")
    if stage_path.exists():
        _STAGE_DATA = json.loads(stage_path.read_text(encoding="utf-8"))
        return _STAGE_DATA

    # Fallback: inline data when JSON file is not installed alongside the module
    _STAGE_DATA = {
        "stage1_search": [39, 76, 128, 173, 256, 274, 289, 307, 315, 413, 415, 494, 588, 618, 640, 677, 809],
        "stage2_article": [0, 4, 7, 10, 12, 13, 17, 31, 37, 38, 41, 42, 44, 49, 50, 51, 53, 55, 56, 57, 58, 61, 63, 66, 68, 71, 72, 73, 80, 88, 91, 92, 94, 96, 101, 110, 113, 116, 119, 121, 126, 127, 129, 130, 131, 134, 135, 138, 139, 142, 144, 147, 148, 150, 152, 154, 155, 156, 162, 164, 166, 167, 169, 170, 172, 174, 178, 180, 181, 182, 185, 187, 188, 189, 190, 191, 197, 198, 199, 200, 202, 204, 208, 210, 212, 213, 215, 220, 225, 228, 233, 236, 237, 238, 240, 245, 249, 252, 257, 259, 260, 261, 263, 264, 273, 275, 276, 277, 278, 280, 282, 283, 286, 291, 293, 296, 299, 301, 308, 311, 318, 326, 329, 332, 337, 338, 339, 341, 345, 346, 349, 351, 356, 359, 360, 365, 366, 368, 376, 377, 380, 382, 383, 384, 387, 391, 398, 399, 404, 406, 409, 412, 417, 418, 419, 420, 421, 424, 428, 430, 431, 432, 436, 437, 440, 441, 443, 446, 448, 452, 454, 458, 464, 466, 468, 470, 472, 473, 475, 484, 488, 491, 492, 493, 495, 496, 497, 499, 500, 504, 506, 509, 512, 514, 515, 516, 519, 522, 525, 526, 530, 532, 535, 536, 537, 544, 546, 547, 550, 551, 552, 553, 556, 558, 559, 560, 561, 565, 566, 571, 572, 573, 581, 582, 583, 585, 590, 593, 594, 600, 601, 602, 603, 604, 607, 609, 610, 611, 612, 617, 621, 623, 624, 628, 631, 634, 641, 644, 652, 653, 655, 658, 659, 660, 661, 663, 665, 666, 667, 669, 670, 671, 674, 679, 681, 683, 687, 688, 693, 695, 696, 697, 698, 699, 704, 707, 709, 710, 711, 715, 719, 720, 721, 722, 723, 724, 725, 728, 729, 732, 733, 734, 735, 736, 739, 747, 751, 756, 757, 759, 760, 762, 763, 765, 769, 770, 774, 776, 778, 780, 781, 788, 789, 792, 793, 794, 795, 798, 801, 803, 810, 812, 813, 814, 816, 817, 822],
        "stage3_lookup": [1, 2, 3, 5, 6, 8, 9, 14, 16, 18, 20, 21, 22, 24, 25, 26, 27, 28, 29, 30, 32, 33, 34, 35, 36, 43, 45, 52, 59, 60, 62, 64, 65, 67, 69, 70, 74, 75, 77, 78, 79, 81, 82, 83, 84, 85, 89, 90, 93, 95, 99, 100, 103, 104, 105, 106, 107, 108, 109, 111, 114, 117, 118, 122, 124, 125, 132, 133, 136, 137, 140, 141, 143, 149, 151, 157, 158, 159, 160, 161, 163, 168, 171, 175, 176, 177, 179, 183, 184, 186, 192, 193, 196, 203, 205, 206, 207, 209, 211, 214, 216, 217, 218, 219, 221, 223, 224, 226, 227, 232, 234, 239, 242, 243, 244, 246, 247, 248, 250, 253, 254, 255, 258, 265, 266, 267, 268, 269, 270, 272, 279, 284, 285, 287, 294, 295, 297, 298, 300, 302, 303, 304, 305, 309, 310, 312, 313, 314, 316, 317, 319, 320, 321, 323, 324, 328, 330, 331, 333, 334, 335, 342, 343, 344, 347, 348, 350, 352, 353, 354, 355, 357, 358, 361, 362, 363, 367, 369, 370, 371, 374, 378, 379, 381, 385, 388, 389, 390, 392, 393, 394, 395, 401, 402, 403, 405, 407, 408, 410, 411, 414, 422, 423, 426, 427, 429, 434, 435, 442, 444, 445, 447, 449, 451, 453, 455, 456, 457, 459, 460, 462, 463, 465, 467, 469, 471, 474, 476, 477, 478, 479, 481, 482, 483, 486, 487, 489, 490, 498, 501, 502, 503, 505, 507, 508, 511, 513, 517, 518, 520, 521, 523, 524, 527, 528, 529, 533, 534, 538, 539, 542, 545, 548, 549, 554, 555, 557, 562, 563, 564, 568, 570, 574, 575, 576, 577, 578, 579, 580, 586, 587, 589, 595, 596, 598, 599, 605, 606, 608, 613, 615, 616, 620, 622, 625, 626, 629, 630, 632, 633, 635, 636, 637, 638, 639, 642, 643, 645, 646, 647, 648, 649, 650, 654, 656, 662, 664, 672, 673, 675, 676, 680, 682, 684, 686, 689, 691, 692, 694, 700, 701, 702, 703, 705, 708, 712, 713, 714, 717, 718, 726, 727, 731, 737, 740, 743, 744, 745, 746, 748, 750, 752, 753, 754, 755, 758, 761, 766, 768, 771, 773, 775, 777, 779, 782, 783, 784, 785, 787, 790, 796, 797, 799, 802, 804, 806, 807, 808, 811, 818, 819, 820, 821],
        "stage4_compare": [11, 15, 19, 23, 40, 46, 47, 48, 54, 86, 87, 97, 98, 102, 112, 115, 120, 123, 145, 146, 153, 165, 194, 195, 201, 222, 229, 230, 231, 235, 241, 251, 262, 271, 281, 288, 290, 292, 306, 322, 325, 327, 336, 340, 364, 372, 373, 375, 386, 396, 397, 400, 416, 425, 433, 438, 439, 450, 461, 480, 485, 510, 531, 540, 541, 543, 567, 569, 584, 591, 592, 597, 614, 619, 627, 651, 657, 668, 678, 685, 690, 706, 716, 730, 738, 741, 742, 749, 764, 767, 772, 786, 791, 800, 805, 815, 823],
    }
    return _STAGE_DATA


def load_stage_indices(stage: int) -> list[int]:
    stage_key = STAGE_KEYS.get(int(stage))
    if stage_key is None:
        raise ValueError(f"Unknown curriculum stage: {stage}")

    stage_map = _get_stage_data()
    indices = stage_map.get(stage_key)
    if not isinstance(indices, list) or not all(isinstance(index, int) for index in indices):
        raise ValueError(f"Invalid stage definition for {stage_key}")

    return indices


def extract_user_question(prompt: Any) -> str:
    if not isinstance(prompt, list):
        return ""

    for message in prompt:
        if isinstance(message, dict):
            role = message.get("role", "")
            content = message.get("content", "")
        else:
            role = getattr(message, "role", "")
            content = getattr(message, "content", "")

        if role == "user" and isinstance(content, str) and content:
            return content

    return ""


def make_doc_id(index: int) -> str:
    return f"d{index:03d}"


def make_chunk_id(point_id: int) -> str:
    return f"c{point_id:04d}"


def parse_doc_ids(raw: str) -> list[str]:
    return [part.lower() for part in re.split(r"[\s,]+", raw.strip()) if part]


class FramesQdrantMixin:
    _title_cache: dict[str, list[str]]
    _doc_catalog_cache: dict[str, list[tuple[str, str]]]

    def _get_qdrant(self):
        raise NotImplementedError

    def _embed(self, text: str) -> list[float]:
        raise NotImplementedError

    def _get_collection_titles(self, collection_id: str) -> list[str]:
        if collection_id in self._title_cache:
            return self._title_cache[collection_id]

        titles: set[str] = set()
        offset = None
        while True:
            points, offset = self._get_qdrant().scroll(
                collection_name=collection_id,
                limit=256,
                offset=offset,
                with_payload=["title"],
                with_vectors=False,
            )
            for point in points:
                payload = point.payload or {}
                title = payload.get("title")
                if isinstance(title, str) and title:
                    titles.add(title)
            if offset is None:
                break

        sorted_titles = sorted(titles)
        self._title_cache[collection_id] = sorted_titles
        return sorted_titles

    def _get_doc_catalog(self, collection_id: str) -> list[tuple[str, str]]:
        if collection_id in self._doc_catalog_cache:
            return self._doc_catalog_cache[collection_id]

        catalog = [
            (make_doc_id(index), title)
            for index, title in enumerate(self._get_collection_titles(collection_id), start=1)
        ]
        self._doc_catalog_cache[collection_id] = catalog
        return catalog

    def _doc_id_for_title(self, collection_id: str, title: str) -> str | None:
        for doc_id, candidate_title in self._get_doc_catalog(collection_id):
            if candidate_title == title:
                return doc_id
        return None

    def _resolve_doc_id(self, collection_id: str, requested_doc_id: str) -> tuple[str | None, str | None, list[str]]:
        requested = requested_doc_id.strip().lower()
        if not requested:
            return None, None, []

        mapping = {
            doc_id.lower(): (doc_id, title) for doc_id, title in self._get_doc_catalog(collection_id)
        }
        match = mapping.get(requested)
        if match is not None:
            doc_id, title = match
            return doc_id, title, []

        suggestions = difflib.get_close_matches(requested, list(mapping), n=5, cutoff=0.0)
        return None, None, suggestions

    # ------------------------------------------------------------------
    # Novelty pressure: track seen chunk IDs per question
    # ------------------------------------------------------------------

    def _get_seen_chunk_ids(self, state: dict | None) -> set[str]:
        if state is None:
            return set()
        return set(state.get("seen_chunk_ids", []))

    def _record_seen_chunks(self, state: dict | None, points: list[Any]) -> None:
        """Record chunk IDs and doc IDs from search results into state."""
        if state is None:
            return
        seen_chunks = set(state.get("seen_chunk_ids", []))
        seen_docs = set(state.get("seen_doc_ids", []))
        collection_id = state.get("collection_id", "")
        for point in points:
            chunk_id = make_chunk_id(getattr(point, "id", 0))
            seen_chunks.add(chunk_id)
            # Track doc-level visibility for trajectory recall
            payload = getattr(point, "payload", None) or {}
            title = payload.get("title")
            if isinstance(title, str) and title and collection_id:
                doc_id = self._doc_id_for_title(collection_id, title)
                if doc_id:
                    seen_docs.add(doc_id)
        state["seen_chunk_ids"] = sorted(seen_chunks)
        state["seen_doc_ids"] = sorted(seen_docs)

    def _filter_seen_chunks(self, points: list[Any], seen: set[str]) -> list[Any]:
        """Remove already-seen chunks from search results (novelty pressure)."""
        if not seen:
            return points
        return [p for p in points if make_chunk_id(getattr(p, "id", 0)) not in seen]

    # ------------------------------------------------------------------
    # Qdrant search primitives
    # ------------------------------------------------------------------

    def _query_collection(
        self,
        collection_id: str,
        query: str,
        *,
        limit: int,
        title: str | None = None,
    ):
        use_weighted_rrf = getattr(self, "_use_weighted_rrf", False)
        bm25_prefetch = models.Prefetch(
            query=models.Document(text=query, model="Qdrant/bm25"),
            using="bm25",
            limit=10,
        )
        dense_prefetch = models.Prefetch(query=self._embed(query), using="dense", limit=10)

        if use_weighted_rrf:
            fusion_query = models.RrfQuery(
                rrf=models.Rrf(weights=[0.5, 1.5])  # [bm25_weight, dense_weight]
            )
        else:
            fusion_query = models.FusionQuery(fusion=models.Fusion.RRF)

        kwargs = {
            "collection_name": collection_id,
            "prefetch": [bm25_prefetch, dense_prefetch],
            "query": fusion_query,
            "limit": limit,
            "with_payload": True,
        }
        if title is not None:
            kwargs["query_filter"] = models.Filter(
                must=[models.FieldCondition(key="title", match=models.MatchValue(value=title))]
            )
        return self._get_qdrant().query_points(**kwargs)

    def _query_documents(
        self,
        collection_id: str,
        query: str,
        doc_ids: list[str],
        *,
        per_doc_limit: int = 3,
        overall_limit: int = 6,
    ) -> list[Any]:
        points: list[Any] = []
        seen_snippets: set[tuple[str, str]] = set()

        for doc_id in doc_ids:
            _, title, _ = self._resolve_doc_id(collection_id, doc_id)
            if title is None:
                continue
            results = self._query_collection(collection_id, query, limit=per_doc_limit, title=title)
            for point in results.points:
                payload = point.payload or {}
                point_title = payload.get("title")
                point_text = payload.get("text")
                if not isinstance(point_title, str) or not isinstance(point_text, str):
                    continue
                key = (point_title, point_text)
                if key in seen_snippets:
                    continue
                seen_snippets.add(key)
                points.append(point)

        points.sort(key=lambda point: getattr(point, "score", 0.0), reverse=True)
        return points[:overall_limit]

    def _scroll_document(self, collection_id: str, title: str, *, limit: int = 4) -> list[Any]:
        points, _ = self._get_qdrant().scroll(
            collection_name=collection_id,
            scroll_filter=models.Filter(
                must=[models.FieldCondition(key="title", match=models.MatchValue(value=title))]
            ),
            limit=limit,
            with_payload=True,
        )
        return points

    def _lookup_points(
        self,
        collection_id: str,
        phrase: str,
        *,
        titles: list[str] | None = None,
        limit: int = 5,
    ) -> list[Any]:
        qdrant = self._get_qdrant()
        if not titles:
            points, _ = qdrant.scroll(
                collection_name=collection_id,
                scroll_filter=models.Filter(
                    must=[models.FieldCondition(key="text", match=models.MatchText(text=phrase))]
                ),
                limit=limit,
                with_payload=True,
            )
            return points

        points: list[Any] = []
        seen_snippets: set[tuple[str, str]] = set()
        for title in titles:
            title_points, _ = qdrant.scroll(
                collection_name=collection_id,
                scroll_filter=models.Filter(
                    must=[
                        models.FieldCondition(key="title", match=models.MatchValue(value=title)),
                        models.FieldCondition(key="text", match=models.MatchText(text=phrase)),
                    ]
                ),
                limit=limit,
                with_payload=True,
            )
            for point in title_points:
                payload = point.payload or {}
                point_title = payload.get("title")
                point_text = payload.get("text")
                if not isinstance(point_title, str) or not isinstance(point_text, str):
                    continue
                key = (point_title, point_text)
                if key in seen_snippets:
                    continue
                seen_snippets.add(key)
                points.append(point)
                if len(points) >= limit:
                    return points
        return points

    # ------------------------------------------------------------------
    # Formatting helpers
    # ------------------------------------------------------------------

    def _format_catalog(self, collection_id: str, *, limit: int = 12) -> str:
        catalog = self._get_doc_catalog(collection_id)
        if not catalog:
            return "No documents are available in this collection."

        parts = ["Available documents:"]
        for doc_id, title in catalog[:limit]:
            parts.append(f"{doc_id} | {title}")
        if len(catalog) > limit:
            parts.append(f"... and {len(catalog) - limit} more.")
        return "\n".join(parts)

    def _format_search_results(
        self,
        collection_id: str,
        points: list[Any],
        *,
        focused: bool = False,
    ) -> str:
        if not points:
            return "No results."

        ordered_docs: list[tuple[str, str, list[str]]] = []
        doc_index: dict[str, int] = {}
        for point in points:
            payload = point.payload or {}
            title = payload.get("title")
            text = payload.get("text")
            if not isinstance(title, str) or not isinstance(text, str):
                continue
            doc_id = self._doc_id_for_title(collection_id, title)
            if doc_id is None:
                continue
            if doc_id not in doc_index:
                doc_index[doc_id] = len(ordered_docs)
                ordered_docs.append((doc_id, title, []))
            _, existing_title, snippets = ordered_docs[doc_index[doc_id]]
            if text not in snippets and len(snippets) < 2:
                snippets.append(text)
            ordered_docs[doc_index[doc_id]] = (doc_id, existing_title, snippets)

        if not ordered_docs:
            return "No results."

        header = "Candidate documents within the current focus:" if focused else "Candidate documents:"
        parts = [header]
        for doc_id, title, snippets in ordered_docs[:5]:
            parts.append(f"{doc_id} | {title}")
            for snippet in snippets:
                parts.append(f"Snippet: {snippet}")
        parts.append("Use read_document(doc_id=...) to inspect one document in detail.")
        return "\n".join(parts)

    def _format_document_result(
        self,
        collection_id: str,
        doc_id: str,
        title: str,
        points: list[Any],
        *,
        query: str,
        fallback_open: bool = False,
    ) -> str:
        if not points:
            return f"No passages found in {doc_id} | {title}."

        if query and not fallback_open:
            header = f"Document {doc_id} | {title}\nRelevant passages for query: {query}"
        elif query and fallback_open:
            header = (
                f"Document {doc_id} | {title}\n"
                f"No direct matches for query: {query}\n"
                "Showing opening passages instead."
            )
        else:
            header = f"Document {doc_id} | {title}\nOpening passages:"

        parts = [header]
        for point in points[:4]:
            payload = point.payload or {}
            text = payload.get("text")
            if isinstance(text, str) and text:
                parts.append(text)
        return "\n\n".join(parts)

    def _format_lookup_results(self, collection_id: str, phrase: str, points: list[Any]) -> str:
        if not points:
            return f"No match for '{phrase}'."

        parts = [f"Matches for '{phrase}':"]
        for point in points[:5]:
            payload = point.payload or {}
            title = payload.get("title")
            text = payload.get("text")
            if not isinstance(title, str) or not isinstance(text, str):
                continue
            doc_id = self._doc_id_for_title(collection_id, title) or "unknown"
            parts.append(f"{doc_id} | {title}")
            parts.append(text)
        return "\n\n".join(parts)

    # ------------------------------------------------------------------
    # Tool dispatch
    # ------------------------------------------------------------------

    def run_tool(self, tool_name: str, tool_args: dict[str, Any]) -> str:
        # Accept both old and new tool names
        canonical = TOOL_ALIASES.get(tool_name, tool_name)

        state = getattr(self, "_current_state", None)
        collection_id = state.get("collection_id", "fr_tmp") if state else "fr_tmp"
        focus_doc_ids = list(state.get("focus_doc_ids", [])) if state else []
        seen_chunks = self._get_seen_chunk_ids(state)

        if canonical == "search_corpus":
            query = str(tool_args.get("query", "")).strip()
            if not query:
                return "Empty search query."
            if focus_doc_ids:
                points = self._query_documents(collection_id, query, focus_doc_ids)
                # Novelty: filter seen chunks from search results
                points = self._filter_seen_chunks(points, seen_chunks)
                self._record_seen_chunks(state, points)
                return self._format_search_results(collection_id, points, focused=True)
            results = self._query_collection(collection_id, query, limit=6)
            points = list(results.points)
            # Novelty: filter seen chunks from search results
            points = self._filter_seen_chunks(points, seen_chunks)
            self._record_seen_chunks(state, points)
            return self._format_search_results(collection_id, points)

        if canonical == "read_document":
            # read_document is exempt from novelty exclusion
            requested_doc_id = str(tool_args.get("doc_id", "")).strip()
            query = str(tool_args.get("query", "")).strip()
            doc_id, title, suggestions = self._resolve_doc_id(collection_id, requested_doc_id)
            if doc_id is None or title is None:
                parts = [f"Unknown doc_id '{requested_doc_id}'."]
                if suggestions:
                    parts.append("Closest doc_ids: " + ", ".join(suggestions))
                parts.append(self._format_catalog(collection_id))
                parts.append("Search first to discover promising doc_ids.")
                return "\n\n".join(parts)

            if query:
                points = list(self._query_collection(collection_id, query, limit=4, title=title).points)
                if points:
                    # Record seen but do not filter (read_document is exempt)
                    self._record_seen_chunks(state, points)
                    return self._format_document_result(collection_id, doc_id, title, points, query=query)
                opening_points = self._scroll_document(collection_id, title, limit=4)
                self._record_seen_chunks(state, opening_points)
                return self._format_document_result(
                    collection_id,
                    doc_id,
                    title,
                    opening_points,
                    query=query,
                    fallback_open=True,
                )

            points = self._scroll_document(collection_id, title, limit=4)
            self._record_seen_chunks(state, points)
            return self._format_document_result(collection_id, doc_id, title, points, query="")

        if canonical == "text_search":
            phrase = str(tool_args.get("phrase", "")).strip()
            requested_doc_id = str(tool_args.get("doc_id", "")).strip()
            if not phrase:
                return "Empty lookup phrase."

            titles: list[str] | None = None
            if requested_doc_id:
                doc_id, title, suggestions = self._resolve_doc_id(collection_id, requested_doc_id)
                if doc_id is None or title is None:
                    parts = [f"Unknown doc_id '{requested_doc_id}'."]
                    if suggestions:
                        parts.append("Closest doc_ids: " + ", ".join(suggestions))
                    parts.append(self._format_catalog(collection_id))
                    return "\n\n".join(parts)
                titles = [title]
            elif focus_doc_ids:
                titles = []
                for doc_id in focus_doc_ids:
                    _, title, _ = self._resolve_doc_id(collection_id, doc_id)
                    if title is not None:
                        titles.append(title)

            points = self._lookup_points(collection_id, phrase, titles=titles, limit=5)
            # Novelty: filter seen chunks
            points = self._filter_seen_chunks(points, seen_chunks)
            self._record_seen_chunks(state, points)
            return self._format_lookup_results(collection_id, phrase, points)

        if canonical == "search_similar":
            requested_doc_id = str(tool_args.get("doc_id", "")).strip()
            if not requested_doc_id:
                return "Missing doc_id. Provide a doc_id to find similar documents."
            doc_id, title, suggestions = self._resolve_doc_id(collection_id, requested_doc_id)
            if doc_id is None or title is None:
                parts = [f"Unknown doc_id '{requested_doc_id}'."]
                if suggestions:
                    parts.append("Closest doc_ids: " + ", ".join(suggestions))
                return "\n".join(parts)
            # Get a point from this document to use as positive example
            ref_points = self._scroll_document(collection_id, title, limit=1)
            if not ref_points:
                return f"No content found for {doc_id}."
            positive_ids = [ref_points[0].id]
            try:
                results = self._get_qdrant().query_points(
                    collection_name=collection_id,
                    query=models.RecommendQuery(
                        recommend=models.RecommendInput(positive=positive_ids)
                    ),
                    using="dense",
                    limit=6,
                    with_payload=True,
                )
                points = list(results.points)
                points = self._filter_seen_chunks(points, seen_chunks)
                self._record_seen_chunks(state, points)
                return self._format_search_results(collection_id, points)
            except Exception as e:
                return f"Search similar failed: {e}"

        if canonical == "search_grouped":
            query = str(tool_args.get("query", "")).strip()
            if not query:
                return "Empty search query."
            try:
                grouped = self._get_qdrant().query_points_groups(
                    collection_name=collection_id,
                    prefetch=[
                        models.Prefetch(
                            query=models.Document(text=query, model="Qdrant/bm25"),
                            using="bm25",
                            limit=10,
                        ),
                        models.Prefetch(query=self._embed(query), using="dense", limit=10),
                    ],
                    query=models.FusionQuery(fusion=models.Fusion.RRF),
                    group_by="title",
                    group_size=2,
                    limit=6,
                    with_payload=True,
                )
                # Flatten groups into points
                points = []
                for group in getattr(grouped, "groups", []):
                    for hit in getattr(group, "hits", []):
                        points.append(hit)
                points = self._filter_seen_chunks(points, seen_chunks)
                self._record_seen_chunks(state, points)
                return self._format_search_results(collection_id, points)
            except Exception as e:
                return f"Grouped search failed: {e}"

        if canonical == "prune_chunks":
            if state is None:
                return "Tool error: missing environment state."

            raw_doc_ids = str(tool_args.get("doc_ids", "")).strip()
            if raw_doc_ids.lower() in {"", "*", "all", "clear", "none", "reset"}:
                state["focus_doc_ids"] = []
                return "Cleared document focus. Future search_corpus and text_search calls will use the full collection."

            requested_doc_ids = parse_doc_ids(raw_doc_ids)
            if not requested_doc_ids:
                state["focus_doc_ids"] = []
                return "Cleared document focus. Future search_corpus and text_search calls will use the full collection."

            resolved_doc_ids: list[str] = []
            unknown_doc_ids: list[str] = []
            labels: list[str] = []
            for requested_doc_id in requested_doc_ids:
                doc_id, title, _ = self._resolve_doc_id(collection_id, requested_doc_id)
                if doc_id is None or title is None:
                    unknown_doc_ids.append(requested_doc_id)
                    continue
                if doc_id not in resolved_doc_ids:
                    resolved_doc_ids.append(doc_id)
                    labels.append(f"{doc_id} | {title}")

            if not resolved_doc_ids:
                parts = [f"Could not match any doc_ids from '{raw_doc_ids}'."]
                parts.append(self._format_catalog(collection_id))
                return "\n\n".join(parts)

            state["focus_doc_ids"] = resolved_doc_ids
            parts = ["Focused future search_corpus and text_search on:"]
            parts.extend(labels)
            if unknown_doc_ids:
                parts.append("Unrecognized doc_ids: " + ", ".join(unknown_doc_ids))
            parts.append("Call prune_chunks(doc_ids='all') to clear the focus.")
            return "\n".join(parts)

        return f"Unknown tool: {tool_name}"
