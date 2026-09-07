from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_retriever_finds_drainage_guidance():
    from app.insights.retriever import get_retriever

    hits = get_retriever().retrieve("urban drainage storm drains Karachi Hyderabad", top_k=4)
    assert hits
    headings = " ".join(h["heading"] for h in hits).lower()
    assert "drainage" in headings


def test_insights_hyderabad_template_fallback():
    resp = client.get("/api/insights/hyderabad")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Hyderabad"
    assert data["explanation_source"] in {"template", "llm"}
    assert "Hyderabad" in data["explanation"]
    assert data["recommendations"], "expected evidence-grounded recommendations"
    for rec in data["recommendations"]:
        assert rec["action"] and rec["source"]
    assert data["retrieved"], "expected retrieved sources"
    assert data["inputs_are_demo"] is True


def test_insights_unknown_zone_404():
    assert client.get("/api/insights/atlantis").status_code == 404
