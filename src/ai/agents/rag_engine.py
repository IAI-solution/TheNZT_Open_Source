from pathlib import Path
"""
Complete RAG Pipeline in a single module:
- Loads documents (PDF, TXT, JSON, MD)
- Chunks text intelligently
- Embeds chunks with sentence-transformers
- Stores/retrieves vectors from Qdrant
- Optionally uses OpenAI for answer generation
"""
from dotenv import load_dotenv
load_dotenv()
env_path = Path("/home/manikandana/Desktop/open source/docker/.env")
load_dotenv(env_path)
import os
import json
from typing import List, Dict, Optional
import uuid
from qdrant_client import QdrantClient
from qdrant_client.http.models import VectorParams, Distance
from sentence_transformers import SentenceTransformer
from PyPDF2 import PdfReader
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# ============================================================================
# Document Loading and Chunking
# ============================================================================
class RecursiveCharacterTextSplitter:
    """
    A simple text splitter that divides text into chunks of specified size
    with a given overlap, using character-level splitting.
    """
    def __init__(self, chunk_size: int = 1000, overlap: int = 200):
        """
        Args:
            chunk_size: maximum number of characters per chunk
            overlap: number of overlapping characters between consecutive chunks
        """
        self.chunk_size = chunk_size
        self.overlap = overlap
    def split_text(self, text: str) -> List[str]:
        """
        Split the input text into chunks.
        Args:
            text: the input document text
        Returns:
            list of text chunks
        """
        if not text:
            return []
        chunks = []
        start = 0
        text_len = len(text)
        while start < text_len:
            end = min(start + self.chunk_size, text_len)
            chunk = text[start:end]
            chunks.append(chunk)
            start += self.chunk_size - self.overlap
        return chunks
