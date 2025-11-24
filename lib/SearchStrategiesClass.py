from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import math
from typing import Optional, Any, List, Dict, Tuple, Callable, Protocol
from collections import Counter
import re
import random
import string

# VectorIndex Implementation
class VectorIndex:
    def __init__(
            self,
            distance_metric: str = "cosine",
            embedding_fn = None
    ):
        self.vectors: List[List[float]] = []
        self.documents: List[Dict[str, Any]] = []
        self._vector_dim: Optional[int] = None
        if distance_metric not in ["cosine", "euclidean"]:
            raise ValueError("distance_metric must be 'cosine' or 'euclidean'")
        self._distance_metric = distance_metric
        self._embedding_fn = embedding_fn
    
    def _validate_input_variables(self, validations: dict = {}, **kwargs):
        validations.update(kwargs)
        for key, value in validations.items():
            match key:
                case "vector":
                    # Validate it's a list of numbers
                    if not isinstance(value, list) or not all(
                        isinstance(x, (int, float)) for x in value
                        ):
                        raise ValueError("Vector must be a list of numbers.")
                case "document":
                    # Validate it's a dictionary
                    if not isinstance(value, dict):
                        raise ValueError("Document must be a dictionary.")
                    # Validate 'content' key
                    if "content" not in value:
                        raise ValueError("Document must contain a 'content' key.")
                case "embedding_fn":
                    # Validate embedding_fn
                    if not value:
                        raise ValueError("Embedding function not set.")
                case "query":
                    # Validate query
                    if not (isinstance(value, str) or (isinstance(
                        value, list) and all(
                            isinstance(x, (int, float)) for x in value
                            )
                        )
                    ):
                        raise TypeError("Query must be either a string or a list of numbers.")
                case "k":
                    if value <= 0:
                        raise ValueError("k must be a positive integer.")
                case "vector_dim":
                    len_1 = len(value[0]) if isinstance(value[0], list) else value[0]
                    len_2 = len(value[1]) if isinstance(value[1], list) else value[1]
                    if len_1 != len_2:
                        raise ValueError(f"Vector dimension mismatch. Expected {len_1}, got {len_2}")

    def add_vector(self,
                   vector: list,
                   document: Dict[str, Any]
    ):
        '''
        Add a vector to the index.
        '''
        self._validate_input_variables(locals())
        if not self.vectors:
            self._vector_dim = len(vector)
        else:
            self._validate_input_variables(vector_dim = [self._vector_dim, vector])
        
        self.vectors.append(list(vector))
        self.documents.append(document)
    
    def add_document(self, document: Dict[str, Any]):
        '''
        Add a document to the index.
        '''
        self._validate_input_variables(locals(), embedding_fn = self._embedding_fn)
        content = document["content"]
        if self._embedding_fn:
            vector = self._embedding_fn(content)
            self.add_vector(vector, document)
    
    def add_documents(self, documents: List[Dict[str, Any]]):
        if not self._embedding_fn:
            raise ValueError(
                "Embedding function not provided during initialization."
            )

        if not isinstance(documents, list):
            raise TypeError("Documents must be a list of dictionaries.")

        if not documents:
            return

        contents = []
        for i, doc in enumerate(documents):
            if not isinstance(doc, dict):
                raise TypeError(f"Document at index {i} must be a dictionary.")
            if "content" not in doc:
                raise ValueError(
                    f"Document at index {i} must contain a 'content' key."
                )
            if not isinstance(doc["content"], str):
                raise TypeError(
                    f"Document 'content' at index {i} must be a string."
                )
            contents.append(doc["content"])

        vectors = self._embedding_fn(contents)

        for vector, document in zip(vectors, documents):
            self.add_vector(vector=vector, document=document)

    def search(
            self,
            query: Any,
            k: int = 1
    ) -> List[Tuple[Dict[str, Any], float]]:
        '''
        Search the index for the closest vectors to the query.
        '''
        self._validate_input_variables(locals())
        if not self.vectors or self._vector_dim is None:
            return []
        if isinstance(query, str):
            self._validate_input_variables(embedding_fn = self._embedding_fn)
            if self._embedding_fn:
                query_vector = self._embedding_fn(query)
        elif isinstance(query, list) and all(
            isinstance(x, (int, float)) for x in query
        ):
            query_vector = query

        self._validate_input_variables(vector_dim = [self._vector_dim,query_vector])
        
        if self._distance_metric == "cosine":
            dist_func = self._cosine_distance
        elif self._distance_metric == "euclidean":
            dist_func = self._euclidean_distance

        distances = []
        for i, stored_vector in enumerate(self.vectors):
            distance = dist_func(query_vector, stored_vector)
            distances.append((distance, self.documents[i]))

        distances.sort(key=lambda x: x[0])        
        return [(doc, dist) for dist, doc in distances[:k]]
    
    def _cosine_distance(self,
                         vector1: List[float],
                         vector2: List[float]
    ) -> float:
        '''
        Calculate the cosine distance between two vectors.
        '''
        self._validate_input_variables(vector = vector1, vector_dim = [len(vector1), len(vector2)])
        self._validate_input_variables(vector = vector2)

        vec1 = np.array([vector1])
        vec2 = np.array([vector2])

        cosine_sim = cosine_similarity(vec1, vec2)[0][0]
        return 1 - float(cosine_sim)
    
    def _euclidean_distance(self,
                            vector1: List[float],
                            vector2: List[float]
    ) -> float:
        '''
        Calculate the euclidean distance between two vectors.
        '''
        self._validate_input_variables(vector = vector1, vector_dim = [len(vector1), len(vector2)])
        self._validate_input_variables(vector = vector2)
        return math.sqrt(sum((p - q) ** 2 for p, q in zip(vector1, vector2)))
    
    def __len__(self) -> int:
        return len(self.vectors)

    def __repr__(self) -> str:
        has_embed_fn = "Yes" if self._embedding_fn else "No"
        return f"VectorIndex(count={len(self)}, dim={self._vector_dim}, metric='{self._distance_metric}', has_embedding_fn='{has_embed_fn}')"

