"""Unit tests for the Rule Engine — deterministic pattern matching."""


from src.rules.known_patterns import match_rule


class TestRuleMatching:
    def test_matches_error_504_licensing(self):
        result = match_rule(error_codes=["504"], keywords=["error"], category="licensing")
        assert result is not None
        assert result.rule_id == "ERR_504_LICENSE"
        assert result.confidence == 0.95

    def test_no_match_error_504_wrong_category(self):
        result = match_rule(error_codes=["504"], keywords=["error"], category="installation")
        assert result is None

    def test_matches_offline_license(self):
        result = match_rule(error_codes=[], keywords=["offline", "license"], category="licensing")
        assert result is not None
        assert result.rule_id == "OFFLINE_LICENSE_ACTIVATION"

    def test_offline_rule_requires_no_error_codes(self):
        result = match_rule(error_codes=["504"], keywords=["offline", "license"], category="licensing")
        assert result is not None
        assert result.rule_id == "ERR_504_LICENSE"  # Error code rule takes priority (first match)

    def test_no_match_unknown_category(self):
        result = match_rule(error_codes=[], keywords=["crash"], category="unknown")
        assert result is None

    def test_no_match_empty_signals(self):
        result = match_rule(error_codes=[], keywords=[], category="licensing")
        assert result is None

    def test_no_match_installation_no_rules(self):
        result = match_rule(error_codes=[], keywords=["installation"], category="installation")
        assert result is None

    def test_rule_match_has_expected_sources(self):
        result = match_rule(error_codes=["504"], keywords=[], category="licensing")
        assert result is not None
        assert "Common_Errors.md" in result.expected_sources

    def test_rule_match_has_reasoning(self):
        result = match_rule(error_codes=["504"], keywords=[], category="licensing")
        assert result is not None
        assert len(result.reasoning) > 0
