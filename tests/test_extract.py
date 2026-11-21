import base64
from types import SimpleNamespace

import pytest

from invoice_extractor.extract import MODEL, ExtractionError, content_block, extract, extract_many
from invoice_extractor.samples import SAMPLES
from invoice_extractor.schema import Invoice

INVOICE = SAMPLES[0][1]


class FakeClient:
    """Stands in for anthropic.Anthropic(): records the request, returns a canned parse() response."""

    def __init__(self, stop_reason="end_turn", parsed=INVOICE, fail_on=None):
        self.calls = []
        self.fail_on = fail_on
        self.response = SimpleNamespace(stop_reason=stop_reason, parsed_output=parsed)
        self.beta = SimpleNamespace(messages=SimpleNamespace(parse=self.parse))

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        text = kwargs["messages"][0]["content"][1]["text"]
        if self.fail_on and self.fail_on in text:
            raise RuntimeError("boom")
        return self.response


def test_pdf_becomes_document_block_and_photo_becomes_image_block():
    pdf = content_block(b"%PDF-1.7", "a.PDF")
    assert pdf["type"] == "document" and pdf["source"]["media_type"] == "application/pdf"
    assert base64.b64decode(pdf["source"]["data"]) == b"%PDF-1.7"
    assert content_block(b"x", "r.jpeg")["source"]["media_type"] == "image/jpeg"
    assert content_block(b"x", "r.png")["type"] == "image"
    with pytest.raises(ValueError):
        content_block(b"x", "notes.docx")


def test_request_uses_structured_output_latest_model_and_fallbacks():
    client = FakeClient()
    assert extract(b"%PDF", "inv.pdf", client=client) == INVOICE
    call = client.calls[0]
    assert call["model"] == MODEL == "claude-opus-5-5"
    assert call["output_format"] is Invoice
    assert call["fallbacks"] == "default"
    assert "server-side-fallback-2026-07-01" in call["betas"]
    assert "Never correct the document's arithmetic" in call["system"]


@pytest.mark.parametrize("stop_reason", ["refusal", "max_tokens"])
def test_unusable_responses_raise(stop_reason):
    with pytest.raises(ExtractionError):
        extract(b"x", "r.png", client=FakeClient(stop_reason=stop_reason))


def test_batch_keeps_order_and_isolates_failures():
    client = FakeClient(fail_on="bad.png")
    out = extract_many([("a.pdf", b"1"), ("bad.png", b"2"), ("c.jpg", b"3")], client=client)
    assert [name for name, _, _ in out] == ["a.pdf", "bad.png", "c.jpg"]
    assert out[0][1] == INVOICE and out[0][2] is None
    assert out[1][1] is None and "boom" in out[1][2]
    assert out[2][1] == INVOICE


def test_schema_is_accepted_by_structured_outputs():
    """Structured outputs need a closed JSON schema; every field must be typed."""
    schema = Invoice.model_json_schema()
    assert {"vendor_name", "currency", "line_items", "total"} <= set(schema["required"])
    assert schema["$defs"]["LineItem"]["required"] == ["description", "amount"]
