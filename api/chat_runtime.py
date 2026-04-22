import logging
from dataclasses import dataclass
from typing import Any, Optional
from urllib.parse import unquote

from adalflow.components.model_client.ollama_client import OllamaClient
from adalflow.core.types import ModelType

from api.azureai_client import AzureAIClient
from api.bedrock_client import BedrockClient
from api.config import (
    AWS_ACCESS_KEY_ID,
    AWS_SECRET_ACCESS_KEY,
    MINIMAX_API_KEY,
    MINIMAX_BASE_URL,
    OPENAI_API_KEY,
    OPENROUTER_API_KEY,
    build_minimax_request_kwargs,
    configs,
    get_model_config,
)
from api.dashscope_client import DashscopeClient
from api.data_pipeline import count_tokens, get_file_content
from api.openai_client import OpenAIClient
from api.openrouter_client import OpenRouterClient
from api.prompts import (
    DEEP_RESEARCH_FINAL_ITERATION_PROMPT,
    DEEP_RESEARCH_FIRST_ITERATION_PROMPT,
    DEEP_RESEARCH_INTERMEDIATE_ITERATION_PROMPT,
    SIMPLE_CHAT_SYSTEM_PROMPT,
)
from api.rag import RAG
from api.wiki_generation import (
    build_context_text,
    build_shared_page_prompt,
    build_shared_structure_prompt,
)

logger = logging.getLogger(__name__)


@dataclass
class PreparedChatContext:
    rag: RAG
    input_too_large: bool
    repo_url: str
    repo_type: str
    language_code: str
    language_name: str


async def prepare_chat_context(request: Any) -> PreparedChatContext:
    input_too_large = False
    if request.messages and len(request.messages) > 0:
        last_message = request.messages[-1]
        if hasattr(last_message, 'content') and last_message.content:
            tokens = count_tokens(last_message.content, request.provider == 'ollama')
            logger.info(f"Request size: {tokens} tokens")
            if tokens > 8000:
                logger.warning(f"Request exceeds recommended token limit ({tokens} > 7500)")
                input_too_large = True

    request_rag = RAG(provider=request.provider, model=request.model)

    excluded_dirs = _split_multiline(request.excluded_dirs)
    excluded_files = _split_multiline(request.excluded_files)
    included_dirs = _split_multiline(request.included_dirs)
    included_files = _split_multiline(request.included_files)

    request_rag.prepare_retriever(
        request.repo_url,
        request.type,
        request.token,
        excluded_dirs,
        excluded_files,
        included_dirs,
        included_files,
    )

    language_code = request.language or configs['lang_config']['default']
    supported_langs = configs['lang_config']['supported_languages']
    language_name = supported_langs.get(language_code, 'English')

    return PreparedChatContext(
        rag=request_rag,
        input_too_large=input_too_large,
        repo_url=request.repo_url,
        repo_type=request.type,
        language_code=language_code,
        language_name=language_name,
    )


def apply_conversation_history(request: Any, rag: RAG) -> None:
    for index in range(0, len(request.messages) - 1, 2):
        if index + 1 < len(request.messages):
            user_msg = request.messages[index]
            assistant_msg = request.messages[index + 1]
            if user_msg.role == 'user' and assistant_msg.role == 'assistant':
                rag.memory.add_dialog_turn(
                    user_query=user_msg.content,
                    assistant_response=assistant_msg.content,
                )


def resolve_request_mode(request: Any) -> tuple[bool, int, str]:
    is_deep_research = False
    research_iteration = 1
    last_message = request.messages[-1]

    for msg in request.messages:
        if hasattr(msg, 'content') and msg.content and '[DEEP RESEARCH]' in msg.content:
            is_deep_research = True
            if msg == last_message:
                msg.content = msg.content.replace('[DEEP RESEARCH]', '').strip()

    if is_deep_research:
        research_iteration = sum(1 for msg in request.messages if msg.role == 'assistant') + 1
        if 'continue' in last_message.content.lower() and 'research' in last_message.content.lower():
            for msg in request.messages:
                if msg.role == 'user' and 'continue' not in msg.content.lower():
                    last_message.content = msg.content.replace('[DEEP RESEARCH]', '').strip()
                    break

    return is_deep_research, research_iteration, last_message.content


def build_context_text_for_query(
    rag: RAG,
    query: str,
    language: str,
    input_too_large: bool,
    file_path: Optional[str] = None,
) -> str:
    if input_too_large:
        return ''

    rag_query = f'Contexts related to {file_path}' if file_path else query
    try:
        retrieved_documents = rag(rag_query, language=language)
        if retrieved_documents and retrieved_documents[0].documents:
            documents = [
                {
                    'file_path': doc.meta_data.get('file_path', 'unknown'),
                    'text': doc.text,
                }
                for doc in retrieved_documents[0].documents
                if hasattr(doc, 'meta_data') and hasattr(doc, 'text')
            ]
            logger.info(f"Retrieved {len(documents)} documents")
            return build_context_text(documents)
    except Exception as error:
        logger.error(f"Error in RAG retrieval: {error}")
    return ''


