# Image backends

[Back to the README](../../README.md)

Three kinds of image backend can be set up (PRD F5 to F9). Every backend is off until the user sets it up. The
code is in `dungeon/images/`. Since Milestone 0 nothing asks for a picture: the companion's photos and post
pictures are gone, and the story's own pictures come back in a later milestone (see
[the roadmap](../../docs/roadmap.md)). The backend setup, checks and content routing below are kept for it.

## Backends (F5, F7 to F9)

| Kind | Adapter | Receives | Runs |
| --- | --- | --- | --- |
| `comfyui` | `adapters/comfyui.py`: ComfyUI HTTP API (`/prompt`, `/history`, `/view`) | Safe; NSFW too when local | One job at a time |
| `codex` | `adapters/codex.py`: the Codex CLI's built-in image generation (`codex exec`) | Safe only | One job at a time across every Codex backend |
| `hosted` | `adapters/hosted.py`: OpenAI-style `/images/generations`, OpenRouter's image API (`/images`), or a chat-style `/chat/completions` with image output | Safe only; NSFW too when the user switches it on (OpenRouter, NanoGPT, NovelAI and other APIs only) | Its configured limit (1 to 4) |

- **ComfyUI** is local when its address is a loopback address, or when the user marks it as a
  machine they control. A remote address otherwise counts as hosted (F6). The app only connects to
  the server the user entered; it never starts, stops or restarts one. Cancelling removes the
  app's own prompt from the queue, or interrupts it only when it is the prompt running.