class BM25Index:
    def __init__(
            self,
            k1: float = 1.5,
            b: float = 0.75,
            tokenizer: Optional[Callable[[str], List[str]]] = None
    ):
        self.documents: List[Dict[str, Any]] = []
        self._corpus_tokens: List[List[str]] = []
        self._doc_len: List[int] = []
        self._doc_freqs: Dict[str, int] = {}
        self._avg_doc_len: float = 0.0
        self._idf: Dict[str, float] = {}
        self._index_built: bool = False

        self.k1 = k1
        self.b = b
        self._tokenizer = tokenizer if tokenizer else self._default_tokenizer
    
    def _validate_input_variables(self, validations: dict = {}, **kwargs):
        validations.update(kwargs)
        for key, value in validations.items():
            match key:
                case "document":
                    # Validate it's a dictionary
                    if not isinstance(value, dict):
                        raise ValueError("Document must be a dictionary.")
                    # Validate 'content' key
                    if "content" not in value:
                        raise ValueError("Document must contain a 'content' key.")
                    if not isinstance(value.get("content", ""), str):
                        raise TypeError("Document 'content' must be a string.")
                case "query_text":
                    if not isinstance(value, str):
                        raise TypeError("Query text must be a string.")
                case "k":
                    if value <= 0 or not isinstance(value, int):
                        raise ValueError("k must be a positive integer.")

    def _default_tokenizer(self, text: str) -> List[str]:
        '''
        Default tokenizer that splits on non-alphanumeric characters.
        '''
        text = text.lower()
        tokens = re.split(r"\W+", text)
        return [token for token in tokens if token]

    def _update_stats_add(self, doc_tokens: List[str]):
        '''
        Update statistics for a new document.
        '''
        self._doc_len.append(len(doc_tokens))
        seen_in_doc = set()
        for token in doc_tokens:
            if token not in seen_in_doc:
                self._doc_freqs[token] = self._doc_freqs.get(token, 0) + 1
                seen_in_doc.add(token)
        self._index_built = False
    
    def _calculate_idf(self):
        '''
        Calculate IDF scores for all terms in the corpus.
        '''
        N = len(self.documents)
        self._idf = {}
        for term, freq in self._doc_freqs.items():
            idf_score = math.log(((N - freq + 0.5) / (freq + 0.5)) + 1)
            self._idf[term] = idf_score
    
    def _build_index(self):
        '''
        Build the index.
        '''
        if not self.documents:
            self._avg_doc_len = 0.0
            self._idf = {}
            self._index_built = True
            return
        
        self._avg_doc_len = sum(self._doc_len) / len(self.documents)
        self._calculate_idf()
        self._index_built = True

    def add_document(self, document: Dict[str, Any]):
        self._validate_input_variables(locals())
        content = document.get("content", "")
        doc_tokens = self._tokenizer(content)

        self.documents.append(document)
        self._corpus_tokens.append(doc_tokens)
        self._update_stats_add(doc_tokens)

    def add_documents(self, documents: List[Dict[str, Any]]):
        if not isinstance(documents, list):
            raise TypeError("Documents must be a list of dictionaries.")

        if not documents:
            return

        for i, doc in enumerate(documents):
            if not isinstance(doc, dict):
                raise TypeError(f"Document at index {i} must be a dictionary.")
            if "content" not in doc:
                raise ValueError(
                    f"Document at index {i} must contain a 'content' key."
                )
            if not isinstance(doc["content"], str):
                raise TypeError(
                    f"Document 'content' at index {i} must be a string."
                )

            content = doc["content"]
            doc_tokens = self._tokenizer(content)

            self.documents.append(doc)
            self._corpus_tokens.append(doc_tokens)
            self._update_stats_add(doc_tokens)

        self._index_built = False

    def _compute_bm25_score(
            self,
            query_tokens: List[str],
            doc_index: int
    ) -> float:
        score = 0.0
        doct_term_counts = Counter(self._corpus_tokens[doc_index])
        doc_length = self._doc_len[doc_index]

        for token in query_tokens:
            if token not in self._idf:
                continue
                
            idf = self._idf[token]
            term_freq = doct_term_counts.get(token, 0)

            numerator = idf * term_freq * (self.k1 + 1)
            denominator = term_freq + self.k1 * (
                1 - self.b + self.b * (
                    doc_length / self._avg_doc_len
                )
            )

            score += numerator / (denominator + 1e-9)
        
        return score

    def search(
            self,
            query: str,
            k: int = 1,
            score_normalization_factor: float = 0.1
    ) -> List[Tuple[Dict[str, Any], float]]:
        self._validate_input_variables(query_text = query, k = k)
        if not self.documents:
            return []
        if not self._index_built:
            self._build_index()
        if self._avg_doc_len == 0:
            return []
        
        query_tokens = self._tokenizer(query)
        if not query_tokens:
            return []
        
        raw_scores = []
        for i in range(len(self.documents)):
            raw_score = self._compute_bm25_score(query_tokens, i)
            if raw_score > 1e-9:
                raw_scores.append((raw_score, self.documents[i]))
        
        # Match higher scores
        raw_scores.sort(key = lambda item: item[0], reverse=True)

        normalized_results = []
        for raw_score, doc in raw_scores[:k]:
            normalized_score = math.exp(-score_normalization_factor * raw_score)
            normalized_results.append((doc, normalized_score))
        
        normalized_results.sort(key = lambda item: item[1])

        return normalized_results
    
    def __len__(self) -> int:
        return len(self.documents)
    
    def __repr__(self) -> str:
        return f"BM25VectorStore(count={len(self)}, k1={self.k1}, b={self.b}, index_built={self._index_built})"

