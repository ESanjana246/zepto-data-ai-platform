import json
import os
from pathlib import Path
from typing import TypedDict

import chromadb
from fastapi import FastAPI
from pydantic import BaseModel, Field
from sentence_transformers import SentenceTransformer
from langgraph.graph import StateGraph, START, END

from support_assistant.prompt import build_prompt


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
CHROMA_DIR = BASE_DIR / "chroma_db"


# ============================================================
# CONFIGURATION
# ============================================================

# Default is mock mode.
# MOCK_LLM=1 or unset -> offline graded mode
# MOCK_LLM=0          -> optional real LLM mode
MOCK_LLM = os.getenv("MOCK_LLM", "1")


# ============================================================
# EMBEDDING MODEL + CHROMADB
# ============================================================

print("Loading embedding model...")

embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

client = chromadb.PersistentClient(
    path=str(CHROMA_DIR)
)

collection = client.get_or_create_collection(
    name="zepto_policies",
    metadata={"hnsw:space": "cosine"},
)


# ============================================================
# PYDANTIC MODELS
# ============================================================

class AskRequest(BaseModel):
    query: str


class SupportResponse(BaseModel):
    answer: str
    sources: list[str]
    confidence: float = Field(ge=0.0, le=1.0)


# ============================================================
# LANGGRAPH STATE
# ============================================================

class SupportState(TypedDict, total=False):
    query: str
    intent: str
    retrieved_documents: list[str]
    retrieved_ids: list[str]
    answer: str
    sources: list[str]
    confidence: float


# ============================================================
# MOCK LLM HELPERS
# ============================================================

POLICY_KEYWORDS = [
    "delivery",
    "return",
    "refund",
    "membership",
    "tracking",
    "cancel",
    "gift card",
    "support hours",
]


def mock_classify(query: str) -> str:
    """
    Required deterministic classification logic.
    """
    query_lower = query.lower()

    for keyword in POLICY_KEYWORDS:
        if keyword in query_lower:
            return "policy_question"

    return "general_question"


def mock_policy_answer(
    retrieved_documents: list[str],
) -> str:
    """
    Required deterministic answer format.
    """
    if not retrieved_documents:
        return "Based on the retrieved context: No relevant context was found."

    top_chunk_snippet = retrieved_documents[0][:200]

    return f"Based on the retrieved context: {top_chunk_snippet}"


def mock_general_answer() -> str:
    """
    Required deterministic response for general questions.
    """
    return "I can only answer questions about Zepto policies right now."


# ============================================================
# OPTIONAL REAL LLM SUPPORT
# ============================================================

def call_real_llm(prompt: str) -> str:
    """
    Optional real-LLM extension.

    This uses Groq's OpenAI-compatible API when MOCK_LLM=0.

    Required graded mode never reaches this function.
    """

    import urllib.request

    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        raise RuntimeError(
            "MOCK_LLM=0 requires GROQ_API_KEY."
        )

    payload = {
        "model": os.getenv(
            "GROQ_MODEL",
            "llama-3.1-8b-instant",
        ),
        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],
        "temperature": 0,
    }

    request = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.loads(response.read().decode("utf-8"))

    return result["choices"][0]["message"]["content"]


def parse_real_llm_response(
    raw_output: str,
    query: str,
    context: str,
) -> SupportResponse:
    """
    Parse and validate real LLM output.
    """

    data = json.loads(raw_output)

    return SupportResponse.model_validate(data)


def real_llm_with_retry(
    query: str,
    context: str,
    source_ids: list[str],
) -> SupportResponse:
    """
    Optional real-LLM path.

    Retry up to two additional times if the raw output
    fails JSON/Pydantic validation.
    """

    prompt = build_prompt(
        query=query,
        context=context,
    )

    last_error = None

    for attempt in range(3):
        try:
            if attempt == 0:
                current_prompt = prompt
            else:
                current_prompt = f"""
Your previous answer failed validation.

Return ONLY valid JSON matching this exact schema:

{{
  "answer": "string",
  "sources": ["document_id"],
  "confidence": 0.0
}}

Do not include Markdown.
Do not include explanations outside the JSON.

The answer must use only the provided context.

Original prompt:

{prompt}
"""

            raw_output = call_real_llm(current_prompt)

            result = parse_real_llm_response(
                raw_output,
                query,
                context,
            )

            return result

        except Exception as exc:
            last_error = exc

    return SupportResponse(
        answer=f"ERROR: Unable to validate LLM response after 3 attempts: {last_error}",
        sources=source_ids,
        confidence=0.0,
    )


# ============================================================
# NODE 1 — CLASSIFY INTENT
# ============================================================

def classify_intent(state: SupportState) -> SupportState:
    """
    Classify the incoming query.

    MOCK_LLM default:
        keyword heuristic

    MOCK_LLM=0:
        optional real LLM classification
    """

    query = state["query"]

    if MOCK_LLM != "0":
        intent = mock_classify(query)

    else:
        classification_prompt = f"""
Classify this customer question as exactly one of:

policy_question
general_question

Return only the classification.

Customer question:
{query}
"""

        raw = call_real_llm(classification_prompt)

        intent = raw.strip().lower()

        if "policy_question" in intent:
            intent = "policy_question"
        else:
            intent = "general_question"

    return {
        **state,
        "intent": intent,
    }


# ============================================================
# NODE 2 — RETRIEVE AND ANSWER
# ============================================================

