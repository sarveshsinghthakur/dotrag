import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from app.models import (
    ChatRequest, ChatResponse, Message, MessageRole,
    Conversation, Citation, DocumentScope,
)
from app.services.database import get_db
from app.services.mistral import get_mistral_service
from app.retrieval.retriever import get_retriever

router = APIRouter(prefix="/api/chat", tags=["chat"])

SYSTEM_PROMPT = """You are DotRAG, an intelligent document research assistant.

CORE RULES:
1. When document context is provided, use it as your PRIMARY source.
2. Do not invent facts not supported by retrieved context.
3. Cite every important document-derived claim using [Source N] format.
4. If the information is NOT in the documents, say so explicitly — never guess.
5. Never fabricate page numbers or source references.
6. Preserve document-specific terminology.
7. Distinguish between document facts and general knowledge.
8. Be concise unless the user requests detail.
9. For general-knowledge questions unrelated to documents, answer directly.
10. When comparing documents, present a structured comparison.

IMPORTANT: If no relevant context is found but documents are available, tell the user
you couldn't find a matching section and suggest rephrasing their question."""


def _resolve_doc_ids_for_chat(
    db,
    provided_doc_ids: list[str],
    conversation_id: str | None,
) -> list[str]:
    """Return the correct set of document IDs to search for a given chat.

    Priority:
    1. If caller explicitly supplies doc IDs, use those (already scoped by frontend).
    2. Otherwise, include LIBRARY docs + this chat's CHAT-scoped docs.
    3. Fall back to all ready LIBRARY docs if no conversation_id.
    """
    if provided_doc_ids:
        return provided_doc_ids

    if conversation_id:
        docs = db.list_documents_for_chat(conversation_id)
    else:
        docs = db.list_library_documents()

    return [d.id for d in docs if d.status == "ready"]


# ─── Non-streaming endpoint ────────────────────────────────────────────────────

@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest):
    db = get_db()

    # Get or create conversation
    conversation = None
    if request.conversation_id:
        conversation = db.get_conversation(request.conversation_id)

    if not conversation:
        conversation = Conversation(
            document_ids=request.document_ids,
            title=request.message[:50],
        )
        conversation = db.create_conversation(conversation)

    # Save user message
    user_msg = Message(
        conversation_id=conversation.id,
        role=MessageRole.USER,
        content=request.message,
    )
    db.create_message(user_msg)

    # Conversation history (exclude current message)
    history = db.get_messages_by_conversation(conversation.id, limit=10)
    conversation_history = [
        {"role": m.role.value, "content": m.content}
        for m in history[:-1]
    ]

    # Resolve documents for this chat
    doc_ids = _resolve_doc_ids_for_chat(db, request.document_ids, conversation.id)

    context = ""
    search_results = []

    if doc_ids:
        try:
            retriever = get_retriever()
            results = await retriever.search(request.message, document_ids=doc_ids)
            search_results = [r.__dict__ for r in results] if results else []
            if search_results:
                context = retriever.build_context(results)
        except Exception:
            pass

    # Document inventory string
    try:
        all_docs = db.list_documents()
        ready_docs = [d for d in all_docs if d.status == "ready"]
        doc_list = ", ".join([d.filename for d in ready_docs]) if ready_docs else "None"
    except Exception:
        doc_list = "Unknown"

    # Build prompt
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for msg in conversation_history[-5:]:
        messages.append(msg)

    if context:
        user_content = (
            f"DOCUMENT CONTEXT:\n{context}\n\n"
            f"AVAILABLE DOCUMENTS: {doc_list}\n\n"
            f"USER QUESTION: {request.message}\n\n"
            "Cite sources as [Source N]."
        )
    else:
        user_content = (
            f"AVAILABLE DOCUMENTS: {doc_list}\n\n"
            f"USER QUESTION: {request.message}\n\n"
            "No matching document context was retrieved. "
            "If the question is about the documents, say so and suggest the user rephrase. "
            "For general questions, answer directly."
        )

    messages.append({"role": "user", "content": user_content})

    # Call Mistral
    try:
        mistral = get_mistral_service()
        response = await mistral.chat_completion(messages=messages)
        response_text = response["choices"][0]["message"].get("content", "")
    except Exception as e:
        response_text = f"I encountered an error communicating with the AI: {str(e)}"

    # Build citations
    citations = []
    for i, result in enumerate(search_results[:5]):
        citations.append(
            Citation(
                message_id="",
                document_id=result.get("document_id", ""),
                document_name=result.get("document_name", ""),
                page_number=result.get("page_number", 0),
                chunk_id=result.get("chunk_id", ""),
                text_snippet=result.get("content", "")[:200],
                relevance_score=result.get("score", 0),
                citation_index=i + 1,
            )
        )

    assistant_msg = Message(
        conversation_id=conversation.id,
        role=MessageRole.ASSISTANT,
        content=response_text,
        citations=citations,
    )
    db.create_message(assistant_msg)

    if not conversation.title or conversation.title == "New Conversation":
        db.update_conversation(conversation.id, title=request.message[:50])

    return ChatResponse(
        response=response_text,
        conversation_id=conversation.id,
        citations=citations,
        tool_executions=[],
    )