- **Model family.** Each ComfyUI backend has a **Model family** (Vanta, 2026-10-13: not Krea 2
  every time), stored as `family` in its config and Krea 2 when unset. It picks the built-in
  workflow, which files the pickers list first, the sampling the workflow starts on, and whether there
  it uses for pictures made from a reference. Changing it clears file and sampling choices made for the old
  family; style LoRAs and the user's own workflows stay. The built-in workflows are made from Vanta's own
  TXT2IMG and reference workflows (2026-10-13), on public default files; they are untested on a real
  server except Krea 2's text workflow:

  | Family | Built-in workflow | Files (defaults) | Sampling | Reference workflow |
  | --- | --- | --- | --- | --- |
  | Krea 2 (`krea2`) | `krea2-turbo.json`, empty negative | as below | 8 steps, CFG 1, euler_ancestral, simple | `krea2-turbo-reference.json`: Identity Edit LoRA + comfyui-krea2edit nodes (below) |
  | Qwen Image 2.1 (`qwen21`) | `qwen-image-2.1.json`, empty negative | `qwen_image_2.1_int8_convrot`, `qwen3vl_8b_int8_convrot` (type `qwen_image`), `qwen_image_2.1_vae_bf16` | 25 steps, CFG 1, euler, simple | `qwen-image-2.1-reference.json`: the picture goes to core `TextEncodeQwenImage21` as `<image1>` |
  | Z-Image Turbo (`zimage`) | `z-image-turbo.json`, empty negative | `z_image_turbo_bf16`, `qwen_3_4b` (type `lumina2`), `ae` (Flux VAE); `ModelSamplingAuraFlow` shift 3 | 9 steps, CFG 1, res_multistep, simple | `z-image-turbo-reference.json`: image-to-image at denoise 0.7, core nodes; keeps the picture's pose and colours |
  | Anima (`anima`) | `anima.json`, `masterpiece, best quality, score_7, newest` ahead of the prompt (no rating tag) | `anima-base-v1.0`, `qwen_3_06b_base` (type `stable_diffusion`), `qwen_image_vae` | 30 steps, CFG 4, er_sde, simple | `anima-reference.json`: the Anima Edit LoRA (`AnimeEditV2.safetensors`, on Civitai; no link in the app) and `ApplyCosmosReferenceLatent` from ComfyUI-Cosmos-Reference |
  | Booru (`booru`: SDXL, Pony, Illustrious) | `booru-sdxl.json`; the prompt goes out as booru tags (below) | one checkpoint (`ckpt_name`, `Illustrious-XL-v2.0`), clip skip 2 | 30 steps, CFG 6, euler_ancestral, normal | `booru-sdxl-reference.json`: IP-Adapter Plus (ComfyUI_IPAdapter_plus; weight 0.7 ending at 0.5) |

  The adopted character LoRA is trained on Krea 2, so only Krea 2 applies it. Anima backends start
  their prompts as an "Anime illustration" unless the backend has a style of its own
  (`backends.own_style`).

  **Booru tags** (`images/tags.py`). Illustrious, NoobAI and Pony checkpoints read short comma-separated
  tags, not sentences: a sentence prompt drew a man as a woman, or as two half figures. On the Booru family
  (or a workflow of the user's own that loads such a checkpoint, `comfyui.tag_kind`) the prompt is turned into
  tags at dispatch, by rules and after the content check has read it as written: the quality tags first (the
  family's default Prompt style, `masterpiece, best quality, ...`; Pony checkpoints get `score_9, score_8_up, ...`),
  then `solo`, `1boy`/`1girl` and `male focus`, then the looks, framing and light as tags. The negative prompt
  gets the model's own words, plus the other gender and more people for a picture of one person. The built-in
  Booru workflows add nothing of their own, so the quality tags show and can be edited under Prompt style. A reference workflow that needs a custom node pack is still offered; the check
  names the missing nodes and their page. Only the Krea 2 pack installs with one press. Krea 2 can use a
  separate model for pictures from a reference (`ref_unet_name`, "Same as the Model" by default). With a
  Krea 2 Edit merge (a name with "Edit", such as the KREA 2 Edit SNOFS Merge, recognised by name only), the
  Identity Edit LoRA is left out, since the merge has it built in, and `ref_boost` goes to 2.5.
- **The built-in Krea 2 workflow** (`workflows/krea2-turbo.json`) targets Krea 2 Turbo with the files
  ComfyUI's own Krea 2 template uses: `UNETLoader` with `krea2_turbo_fp8_scaled.safetensors`,
  `CLIPLoader` of type `krea2` with `qwen3vl_4b_fp8_scaled.safetensors`, `qwen_image_vae.safetensors`,
  8 steps at CFG 1 (euler and simple then; euler_ancestral and an empty negative since Vanta's workflow). Verified on Windows with an RTX 5090 and ComfyUI 0.39.0,
  unchanged, with a Krea 2 fine-tune in NVFP4 (Muse Krea2 V3.5) and a Qwen3-VL 4B NVFP4 text encoder
  chosen for its loaders: about 3 seconds an image once loaded, after a first load of about 216
  seconds. Text drawn inside a picture usually comes out garbled. The default files themselves
  have not been run.
- **Model files.** Under the backend, **Model files for the built-in workflow** asks the server
  (`/object_info/UNETLoader`, `/object_info/CLIPLoader`, `/object_info/VAELoader`, at the address
  entered only) which files it has and offers them in dropdowns: Model, Text encoder, Text encoder
  type and VAE, with the current choice selected and a **Refresh list** button. The choices are
  stored in the backend's config (`unet_name`, `clip_name`, `clip_type`, `vae_name`); an empty one
  means the default file. Names are kept exactly as the server lists them, subfolder and all (a
  Windows server lists `Krea 2\model.safetensors`). When the server cannot be reached the names can
  be typed. A custom workflow is used as given and ignores these choices. Krea 2's files are listed
  first and **Only Krea 2 files** (on by default; named for the backend's family) narrows each list to them: a model or LoRA whose
  path matches `krea`, `kr2` or `kera` (so a `Krea 2\` folder counts), the Qwen3-VL 4B encoder and
  a Qwen VAE (`adapters/comfyui.KREA_FILES`). ComfyUI cannot say a file's model family, so this only
  sorts; the current choice always stays in the list, and the toggle shows everything.
- **Sampling.** **Sampling** sets the built-in workflow's KSampler for a model that wants other
  settings: Steps, CFG, Sampler and Scheduler, the last two from the server's own lists
  (`/object_info/KSampler`). It starts on Krea 2 Turbo's (8 steps, CFG 1, euler, simple: the
  workflow's own); a value equal to those is stored as unset, so **Use the defaults** clears them.
  Saved per backend as `steps`, `cfg`, `sampler_name`, `scheduler`. A job's workflow name records
  changed settings (`krea2-turbo (10 steps, CFG 1, euler/beta)`). A custom workflow keeps its own.
- **Style LoRAs.** **Style LoRAs** offers up to three files from the server's loras folder
  (`/object_info/LoraLoaderModelOnly`), each with a strength (0.7 by default) and trigger words,
  stored as `style_loras` in the backend's config and used by any workflow. Each becomes a
  `LoraLoaderModelOnly` chained after the character's adopted LoRA, so the likeness applies first;
  the trigger words follow the character's at the start of the prompt. The character's own file is
  never offered here or applied twice. Check reports a style LoRA missing from the loras folder. A
  style LoRA never makes a server less strict: one whose name or trigger words do not classify as
  safe is refused on any server that does not accept NSFW requests (`backends.require_safe_loras`).
  LoRA names go only to the ComfyUI server they belong to.
- **Where to get models.** Beside the dropdowns is a short list of download pages from
  `dungeon/images/model_links.json`. Each entry links to the official model page, never straight
  to a file, with its licence: the Krea 2 Turbo files repackaged for ComfyUI by Comfy-Org (Krea 2
  Community License, not gated), Krea's own Krea 2 Turbo page (gated: accept the licence on Hugging
  Face first), and Comfy-Org's Qwen3-VL text encoder and Qwen Image VAE pages (Apache 2.0; the same
  files as in the Krea 2 repackage). Community fine-tunes are not listed; any file on the server can
  still be chosen.
- **Check** asks the server for its node list and reports every missing node or model file, using
  the chosen file names; nothing is installed or downloaded. A custom workflow in ComfyUI's API
  format replaces the built-in one, with `{{prompt}}`, `{{negative}}`, `{{seed}}`, `{{width}}` and
  `{{height}}` where the request's values belong. On the PC, **Workflow** and **Workflow for pictures
  made from a reference** under the backend show the workflows, indented, to read or edit. Each box
  starts filled in with the built-in one (with the chosen model files and sampler settings in
  place); saving an edited or pasted one makes it the backend's own, and **Use the built-in one**
  goes back (saving the built-in text unchanged stores nothing). A paired phone never sees or
  changes them.
- **The built-in reference workflow** (`workflows/krea2-turbo-reference.json`) follows the Krea 2
  Identity Edit setup Vanta runs: the built-in workflow's model with the
  `krea2_identity_edit_v1_2.safetensors` LoRA, the `{{reference_image}}` scaled to 1 megapixel and
  read by `Krea2EditModelPatch` (appearance, `ref_boost` 1) and `Krea2EditGroundedEncode` (the
  prompt read with the picture), a zeroed negative, then the usual sampler. Those two nodes come
  from the [comfyui-krea2edit](https://github.com/lbouaraba/comfyui-krea2edit) pack (Apache-2.0, no
  Python dependencies); ComfyUI has no core equivalent. The LoRA's page is in the model links. It
  takes the same file and sampler choices. Check lists what it is missing with where to get it,
  but that does not fail the backend: only profile pictures need it.
- **Installing the nodes** (Vanta's one exception to "the app never writes into ComfyUI",
  2026-10-13). When Check finds a node a listed pack provides (`images/node_packs.py`) on a ComfyUI
  at a loopback address, it offers **Install the Krea 2 Identity Edit nodes**. The press asks
  ComfyUI for its custom_nodes folder (`/internal/folder_paths`; only a folder named custom_nodes with
  main.py, comfy/ or models/ beside it is used, anything else is refused), downloads the pack's files from
  the pinned commit, checks each against its SHA-256, and moves them in as a new
  `comfyui-krea2edit` folder. An existing folder is never replaced, no Python package is installed
  (the pack needs none), and nothing else is touched. ComfyUI loads it on its next start. Never from
  a paired phone.
- **Codex** uses Codex's own `image_generation` feature (stable and on by default in codex-cli
  0.160.1). Each image is one turn of `codex exec --json --skip-git-repo-check --ephemeral
  --ignore-user-config --ignore-rules --sandbox read-only --cd <empty scratch folder> -`, with a
  prompt on stdin asking for exactly one image of a verified size. Codex saves the PNG under
  `CODEX_HOME/generated_images/<thread id>/`; the app takes the path from the turn's `saved_path`
  event, or the newest PNG in that thread's folder, and copies it to `images/raw/`. A turn can take
  a few minutes (600-second limit) and counts against the plan's Codex usage limits. The CLI is
  found from `cli_path` or `codex` on `PATH`; a location saved for the retired `chatgpt-imagegen`
  method is ignored. The app only checks that `auth.json` exists in `CODEX_HOME` (or `~/.codex`),
  and **Check** runs `codex login status`; it never reads the token. A Codex signed in with an API
  key works but bills that key, and Check says so. An authentication error fails that job, marks
  the backend blocked and leaves its other jobs queued, shown as waiting for sign-in, until the
  user runs `codex login` and chooses **Signed in again**. Nothing is retried automatically. The
  raw output stays in `images/raw/` until it passes the image check. The path is labelled
  experimental and has only been tested against a stand-in `codex`, not a real login.
- **Hosted APIs** default to OpenRouter, Google's OpenAI-compatible endpoint
  (`images` style), the OpenAI API or NanoGPT (`https://nano-gpt.com/api/v1`, `images` style;
  **Check** reads its image list at `/images/models`, since its `/models` lists text models only,
  also for a NanoGPT address entered as another API). A base URL saved with a request path on the
  end (`/images/generations`, `/chat/completions`, `/models`, `/images`) is trimmed to the base.
  An OpenRouter backend (any address at openrouter.ai, whatever style it was saved with) lists models
  from `/images/models` and makes pictures with `POST /images`, sending the size as the nearest aspect
  ratio and a reference picture as `input_references`. Its `/models` leaves out models that write no
  text, so only the Google and OpenAI image models showed there, and the chat route has no
  endpoint for FLUX, Seedream, Recraft or Krea. SVG-only vector models are left out of the list.
  Each backend's **Connection** panel edits its name, model, API key and address (another API's
  base URL or a ComfyUI address) in place; saving a new address accepts its disclosure again. Keys are stored in the OS vault as `image-backend:<id>`.
  Enabling a hosted backend, a Codex backend or a remote ComfyUI server requires accepting a
  disclosure of what each request sends. Requests carry the prompt only. Provider-reported
  `usage` is stored as given. The tested request shapes are the two above; a model behind an
  aggregator is not assumed to work until an image comes back.
- **NSFW on an image API** (Vanta, 2026-10-07): an OpenRouter, NanoGPT, NovelAI or other image API backend has an
  **Also take NSFW requests** switch (`allows_nsfw`), off by default, for a provider whose terms
  allow such images. Google and the OpenAI API never offer it, and Codex stays safe-only. With it on,
  the disclosure adds that NSFW requests go to that provider under its terms, and turning it on for
  an existing backend asks for the disclosure again. The local check still runs before every
  dispatch and still fails closed; the switch only adds that backend to where NSFW requests may go.
  Prohibited requests are refused everywhere regardless.
- **NovelAI** (provider `novelai`, `images/adapters/novelai.py`): NovelAI's own image API at
  `https://image.novelai.net`, with the persistent API token from Account Settings on novelai.net. It is not
  OpenAI-style: `POST /ai/generate-image` answers with a ZIP holding the PNG. Its models (V3, V4, V4.5, V5) are
  trained on booru tags, so the prompt goes through `images/tags.convert` (kind `novelai`), the same tag
  treatment as a Booru ComfyUI family, after the local content check has read it as written; with no style of
  its own, the backend opens with the Booru family's quality tags. Each request is one picture at 832×1216,
  1216×832 or 1024×1024 and 28 steps, which an Opus plan makes for free; other plans spend Anlas. NovelAI makes one
  picture at a time per account, so the backend runs one job at a time and waits out a short 429. It takes no
  reference picture. Check reads `GET /user/subscription` (plan and whether it is active) and spends nothing.

## One graphics card or two

The Dungeon never loads or unloads models: KoboldCPP, LM Studio or Ollama hold the text model and
ComfyUI holds the picture model, each in its own graphics memory. Local ComfyUI jobs wait while a reply
is being written and while a LoRA trains, so they never start at the same moment, but both models stay
loaded. When they don't both fit on one card, ComfyUI runs very slowly from system memory or fails.

- **Two cards:** start ComfyUI with `--cuda-device 1` (the second card) and keep the text model on the
  bigger one.
- **One card:** a smaller text model leaves room (Krea 2 Turbo's FP8 file needs about 14 GB, its NVFP4
  file about 9 GB and its Q4_K_M GGUF about 9 GB), or use a hosted image service for pictures.
- **Cards under about 8 GB:** a hosted image service.

### Krea 2 on smaller cards

ComfyUI moves the text encoder off the card while the model draws, so Krea 2 needs about its diffusion
model's file size plus 2 GB (sizes from the files on Comfy-Org/Krea-2 and the community GGUF repos,
2026-10-28): bf16 26.5, FP8 14.2, NVFP4 9.1, Q6_K 11.9, Q5_K_M 10.3, Q4_K_M 9.0, Q3_K_M 7.6 GB.

When the built-in FP8 file is too big for the biggest card, a Krea 2 server on this computer starts on
one that fits (Vanta, 2026-10-28: the app decides, the user overrides): a fitting Turbo file the server
already lists (Raw/Base and Edit models aside), else the one to download. NVFP4 comes first on a
Blackwell card (RTX 50-series), which runs it natively; other cards get the largest GGUF that fits. The
pick is kept as `unet_fit` (`hardware.fit_images`, run by Settings > Images, Check, the file list and
saving a backend) and used only while the user hasn't chosen a model; Model files shows it as the
default. A `.gguf` model loads through the ComfyUI-GGUF nodes' `UnetLoaderGGUF` in place of
`UNETLoader` (the one node swapped); their file list is merged into the model choices, and Check names
the nodes when the server lacks them. They need the `gguf` Python package, so the app doesn't install
them.

### Other families on smaller cards

The same pick runs for every family with smaller files (Vanta, 2026-10-28; `hardware.FITS`), each with
its own sizes (file plus 2 GB) and the files that don't suit its built-in workflow left aside:

- **Qwen Image 2.1:** int8 about 8.8 GB; else Abiray/Qwen-Image-2.1-GGUF Q6_K 7.8, Q5_K_M 7.0, Q4_K_M
  5.9, Q3_K_M 5.0 GB. Turbo, Edit and I2I files are left aside (the workflow runs 25 steps).
- **Z-Image Turbo:** bf16 about 13.5 GB; else NVFP4 6.2 (Blackwell only), int8 7.8, then
  unsloth/Z-Image-Turbo-GGUF Q6_K 7.5, Q5_K_M 7.2, Q4_K_M 6.7, Q3_K_M 5.9 GB. Base and Edit files aside.
- **Anima:** about 5.9 GB; else Abiray/Anima-base-v1.0-GGUF Q8_0 4.1 down to Q3_K_M 3.0 GB. Turbo
  files aside.
- **Booru** (SDXL checkpoints) has no smaller files, so nothing is picked.

Changing a backend's family drops the old pick for the new family's own. A `.gguf` file counts as on
the server only where `UnetLoaderGGUF` lists it, so the too-big warning's one-press switch never
offers a file ComfyUI can't load (Iris).

Settings > Models > This computer checks this for you (see [models.md](models.md#this-computer)), and
Settings > Images repeats any picture warnings.

## Content routing (F6)

`content.py` classifies the whole request (prompt, negatives, the events and captions it was
built from, the appearance description and relationship) with fixed local term lists. It never
asks a service. `routing.py` then decides where it may go:

| Tier | Goes to |
| --- | --- |
| `prohibited`: sexual content with a minor or someone presented as one, sexual depictions of real people, sexual violence | Nowhere; refused with the reason |
| `nsfw`: sexual content, nudity, graphic gore, anything not confidently safe, a classifier error, or marked by the user | A local ComfyUI, or an image API with the NSFW switch on; refused with a pointer to Settings when none is enabled |
| `safe` | Any enabled backend, in the user's order |

- The request is classified again at every dispatch, retry and fallback, and a job never becomes
  less strict than it was.
- A hosted provider's content refusal reclassifies the request as NSFW. With fallback on, it is
  offered only to a backend that accepts NSFW (never back to the one that refused it), so a
  safe-only provider is never tried.
- Known false positives: wording such as "steamy", "injured" or "chicken breasts" routes as NSFW.
  On the shipped city data that is 4 of 3,749 names and descriptions; the composer's own captions
  produce none (`tests/test_images.py`).

## Interface

Settings has an **Images** section: add a ComfyUI server, a Codex backend or an image API, accept what it
receives, order, check, enable or remove each one, and give each its own style line. A blocked Codex backend
shows the sign-in step and a **Signed in again** button. Display logic that needs no browser is in
`src/features/images/imageState.ts`.

## API

All writes need the `x-dungeon-client: workspace` header.

| Method and path | Purpose |
| --- | --- |
| `GET /api/images/backends` | Backends in order, with `local`, `accepts_nsfw`, `allows_nsfw`, `nsfw_switch` (whether the switch is offered), `disclosure`, `blocked_reason`, `has_key`, `model_files` (ComfyUI); never a key |
| `POST /api/images/backends` | `{kind, provider?, label?, base_url?, model?, workflow?, reference_workflow?, unet_name?, clip_name?, clip_type?, vae_name?, cli_path?, api_style?, api_key?, controlled_machine?, allows_nsfw?, concurrency?, enabled?, accept_disclosure?}` |
| `PUT /api/images/backends/{id}` | The same fields; saving a key clears a sign-in block; changing the address or turning `allows_nsfw` on needs the disclosure again |
| `POST /api/images/backends/{id}/move` | `{position}` |
| `DELETE /api/images/backends/{id}` | Remove it; its queued jobs fail at dispatch |
| `POST /api/images/backends/{id}/check` | `{ok, summary, details, install}`; spends no generation quota; `install` lists node packs (`{id, label}`) the app can put into a ComfyUI on this computer |
| `POST /api/images/backends/{id}/install-nodes/{pack}` | Installs a listed node pack into that ComfyUI's custom_nodes (loopback only, PC only); `{installed, folder}` |
| `GET /api/images/backends/{id}/workflows` | ComfyUI's saved `{workflow, reference_workflow}` text (empty when unset) and the built-in ones as `built_in` and `built_in_reference`, for editing on the PC; refused from a paired phone |
| `GET /api/images/backends/{id}/files` | ComfyUI only: `{ok, error, family, defaults, sampler_defaults, options, matching, character_lora}`, the files the server offers each of the family's built-in loaders (`unet_name`, `clip_name`, `clip_type`, `vae_name`, Krea 2's `ref_unet_name`, or `ckpt_name`), its LoRAs (`lora`, without the character's own) and KSampler's `sampler_name` and `scheduler` lists, the family's own first and listed in `matching` |
| `GET /api/images/model-links` | `{links: [{name, role, file, url, licence, family}]}`: download pages for each family's built-in workflow files |
| `POST /api/images/backends/{id}/unblock` | The user signed in to Codex again |
