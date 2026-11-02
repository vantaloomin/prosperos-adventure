# Models

[Back to the README](../../README.md)

Settings > Models picks the text models the Dungeon uses. It is the model selection from
Prospero's Study (`server/providers/`, `server/profiles.py`, `src/features/models/` at `bbcbde4`),
copied into this repository and adapted; see [Development](development.md#code-reused-from-prosperos-study).

## Profiles

A profile is one provider, one model and its settings, plus an API key kept in the OS credential
vault under the service name `Prospero Dungeon` (never the Study's). Saving a profile never
contacts the service.

One key does every job on its service. A new or keyless profile on the same provider and address as a
profile with a saved key uses that key (the most recently changed one) without asking for it again, so
the OpenAI key typed for the narrator also does recall. The form says "Uses the API key saved with …" and
"Use a different key" gives that profile a key of its own. A key leaves the vault only once no profile
uses it. Replacing the key on a profile that shares it replaces it for every profile sharing it (so a
rotated key keeps recall working), unless "Also use it for …" is unticked (`share_key: false`), which gives
that profile a key of its own. A hosted image backend with no key of its own borrows the key saved with a text
profile for the same provider at its usual address (an "other" image API: a compatible text profile at the same address).

| Provider | Address | Key | Request |
| --- | --- | --- | --- |
| OpenAI | official | `OPENAI_API_KEY` or saved | Responses API |
| Anthropic | official | `ANTHROPIC_API_KEY` or saved | Messages API |
| OpenRouter | official | `OPENROUTER_API_KEY` or saved | Chat Completions, provider fallbacks off |
| Google / Gemini | official | `GEMINI_API_KEY` or saved | `streamGenerateContent` |
| NanoGPT | official (`https://nano-gpt.com/api/v1`) | `NANOGPT_API_KEY` or saved | Chat Completions; also embeddings for a recall profile |
| OpenAI-compatible API | any HTTPS, or HTTP on loopback | optional; `DUNGEON_API_KEY` | Chat Completions |
| Local / LM Studio | loopback only | optional; `DUNGEON_API_KEY` | Chat Completions |
| Kobold | loopback only | none | native `/generate` |
| Codex / ChatGPT | none | the Codex CLI's own login | `codex exec` in an empty read-only folder |
| Claude Code / Claude plan | none | the Claude Code CLI's own login (your Claude plan) | `claude -p` in an empty folder, every tool off |

**Test connection** lists the service's models (`GET /models`) without generating text, and fills
the context size and longest reply from what the service reports; unreported limits stay manual,
and nothing is guessed. Generation settings offer only the controls each adapter supports:
sampling, reasoning effort, thinking mode and budget, chat-template thinking and the output-limit
parameter, as in the Study. Reasoning effort lists only the levels the model takes when the app can tell: the
levels the service reports, or the ones a model named when it turned a level down. Most services (OpenAI among
them) do not list them, so a model can refuse the level a profile asks for; the app then asks again at the nearest
level it named (between two equally close, the lighter one; with none named, no effort at all), and saves that
level and the list to the profile (`companion/providers/efforts.py`, `text_models.learn_effort`). An OpenRouter
model whose parameters leave out reasoning gets no thinking controls. For Codex / ChatGPT, Test connection checks `codex login status`
and then asks `codex app-server` for `model/list`, the models the signed-in ChatGPT plan can use, with
the reasoning efforts each one reports. A CLI too old for `model/list` (or a failed call) gets a short
fallback list of common Codex models instead, and the note under the button says which you are seeing. A saved key stays with its provider and address: changing either drops
it from the vault rather than sending it somewhere new.

### Claude Code / Claude plan

Uses the official, unmodified `claude` program the user installed and signed in to themselves, so replies
draw on their Claude plan (`dungeon/providers/claude_code.py`). The app finds `claude` on PATH, then at
`~/.local/bin` (where the native installer puts it), or at the location set in the profile. It never
installs Claude Code, changes PATH, reads or stores the login (no credential files, tokens or sign-in of
its own), or passes `--bare` (bare mode ignores the plan login). `ANTHROPIC_API_KEY` is left out of the
CLI's environment so a key set for the Anthropic provider never takes the place of the plan.

Each reply is one `claude -p --output-format stream-json --include-partial-messages` turn in an empty
temporary folder: the system prompt from a file there (`--system-prompt-file`, which also replaces Claude
Code's own prompt), the conversation as one transcript on stdin, `--tools ""`, `--strict-mcp-config`,
`--disable-slash-commands` and `--no-session-persistence`. Reasoning effort maps to `--effort`. Test
connection runs `claude auth status`, keeps only whether it is signed in and whether that is an API key,
and lists the model aliases (`sonnet`, `opus`, `haiku`, `fable`), since the CLI has no model list; any full
model name can be typed instead. If the CLI is not signed in, it says to run `claude` once in a terminal.
Claude follows Anthropic's usage policy, so the profile help says to keep adult scenes on another profile.
Two requests run at once per account; no usage is shown on the card.

**More than one Claude account.** A profile's optional *Claude account folder* runs the CLI with
`CLAUDE_CONFIG_DIR` set to that folder, where Claude Code keeps that account's sign-in, so two plans can each
have a profile (and each job can use either). The user signs in once in a terminal with the variable set; when
the folder's account is not signed in, Test connection gives the exact command (`$env:CLAUDE_CONFIG_DIR="…";
claude` on Windows). With a folder set, `CLAUDE_CODE_OAUTH_TOKEN` is left out, since it would win over the
folder's account. Test connection names the account's email when `claude auth status` reports one, and each
account queues on its own.

Not copied from the Study: the LM Studio native protocol and its verified background interruption
(local servers use the OpenAI-compatible API, and background work here yields between streamed
chunks through the scheduler), versioned profiles and exact retries, and usage and cost summaries.

### Credits and usage

A profile card shows credits or usage when its service reports them for free, without calling a model
(`dungeon/providers/balance.py`): OpenRouter (credits left, the key's own limit if it has one, and
today's spend), NanoGPT, DeepSeek and Moonshot (account balance), and Codex / ChatGPT (the plan and its
5-hour and weekly limits from `codex app-server` `account/rateLimits/read`). Other services, and any
lookup that fails, show nothing. Each card asks once when Settings > Models opens; the answer is kept for
five minutes, and Check connection asks again. Nothing polls in the background.

## Jobs

| Job | What uses it |
| --- | --- |
| Default | Every job uses this profile unless given its own, like the Study's Primary Writer. |
| Story narrator | Narrator turns ([story.md](story.md)). |
| Referee | Splits each story turn into actions and picks the stat and difficulty of each roll ([story.md](story.md#the-turn-loop)). Off unless a profile is chosen for it: the Default is never borrowed, so a turn costs one narrator call. Without one, keyword rules decide. A small, fast model fits. |
| Continuity | After each story turn, lists the new facts the narrator brought in for the record ([story.md](story.md#the-record-and-the-story-so-far)); facts are only kept when a profile is chosen for it. Also folds older turns into the story so far, using the Default when it has none. A small, fast model fits. |
| Semantic recall | Embeddings, from a recall profile, or from built-in recall when it is on. Recall profiles (`purpose: recall`) have their own section, Settings > Models > Recall: an OpenAI, NanoGPT, local or compatible service and an `embedding_model`, with no text model. They do this job and no other, text profiles never do it, and the first one saved takes the job when recall has none. Without one, recall matches keywords only. |

### Mix narrator models

Settings > Models > Story narrator can **Mix narrator models**: tick two or more finished profiles and each
narration comes from one of them, **At random** or **In turn**, each with its own model and settings
(`text_models.reply_config`, ported from Prospero's Companion #441). Only the narrator mixes; the Referee,
Continuity and recall keep one steady model, and rewrites and chapter openers use the narrator's own profile.
With the Mix off, or fewer than two finished profiles in it, the narrator's profile answers as before. A profile
in the Mix must keep a model, and deleting one drops it from the Mix. "Add another model" copies the narrator's
profile so a second model can be set up beside it.

There is no automatic fallback to another profile when a request fails; like the Study, a failed
request reports its error, and OpenRouter requests forbid OpenRouter's own provider fallbacks. The one
exception is a rate limit (HTTP 429) before any text arrives: hosted models answer it for a few
seconds at busy times, so the same request is sent once more after its `Retry-After` wait (1 to 5 seconds).
Image prompts are assembled without a model, and image backends (and their NSFW routing) have
their own settings under Images.

## Prompt caching

Narrator requests are laid out so that the start of each one matches the one before it, which local servers and
providers reuse instead of reading it again. With a local server this matters most: on a mid-size model a reused
prompt answers in a moment, where reading it fresh can take many seconds. On a local server
(`dungeon/providers/scheduling.py`) background work waits until 90 seconds after the last reply, so a quick
back-and-forth keeps reusing the story's prompt. With llama.cpp's server started with `--slot-save-path <folder>`,
the app can also save a prompt's start and put it back later (`dungeon/providers/prompt_cache.py`); a failure there
only means the prompt is read again, never a failed reply.

## This computer

`dungeon/hardware.py` reads the graphics cards (NVIDIA through `nvidia-smi`; Apple silicon as shared
memory, about three quarters usable by the GPU) and system memory, and says what local models fit:
text models up to about N billion parameters at 4-bit, and whether Krea 2 pictures fit beside one. It
then checks the setup in use and warns when:

- a local text model (Local / LM Studio, Kobold, or a loopback OpenAI-compatible address that does a
  job) is bigger than the largest card, or bigger than the card plus system memory;
- a local ComfyUI backend's diffusion model is bigger than its card;
- a local text model and local ComfyUI pictures don't both fit on one card. With two cards it asks
  ComfyUI (`/system_stats`) which card it uses and suggests `--cuda-device` when it shares the text
  model's card;
- the computer has less than 16 GB of memory.

Sizes are estimates from names: billions of parameters (`31b`, `8x7b`) times the bits of the
quantization in the name (`Q4_K_M`, `Q8_0`, `fp16`; 4-bit when none is named), plus 10% and 1.5 GB for
the context. A name without a size gets a tip instead of a check. Picture models are sized by the
precision in the diffusion model's file name: Krea 2 by its real file sizes plus working room (FP8
about 14 GB, NVFP4 about 9 GB, GGUF by quantization; see [images.md](images.md#krea-2-on-smaller-cards)),
other families roughly (FP8 about 16 GB, otherwise about 24 GB). The scan is kept for five minutes; Check again
scans now. Other cards (AMD, Intel) are named on Windows but not measured, so nothing is checked.

`install.bat` and `install.command` print the same summary when setup finishes
(`python -m dungeon.hardware`), and the welcome screen shows it before the first model is set up.

## Upgrading from a single connection

Earlier versions had one OpenAI-compatible connection. The first start after upgrading turns it
into a profile named "Text model" doing the conversation, so every other job keeps using it: a
loopback address becomes a Local profile and any other a compatible one, so requests are unchanged.
Its saved key carries over, and its embedding model becomes a recall profile on the same service.

Text profiles used to carry an optional embedding model. Each start moves any such model into a
recall profile of its own on the same service, sharing the saved key (a key is removed only once no
profile uses it), and recall keeps the profile it used. `GET /api/connection` still describes the
conversation profile, and `PUT /api/connection` remains a one-call setup for a compatible or
local server.

## API

| Request | Purpose |
| --- | --- |
| `GET /api/models` | Profiles, job assignments and the job list |
| `POST /api/models/profiles`, `PUT`/`DELETE /api/models/profiles/{id}` | Add, edit (with `expected_revision`), delete |
| `POST /api/models/discover` | Test an unsaved form; reuses a profile's saved key when given its `profile_id` |
| `POST /api/models/profiles/{id}/check` | Test a saved profile |
| `GET /api/models/profiles/{id}/usage` | Credits or usage the service reports for free, or `null`; `?fresh=true` skips the five-minute cache |
| `PUT /api/models/routes` | `{job, profile_id}`; `null` returns the job to the conversation profile |
| `PUT /api/models/mix` | `{job: 'story', profile_ids, mode: 'random' \| 'in_turn', enabled}`: the narrator's Mix |
| `GET /api/hardware` | This computer: `computer`, `can_run` lines, the `local_text` and `local_images` checked, and `warnings` (`area`, `tone`, `text`); `?fresh=true` scans again |
