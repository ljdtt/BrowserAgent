from src.core.model_adapter import ModelResponseError, QwenModelAdapter


class FakeQwenModel:
    def __init__(self, responses):
        self.responses = responses

    def chat(self, **_kwargs):
        return self.responses


def test_adapter_returns_last_assistant_message():
    model = FakeQwenModel([
        {"role": "assistant", "content": "draft"},
        {"role": "assistant", "content": "", "function_call": {
            "name": "finish", "arguments": '{"success":true,"result":"完成","evidence":[]}'
        }},
    ])

    message = QwenModelAdapter(model=model).next([], [])

    assert message["function_call"]["name"] == "finish"


def test_adapter_rejects_empty_response():
    model = FakeQwenModel([])

    try:
        QwenModelAdapter(model=model).next([], [])
    except ModelResponseError as exc:
        assert str(exc) == "empty model response"
    else:
        raise AssertionError("empty response must fail")
