from api.chat_runtime import build_context_text_for_query


class _FakeRAGReturnsTuple:
    def __call__(self, query, language='en'):
        return ('error', [])


def test_build_context_text_for_query_handles_tuple_error_shape():
    context = build_context_text_for_query(
        rag=_FakeRAGReturnsTuple(),
        query='wiki structure',
        language='zh',
        input_too_large=False,
        file_path=None,
    )

    assert context == ''
