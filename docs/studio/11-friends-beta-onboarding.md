# Friends Beta onboarding kit

## Invite message draft

Hi! I’m opening a small Friends Beta for Storyteller, an AI text-quest demo where you start an interactive story from any setting and then type what you do next.

If you’d like to try it:

1. Open the beta link Max sends you.
2. Sign in with the email address Max invited.
3. Start a quest with a setting like “rainy cyberpunk bazaar on Mars before curfew” or “1920s Cairo museum mystery.”
4. Send in-app feedback whenever something breaks, feels confusing, or gives you an idea.

This is an early beta, so rough edges are expected. Please do not share the link publicly yet.

Contact/privacy channel: **TODO(Max approval): confirm the preferred Max contact/privacy channel before sending invites.**

## PWA install instructions

### iPhone / iPad Safari

1. Open the Storyteller beta link in Safari.
2. Tap the Share button.
3. Tap **Add to Home Screen**.
4. Keep the default name “Storyteller” and tap **Add**.
5. Launch Storyteller from the new home-screen icon.

### Android Chrome

1. Open the Storyteller beta link in Chrome.
2. Tap the browser menu.
3. Tap **Install app** or **Add to Home screen**.
4. Confirm the install.
5. Launch Storyteller from the app icon.

### Desktop Chrome / Edge

1. Open the Storyteller beta link.
2. Click the install icon in the address bar, or open the browser menu and choose **Install Storyteller**.
3. Confirm the install.

Storyteller still needs an internet connection and model-provider access while playing.

## Known limitations

- The beta is invite-only and may be unavailable if invite, cost, or quota limits are reached.
- Starting a new quest and resolving turns can take time while AI models research and narrate.
- The app is online-first; offline launch may show cached shell UI, but gameplay requires the server.
- Narration, facts, and character behavior can be inconsistent or wrong.
- Long games may expose memory, continuity, or pacing issues.
- The UI is intentionally lightweight and may lack polish on some mobile browsers.
- Story content is AI-generated and may include surprising or unwanted material.

## Lightweight privacy / beta disclaimer

Storyteller is an experimental Friends Beta. The app stores account identity, email, game/session metadata, story state, prompts/responses needed to run the game, usage/cost logs, and any feedback you submit. AI requests and relevant gameplay context are sent to configured model providers so the game can generate scenes and responses. Max/Hermes may review logs, feedback, prompts, responses, and game/session metadata to debug issues, control beta costs, improve product quality, and monitor safety.

Do not enter sensitive personal information, secrets, credentials, private health/financial details, or anything you would not want reviewed by the beta operator. AI-generated output may be inaccurate or inappropriate. Access may be changed, paused, or removed during the beta. You can ask Max to delete your account/game data during the beta using the approved contact/privacy channel below.

Contact/privacy channel: **TODO(Max approval): add approved contact/privacy email or form before distribution.**

## Feedback instructions

Use **Send beta feedback** in the game screen whenever you notice something useful. Pick the closest category:

- **Bug** — something broke, repeated, disappeared, or behaved incorrectly.
- **Confusing moment** — you were not sure what happened or what to do next.
- **Idea** — a feature or improvement request.
- **Praise** — something worked especially well.
- **Other** — anything else.

Good feedback includes what you tried, what happened, and what you expected. In-app feedback automatically attaches your account, email when available, game id, current turn number when available, category, message, and timestamp.


## Admin feedback review / export

Use the admin dashboard during the Friends Beta to turn tester reports into GTD follow-up work:

1. Open the Storyteller admin dashboard with the configured admin credentials.
2. Review the **Beta Feedback** panel for recent reports. Each row includes timestamp, tester email when available, user id, game id, session id, turn number, category, setting, and message.
3. Export `/api/admin/beta/feedback.csv` when you want offline triage. The CSV is intended for spreadsheet review and formula-like user text is neutralised before export.
4. Convert actionable reports into GitHub issues with reproduction notes, affected game/session id, expected behavior, actual behavior, priority, and whether the fix is player-visible.
5. For privacy, do not paste raw tester emails, user ids, session ids, or story transcripts into public channels. Use private GitHub issues/PRs or redacted summaries.

Suggested GTD buckets:

- **Fix now** — blocks login, starting/continuing games, safe quota behavior, or basic feedback submission.
- **Beta polish** — confusing UX, install friction, copy tweaks, mobile layout bugs.
- **Narrative quality** — continuity, pacing, factuality, character behavior, or content-safety concerns.
- **Later** — ideas that are useful but not required for Friends Beta operations.
