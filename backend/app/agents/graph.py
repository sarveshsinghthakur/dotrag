from typing import Annotated, TypedDict, Optional, Literal
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage

from app.services.mistral import get_mistral_service
from app.retrieval.retriever import get_retriever
from app.tools import TOOLS, search_documents, summarize_document, compare_documents, get_source_info


# Agent state
class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    query: str
    intent: Literal["rag", "chat", "summarize", "compare"]
    document_ids: list[str]
    search_results: list[dict]
    context: str
    response: str
    citations: list[dict]
    tool_executions: list[dict]


SYSTEM_PROMPT = """You are DotRAG, an intelligent PDF research assistant. You help users search, understand, and analyze their uploaded documents.

CORE RULES:
1. When answering questions about uploaded documents, use retrieved document context as the primary source.
2. Do not invent facts that are not supported by retrieved context.
3. Cite every important document-derived claim using [Source N] format.
4. If the information is not present in the documents, explicitly say that it was not found.
5. Never fabricate page numbers or source references.
6. Preserve document-specific terminology and phrasing.
7. Distinguish between document-derived facts and your general knowledge.
8. Keep answers concise unless the user requests detail.
9. For general knowledge questions (not about documents), answer directly without retrieval.
10. When comparing documents, present a structured comparison.

CITATION FORMAT:
When referencing document content, always use this format:
[Source N] where N is the source number from the retrieved context.

Example: "The paper proposes a novel architecture [Source 1] that improves latency by 40% [Source 2]."

Available tools:
- search_documents: Search across uploaded PDFs
- summarize_document: Get document content for summarization
- compare_documents: Compare multiple documents
- get_source_info: Get details about a specific source chunk"""


def create_agent_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("router", route_query)
    graph.add_node("rag_agent", rag_agent)
    graph.add_node("chat_agent", chat_agent)
    graph.add_node("tool_executor", execute_tools)

    # Set entry point
    graph.set_entry_point("router")

    # Add conditional edges
    graph.add_conditional_edges(
        "router",
        lambda state: state["intent"],
        {
            "rag": "rag_agent",
            "summarize": "rag_agent",
            "compare": "rag_agent",
            "chat": "chat_agent",
        },
    )

    # Add edges from agents
    graph.add_edge("rag_agent", "tool_executor")
    graph.add_edge("tool_executor", END)
    graph.add_edge("chat_agent", END)

    return graph.compile()


def route_query(state: AgentState) -> AgentState:
    """Classify user intent."""
    messages = state["messages"]
    last_message = messages[-1].content if messages else ""

    # Simple intent classification
    query_lower = last_message.lower()
    intent = "rag"  # Default to RAG

    # Check for general chat (no document reference)
    general_patterns = [
        "what is", "how does", "explain", "tell me about",
        "what are", "define", "who is", "when did",
    ]
    document_patterns = [
        "this document", "this paper", "this pdf", "upload",
        "search", "find", "look for", "page",
        "summarize", "compare", "extract",
    ]

    has_doc_ref = any(p in query_lower for p in document_patterns)
    is_general = any(p in query_lower for p in general_patterns) and not has_doc_ref

    if is_general and not state.get("document_ids"):
        intent = "chat"
    elif "summarize" in query_lower or "summary" in query_lower or "overview" in query_lower:
        intent = "summarize"
    elif "compare" in query_lower or "comparison" in query_lower:
        intent = "compare"
    else:
        intent = "rag"

    return {**state, "intent": intent, "query": last_message}


def rag_agent(state: AgentState) -> AgentState:
    """RAG processing: retrieve, generate, cite."""
    mistral = get_mistral_service()
    retriever = get_retriever()

    query = state["query"]
    document_ids = state.get("document_ids", [])

    # Build messages with tool definitions
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
    ]

    # Add conversation history (last 5 messages)
    for msg in state["messages"][-5:]:
        if isinstance(msg, HumanMessage):
            messages.append({"role": "user", "content": msg.content})
        elif isinstance(msg, AIMessage):
            messages.append({"role": "assistant", "content": msg.content})

    messages.append({"role": "user", "content": query})

    # Call Mistral with tools
    try:
        import asyncio
        response = asyncio.get_event_loop().run_until_complete(
            mistral.chat_completion(messages=messages, tools=TOOLS)
        )

        assistant_message = response["choices"][0]["message"]

        # Check if tool was called
        if assistant_message.get("tool_calls"):
            return {
                **state,
                "tool_executions": [
                    {
                        "tool_name": tc["function"]["name"],
                        "input_data": tc["function"]["arguments"],
                        "tool_call_id": tc["id"],
                    }
                    for tc in assistant_message["tool_calls"]
                ],
            }
        else:
            # Direct response without tool use
            return {
                **state,
                "response": assistant_message.get("content", ""),
                "tool_executions": [],
            }

    except Exception as e:
        return {
            **state,
            "response": f"I encountered an error while processing your query: {str(e)}",
            "tool_executions": [],
        }


