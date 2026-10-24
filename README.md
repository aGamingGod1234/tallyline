# Tallyline

**Evidence-first grant closeout for small community organizations.**

Tallyline turns an award brief, activity log, finance export, and story notes into a funder-ready closeout draft whose claims stay attached to their evidence. It shows the operator what is supported, what needs review, and what is blocked by consent or missing context. The operator resolves the final decisions; Tallyline does not submit, email, pay, or move money.

This is a synthetic demo for the Agents for Humans Hackathon. No beneficiary data is real. The default path is local and deterministic; the demonstrated live path uses Gemini through Strands with the same bounded tools.

## Run it

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/). Python 3.10 reached end of life in October 2026. CI checks the locked environment on Python 3.11 and 3.15, including macOS on 3.15.

On macOS, double-click `START_TALLYLINE.command`. It installs the locked dependencies, starts the local server, and opens the correct browser URL. Do not double-click `app/static/index.html`: the UI needs the FastAPI server for its CSS, JavaScript, and API.

```bash
uv sync --locked
uv run --locked uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000. The page runs the synthetic case on load. Use the explicit action to replay it, expand a claim to inspect its source note, resolve the three human decisions, and export the Markdown packet.

This is a single-operator local demo. Decisions are held in memory, shared by tabs using the same server, and cleared on reset or server restart. Run one server worker; there is no account system or persistent storage.

Run the test suite (no provider credentials or paid calls required):

```bash
uv sync --locked --extra dev
uv run --locked --extra dev pytest -q
```

## What the demo proves

- The activity pass deduplicates a repeated `event_id` before totaling outputs: 128 households, 124 kits, and 3 workshops.
- Finance totals reconcile to $15,940 against the $18,000 award and stay in the human queue as a $2,060 variance until the operator explains it.
- A non-consented story remains excluded, including after the operator confirms that it should stay private.
- The exported packet retains each resolved human note alongside the remaining questions and evidence index.
- The same state is available through direct JSON APIs: `GET /api/case`, `POST /api/run`, `POST /api/decisions/approve`, `POST /api/reset`, and `GET /api/export`.

## Agent architecture

The default local path is deterministic so a reviewer can inspect the exact behavior without a provider account or model key. `app/agent.py` contains a real Strands `Agent` and two bounded typed tools. Set `TALLYLINE_AGENT_MODE=live` to make `/api/run` perform a live agent pass; the app returns an error rather than labeling a failed call as live. Both tools use a snapshot of the operator's approvals from that run; the model cannot supply approvals through tool arguments. This submission's recorded demo and direct probe use `GeminiModel` with `gemini-2.5-flash` through Strands. The same coordinator can use Amazon Bedrock when AWS credentials, region, and model access are supplied. `app/service.py` owns the evidence ledger and report assembly; a live model only receives the typed evidence operations and returns an advisory readout. Bedrock AgentCore is a compatible hosting path, but it is not claimed as deployed here.

New Gemini runs default to `gemini-3.8-flash`. Google's [model lifecycle guidance](https://ai.google.dev/gemini-api/docs/deprecations) limits 2.5 model access to existing users; the archived hackathon verification used 2.5 Flash. Set `TALLYLINE_MODEL_ID` to override the current default. The modernization tests do not call a paid provider.

Example Gemini live run (model calls may incur cost):

```bash
export GEMINI_API_KEY=YOUR_GEMINI_API_KEY
TALLYLINE_AGENT_MODE=live TALLYLINE_MODEL_PROVIDER=gemini \
  uv run --locked uvicorn app.main:app --host 127.0.0.1 --port 8000
curl -X POST http://127.0.0.1:8000/api/run
```

Example Bedrock live run (use a model enabled in your AWS region; model calls may incur cost):

```bash
TALLYLINE_AGENT_MODE=live AWS_REGION=YOUR_REGION TALLYLINE_MODEL_ID=YOUR_MODEL_ID \
  uv run --locked uvicorn app.main:app --host 127.0.0.1 --port 8000
curl -X POST http://127.0.0.1:8000/api/run
```

See [docs/architecture.svg](docs/architecture.svg) and [docs/submission.md](docs/submission.md).

## Project status and disclosure

The application, fixture data, tests, documentation, and visual direction in this repository were created for this hackathon build during the stated competition window. The underlying idea—evidence-first reporting with human consent boundaries—is the build thesis, not evidence of a deployed product. See the disclosure section in [docs/submission.md](docs/submission.md) for the exact competition wording.

## License

MIT. See [LICENSE](LICENSE).
