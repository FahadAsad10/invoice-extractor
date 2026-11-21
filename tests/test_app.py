from streamlit.testing.v1 import AppTest


def test_app_renders_samples_without_an_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    at = AppTest.from_file("../app.py", default_timeout=60).run()
    assert not at.exception
    assert at.title[0].value.startswith("🧾 Invoice Extractor")
    metrics = {m.label: m.value for m in at.metric}
    assert metrics["Documents"] == "6"
    assert metrics["Ready to post"] == "3"
    assert any(b.label == "Extract with Claude" and b.disabled for b in at.button)


def test_fixing_a_flagged_invoice_clears_the_error():
    at = AppTest.from_file("../app.py", default_timeout=60).run()
    at.selectbox[0].set_value("brightclean-BC-3391.pdf").run()
    assert any("subtotal" in e.value for e in at.error)
    net = next(n for n in at.number_input if n.label == "Net")
    vat = next(n for n in at.number_input if n.label == "VAT")
    total = next(n for n in at.number_input if n.label == "Total")
    net.set_value(1290.0)
    vat.set_value(258.0)
    total.set_value(1548.0)
    at.button(key="FormSubmitter:edit-brightclean-BC-3391.pdf-Save corrections").click().run()
    assert not at.exception
    assert not any("subtotal" in e.value for e in at.error)
    assert {m.label: m.value for m in at.metric}["Ready to post"] == "4"