def load_document(file_path: str) -> str:
    """
    Load document from various file formats.
    
    Args:
        file_path: path to the document file
        
    Returns:
        extracted text content
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    ext = os.path.splitext(file_path)[-1].lower()
    if ext == ".pdf":
        reader = PdfReader(file_path)
        return "\n".join([page.extract_text() or "" for page in reader.pages])
    elif ext == ".txt":
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    elif ext == ".json":
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return json.dumps(data, indent=2)
    elif ext == ".md":
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    else:
        raise ValueError(f"Unsupported file type: {ext}")
def chunk_document(text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
    """
    Chunk a document into smaller pieces.
    
    Args:
        text: input text to chunk
        chunk_size: maximum characters per chunk
        overlap: overlapping characters between chunks
        
    Returns:
        list of text chunks
    """
    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, overlap=overlap)
    return splitter.split_text(text)
# ============================================================================
# RAG Engine
# ============================================================================
class RAGEngine:
    """
    Main RAG Engine for document processing and querying.
    """
    def __init__(
        self,
        qdrant_url: str = "http://localhost:6333",
        qdrant_api_key: Optional[str] = None,
        collection_name: str = "rag_documents",
        embedding_model_name: str = "all-MiniLM-L6-v2",
        openai_api_key: Optional[str] = None,
        vector_distance: Distance = Distance.COSINE,
    ):
        """
        Initialize RAG Engine.
        
        Args:
            qdrant_url: URL of the Qdrant instance
            qdrant_api_key: optional auth for Qdrant cloud
            collection_name: Name of the Qdrant collection
            embedding_model_name: Sentence-transformer model for embeddings
            openai_api_key: Set to use OpenAI for answer generation
            vector_distance: Distance metric for vector search
        """
        # Setup Qdrant client
        self.client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
        self.collection = collection_name
        # Setup embedder
        print(f"Loading embedding model: {embedding_model_name}...")
        self.embedder = SentenceTransformer(embedding_model_name)
        self.dim = self.embedder.get_sentence_embedding_dimension()
        print(f"Model loaded. Embedding dimension: {self.dim}")
        # Ensure collection exists
        collection_exists = True
        try:
            self.client.get_collection(self.collection)
            print(f"Using existing collection: {self.collection}")
        except Exception:
            collection_exists = False
        if not collection_exists:
            try:
                self.client.create_collection(
                    collection_name=self.collection,
                    vectors_config=VectorParams(size=self.dim, distance=vector_distance),
                )
                print(f"Created new collection: {self.collection}")
            except Exception as e:
                print(f"Warning: Could not create collection: {e}")
        # Setup OpenAI if provided
        if openai_api_key:
            self.openai_api_key = openai_api_key
            print("OpenAI API key provided; answer generation enabled.")
    def embed(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of texts."""
        embs = self.embedder.encode(texts, normalize_embeddings=True)
        try:
            return embs.tolist()
        except Exception:
            return list(embs)
    def add_documents(self, docs: List[Dict]):
        """
        Add documents to Qdrant.
        
        Args:
            docs: List of documents with format:
                  {'id': <int or str>, 'text': <str>, 'meta': <dict, optional>}
        """
        if not docs:
            return
        ids = [doc["id"] for doc in docs]
        texts = [doc["text"] for doc in docs]
        metas = [doc.get("meta", {}) for doc in docs]
        # Normalize ids for Qdrant
        norm_ids = []
        for _id in ids:
            if isinstance(_id, int):
                norm_ids.append(_id)
            elif isinstance(_id, str):
                try:
                    _u = uuid.UUID(_id)
                    norm_ids.append(str(_u))
                except Exception:
                    norm_ids.append(str(uuid.uuid5(uuid.NAMESPACE_OID, _id)))
            else:
                norm_ids.append(str(uuid.uuid5(uuid.NAMESPACE_OID, str(_id))))
        print(f"Embedding {len(texts)} documents...")
        vectors = self.embed(texts)
        points = [
            {
                "id": _id,
                "vector": vec,
                "payload": {"text": txt, "meta": meta},
            }
            for _id, vec, txt, meta in zip(norm_ids, vectors, texts, metas)
        ]
        print(f"Upserting {len(points)} points to Qdrant...")
        self.client.upsert(collection_name=self.collection, points=points)
        print("Done!")
    def _search_vectors(self, query: str, top_k: int = 5) -> List[Dict]:
        """Search Qdrant, return list of hits with payload and score."""
        query_vector = self.embed([query])[0]
        results = self.client.search(
            collection_name=self.collection,
            query_vector=query_vector,
            limit=top_k,
            with_payload=True,
        )
        # results = self.client.query_points(
        #     collection_name=self.collection,
        #     query=query_vector,
        #     limit=top_k,
        #     with_payload=True,
        # )
        hits = []
        for hit in results:
            try:
                _id = getattr(hit, "id", None) or hit.get("id")
            except Exception:
                _id = None
            try:
                _score = getattr(hit, "score", None) or hit.get("score")
            except Exception:
                _score = None
            try:
                _payload = getattr(hit, "payload", None) or hit.get("payload")
            except Exception:
                _payload = None
            hits.append({"id": _id, "score": _score, "payload": _payload})
        return hits
    def _build_context(self, hits: List[Dict], char_limit: int = 1500) -> str:
        """Concatenate hit texts into a single context string."""
        parts = []
        total_chars = 0
        for hit in hits:
            payload = hit.get("payload") or {}
            text = payload.get("text") if isinstance(payload, dict) else None
            if not text:
                continue
            if total_chars + len(text) > char_limit:
                remaining = max(0, char_limit - total_chars)
                if remaining <= 0:
                    break
                parts.append(text[:remaining])
                total_chars += remaining
                break
            parts.append(text)
            total_chars += len(text)
        return "\n\n---\n\n".join(parts)
    def generate_answer(self, query: str, hits: List[Dict], use_openai: bool = True) -> str:
        """
        Generate an answer from retrieved documents.
        
        Args:
            query: user's question
            hits: retrieved document chunks
            use_openai: whether to use OpenAI for generation
            
        Returns:
            generated answer
        """
        context = self._build_context(hits)
        if use_openai and self.openai_api_key:
            system = "You are a helpful assistant. Use the provided context to answer the user's questions succinctly."
            user_prompt = f"Context:\n{context}\n\nQuestion: {query}\n\nAnswer:"
            response = client.chat.completions.create(model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=500,
            temperature=0.1)
            return response.choices[0].message.content.strip()
        else:
            return f"Based on the following context:\n{context}\n\nThe answer to your question '{query}' is likely contained above."
    def query(self, query: str, top_k: int = 5, use_openai: bool = True) -> Dict:
        """
        High-level query method: search and generate answer.
        
        Args:
            query: user's question
            top_k: number of top results to retrieve
            use_openai: whether to use OpenAI for answer generation
            
        Returns:
            dict with query, hits, and answer
        """
        print(f"Searching for: '{query}'...")
        hits = self._search_vectors(query, top_k=top_k)
        print(f"Found {len(hits)} relevant chunks")
        answer = self.generate_answer(query, hits, use_openai=use_openai)
        return {"query": query, "hits": hits, "answer": answer}
    def ingest_document(
        self, 
        file_path: str, 
        chunk_size: int = 1000, 
        overlap: int = 200,
        doc_metadata: Optional[Dict] = None
    ):
        """
        End-to-end document ingestion pipeline.
        
        Args:
            file_path: path to the document
            chunk_size: size of each text chunk
            overlap: overlap between chunks
            doc_metadata: additional metadata to attach to all chunks
        """
        print(f"\n{'='*60}")
        print(f"INGESTING DOCUMENT: {file_path}")
        print(f"{'='*60}")
        # Load document
        print(f"Loading document...")
        text = load_document(file_path)
        print(f"Loaded {len(text)} characters")
        # Chunk document
        print(f"Chunking document (chunk_size={chunk_size}, overlap={overlap})...")
        chunks = chunk_document(text, chunk_size=chunk_size, overlap=overlap)
        print(f"Created {len(chunks)} chunks")
        # Prepare documents for ingestion
        doc_name = os.path.basename(file_path)
        docs = []
        for i, chunk in enumerate(chunks):
            meta = {
                "source": doc_name,
                "chunk_id": i,
                "total_chunks": len(chunks),
            }
            if doc_metadata:
                meta.update(doc_metadata)
            docs.append({
                "id": f"{doc_name}_chunk_{i}",
                "text": chunk,
                "meta": meta
            })
        # Add to vector store
        self.add_documents(docs)
        print(f"\n✓ Successfully ingested '{doc_name}' ({len(chunks)} chunks)")
