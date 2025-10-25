# Alto

## How to call the agents

- Endpoint: `POST http://localhost:8080/orchestrate/plan`
- Request/Response schema: see `docs/CONTRACTS.md`
- Test payload: `services/agents/app/sample_payload.json`
- We return a `plan` with `changes[]`, `metrics{}`, `explain[]` you can animate.