def build_system_prompt(
    repo_type: str,
    repo_url: str,
    language_name: str,
    is_deep_research: bool,
    research_iteration: int,
) -> str:
    repo_name = repo_url.split('/')[-1] if '/' in repo_url else repo_url
    if not is_deep_research:
        return SIMPLE_CHAT_SYSTEM_PROMPT.format(
            repo_type=repo_type,
            repo_url=repo_url,
            repo_name=repo_name,
            language_name=language_name,
        )
    if research_iteration == 1:
        return DEEP_RESEARCH_FIRST_ITERATION_PROMPT.format(
            repo_type=repo_type,
            repo_url=repo_url,
            repo_name=repo_name,
            language_name=language_name,
        )
    if research_iteration >= 5:
        return DEEP_RESEARCH_FINAL_ITERATION_PROMPT.format(
            repo_type=repo_type,
            repo_url=repo_url,
            repo_name=repo_name,
            research_iteration=research_iteration,
            language_name=language_name,
        )
    return DEEP_RESEARCH_INTERMEDIATE_ITERATION_PROMPT.format(
        repo_type=repo_type,
        repo_url=repo_url,
        repo_name=repo_name,
        research_iteration=research_iteration,
        language_name=language_name,
    )


def build_prompt(
    rag: RAG,
    system_prompt: str,
    query: str,
    context_text: str,
    file_content: str = '',
    file_path: Optional[str] = None,
) -> str:
    conversation_history = ''
    for turn_id, turn in rag.memory().items():
        if not isinstance(turn_id, int) and hasattr(turn, 'user_query') and hasattr(turn, 'assistant_response'):
            conversation_history += (
                f"<turn>\n<user>{turn.user_query.query_str}</user>\n"
                f"<assistant>{turn.assistant_response.response_str}</assistant>\n</turn>\n"
            )

    prompt = f"/no_think {system_prompt}\n\n"
    if conversation_history:
        prompt += f"<conversation_history>\n{conversation_history}</conversation_history>\n\n"
    if file_content and file_path:
        prompt += f"<currentFileContent path=\"{file_path}\">\n{file_content}\n</currentFileContent>\n\n"
    if context_text.strip():
        prompt += f"<START_OF_CONTEXT>\n{context_text}\n<END_OF_CONTEXT>\n\n"
    else:
        prompt += '<note>Answering without retrieval augmentation.</note>\n\n'
    prompt += f"<query>\n{query}\n</query>\n\nAssistant: "
    return prompt


async def create_model_call(request: Any, prompt: str) -> tuple[Any, dict[str, Any]]:
    model_config = get_model_config(request.provider, request.model)['model_kwargs']

    if request.provider == 'ollama':
        prompt += ' /no_think'
        model = OllamaClient()
        model_kwargs = {
            'model': model_config['model'],
            'stream': True,
            'options': {
                'temperature': model_config['temperature'],
                'top_p': model_config['top_p'],
                'num_ctx': model_config['num_ctx'],
            },
        }
        api_kwargs = model.convert_inputs_to_api_kwargs(input=prompt, model_kwargs=model_kwargs, model_type=ModelType.LLM)
        return model, api_kwargs

    if request.provider == 'openrouter':
        if not OPENROUTER_API_KEY:
            logger.warning('OPENROUTER_API_KEY not configured, but continuing with request')
        model = OpenRouterClient()
        model_kwargs = {'model': request.model, 'stream': True, 'temperature': model_config['temperature']}
        if 'top_p' in model_config:
            model_kwargs['top_p'] = model_config['top_p']
        api_kwargs = model.convert_inputs_to_api_kwargs(input=prompt, model_kwargs=model_kwargs, model_type=ModelType.LLM)
        return model, api_kwargs

    if request.provider == 'openai':
        if not OPENAI_API_KEY:
            logger.warning('OPENAI_API_KEY not configured, but continuing with request')
        model = OpenAIClient()
        model_kwargs = {'model': request.model, 'stream': True, 'temperature': model_config['temperature']}
        if 'top_p' in model_config:
            model_kwargs['top_p'] = model_config['top_p']
        api_kwargs = model.convert_inputs_to_api_kwargs(input=prompt, model_kwargs=model_kwargs, model_type=ModelType.LLM)
        return model, api_kwargs

    if request.provider == 'minimax':
        model = OpenAIClient(api_key=MINIMAX_API_KEY, base_url=MINIMAX_BASE_URL)
        model_kwargs = build_minimax_request_kwargs(model=request.model, model_config=model_config, stream=True)
        api_kwargs = model.convert_inputs_to_api_kwargs(input=prompt, model_kwargs=model_kwargs, model_type=ModelType.LLM)
        return model, api_kwargs

    if request.provider == 'bedrock':
        if not AWS_ACCESS_KEY_ID or not AWS_SECRET_ACCESS_KEY:
            logger.warning('AWS credentials not configured, but continuing with request')
        model = BedrockClient()
        model_kwargs = {'model': request.model, 'temperature': model_config['temperature'], 'top_p': model_config['top_p']}
        api_kwargs = model.convert_inputs_to_api_kwargs(input=prompt, model_kwargs=model_kwargs, model_type=ModelType.LLM)
        return model, api_kwargs

    if request.provider == 'azure':
        model = AzureAIClient()
        model_kwargs = {'model': request.model, 'stream': True, 'temperature': model_config['temperature'], 'top_p': model_config['top_p']}
        api_kwargs = model.convert_inputs_to_api_kwargs(input=prompt, model_kwargs=model_kwargs, model_type=ModelType.LLM)
        return model, api_kwargs

    if request.provider == 'dashscope':
        model = DashscopeClient()
        model_kwargs = {'model': request.model, 'stream': True, 'temperature': model_config['temperature'], 'top_p': model_config['top_p']}
        api_kwargs = model.convert_inputs_to_api_kwargs(input=prompt, model_kwargs=model_kwargs, model_type=ModelType.LLM)
        return model, api_kwargs

    raise HTTPException(status_code=400, detail=f'Unsupported provider: {request.provider}')


