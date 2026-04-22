import logging

import google.generativeai as genai
from adalflow.core.types import ModelType
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

app = FastAPI(
    title='Simple Chat API',
    description='Simplified API for streaming chat completions',
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


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


@app.post('/chat/completions/stream')
async def chat_completions_stream(request: ChatCompletionRequest):
    try:
        model, api_kwargs, prompt = await build_chat_runtime(request)

        async def response_stream():
            try:
                if request.provider == 'google':
                    generation = await genai.GenerativeModel(
                        model_name=request.model,
                        system_instruction=''
                    ).generate_content_async(prompt, stream=True)
                    async for chunk in generation:
                        if getattr(chunk, 'text', None):
                            yield chunk.text
                    return

                if request.provider in {'ollama', 'openrouter', 'openai', 'minimax', 'azure', 'dashscope'}:
                    async for chunk in model.astream(api_kwargs=api_kwargs, model_type=ModelType.LLM):
                        text = getattr(chunk, 'raw_response', None)
                        if isinstance(text, str) and text:
                            yield text
                        elif isinstance(chunk, str) and chunk:
                            yield chunk
                    return

                if request.provider == 'bedrock':
                    async for chunk in model.astream(api_kwargs=api_kwargs, model_type=ModelType.LLM):
                        text = model.extract_text_delta(chunk)
                        if text:
                            yield text
                    return

                raise HTTPException(status_code=400, detail=f'Unsupported provider: {request.provider}')
            except Exception as error:
                logger.error(f'Streaming error: {error}', exc_info=True)
                yield f'Error: {error}'

        return StreamingResponse(response_stream(), media_type='text/event-stream')
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except HTTPException:
        raise
    except Exception as error:
        logger.error(f'Error in chat_completions_stream: {error}', exc_info=True)
        raise HTTPException(status_code=500, detail=f'Error preparing chat runtime: {error}') from error
