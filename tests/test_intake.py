"""Unit tests for the Intake Executor — parsing, sanitization, signal extraction."""


from src.executors.intake import process_ticket
from src.models.ticket import TicketInput, TicketMetadata


class TestIntakeBasicParsing:
    def test_parses_valid_ticket(self):
        ticket = TicketInput(
            ticket_id="T-100",
            text="Application fails to start after update. Error 504 appears.",
            metadata=TicketMetadata(product="WSCAD Suite", version="2.3", os="Windows 11"),
        )
        result = process_ticket(ticket)

        assert result.ticket_id == "T-100"
        assert result.sanitized_text  # not empty
        assert result.metadata.product == "WSCAD Suite"
        assert result.injection_detected is False

    def test_preserves_original_text(self):
        original = "  Some text with  spaces  "
        ticket = TicketInput(ticket_id="T-101", text=original)
        result = process_ticket(ticket)

        assert result.original_text == original
        assert result.sanitized_text != original  # should be cleaned

    def test_handles_empty_metadata(self):
        ticket = TicketInput(ticket_id="T-102", text="Something broke")
        result = process_ticket(ticket)

        assert result.metadata.product is None
        assert result.metadata.version is None
        assert result.metadata.os is None


class TestIntakeErrorCodeExtraction:
    def test_extracts_error_504(self):
        ticket = TicketInput(ticket_id="T-200", text="Error 504 after update")
        result = process_ticket(ticket)

        assert "504" in result.extracted_error_codes

    def test_extracts_multiple_error_codes(self):
        ticket = TicketInput(ticket_id="T-201", text="Got error 504 and then error 1023")
        result = process_ticket(ticket)

        assert "504" in result.extracted_error_codes
        assert "1023" in result.extracted_error_codes

    def test_no_error_codes_when_none_present(self):
        ticket = TicketInput(ticket_id="T-202", text="The application crashes")
        result = process_ticket(ticket)

        assert result.extracted_error_codes == []


class TestIntakeKeywordExtraction:
    def test_extracts_license_keywords(self):
        ticket = TicketInput(ticket_id="T-300", text="My license has expired")
        result = process_ticket(ticket)

        assert "license" in result.extracted_keywords

    def test_extracts_installation_keywords(self):
        ticket = TicketInput(ticket_id="T-301", text="Installation failed on Windows")
        result = process_ticket(ticket)

        assert "installation" in result.extracted_keywords

    def test_extracts_crash_keywords(self):
        ticket = TicketInput(ticket_id="T-302", text="The app crashes when opening a project")
        result = process_ticket(ticket)

        assert "crash" in result.extracted_keywords

    def test_extracts_offline_keywords(self):
        ticket = TicketInput(ticket_id="T-303", text="Machine has no internet, need offline license")
        result = process_ticket(ticket)

        assert "offline" in result.extracted_keywords
        assert "license" in result.extracted_keywords


class TestIntakeSanitization:
    def test_strips_html_tags(self):
        ticket = TicketInput(ticket_id="T-400", text="<b>Error</b> <script>alert(1)</script> happened")
        result = process_ticket(ticket)

        assert "<b>" not in result.sanitized_text
        assert "<script>" not in result.sanitized_text

    def test_truncates_long_text(self):
        long_text = "A" * 5000
        ticket = TicketInput(ticket_id="T-401", text=long_text)
        result = process_ticket(ticket)

        assert len(result.sanitized_text) <= 2000
        assert any("truncated" in w.lower() for w in result.validation_warnings)

    def test_handles_empty_text(self):
        ticket = TicketInput(ticket_id="T-402", text="   ")
        result = process_ticket(ticket)

        assert any("empty" in w.lower() for w in result.validation_warnings)