async def build_chat_runtime(request: Any) -> tuple[Any, dict[str, Any], str]:
    if not request.messages or len(request.messages) == 0:
        raise ValueError('No messages provided')
    last_message = request.messages[-1]
    if last_message.role != 'user':
        raise ValueError('Last message must be from the user')

    prepared = await prepare_chat_context(request)
    apply_conversation_history(request, prepared.rag)
    is_deep_research, research_iteration, query = resolve_request_mode(request)
    context_text = build_context_text_for_query(
        prepared.rag,
        query,
        request.language,
        prepared.input_too_large,
        request.filePath,
    )
    file_content = ''
    if request.filePath:
        try:
            file_content = get_file_content(request.repo_url, request.filePath, request.type, request.token)
        except Exception as error:
            logger.error(f'Error retrieving file content: {error}')

    if getattr(request, 'wiki_task', None) == 'structure':
        query = build_shared_structure_prompt(
            owner=request.repo_url.rstrip('/').split('/')[-2] if '/' in request.repo_url else '',
            repo=request.repo_url.rstrip('/').split('/')[-1] if '/' in request.repo_url else request.repo_url,
            repo_files=(request.wiki_file_tree or '').splitlines(),
            readme=request.wiki_readme or '',
            language=request.language,
            is_comprehensive=bool(request.wiki_is_comprehensive),
        )
        context_text = ''
        file_content = ''
    elif getattr(request, 'wiki_task', None) == 'page':
        query = build_shared_page_prompt(
            page_title=request.wiki_page_title or 'Wiki Page',
            file_paths=request.wiki_file_paths or [],
            language=request.language,
            repo_url=request.repo_url,
            default_branch='main',
            file_contents=None,
        )

    system_prompt = build_system_prompt(
        prepared.repo_type,
        prepared.repo_url,
        prepared.language_name,
        is_deep_research,
        research_iteration,
    )
    prompt = build_prompt(prepared.rag, system_prompt, query, context_text, file_content, request.filePath)
    model, api_kwargs = await create_model_call(request, prompt)
    return model, api_kwargs, prompt


async def run_chat_once(request: Any) -> str:
    model, api_kwargs, prompt = await build_chat_runtime(request)
    api_kwargs = dict(api_kwargs)
    api_kwargs['stream'] = False

    if request.provider == 'google':
        generation = await genai.GenerativeModel(
            model_name=request.model,
            system_instruction=''
        ).generate_content_async(prompt, stream=False)
        return getattr(generation, 'text', '') or ''

    if request.provider in {'ollama', 'openrouter', 'openai', 'minimax', 'azure', 'dashscope'}:
        response = await model.acall(api_kwargs=api_kwargs, model_type=ModelType.LLM)
        if hasattr(model, 'parse_chat_completion'):
            parsed = model.parse_chat_completion(response)
            if hasattr(parsed, 'raw_response'):
                return parsed.raw_response or ''
            return parsed or ''
        if isinstance(response, str):
            return response
        return getattr(response, 'text', '') or str(response)

    if request.provider == 'bedrock':
        response = await model.acall(api_kwargs=api_kwargs, model_type=ModelType.LLM)
        return model.extract_response_text(response) or ''

    raise ValueError(f'Unsupported provider: {request.provider}')


def _split_multiline(value: Optional[str]) -> Optional[list[str]]:
    if not value:
        return None
    values = [unquote(item) for item in value.split('\n') if item.strip()]
    return values or None
