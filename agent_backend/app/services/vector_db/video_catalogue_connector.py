import os
import json
from typing import Optional, Dict, Any, List, Tuple

from langchain_community.document_compressors import FlashrankRerank
from langchain_milvus import BM25BuiltInFunction, Milvus
from langchain_core.documents import Document
from langchain_classic.retrievers.contextual_compression import ContextualCompressionRetriever

from pymilvus import connections

from .lm_studio_embeddings import LMStudioEmbeddings
from ...utils.logger import get_logger
from ...config.config import MILVUS_HOST, MILVUS_PORT

logger = get_logger(__name__)


class VideoCatalogueConnector:
    """
    Milvus connector for the video_catalogue collection.

    Stores one entry per video. The brief_summary is embedded for semantic
    search; person names and deduplicated topics are concatenated into
    bm25_text for keyword retrieval.

    Use this as the discovery layer — find which videos are relevant, then
    drill into individual segments via VideoSegmentsConnector.

    Dynamic metadata fields stored per entry:
        video_id       — video name / identifier
        timestamp      — ISO datetime the video was recorded
        people         — JSON-encoded list of person names
        total_segments — number of segments in the video
        kind           — always "video"
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
        collection_name: str = "video_catalogue",
        host: Optional[str] = None,
        port: Optional[int] = None,
    ):
        if VideoCatalogueConnector._initialized:
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
            logger.info(f"VideoCatalogueConnector: connecting to Milvus — {connection_args}")

            # langchain_milvus uses Collection(using=alias) internally for schema
            # inspection. Connecting via URI alone doesn't register the ORM alias,
            # so we do it explicitly — same fix as MilvusConnector.
            if not connections.has_connection("default"):
                connections.connect(
                    alias="default",
                    host=host or MILVUS_HOST,
                    port=int(port or MILVUS_PORT),
                )

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

            logger.info(f"VideoCatalogueConnector initialised — collection: {collection_name}")
            VideoCatalogueConnector._initialized = True
        except Exception as e:
            logger.error(f"Failed to initialise VideoCatalogueConnector: {e}", exc_info=True)
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

    def store_video(self, metadata: dict) -> List[str]:
        """
        Store a video-level catalogue entry from an orchestrator result.

        Parameters
        ----------
        metadata : dict
            The dict returned by Orchestrator.analyse_video(). Expected keys:
              - video          : str   — video identifier
              - brief_summary  : str   — narrative paragraph of the day
              - total_segments : int
              - people_encountered : list[dict]  — each dict has a "name" key
              - segments       : list[dict]       — each dict has "topics"
              - timestamp      : str   — ISO datetime the video was recorded

        Returns
        -------
        List of Milvus-assigned primary-key strings.
        """
        brief_summary = metadata.get("brief_summary", "")
        people = [p["name"] for p in metadata.get("people_encountered", [])]

        # Deduplicate topics while preserving order (dict.fromkeys trick).
        all_topics = list(dict.fromkeys(
            topic
            for seg in metadata.get("segments", [])
            for topic in seg.get("topics", [])
        ))

        # Dense vector captures the prose meaning of the day.
        # BM25 additionally indexes person names and topic keywords so
        # exact-match queries like "colleague" or "diarization" also hit.
        bm25_text = " ".join(filter(None, [
            brief_summary,
            " ".join(people),
            " ".join(all_topics),
        ]))

        doc = Document(
            page_content=brief_summary,
            metadata={
                "bm25_text": bm25_text,
                "video_id": metadata.get("video", ""),
                "timestamp": metadata.get("timestamp", ""),
                "people": json.dumps(people),
                "total_segments": metadata.get("total_segments", 0),
                "kind": "video",
            },
        )

        ids = self._vector_store.add_documents([doc])
        logger.info(f"Stored video catalogue entry — video: '{metadata.get('video')}', id: {ids}")
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
        Hybrid search (dense + BM25) over the video catalogue.

        Parameters
        ----------
        query   : free-text search query
        k       : number of videos to return
        weights : (dense_weight, sparse_weight) — (0.7, 0.3) = mostly semantic
        expr    : optional Milvus filter, e.g. 'video_id == "demo1"'
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
            logger.error(f"Error searching video catalogue: {e}", exc_info=True)
            raise
