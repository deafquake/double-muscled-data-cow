import os
import json
from typing import Optional, Dict, Any, List, Tuple

from langchain_community.document_compressors import FlashrankRerank
from langchain_milvus import BM25BuiltInFunction, Milvus
from langchain_core.documents import Document
from langchain_classic.retrievers.contextual_compression import ContextualCompressionRetriever

from .lm_studio_embeddings import LMStudioEmbeddings
from ...utils.logger import get_logger
from ...config.config import MILVUS_HOST, MILVUS_PORT

logger = get_logger(__name__)


class VideoSegmentsConnector:
    """
    Milvus connector for the video_segments collection.

    Stores one entry per video segment. The segment summary is embedded for
    semantic search; person names and topic keywords are appended to bm25_text
    for exact-match retrieval.

    Dynamic metadata fields stored per entry:
        video_id        — video name / identifier
        segment_number  — 0-based segment index
        timestamp       — ISO datetime the video was recorded
        people_present  — JSON-encoded list of person names in this segment
        topics          — JSON-encoded list of topic strings
        tone            — conversational tone (e.g. "formal", "friendly")
        calendar_events — JSON-encoded list of event dicts from this segment
        decisions       — JSON-encoded list of decision strings
        kind            — always "segment"
    """

    _instance = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        embeddings=None,
        uri: Optional[str] = None,
        collection_name: str = "video_segments",
        host: Optional[str] = None,
        port: Optional[int] = None,
    ):
        if VideoSegmentsConnector._initialized:
            return

        if embeddings is None:
            embeddings = LMStudioEmbeddings()

        self._embeddings = embeddings
        self._collection_name = collection_name
        self._builtin_function = BM25BuiltInFunction(
            input_field_names="bm25_text",
            output_field_names="sparse",
        )

        try:
            connection_args = self._build_connection_args(uri, host, port)
            logger.info(f"VideoSegmentsConnector: connecting to Milvus — {connection_args}")

            self._vector_store = Milvus(
                embedding_function=embeddings,
                collection_name=collection_name,
                connection_args=connection_args,
                index_params=[
                    {"index_type": "FLAT", "metric_type": "COSINE", "params": {}},
                    {"index_type": "SPARSE_INVERTED_INDEX", "metric_type": "BM25", "params": {}},
                ],
                builtin_function=self._builtin_function,
                vector_field=["dense", "sparse"],
                text_field="bm25_text",
                enable_dynamic_field=True,
            )
            self._compressor = FlashrankRerank()

            logger.info(f"VideoSegmentsConnector initialised — collection: {collection_name}")
            VideoSegmentsConnector._initialized = True
        except Exception as e:
            logger.error(f"Failed to initialise VideoSegmentsConnector: {e}", exc_info=True)
            raise

    # ------------------------------------------------------------------
    # Connection helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_connection_args(
        uri: Optional[str],
        host: Optional[str],
        port: Optional[int],
    ) -> Dict[str, Any]:
        if uri:
            return {"uri": uri}
        h = host or MILVUS_HOST
        p = port or MILVUS_PORT
        if h and p:
            return {"uri": f"http://{h}:{p}"}
        return {"uri": os.getenv("MILVUS_DB_PATH", "./milvus_data.db")}

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def store_segments(self, metadata: dict) -> List[str]:
        """
        Store all segments of a video as individual Milvus documents.

        Parameters
        ----------
        metadata : dict
            The dict returned by Orchestrator.analyse_video(). Expected keys:
              - video     : str         — video identifier
              - timestamp : str         — ISO datetime the video was recorded
              - segments  : list[dict]  — each dict is one segment entry

            Each segment dict is expected to have:
              - segment_number  : int
              - summary         : str
              - people_present  : list[str]
              - topics          : list[str]
              - tone            : str
              - calendar_events : list[dict]
              - martins_decisions : list[str]

        Returns
        -------
        List of Milvus-assigned primary-key strings (one per segment).
        """
        video_id = metadata.get("video", "")
        timestamp = metadata.get("timestamp", "")
        documents = []

        for seg in metadata.get("segments", []):
            summary = seg.get("summary", "")
            people_present = seg.get("people_present", [])
            topics = seg.get("topics", [])

            # Dense vector captures the prose meaning of the segment.
            # BM25 additionally indexes person names and topic keywords.
            bm25_text = " ".join(filter(None, [
                summary,
                " ".join(people_present),
                " ".join(topics),
            ]))

            doc = Document(
                page_content=summary,
                metadata={
                    "bm25_text": bm25_text,
                    "video_id": video_id,
                    "segment_number": seg.get("segment_number", 0),
                    "timestamp": timestamp,
                    "people_present": json.dumps(people_present),
                    "topics": json.dumps(topics),
                    "tone": seg.get("tone", ""),
                    "calendar_events": json.dumps(seg.get("calendar_events", [])),
                    "decisions": json.dumps(seg.get("martins_decisions", [])),
                    "kind": "segment",
                },
            )
            documents.append(doc)

        if not documents:
            logger.warning(f"No segments to store for video '{video_id}'")
            return []

        ids = self._vector_store.add_documents(documents)
        logger.info(f"Stored {len(ids)} segments for video '{video_id}'")
        return ids

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        k: int = 5,
        weights: Tuple[float, float] = (0.7, 0.3),
        expr: Optional[str] = None,
        rerank: bool = True,
    ) -> List[Document]:
        """
        Hybrid search (dense + BM25) over video segments.

        Parameters
        ----------
        query   : free-text search query
        k       : number of segments to return
        weights : (dense_weight, sparse_weight) — (0.7, 0.3) = mostly semantic
        expr    : optional Milvus filter expression
                  e.g. 'video_id == "demo1"' or 'tone == "formal"'
        rerank  : whether to apply FlashRank cross-encoder reranking
        """
        try:
            search_kwargs = {
                "k": k * 2 if rerank else k,
                "ranker_type": "weighted",
                "ranker_params": {"weights": list(weights)},
            }
            if expr:
                search_kwargs["expr"] = expr

            if not rerank:
                return self._vector_store.similarity_search(query, **search_kwargs)

            retriever = self._vector_store.as_retriever(search_kwargs=search_kwargs)
            compression_retriever = ContextualCompressionRetriever(
                base_compressor=self._compressor,
                base_retriever=retriever,
            )
            return compression_retriever.invoke(query)[:k]
        except Exception as e:
            logger.error(f"Error searching video segments: {e}", exc_info=True)
            raise
