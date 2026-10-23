import json

from backend import agents, db


class MockProvider(agents.ModelProvider):
    provider = "MOCK"
    model = "farmtwin-test"

    def __init__(self, role_payload=None):
        self.role_payload = role_payload or {"roles": ["Production", "Finance", "Pricing", "Sales"], "reason": "test"}
        self.calls = 0

    def status(self):
        return {"available": True, "provider": self.provider, "model": self.model, "message": "Test provider"}

    def complete(self, messages, *, max_output_tokens=agents.MAX_OUTPUT_TOKENS):
        self.calls += 1
        if self.calls == 1:
            text = json.dumps(self.role_payload)
        else:
            text = "Evidence-backed test synthesis; all values come from deterministic tools."
        return agents.ModelResult(text, self.provider, self.model,
                                  {"input_tokens": 10, "cached_input_tokens": 2,
                                   "output_tokens": 8, "reasoning_tokens": None,
                                   "total_tokens": 18}, 1.5)


def test_mock_agent_persists_calls_tools_and_usage():
    db.seed_database()
    provider = MockProvider()
    result = agents.run_agent("Review tomato economics and suitable buyers", provider)

    assert result["status"] == "COMPLETED"
    assert result["real_model_run"] is True
    assert result["agents"] == ["Production", "Finance", "Pricing", "Sales"]
    assert len(result["calls"]) == 2
    assert len(result["tool_events"]) >= 4
    assert sum(call["total_tokens"] for call in result["calls"]) == 36
    exported = agents.get_run(result["run_id"])
    assert exported["final_response"]


def test_invalid_role_json_is_bounded_error():
    class InvalidProvider(MockProvider):
        def complete(self, messages, *, max_output_tokens=agents.MAX_OUTPUT_TOKENS):
            return agents.ModelResult("not json", self.provider, self.model, {}, 1)

    db.seed_database()
    result = agents.run_agent("Run a farm review", InvalidProvider())
    assert result["status"] == "ERROR"
    assert "JSON" in result["warnings"][0]
    assert result["final_response"] is None


def test_no_key_provider_does_not_fabricate_answer():
    db.seed_database()
    result = agents.run_agent("What is the tomato unit cost?", agents.ModelProvider())
    assert result["status"] == "UNAVAILABLE"
    assert result["real_model_run"] is False
    assert result["final_response"] is None
    assert result["calls"][0]["status"] == "ERROR"
    assert result["calls"][0]["input_tokens"] is None
    assert result["tool_events"][0]["status"] == "BLOCKED"
    assert result["tool_events"][0]["tool_name"] == "model_provider:ROLE_SELECTION"


def test_registry_is_allowlisted_and_read_only():
    registry = agents.tool_registry()
    assert registry
    assert all(item["mutating"] is False for item in registry.values())
    assert "execute_python" not in registry
    assert all(item["input_schema"]["additionalProperties"] is False for item in registry.values())


def test_token_budget_stops_malformed_or_expensive_provider():
    class ExpensiveProvider(MockProvider):
        def complete(self, messages, *, max_output_tokens=agents.MAX_OUTPUT_TOKENS):
            result = super().complete(messages, max_output_tokens=max_output_tokens)
            result.usage["total_tokens"] = agents.MAX_TOTAL_TOKENS + 1
            return result

    db.seed_database()
    result = agents.run_agent("Run a bounded farm review", ExpensiveProvider())
    assert result["status"] == "ERROR"
    assert "Token budget" in result["warnings"][0]