# ─── Streaming endpoint ────────────────────────────────────────────────────────

@router.post("/stream")
async def chat_stream(request: ChatRequest):
    db = get_db()

    conversation = None
    if request.conversation_id:
        conversation = db.get_conversation(request.conversation_id)

    if not conversation:
        conversation = Conversation(
            document_ids=request.document_ids,
            title=request.message[:50],
        )
        conversation = db.create_conversation(conversation)

    user_msg = Message(
        conversation_id=conversation.id,
        role=MessageRole.USER,
        content=request.message,
    )
    db.create_message(user_msg)

    history = db.get_messages_by_conversation(conversation.id, limit=10)
    conversation_history = [
        {"role": m.role.value, "content": m.content}
        for m in history[:-1]
    ]

    # Snapshot for closure
    conv_id = conversation.id
    conv_title = conversation.title

    async def event_generator():
        import json as json_mod

        yield f"data: {json_mod.dumps({'type': 'status', 'content': 'analyzing query'})}\n\n"

        # Resolve documents
        doc_ids = _resolve_doc_ids_for_chat(db, request.document_ids, conv_id)

        context = ""
        search_results = []

        if doc_ids:
            yield f"data: {json_mod.dumps({'type': 'status', 'content': 'searching documents'})}\n\n"
            try:
                retriever = get_retriever()
                results = await retriever.search(request.message, document_ids=doc_ids)
                search_results = [r.__dict__ for r in results] if results else []
                if search_results:
                    context = retriever.build_context(results)
                yield f"data: {json_mod.dumps({'type': 'status', 'content': f'found {len(search_results)} relevant chunks'})}\n\n"
            except Exception as e:
                yield f"data: {json_mod.dumps({'type': 'status', 'content': 'vector search unavailable'})}\n\n"
        else:
            yield f"data: {json_mod.dumps({'type': 'status', 'content': 'no documents in scope'})}\n\n"

        # Document inventory
        try:
            all_docs = db.list_documents()
            ready_docs = [d for d in all_docs if d.status == "ready"]
            doc_list = ", ".join([d.filename for d in ready_docs]) if ready_docs else "None"
        except Exception:
            doc_list = "Unknown"

        # Build messages
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for msg in conversation_history[-5:]:
            messages.append(msg)

        if context:
            user_content = (
                f"DOCUMENT CONTEXT:\n{context}\n\n"
                f"AVAILABLE DOCUMENTS: {doc_list}\n\n"
                f"USER QUESTION: {request.message}\n\n"
                "Cite sources as [Source N]."
            )
        else:
            user_content = (
                f"AVAILABLE DOCUMENTS: {doc_list}\n\n"
                f"USER QUESTION: {request.message}\n\n"
                "No matching document context was retrieved. "
                "If the question is about the documents, say so and suggest the user rephrase. "
                "For general questions, answer directly."
            )

        messages.append({"role": "user", "content": user_content})

        yield f"data: {json_mod.dumps({'type': 'status', 'content': 'generating response'})}\n\n"

        full_response = ""
        try:
            mistral = get_mistral_service()
            async for chunk in mistral.chat_completion_stream(messages=messages):
                full_response += chunk
                yield f"data: {json_mod.dumps({'type': 'chunk', 'content': chunk})}\n\n"
        except Exception as e:
            error_msg = f"Error communicating with AI: {str(e)}"
            full_response = error_msg
            yield f"data: {json_mod.dumps({'type': 'chunk', 'content': error_msg})}\n\n"

        # Citations
        citations_payload = []
        for i, result in enumerate(search_results[:5]):
            citations_payload.append({
                "document_name": result.get("document_name", ""),
                "page_number": result.get("page_number", 0),
                "chunk_id": result.get("chunk_id", ""),
                "document_id": result.get("document_id", ""),
                "text_snippet": result.get("content", "")[:200],
                "score": result.get("score", 0),
                "citation_index": i + 1,
            })

        yield f"data: {json_mod.dumps({'type': 'citations', 'content': citations_payload})}\n\n"

        # Persist assistant message
        citation_models = [
            Citation(
                message_id="",
                document_id=c.get("document_id", ""),
                document_name=c.get("document_name", ""),
                page_number=c.get("page_number", 0),
                chunk_id=c.get("chunk_id", ""),
                text_snippet=c.get("text_snippet", ""),
                relevance_score=c.get("score", 0),
                citation_index=c.get("citation_index", 0),
            )
            for c in citations_payload
        ]

        assistant_msg = Message(
            conversation_id=conv_id,
            role=MessageRole.ASSISTANT,
            content=full_response,
            citations=citation_models,
        )
        db.create_message(assistant_msg)

        if not conv_title or conv_title == "New Conversation":
            db.update_conversation(conv_id, title=request.message[:50])

        yield f"data: {json_mod.dumps({'type': 'conversation_id', 'content': conv_id})}\n\n"
        yield f"data: {json_mod.dumps({'type': 'status', 'content': 'complete'})}\n\n"
        yield f"data: {json_mod.dumps({'type': 'done', 'content': ''})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