def retrieve_and_answer(state: SupportState) -> SupportState:
    """
    Retrieve top-3 documents using cosine similarity.

    Retrieval happens in BOTH mock and real modes.
    Only answer generation branches on MOCK_LLM.
    """

    query = state["query"]

    # --------------------------------------------------------
    # REAL LOCAL EMBEDDING
    # --------------------------------------------------------

    query_embedding = embedding_model.encode(
        [query],
        normalize_embeddings=True,
    ).tolist()

    # --------------------------------------------------------
    # CHROMADB RETRIEVAL
    # --------------------------------------------------------

    results = collection.query(
        query_embeddings=query_embedding,
        n_results=3,
    )

    retrieved_documents = results.get(
        "documents",
        [[]],
    )[0]

    retrieved_ids = results.get(
        "ids",
        [[]],
    )[0]

    # --------------------------------------------------------
    # MOCK MODE
    # --------------------------------------------------------

    if MOCK_LLM != "0":

        answer = mock_policy_answer(
            retrieved_documents
        )

        return {
            **state,
            "retrieved_documents": retrieved_documents,
            "retrieved_ids": retrieved_ids,
            "answer": answer,
            "sources": retrieved_ids,
            "confidence": 1.0,
        }

    # --------------------------------------------------------
    # OPTIONAL REAL LLM MODE
    # --------------------------------------------------------

    context_parts = []

    for doc_id, document in zip(
        retrieved_ids,
        retrieved_documents,
    ):
        context_parts.append(
            f"[{doc_id}]\n{document}"
        )

    context = "\n\n".join(context_parts)

    result = real_llm_with_retry(
        query=query,
        context=context,
        source_ids=retrieved_ids,
    )

    return {
        **state,
        "retrieved_documents": retrieved_documents,
        "retrieved_ids": retrieved_ids,
        "answer": result.answer,
        "sources": result.sources,
        "confidence": result.confidence,
    }


# ============================================================
# NODE 3 — DIRECT ANSWER
# ============================================================

def direct_answer(state: SupportState) -> SupportState:
    """
    Handle general questions without retrieval.
    """

    query = state["query"]

    # --------------------------------------------------------
    # MOCK MODE
    # --------------------------------------------------------

    if MOCK_LLM != "0":

        answer = mock_general_answer()

        return {
            **state,
            "answer": answer,
            "sources": [],
            "confidence": 1.0,
        }

    # --------------------------------------------------------
    # OPTIONAL REAL LLM MODE
    # --------------------------------------------------------

    prompt = f"""
You are a Zepto Support Assistant.

Answer the customer's question directly.

Do not invent Zepto policy information.

Return ONLY valid JSON:

{{
  "answer": "string",
  "sources": [],
  "confidence": 0.0
}}

Customer question:
{query}
"""

    last_error = None

    for attempt in range(3):
        try:

            current_prompt = prompt

            if attempt > 0:
                current_prompt = f"""
Return ONLY valid JSON with exactly:

{{
  "answer": "string",
  "sources": [],
  "confidence": 0.0
}}

Do not include Markdown or additional text.

{prompt}
"""

            raw_output = call_real_llm(
                current_prompt
            )

            result = SupportResponse.model_validate(
                json.loads(raw_output)
            )

            return {
                **state,
                "answer": result.answer,
                "sources": [],
                "confidence": result.confidence,
            }

        except Exception as exc:
            last_error = exc

    return {
        **state,
        "answer": (
            "ERROR: Unable to validate LLM response "
            f"after 3 attempts: {last_error}"
        ),
        "sources": [],
        "confidence": 0.0,
    }


# ============================================================
# CONDITIONAL ROUTING
# ============================================================

def route_after_classification(
    state: SupportState,
) -> str:

    if state["intent"] == "policy_question":
        return "retrieve_and_answer"

    return "direct_answer"


# ============================================================
# BUILD LANGGRAPH
# ============================================================

graph_builder = StateGraph(SupportState)

graph_builder.add_node(
    "classify_intent",
    classify_intent,
)

graph_builder.add_node(
    "retrieve_and_answer",
    retrieve_and_answer,
)

graph_builder.add_node(
    "direct_answer",
    direct_answer,
)

graph_builder.add_edge(
    START,
    "classify_intent",
)

graph_builder.add_conditional_edges(
    "classify_intent",
    route_after_classification,
    {
        "retrieve_and_answer": "retrieve_and_answer",
        "direct_answer": "direct_answer",
    },
)

graph_builder.add_edge(
    "retrieve_and_answer",
    END,
)

graph_builder.add_edge(
    "direct_answer",
    END,
)

graph = graph_builder.compile()


# ============================================================
# GRAPH EXECUTION
# ============================================================

def run_support_graph(query: str) -> SupportResponse:

    initial_state: SupportState = {
        "query": query,
    }

    final_state = graph.invoke(
        initial_state
    )

    response = SupportResponse(
        answer=final_state["answer"],
        sources=final_state.get("sources", []),
        confidence=final_state.get("confidence", 1.0),
    )

    return response


# ============================================================
# FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title="Zepto Support Assistant",
    description="Offline RAG-based Zepto policy support service",
    version="1.0.0",
)


@app.get("/")
def root():
    return {
        "service": "Zepto Support Assistant",
        "endpoint": "POST /ask",
        "mock_llm": MOCK_LLM != "0",
    }


@app.post(
    "/ask",
    response_model=SupportResponse,
)
def ask(request: AskRequest) -> SupportResponse:

    query = request.query.strip()

    if not query:
        return SupportResponse(
            answer="Please provide a question.",
            sources=[],
            confidence=1.0,
        )

    return run_support_graph(query)