# ============================================================================
# Main Entry Point
# ============================================================================
if __name__ == "__main__":
    import sys
    # Configuration from environment variables
    QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
    QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", None)
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", None)
    # Initialize RAG Engine
    print("Initializing RAG Engine...")
    engine = RAGEngine(
        qdrant_url=QDRANT_URL,
        qdrant_api_key=QDRANT_API_KEY,
        openai_api_key=OPENAI_API_KEY,
        collection_name="rag_documents",
        embedding_model_name="all-MiniLM-L6-v2"
    )
    # Check if file path provided via command line
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        # Ingest the document
        engine.ingest_document(
            file_path=file_path,
            chunk_size=1000,
            overlap=200,
            doc_metadata={"ingested_by": "cli"}
        )
        # Interactive query loop
        print("\n" + "="*60)
        print("READY TO QUERY")
        print("="*60)
        print("Enter your questions (or 'quit' to exit):\n")
        while True:
            try:
                query = input("Query: ").strip()
                if query.lower() in ['quit', 'exit', 'q']:
                    print("Goodbye!")
                    break
                if not query:
                    continue
                result = engine.query(query, top_k=3, use_openai=bool(OPENAI_API_KEY))
                print("\n" + "-"*60)
                print("ANSWER:")
                print("-"*60)
                print(result["answer"])
                print("\n" + "-"*60)
                print("SOURCES:")
                print("-"*60)
                for i, hit in enumerate(result["hits"], 1):
                    payload = hit.get("payload") or {}
                    meta = payload.get("meta", {}) if isinstance(payload, dict) else {}
                    score = hit.get("score", 0)
                    print(f"{i}. {meta.get('source', 'unknown')} (chunk {meta.get('chunk_id', '?')}) - Score: {score:.4f}")
                print("\n")
            except KeyboardInterrupt:
                print("\nGoodbye!")
                break
            except Exception as e:
                print(f"Error: {e}\n")
    else:
        # Demo mode with sample documents
        print("\n" + "="*60)
        print("DEMO MODE - No file specified")
        print("="*60)
        print("Usage: python rag_engine.py /path/to/document.pdf")
        print("\nRunning with sample documents...\n")
        # Sample documents
        docs = [
            {
                "id": "doc1",
                "text": "The capital of France is Paris. Paris is known for the Eiffel Tower and the Louvre Museum.",
                "meta": {"source": "geo_facts"}
            },
            {
                "id": "doc2",
                "text": "Jupiter is the largest planet in our solar system. It has a distinctive Great Red Spot.",
                "meta": {"source": "astro_facts"}
            },
            {
                "id": "doc3",
                "text": "The Great Wall of China is one of the most impressive architectural feats in human history.",
                "meta": {"source": "history_facts"}
            },
        ]
        engine.add_documents(docs)
        # Sample query
        query = "What is the largest planet?"
        result = engine.query(query, top_k=3, use_openai=bool(OPENAI_API_KEY))
        print("\n" + "-"*60)
        print(f"QUERY: {query}")
        print("-"*60)
        print("ANSWER:")
        print(result["answer"])
        print("\n" + "-"*60)
        print("SOURCES:")
        print("-"*60)
        for i, hit in enumerate(result["hits"], 1):
            payload = hit.get("payload") or {}
            text = payload.get("text", "") if isinstance(payload, dict) else ""
            meta = payload.get("meta", {}) if isinstance(payload, dict) else {}
            score = hit.get("score", 0)
            print(f"{i}. [{meta.get('source')}] {text[:100]}... (Score: {score:.4f})")