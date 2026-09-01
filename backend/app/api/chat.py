import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from app.models import ChatRequest, ChatResponse, Message, MessageRole, Conversation, Citation
from app.services.database import get_db
from app.services.mistral import get_mistral_service
from app.retrieval.retriever import get_retriever
from app.tools import TOOLS, search_documents, summarize_document, compare_documents, get_source_info

router = APIRouter(prefix="/api/chat", tags=["chat"])

SYSTEM_PROMPT = """You are DotRAG, an intelligent PDF research assistant. You help users search, understand, and analyze their uploaded documents.

CORE RULES:
1. When document context is provided, use it as the primary source for answering questions.
2. Do not invent facts that are not supported by retrieved context.
3. Cite every important document-derived claim using [Source N] format.
4. If the information is not present in the documents, explicitly say that it was not found.
5. Never fabricate page numbers or source references.
6. Preserve document-specific terminology and phrasing.
7. Distinguish between document-derived facts and your general knowledge.
8. Keep answers concise unless the user requests detail.
9. For general knowledge questions (not about documents), answer directly without retrieval.
10. When comparing documents, present a structured comparison.

IMPORTANT: If documents are available but no specific context is provided, you can still help with general questions. Never ask users to upload documents if documents are already uploaded."""


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

    # Get conversation history
    history = db.get_messages_by_conversation(conversation.id, limit=10)
    conversation_history = [
        {"role": m.role.value, "content": m.content}
        for m in history[:-1]
    ]

    # Try to retrieve documents if any are selected
    context = ""
    search_results = []
    
    # Use provided document_ids or get all ready documents
    doc_ids = request.document_ids
    if not doc_ids:
        try:
            all_docs = db.list_documents()
            doc_ids = [d.id for d in all_docs if d.status == "ready"]
        except Exception:
            pass
    
    if doc_ids:
        try:
            retriever = get_retriever()
            results = await retriever.search(request.message, document_ids=doc_ids)
            search_results = [r.__dict__ for r in results] if results else []
            if search_results:
                context = retriever.build_context(results)
        except Exception:
            pass  # Vector DB may not be running

    # Build messages for Mistral
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for msg in conversation_history[-5:]:
        messages.append(msg)

    user_content = request.message
    
    # Get list of available documents
    try:
        all_docs = db.list_documents()
        ready_docs = [d for d in all_docs if d.status == "ready"]
        doc_list = ", ".join([d.filename for d in ready_docs]) if ready_docs else "None"
    except:
        doc_list = "Unknown"
    
    if context:
        user_content = f"""Based on the following document context, answer the user's question.

DOCUMENT CONTEXT:
{context}

AVAILABLE DOCUMENTS: {doc_list}

USER QUESTION: {request.message}

Remember to cite sources using [Source N] format."""
    else:
        # Even without context, inform about available documents
        user_content = f"""AVAILABLE DOCUMENTS: {doc_list}

USER QUESTION: {request.message}

If the user is asking about the documents, let them know the documents are uploaded but you need more specific questions. For general questions, answer directly."""
    
    messages.append({"role": "user", "content": user_content})

    # Call Mistral
    try:
        mistral = get_mistral_service()
        response = await mistral.chat_completion(messages=messages)
        response_text = response["choices"][0]["message"].get("content", "")
    except Exception as e:
        response_text = f"I encountered an error: {str(e)}"

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

    # Save assistant message
    assistant_msg = Message(
        conversation_id=conversation.id,
        role=MessageRole.ASSISTANT,
        content=response_text,
        citations=citations,
    )
    db.create_message(assistant_msg)

    db.update_conversation(
        conversation.id,
        title=request.message[:50] if not conversation.title or conversation.title == "New Conversation" else conversation.title,
    )

    return ChatResponse(
        response=response_text,
        conversation_id=conversation.id,
        citations=citations,
        tool_executions=[],
    )


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

    async def event_generator():
        import json as json_mod

        # Status: analyzing
        yield f"data: {json_mod.dumps({'type': 'status', 'content': 'analyzing query'})}\n\n"

        # Try retrieval
        context = ""
        search_results = []
        
        # Use provided document_ids or get all ready documents
        doc_ids = request.document_ids
        if not doc_ids:
            try:
                all_docs = db.list_documents()
                doc_ids = [d.id for d in all_docs if d.status == "ready"]
            except Exception:
                pass
        
        if doc_ids:
            yield f"data: {json_mod.dumps({'type': 'status', 'content': 'searching documents'})}\n\n"
            try:
                retriever = get_retriever()
                results = await retriever.search(request.message, document_ids=doc_ids)
                search_results = [r.__dict__ for r in results] if results else []
                if search_results:
                    context = retriever.build_context(results)
                yield f"data: {json_mod.dumps({'type': 'status', 'content': f'retrieved {len(search_results)} chunks'})}\n\n"
            except Exception:
                yield f"data: {json_mod.dumps({'type': 'status', 'content': 'vector search unavailable'})}\n\n"

        # Build messages
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for msg in conversation_history[-5:]:
            messages.append(msg)

        user_content = request.message
        
        # Get list of available documents
        try:
            all_docs = db.list_documents()
            ready_docs = [d for d in all_docs if d.status == "ready"]
            doc_list = ", ".join([d.filename for d in ready_docs]) if ready_docs else "None"
        except:
            doc_list = "Unknown"
        
        if context:
            user_content = f"""Based on the following document context, answer the user's question.

DOCUMENT CONTEXT:
{context}

AVAILABLE DOCUMENTS: {doc_list}

USER QUESTION: {request.message}

Remember to cite sources using [Source N] format."""
        else:
            # Even without context, inform about available documents
            user_content = f"""AVAILABLE DOCUMENTS: {doc_list}

USER QUESTION: {request.message}

If the user is asking about the documents, let them know the documents are uploaded but you need more specific questions. For general questions, answer directly."""
        
        messages.append({"role": "user", "content": user_content})

        yield f"data: {json_mod.dumps({'type': 'status', 'content': 'generating response'})}\n\n"

        # Stream from Mistral
        full_response = ""
        try:
            mistral = get_mistral_service()
            async for chunk in mistral.chat_completion_stream(messages=messages):
                full_response += chunk
                yield f"data: {json_mod.dumps({'type': 'chunk', 'content': chunk})}\n\n"
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            full_response = error_msg
            yield f"data: {json_mod.dumps({'type': 'chunk', 'content': error_msg})}\n\n"

        # Citations
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

        yield f"data: {json_mod.dumps({'type': 'citations', 'content': citations})}\n\n"

        # Save message
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
            for c in citations
        ]

        assistant_msg = Message(
            conversation_id=conversation.id,
            role=MessageRole.ASSISTANT,
            content=full_response,
            citations=citation_models,
        )
        db.create_message(assistant_msg)

        db.update_conversation(
            conversation.id,
            title=request.message[:50] if not conversation.title or conversation.title == "New Conversation" else conversation.title,
        )

        yield f"data: {json_mod.dumps({'type': 'conversation_id', 'content': conversation.id})}\n\n"
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