def execute_tools(state: AgentState) -> AgentState:
    """Execute tool calls and generate final response."""
    import asyncio
    import json

    mistral = get_mistral_service()
    retriever = get_retriever()
    tool_executions = state.get("tool_executions", [])
    all_results = []
    tool_outputs = []

    for tool_call in tool_executions:
        tool_name = tool_call["tool_name"]
        try:
            args = json.loads(tool_call["input_data"]) if isinstance(tool_call["input_data"], str) else tool_call["input_data"]
        except (json.JSONDecodeError, TypeError):
            args = {}

        # Execute tool
        start_time = asyncio.get_event_loop().time()
        if tool_name == "search_documents":
            result = search_documents(**args)
        elif tool_name == "summarize_document":
            result = summarize_document(**args)
        elif tool_name == "compare_documents":
            result = compare_documents(**args)
        elif tool_name == "get_source_info":
            result = get_source_info(**args)
        else:
            result = {"error": f"Unknown tool: {tool_name}"}

        duration = (asyncio.get_event_loop().time() - start_time) * 1000

        tool_outputs.append({
            "tool_name": tool_name,
            "input": args,
            "output": result,
            "duration_ms": duration,
        })

        if "results" in result:
            all_results.extend(result["results"])

    # Build context from results
    search_results = all_results if all_results else []
    context = retriever.build_context(
        [type("R", (), r)() for r in search_results] if search_results else []
    ) if search_results else ""

    # Generate final response with context
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
    ]

    # Add conversation history
    for msg in state["messages"][-5:]:
        if isinstance(msg, HumanMessage):
            messages.append({"role": "user", "content": msg.content})
        elif isinstance(msg, AIMessage):
            messages.append({"role": "assistant", "content": msg.content})

    # Add context and query
    user_msg = state["query"]
    if context:
        user_msg = f"""Based on the following document context, answer the user's question.

DOCUMENT CONTEXT:
{context}

USER QUESTION: {state['query']}

Remember to cite sources using [Source N] format."""

    messages.append({"role": "user", "content": user_msg})

    try:
        response = asyncio.get_event_loop().run_until_complete(
            mistral.chat_completion(messages=messages)
        )
        final_response = response["choices"][0]["message"].get("content", "")
    except Exception as e:
        final_response = f"I found relevant information but encountered an error generating the response: {str(e)}"

    # Build citations
    citations = []
    for i, result in enumerate(search_results[:5]):
        citations.append({
            "document_name": result.get("document_name", ""),
            "page_number": result.get("page_number", 0),
            "chunk_id": result.get("chunk_id", ""),
            "document_id": result.get("document_id", ""),
            "text_snippet": result.get("content", "")[:200],
            "score": result.get("score", 0),
            "citation_index": i + 1,
        })

    return {
        **state,
        "response": final_response,
        "search_results": search_results,
        "citations": citations,
        "tool_executions": tool_outputs,
    }


def chat_agent(state: AgentState) -> AgentState:
    """General chat without document retrieval."""
    mistral = get_mistral_service()

    messages = [
        {"role": "system", "content": "You are DotRAG, a helpful AI assistant. Answer general questions directly and accurately."},
    ]

    for msg in state["messages"][-5:]:
        if isinstance(msg, HumanMessage):
            messages.append({"role": "user", "content": msg.content})
        elif isinstance(msg, AIMessage):
            messages.append({"role": "assistant", "content": msg.content})

    messages.append({"role": "user", "content": state["query"]})

    try:
        import asyncio
        response = asyncio.get_event_loop().run_until_complete(
            mistral.chat_completion(messages=messages)
        )
        return {
            **state,
            "response": response["choices"][0]["message"].get("content", ""),
        }
    except Exception as e:
        return {
            **state,
            "response": f"I encountered an error: {str(e)}",
        }


# Streaming version
async def stream_rag_response(
    query: str,
    document_ids: list[str] = None,
    conversation_history: list[dict] = None,
):
    """Stream RAG response token by token."""
    mistral = get_mistral_service()
    retriever = get_retriever()

    # Yield status updates
    yield {"type": "status", "content": "analyzing query"}

    # Search documents
    yield {"type": "status", "content": "searching documents"}
    results = await retriever.search(query, document_ids=document_ids)
    search_results = [r.__dict__ for r in results] if results else []
    yield {"type": "status", "content": f"retrieved {len(search_results)} chunks"}

    # Build context
    context = retriever.build_context(results) if results else ""

    # Generate response
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    if conversation_history:
        for msg in conversation_history[-5:]:
            messages.append(msg)

    user_msg = query
    if context:
        user_msg = f"""Based on the following document context, answer the user's question.

DOCUMENT CONTEXT:
{context}

USER QUESTION: {query}

Remember to cite sources using [Source N] format."""

    messages.append({"role": "user", "content": user_msg})

    yield {"type": "status", "content": "generating response"}

    # Stream response
    full_response = ""
    async for chunk in mistral.chat_completion_stream(messages=messages):
        full_response += chunk
        yield {"type": "chunk", "content": chunk}

    # Build citations
    citations = []
    for i, result in enumerate(search_results[:5]):
        citations.append({
            "document_name": result.get("document_name", ""),
            "page_number": result.get("page_number", 0),
            "chunk_id": result.get("chunk_id", ""),
            "document_id": result.get("document_id", ""),
            "text_snippet": result.get("content", "")[:200],
            "score": result.get("score", 0),
            "citation_index": i + 1,
        })

    yield {"type": "citations", "content": citations}
    yield {"type": "status", "content": "complete"}
    yield {"type": "done", "content": ""}


def get_agent():
    return create_agent_graph()