class SearchIndex(Protocol):
    def add_document(self, document: Dict[str, Any]) -> None: ...

    # Added the 'add_documents' method to avoid rate limiting errors from VoyageAI
    def add_documents(self, documents: List[Dict[str, Any]]) -> None: ...

    def search(
        self, query: Any, k: int = 1
    ) -> List[Tuple[Dict[str, Any], float]]: ...

class Retriever:
    def __init__(self,
                *indexes: SearchIndex,
                reranker_fn: Optional[
                    Callable[
                        [
                            List[Dict[str, Any]],
                            str,
                            int
                        ],
                        List[str]
                    ]
                ] = None
    ):
        if len(indexes) == 0:
            raise ValueError("At least one index must be provided")
        self._indexes = list(indexes)
        self._reranker_fn = reranker_fn

    def add_document(self, document: Dict[str, Any]):
        # Create random ID for each document
        if "id" not in document:
            document["id"] = "".join(
                random.choices(string.ascii_letters + string.digits, k=4)
            )

        for index in self._indexes:
            index.add_document(document)

    # Added the 'add_documents' method to avoid rate limiting errors from VoyageAI
    def add_documents(self, documents: List[Dict[str, Any]]):
        for index in self._indexes:
            index.add_documents(documents)

    def search(
        self, query_text: str, k: int = 1, k_rrf: int = 60
    ) -> List[Tuple[Dict[str, Any], float]]:
        if not isinstance(query_text, str):
            raise TypeError("Query text must be a string.")
        if k <= 0:
            raise ValueError("k must be a positive integer.")
        if k_rrf < 0:
            raise ValueError("k_rrf must be non-negative.")

        all_results = [
            index.search(query_text, k=k * 5) for index in self._indexes
        ]

        doc_ranks = {}
        for idx, results in enumerate(all_results):
            for rank, (doc, _) in enumerate(results):
                doc_id = id(doc)
                if doc_id not in doc_ranks:
                    doc_ranks[doc_id] = {
                        "doc_obj": doc,
                        "ranks": [float("inf")] * len(self._indexes),
                    }
                doc_ranks[doc_id]["ranks"][idx] = rank + 1

        def calc_rrf_score(ranks: List[float]) -> float:
            return sum(1.0 / (k_rrf + r) for r in ranks if r != float("inf"))

        scored_docs: List[Tuple[Dict[str, Any], float]] = [
            (ranks["doc_obj"], calc_rrf_score(ranks["ranks"]))
            for ranks in doc_ranks.values()
        ]

        filtered_docs = [
            (doc, score) for doc, score in scored_docs if score > 0
        ]
        filtered_docs.sort(key=lambda x: x[1], reverse=True)

        result = filtered_docs[:k]

        if self._reranker_fn is not None:
            docs_only = [doc for doc, _ in result]
            for doc in docs_only:
                if "id" not in doc:
                    doc["id"] = "".join(
                        random.choices(
                            string.ascii_letters + string.digits, k=4
                        )
                    )
            doc_lookup = {doc["id"]: doc for doc in docs_only}
            reranked_ids = self._reranker_fn(docs_only, query_text, k)

            new_result = []
            original_scores = {id(doc): score for doc, score in result}

            for doc_id in reranked_ids:
                if doc_id in doc_lookup:
                    doc = doc_lookup[doc_id]
                    score = original_scores.get(id(doc), 0.0)
                    new_result.append((doc, score))
            
            result = new_result
            
        return result
