# End-to-end user flow testing

[Back to the README](../../README.md)

This is the plan for testing Adventure the way a player uses it: a real browser clicking through the built interface, talking to the real backend, with every model call answered by a script. Nothing here is built yet; [Build order](#build-order) says what comes first.

## What each kind of test covers

| Kind | Where | What it proves |
| --- | --- | --- |
| Backend tests | `tests/`, pytest | Routes, the round engine, rules, privacy fences and prompts, through the API with a fake model |
| Interface logic | `tests/ui/`, Node's test runner | Pure `.ts` modules: turn grouping, drafts, text helpers |
| Install and package jobs | `ci.yml`, `package.yml` | The installers, the launcher, the bundle and the setup start and answer on 8805 |
| End-to-end flows (new) | `e2e/`, pytest and Playwright | The screens, streams and the turn state machine hold together for a player, from the first click to a committed round |

End-to-end tests do not repeat what the others prove. A rule's maths, a prompt's wording or an installer's paths belong in their own tests; an end-to-end test checks that a player can get from one screen to the next and sees the right thing on the way.

## Decisions

| Question | Choice |
| --- | --- |
| Browser driver | Playwright for Python, run by pytest, Chromium only |
| Model calls | Scripted fake models in CI; a live run with a real model by hand before each release |
| Where in CI | Linux on every pull request; Windows on every push to `main` and in the `Release` workflow |
| Where the tests live | `Program/e2e/`, outside pytest's `testpaths`, so `pytest` alone still runs only the backend tests |
| Finding elements | By role and accessible name (`get_by_role('button', name='Begin')`); a `data-testid` only where nothing on screen names the element |
| Screenshots | Taken in Ink and Paper on every run and uploaded as CI artifacts, never compared pixel by pixel |
| Retries | None. A flaky test is a bug in the test or the app and is fixed, not retried |

Playwright for Python fits because `create_app` already takes the model, the Referee's decider, the embedder, the image backends, the vault and the clock as arguments (`adventure/main.py`). The tests start the real app in their own process with fakes in those places, so no test-only switch has to ship in the app.

## How a test runs

1. `npm run build` writes `dist/` once; the backend serves it, exactly as in a release.
2. A session fixture builds one template workspace (the built-in world packages and their art are tens of MB, too slow to install per test). Each test copies it to its own temporary folder.
3. Each test starts `create_app` on that copy with a scripted model, a scripted decider, a fake embedder, a fake image backend that returns one fixed picture, a `MemoryVault`, a `FixedClock` the test can move forward and `background=False`, then serves it with uvicorn on a free port in a thread. The autouse fixtures that keep backend tests quiet (life cards, factions, turnover, the director, graphics cards, the PC time zone) apply here too.
4. `random` is seeded per test, so dice and the Program's picks come out the same every run.
5. The test sets up what its flow does not exercise through the API, not by clicking: the AI notice is confirmed with `PUT /api/settings {"ai_notice_confirmed": true}` (EN-3), a model is connected, a world is entered. Only the flow that tests a screen clicks through it.
6. Playwright opens `http://127.0.0.1:<port>/` with reduced motion emulated and every request off 127.0.0.1 aborted, so a test can never reach the internet.
7. A test waits for state, never for time: a timeline step's name, a row's status, a line appearing. Play renders from the one turn state machine (PL-13), so the harness's first PR adds a `data-turn-state` attribute on the Play region that tests can wait on, instead of guessing from text.
8. On failure the test keeps its Playwright trace, a screenshot, the backend log and the list of model calls it made.

## Scripted models

CI never calls a real model: a hosted model costs money and needs a key in GitHub, a local one is too big for a runner, and either answers differently each run. A scripted model answers every call the way the test says, instantly or with a set delay.

A script is a list of rules. Each rule names:

- the part of the app that asks (`caller`, the module that called the provider, as Record model calls already writes it: `adventure.rounds.agents`, `adventure.rounds.writer`, `adventure.story`, `adventure.referee`);
- optionally, text the prompt must contain (a seat's name, a step), for callers that make several kinds of call;
- the reply: text chunks, a finish reason, a delay between chunks, or an error to raise.

Rules are used in order, each once, unless marked as the default for its caller. An agent's reply is written in the script as the structure the spec's "Agent output" section describes and serialized by the helper, so a script reads like the round it plays.

A call no rule answers fails the test at once, naming the caller and the first lines of the prompt. A pull request that adds a new model call therefore shows up as an end-to-end failure that says which script needs a line, not as a test that hangs until it times out.

If matching on prompt text proves brittle as prompts change, the harness adds an explicit purpose label to each model call (caller, step and seat). Record model calls would write it too, which helps support as well as tests.

The Referee's decision model gets its own scripted decider that returns set probabilities for each question, and embeddings come from a fake embedder that returns fixed vectors.

Because the script sees every prompt, a test can also check what a model was told. The privacy flows use that: in Play, the prompt an agent receives must not contain another character's motive or a lore entry hidden from it. This is the browser-level twin of the leak probes in `tests/leak_probes.py`.

### Scripts from real sessions

Hand-written scripts are short and say what they test. For longer flows, a script can start from a real session: turn on Record model calls (Settings > Developer), play the flow against a real model, then run `e2e/tools/script_from_calls.py` on that day's file in `logs/model-calls/`. It keeps each call's caller and reply in order and drops the prompts, which change every week and would break any script that matched them word for word. Trim the result by hand.

Recorded files hold everything the player and the model wrote. Only commit scripts recorded in a test world with made-up text, and read them before committing. Keys are never in them: Record model calls never writes headers.

### The live run before a release

Before each release, someone runs the same flows against a real model on their own computer:

```sh
ADVENTURE_E2E_LIVE=1 ADVENTURE_E2E_BASE_URL=<server>/v1 ADVENTURE_E2E_MODEL=<model> .venv/bin/python -m pytest e2e -m live_ok
```

The key comes from `ADVENTURE_API_KEY`, as the app's own fallback reads it. Only tests marked `live_ok` run: they check structure (a round reaches Write and returns to Idle, a line appears, no error banner, the reply card appears when a character speaks to you), never wording. The release PR says which model was used and what failed. This is where model-side problems (a model that ignores the agent output format, a Writer that stalls) are caught before players see them.

## Flows to cover

Requirement IDs are from the [style guide](../../docs/style-guide.md#requirements). Each test names the IDs it covers in its docstring.

### First run and the shell

| Flow | What the test checks | IDs |
| --- | --- | --- |
| Enter | The notice shows over the title painting; Enter is disabled until "I'm 18 or older" is ticked; Safety opens the Safety page; after Enter and a reload the notice is gone | EN-1, EN-2, EN-3 |
| No model yet | With no model connected, Send reads "Add a model" and opens Settings > Models; no app-wide banner | SH-3 |
| Command menu | Ctrl+K and the menu button open the one menu; a new story and export run from it | SH-2 |
| Nav | The rail holds the persona, Story and Settings; `#settings/<tab>` deep links open that tab, an unknown tab opens the first | SH-1 |

### Worlds and the cast page

| Flow | What the test checks | IDs |
| --- | --- | --- |
| Choose a world | Tiles in one row, most recent first; arrow keys, Home and End move along it; the pitch card shows on hover and focus; "+" makes a world | WO-1 to WO-4 |
| Pick who you play | Tapping a portrait marks it "You" and shows the bio; Rules and Tone are set in the footer; Begin posts one campaign record and opens Play; Rules is locked afterwards in Settings | CA-1, CA-2, CA-4, CA-5 |
| Make your own | The "+" card makes a character and Begin starts with them | CA-2 |
| Your party | Each other lead has Thinks / Rules with the package's default; Begin sends the party; agents' notes and model choice in an open row are kept | CA-7 |
| The bank | In a town with more leads than the agent cap, − sends a party card to the bank and + brings one back; whoever is banked at Begin appears in town as a background character | CA-8 |
| Mode on the cast page | Play / Author / Watch sits top right; in Author and Watch no card is "You" | CA-6 |

### Play

| Flow | What the test checks | IDs |
| --- | --- | --- |
| One full round | Send a line: the timeline lights Declare, React, Talk, Roll, Write in turn with "Declaring · n of m"; rows go Thinking, Decided; the Writer's prose streams into the story; the player's line has its accent rule; the round returns to Idle and the composer is ready | PL-1, PL-3, PL-7, PL-8, PL-13, PL-14 |
| Spoken to | A character addresses you: the reply card replaces the composer, the speaker's row says "Waiting for you", and with the tab unfocused the title has a badge; answering carries the round on | PL-9 |
| Rolls | Roll chips appear in the story where rolls happened and the dice log matches the seeded rolls | PL-3 |
| Nothing leaks in Play | No row shows an intent or motive; the prompts agents received hold no other character's secrets | PL-8 |
| GM view | Opening it in Play asks first; once opened, the turns it was open on are marked | PL-12 |
| Ask again | Ask again on an agent's row makes a branch labelled "What if X had chosen otherwise?"; switching and restoring branches shows the right story | |
| A model fails mid-round | A scripted error in one step shows the reason, nothing half-written is committed, and trying again finishes the round | |
| Reload and restart mid-round | Reloading the page mid-round comes back at the same step; stopping and starting the backend on the same workspace recovers the round | PL-13 |
| Shops and places | A shop shows in the cast list only while it is open | PL-6 |
| Phone width | At 390 px the cast list folds into a sheet opened from the header, nothing scrolls sideways and the gutters are 16 px | PL-1 |

### Author and Watch

| Flow | What the test checks | IDs |
| --- | --- | --- |
| Leave Play for Author | The banner asks "Show the motives you missed?" once, Keep hidden by default; intents show on rows and motives in expanded rows | PL-8, PL-11 |
| Nudge | The composer's placeholder is "Nudge the story"; a nudge reaches the Writer's prompt; the beat board adds, orders and removes beats | PL-4 |
| Watch | Play runs rounds on their own, Pause stops after the current step, Next runs one; reaching the session cap pauses with the reason in the banner | PL-10 |

### Lore, the Sidebar Assistant and Settings

| Flow | What the test checks | IDs |
| --- | --- | --- |
| Lore | Add and edit an entry, set who can see it and when; an entry hidden from a character never appears in that character's prompt | |
| Sidebar Assistant | Open it beside the story, ask for a change, apply its proposal, see the change in the story or cast | |
| Models and Pace | Adding a model works against a stub `/v1/models` the test server answers; Pace shows Quick, Balanced and Rich with time and call counts; changing an Advanced value makes Pace read "Custom"; Roles lists Writer, Characters, Referee and Memory | SE-1 to SE-5 |
| Data | Make a backup, see it in the list, choose Restore and see it pending until the next start (the launcher's part is tested in the backend suite) | |
| Appearance | Switching between Ink and Paper sticks after a reload | |

Accessibility checks (an axe scan of each screen, and Begin reached by keyboard alone) are a good second pass once these flows exist.

## Layout

```text
Program/e2e/
  conftest.py            template workspace, server, page and script fixtures
  scripted.py            ScriptedModel, ScriptedDecider, fake embedder and image backend
  scripts/               model scripts, one per flow that needs a long one
  tools/script_from_calls.py
  test_first_run.py, test_cast.py, test_play_round.py, test_author_watch.py, ...
```

To run them locally, from `Program/`:

```sh
npm run build
.venv/bin/python -m playwright install chromium
.venv/bin/python -m pytest e2e -q                      # add --headed to watch, -k to pick one flow
```

`pytest-playwright` joins the locked dev dependencies. Traces of failed tests open with `playwright show-trace`.

## In CI

A new `e2e` job in `ci.yml` builds the interface, installs the locked dependencies and Chromium (cached between runs), runs `pytest e2e`, and uploads the Ink and Paper screenshots on every run plus traces and backend logs on failure. It runs on `ubuntu-latest` for every pull request, with a 20 minute limit, and should stay under ten minutes.

The same job runs on `windows-latest` for pushes to `main`, and the `Release` workflow runs it before it tags, so Windows, the launch target, is always covered before a release. If the Linux job grows past ten minutes, it splits into shards the way the Windows backend tests do (`ADVENTURE_TEST_SHARD`).

## What end-to-end tests leave out

- Installers, the launcher, the bundle and the setup: the install and package jobs cover them.
- How good the prose is: the house rules, the scan and the Reviewer have their own tests, and playtesting judges the rest; the live run only checks that rounds complete.
- Image generation, speech and the built-in local models: faked, since a runner has no graphics card.
- Safari and Firefox: the app is opened in the system browser, but nearly every player uses a Chromium browser on Windows. Add WebKit later if Mac players report problems.

## Build order

1. The harness: `e2e/`, the server fixture, the scripted model, `data-turn-state`, the Enter flow and the Linux CI job.
2. The cast page and one full Play round, including the reply card.
3. Author and Watch, the GM view, Ask again and branches, errors and recovery.
4. Lore, the Sidebar Assistant, Settings and phone width.
5. The Windows job on `main` and in `Release`, `script_from_calls.py`, and the live run's checklist in the release notes template.
