import logging

import google.generativeai as genai
from adalflow.core.types import ModelType
from fastapi import HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    repo_url: str = Field(..., description='URL of the repository to query')
    messages: list[ChatMessage] = Field(..., description='List of chat messages')
    filePath: str | None = Field(None, description='Optional path to a file in the repository to include in the prompt')
    token: str | None = Field(None, description='Personal access token for private repositories')
    type: str | None = Field('github', description="Type of repository (e.g., 'github', 'gitlab', 'bitbucket')")
    provider: str = Field('google', description='Model provider')
    model: str | None = Field(None, description='Model name for the specified provider')
    language: str | None = Field('en', description='Language for content generation')
    excluded_dirs: str | None = Field(None, description='Directories to exclude')
    excluded_files: str | None = Field(None, description='Files to exclude')
    included_dirs: str | None = Field(None, description='Directories to include')
    included_files: str | None = Field(None, description='Files to include')
    wiki_task: str | None = Field(None, description='Optional wiki generation mode: structure or page')
    wiki_page_title: str | None = Field(None, description='Wiki page title when wiki_task=page')
    wiki_file_paths: list[str] | None = Field(None, description='Relevant wiki file paths when wiki_task=page')
    wiki_file_tree: str | None = Field(None, description='Repository file tree when wiki_task=structure')
    wiki_readme: str | None = Field(None, description='Repository README when wiki_task=structure')
    wiki_is_comprehensive: bool | None = Field(None, description='Whether structure generation should be comprehensive')


async def handle_websocket_chat(websocket: WebSocket):
    await websocket.accept()
    try:
        request_data = await websocket.receive_json()
        request = ChatCompletionRequest(**request_data)
        model, api_kwargs, prompt = await build_chat_runtime(request)

        if request.provider == 'google':
            generation = await genai.GenerativeModel(
                model_name=request.model,
                system_instruction=''
            ).generate_content_async(prompt, stream=True)
            async for chunk in generation:
                if getattr(chunk, 'text', None):
                    await websocket.send_text(chunk.text)
            await websocket.close()
            return

        if request.provider in {'ollama', 'openrouter', 'openai', 'minimax', 'azure', 'dashscope'}:
            async for chunk in model.astream(api_kwargs=api_kwargs, model_type=ModelType.LLM):
                text = getattr(chunk, 'raw_response', None)
                if isinstance(text, str) and text:
                    await websocket.send_text(text)
                elif isinstance(chunk, str) and chunk:
                    await websocket.send_text(chunk)
            await websocket.close()
            return

        if request.provider == 'bedrock':
            async for chunk in model.astream(api_kwargs=api_kwargs, model_type=ModelType.LLM):
                text = model.extract_text_delta(chunk)
                if text:
                    await websocket.send_text(text)
            await websocket.close()
            return

        raise HTTPException(status_code=400, detail=f'Unsupported provider: {request.provider}')
    except WebSocketDisconnect:
        logger.info('WebSocket client disconnected')
    except ValueError as error:
        await websocket.send_text(f'Error: {error}')
        await websocket.close()
    except HTTPException as error:
        await websocket.send_text(f'Error: {error.detail}')
        await websocket.close()
    except Exception as error:
        logger.error(f'Error in handle_websocket_chat: {error}', exc_info=True)
        await websocket.send_text(f'Error: {error}')
        await websocket.close()
