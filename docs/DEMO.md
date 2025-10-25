# Alto — Agents Demo (90s)

1) Run the service:
   uvicorn services.agents.app.main:app --port 8080 --reload

2) Health:
   curl -s http://localhost:8080/health

3) Plan preview:
   curl -s -X POST http://localhost:8080/orchestrate/plan \
     -H "content-type: application/json" \
     -d @services/agents/app/sample_payload.json | jq .
