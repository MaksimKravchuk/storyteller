# Player Web UI smoke checklist

Purpose: repeatably check that the public player web demo can start a story, accept five player turns, handle an NPC interaction, and avoid exposing raw Python tracebacks to players.

Do not run paid LLM e2e or benchmark suites as part of this smoke unless Max explicitly approves the cost.

## Automated contract smoke

Run the mocked FastAPI smoke before changing or releasing the player web UI:

```bash
uv run pytest tests/test_web_api.py::test_player_web_api_smoke_start_five_turns_and_npc_interaction -v
```

This test covers the HTTP contract without calling LLM providers:

1. `POST /api/games` starts a story.
2. Five sequential `POST /api/games/{game_id}/actions` calls succeed.
3. The scripted turns include talking with an NPC.
4. Responses do not include raw traceback fragments.

## Manual release-candidate smoke

Use this checklist against a local or deployed web UI when preparing the Public Web Demo v0.1 release candidate.

### Setup

1. Start the web UI:
   ```bash
   uv run uvicorn interfaces.web.app:app --reload --host 127.0.0.1 --port 8070
   ```
2. Open `http://localhost:8070` in a clean browser profile or incognito window.
3. Open browser DevTools Console and Network tabs.

### Story start

1. Start a new game with a concise setting, for example `Delft, 1665`.
2. Confirm the UI shows an opening narrator message.
3. Confirm the response is not blank and the Network tab shows a successful start request.

### Five-turn path

Submit these five turns in order, waiting for each response to render before sending the next:

1. `look around`
2. `walk to the tavern`
3. `talk to the nearest person about the missing map`
4. `ask them to describe who they saw`
5. `thank them and wait`

Expected result:

- Every turn returns a player line and narrator response.
- The UI remains interactive after the fifth turn.
- No response is replaced by a server error page or raw JSON error dump.

### NPC interaction

Pass criteria for the NPC turn:

- At least one NPC or clearly described person responds or reacts.
- The response acknowledges the player talking to or asking that person.
- The character/sidebar area remains readable if NPC details are present.

### No raw traceback

Fail the smoke if the page, response body, console, or server log exposes any of these to the player:

- `Traceback (most recent call last)`
- `RuntimeError:`
- `ValueError:`
- `KeyError:`
- `File "...", line ...`
- Python stack frames or unredacted exception dumps

### Evidence to capture

For a release-candidate run, record:

- commit SHA or PR number
- environment URL
- browser and OS
- whether all five turns passed
- any screenshots or copied console/server errors for failures
