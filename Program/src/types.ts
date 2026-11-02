import type { ColorScheme, Palette } from './features/settings/palette'

export type ChatStyle = 'feed' | 'bubbles' | 'community' | 'retro' | 'novel'
export interface WorkspaceSettings {
  user_timezone: string
  auto_backups?: AutoBackups
  /** 'pc' follows this PC's timezone; 'chosen' was picked in Settings; 'default' is the untouched UTC. */
  user_timezone_source: 'default' | 'pc' | 'chosen'
  /** What the backend worked out from the PC (Windows registry, TZ), or null. */
  system_timezone: string | null
  /** Start the app when the PC starts. */
  auto_launch?: boolean
  /** The app's colors (Prospero's Study's palettes). */
  color_scheme?: ColorScheme
  /** The four colors of the custom scheme, or null before one is made. */
  custom_palette?: Palette | null
  /** 'system' matches the computer (Paper or Ink), 'paper' is the light profile, 'scheme' uses color_scheme. */
  theme?: 'system' | 'scheme' | 'paper'
  /** Hidden values: the odds behind what happens; off unless turned on. */
  show_odds?: boolean
  /** Dice that tumble on screen and land on each roll, while the dice are shown. */
  roll_dice?: boolean
  /** Worlds > Adult side of life (dungeon/world/intimacy.py): adults only; off unless turned on. */
  adult_side?: boolean
  /** Hidden values: what townsfolk are like that way, for the user's eyes; off unless turned on. */
  show_adult_side?: boolean
  /** Seconds a story turn may take before its optional steps give way; 0 is automatic (dungeon/pace.py). */
  turn_budget?: number
  /** Rewrite a narration that clashes with the record before it is shown; on by default (dungeon/story.py told). */
  contradiction_check?: boolean
  passive_art?: boolean
  /** Tokens a turn may send at most; 0 is the model's whole window (dungeon/remembering.py). */
  context_cap?: number
  /** The GM view of the record: hidden truth shown and editable (dungeon/record.py). */
  gm_view?: boolean
  /** How far the story goes on the page; 'world' follows the world's own preset. */
  intensity?: IntensityPreset
  /** Settings > Developer: every model request and response is written in full to logs/model-calls; off by default. */
  record_model_calls?: boolean
  /** The one-time notice that the characters are AI, with the 18+ confirmation, has been read. */
  ai_notice_confirmed?: boolean
}

export interface BackupResult { path: string; created_at: string; database_bytes: number }
export interface BackupEntry {
  name: string; bytes: number; kind: 'backup' | 'pre-upgrade' | 'before-reset' | 'before-delete' | 'before-debug' | 'auto'; readable: boolean
  created_at?: string; app_version?: string
}
export interface DataFolderStatus {
  path: string; portable: boolean; pinned: boolean; target: string; default: string
  can_move: boolean; reason: string | null; pending: boolean; notes: string[]
}

export type AutoBackups = 'off' | 'daily' | 'weekly'
export interface BackupList {
  backups: BackupEntry[]; pending: { name: string; requested_at: string } | null
  /** Automatic backups of every world (dungeon/auto_backup.py), and when this world last had one. */
  auto_backups: AutoBackups; last_auto_backup: string | null; auto_backup_count: number
}

/** `world` is the world package the city is on the travel map of (null for one on its own); `home` false marks a
 * road between towns, not somewhere to live (dungeon/world/schema.py). */
export interface CitySummary {
  id: string; name: string; region: string; country: string; timezone: string; summary: string; era?: string; category?: string
  world?: string | null; world_name?: string | null; home?: boolean
}

/** Someone's kind and how long they live (dungeon/world/lifespans.py `described`). `own` is the user's pick of
 * How long they live: null as their kind, 0 doesn't age. `years` is what applies (null: they don't age). */
export interface KindShown {
  kind: string
  label: string
  own: number | null
  years: number | null
  kind_years: number | null
  life_age: number | null
  /** The app's pick, and the user's ('' for none) where it can differ. */
  found?: string
  from_parents?: boolean
  picked?: string
}

/** What the Kind and How long they live pickers offer (GET /life/kinds). */
export interface KindChoices {
  /** `folk` groups the peoples of fantasy worlds in the picker (Beastkin, Fantasy humanoids, Other peoples). */
  kinds: { id: string; label: string; lifespan: number | null; folk?: string | null }[]
  spans: number[]
}

export type ImageStatus = 'none' | 'queued' | 'running' | 'completed' | 'failed' | 'cancelled' | 'interrupted'

export interface PostImage { status: ImageStatus; job_id: string | null; ref: string | null; error: string | null; updated_at: string | null; outdated?: boolean }

export type BackendKind = 'comfyui' | 'codex' | 'hosted'
export type HostedProvider = 'openrouter' | 'google' | 'openai' | 'nanogpt' | 'novelai' | 'other'

export interface ImageBackend {
  id: string
  kind: BackendKind
  provider: string
  label: string
  enabled: boolean
  position: number
  base_url: string
  model: string
  api_style: 'images' | 'chat' | null
  // Starts this backend's image prompts; '' uses the general style.
  style: string
  cli_path: string
  custom_workflow: boolean
  // ComfyUI: the model family whose built-in workflow runs; null for other kinds.
  family: ImageFamily | null
  // The style the model family starts prompts with while `style` is '' (Booru and NovelAI: quality tags); null for none.
  family_style: string | null
  // Its prompts go out as booru tags (solo, 1boy, ...) rather than sentences.
  tag_prompts: boolean
  // ComfyUI: files chosen for the built-in workflow ('' means its default); null for other kinds.
  model_files: ModelFiles | null
  // The smaller Krea 2 model file the app picked for this computer's graphics card, used while no model is chosen.
  model_fit: string | null
  // ComfyUI: LoRAs applied after the character's own, in order; null for other kinds.
  style_loras: StyleLora[] | null
  // ComfyUI: the built-in workflow's sampler; null in a field means the workflow's own value.
  sampler: SamplerSettings | null
  reference_workflow: boolean
  // Can make a picture that follows an earlier one (the onboarding profile pictures).
  takes_reference: boolean
  has_key: boolean
  // With no key of its own: the text model profile whose key it uses for the same service.
  key_from: string | null
  controlled_machine: boolean
  concurrency: number
  local: boolean
  accepts_nsfw: boolean
  // Image APIs other than Google and OpenAI: the user switched it to take NSFW requests too.
  allows_nsfw: boolean
  // Whether that switch is offered for this backend.
  nsfw_switch: boolean
  blocked_reason: string | null
  disclosure: string | null
  disclosure_accepted: boolean
  experimental: boolean
}

export interface BackendCheck { ok: boolean; summary: string; details: string[]; install?: { id: string; label: string }[] }

export type ImageFamily = 'krea2' | 'qwen21' | 'zimage' | 'anima' | 'booru'
export type ModelFileKey = 'unet_name' | 'clip_name' | 'clip_type' | 'vae_name' | 'ckpt_name' | 'ref_unet_name'
/** The files of the family's own loaders only ('' means the workflow's default). */
export type ModelFiles = Partial<Record<ModelFileKey, string>>
export type FileListKey = ModelFileKey | 'lora' | 'sampler_name' | 'scheduler'
export interface SamplerSettings { steps: number | null; cfg: number | null; sampler_name: string | null; scheduler: string | null }
export interface StyleLora { name: string; strength: number; trigger: string }
/** What a ComfyUI server offers the built-in workflow's loaders and its LoRAs, the family's own first (`matching`
 * lists those); ok is false when it could not be asked. The character's own LoRA is left out of `lora`. */
export interface BackendFiles { ok: boolean; error: string | null; family: ImageFamily; defaults: ModelFiles; sampler_defaults: SamplerSettings; options: Partial<Record<FileListKey, string[]>>; matching: Partial<Record<FileListKey, string[]>>; character_lora: string | null }
export interface ModelLink { name: string; role: 'model' | 'clip' | 'vae' | 'reference'; file: string | null; url: string; licence: string; family: ImageFamily }

export interface ImageJob {
  id: string
  post_id: string
  status: Exclude<ImageStatus, 'none'>
  trigger: 'manual' | 'automatic' | 'retry' | 'fallback'
  retry_of: string | null
  classification: 'safe' | 'nsfw' | 'prohibited'
  classification_reasons: string[]
  routing_reason: string
  backend_id: string | null
  backend_label: string | null
  backend_kind: BackendKind | null
  provider: string | null
  model: string | null
  workflow: string | null
  identity_method: string | null
  seed: number | null
  width: number | null
  height: number | null
  usage: Record<string, unknown> | null
  error: string | null
  error_code: string | null
  waiting_for: string | null
  has_image: boolean
  prompt: string
  marked_nsfw: boolean
  current: boolean
  retry_original_available: boolean
  created_at: string
  finished_at: string | null
}

/** Debug time (Settings > Developer, dungeon/debug_time.py): the app clock moved ahead or running faster. */
export interface DebugTime {
  active: boolean
  /** The app's time, and the PC's real time. */
  now: string
  real_now: string
  speed: number
  speeds: number[]
  started_at: string | null
  app_started_at: string | null
  backup: string | null
  jumping: { to: string; done: number } | null
  kept?: boolean
}

/** Story mode (dungeon/story.py): the user's own story with a narrator. */
export interface StoryPlace {
  id: string; name: string; kind: string; neighborhood: string; summary?: string
  /** Named spots inside, for detail (dungeon/world/inside.py): "the back patio". */
  spots?: string[]
}
export interface StoryScene {
  city: { id: string; name: string; era: string }
  place: StoryPlace
  local_time: string
  weather: string
  places: StoryPlace[]
  /** Who is around, as the user would see them ("the barista there"); never names they have not been given. */
  around: string[]
  /** Those same people with their keys, for asking a portrait of someone here (dungeon/art.py). */
  present?: { key: string; label: string }[]
}
export interface StoryMessage {
  id: string; seq: number; role: 'user' | 'narrator' | 'scene'; text: string; reply_to: string | null
  status: 'complete' | 'failed'; error: string | null; city_id: string; place_id: string; created_at: string
  crisis_help?: boolean
  /** The turn's rolls (dungeon/turn.py), only while the dice are shown. */
  rolls?: StoryRoll[]
  /** How long the turn took, step by step, and what gave way for time (dungeon/pace.py); with the dice shown. */
  pace?: TurnPace | null
  /** A narration's paragraphs with a problem the checks left, each with why, and whether it was rewritten and can
   *  switch back (dungeon/passages.py). */
  flags?: StoryFlag[]
  previous?: boolean
  /** On a player's line: what its turn changed (dungeon/receipt.py), for the recent turns. */
  receipt?: ReceiptChip[]
  /** On a player's line: the Life Cards the world drew on it (dungeon/happenings.py with_cards). */
  cards?: LifeCardShown[]
}
/** A drawn Life Card as the story shows it: title, tone and picture (or the card back), never its hidden truth. */
export interface LifeCardShown { title: string; tone: 'good' | 'bad' | 'grey'; art: string | null; veiled: boolean }
/** One thing a turn changed: the purse, the pack, the character's condition, a quest, or something learned. */
export interface ReceiptChip { kind: 'coins' | 'item' | 'hurt' | 'injury' | 'quest' | 'learned'; tone: 'gain' | 'loss' | 'neutral'; text: string }
export interface StoryFlag { passage: string; why: string[] }
/** The dice log (dungeon/dice_log.py): every roll of the branch, turn by turn and newest first, with how long each
 *  turn took; empty while the dice are hidden. */
export interface DiceLog {
  shown: boolean
  turns: { id: string; seq: number; line: string; rolls: StoryRoll[]; pace: TurnPace | null }[]
  tally: { rolls: number; landed: number; bands: Partial<Record<Band, number>> } | null
}
export interface TurnPace { steps: Record<string, number>; skipped: string[]; budget: number; total: number }
export type Band = 'critical_failure' | 'failure' | 'failure_upside' | 'success_cost' | 'success' | 'critical_success'
/** One roll: Prospero's d100 plus the stat die, less the difficulty shift (dungeon/rules/marvel.py); or, under 5E, a d20
 *  plus the skill's bonus against a DC (`target`, dungeon/rules/srd52.py), `skill` naming what it tested. */
export interface StoryRoll {
  action: string; stat: string; difficulty: string; die: number | null; natural: number; bonus: number; shift: number
  total: number; band: Band; label: string; ruleset?: Ruleset; target?: number | null; skill?: string | null
}
export type Ruleset = 'marvel' | 'srd52' | 'ironsworn' | 'brp' | 'narrative' | 'fate'
/** A roll while the dice are hidden: what was tried and with which stat, never the odds (dungeon/turn.py hidden). */
export type HiddenRoll = Pick<StoryRoll, 'action' | 'stat'>
/** One of the ruleset's bands by total, worst first; the top band has no ceiling (dungeon/turn.py bands). */
export interface BandStep { band: Band; label: string; ceiling: number | null }
/** An action a turn rolls for, named before the result; the difficulty only while the dice are shown. */
export interface TurnAction { action: string; stat: string; difficulty?: string }
/** A turn's stages as the stream tells them, before and around the narration (dungeon/story.py answer). */
export type TurnEvent = { stage: 'reading' | 'writing' } | { actions: TurnAction[]; bands?: BandStep[] } | { roll: StoryRoll | HiddenRoll }
/** What a turn under way has shown so far. */
export interface TurnSoFar { stage: 'reading' | 'writing' | null; actions: TurnAction[]; bands: BandStep[] | null; rolls: (StoryRoll | HiddenRoll)[] }
/** The persona's Prospero stats (dungeon/sheet.py) and the die each one rolls; or their 5E sheet (Srd52Sheet). */
/** A Narrative Only sheet (dungeon/rules/narrative.py): no stats, only what the player says the character is good and bad at. */
export interface NarrativeSheet { ruleset: 'narrative'; ruleset_name: string; good_at: string[]; bad_at: string[]; growth?: SheetGrowth }
/** A Fate sheet (dungeon/rules/fate.py): aspects, approaches, stunts, Fate points, stress and consequences. */
export interface FateSheet {
  ruleset: 'fate'; ruleset_name: string; high_concept: string; trouble: string; aspects: string[]; approaches: Record<string, number>
  stunts: string[]; refresh: number; fate_points: number; stress: boolean[]; consequences: Record<string, string>
  ladder: Record<string, string>; attribution: string; growth?: SheetGrowth
}
/** What a Fate character is made from (dungeon/campaign.py view). */
export interface FateChoices { hint: string; approaches: string[]; array: number[]; most_aspects: number; most_stunts: number; attribution: string }
export type Sheet = MarvelSheet | Srd52Sheet | IronswornSheet | BrpSheet | NarrativeSheet | FateSheet
/** A character under the Percentile ruleset (dungeon/rules/brp.py view): BRP characteristics, skills, hit points. */
export interface BrpSheet {
  ruleset: 'brp'; ruleset_name: string; characteristics: Record<string, number>; hp: number; max_hp: number; pp: number; max_pp: number
  names: { profession: string; personality: string }; rolls: Record<string, number>; damage_modifier: string; major_wound: number
  xp_bonus: number; armor_name: string; armor_value: number; checks: string[]
  skill_list: { id: string; name: string; value: number; checked: boolean }[]
  /** A magician's spells (Chapter 4: Powers): each a skill, its power points a level, and the most levels. */
  spell_list?: { id: string; name: string; value: number; cost: number; summary: string; checked: boolean }[]; most_level?: number
  major_wounds: { text: string; characteristic: string; lost: number; by: string }[]; attribution: string; growth?: SheetGrowth
}
/** What a Percentile character is built from at campaign start (dungeon/campaign.py brp_choices). */
export interface BrpChoices {
  characteristics: { id: string; name: string; roll: string | null }[]; points: number; start: number; range: [number, number]
  costly: string[]; costly_price: number; professions: { id: string; name: string; skills: string[] }[]
  personalities: { id: string; name: string; about: string }[]; attribution: string
}
/** An Ironsworn character (dungeon/rules/ironsworn.py view): five stats, the condition meters, momentum, assets. */
export interface IronswornSheet {
  ruleset: 'ironsworn'; ruleset_name: string; stats: Record<string, number>; health: number; spirit: number; supply: number
  momentum: number; momentum_max: number; momentum_reset: number; debilities: string[]; xp: number
  /** Progress tracks: each open vow (with its rank), then bonds; `ticks` run to `of` boxes of four. */
  progress?: { name: string; rank: string | null; ticks: number; boxes: number; of: number }[]
  asset_list: { id: string; name: string; category: string; abilities: string[] }[]; attribution: string; growth?: SheetGrowth
}
/** What an Ironsworn character is built from at campaign start (dungeon/campaign.py ironsworn_choices). */
export interface IronswornChoices {
  stats: { id: string; name: string; about: string }[]; array: number[]; count: number
  assets: { id: string; name: string; category: string; about: string }[]; attribution: string
}
export interface MarvelSheet { ruleset: 'marvel'; ruleset_name: string; stats: Record<string, number>; stat_names: string[]; range: [number, number]; dice: Record<string, number | null>; growth?: SheetGrowth }
/** A 5E character (dungeon/rules/srd52.py view): abilities, proficiency, hit points, Armor Class and every skill. */
export interface Srd52Sheet {
  ruleset: 'srd52'; ruleset_name: string; level: number; xp: number; abilities: Record<string, number>; modifiers: Record<string, number>
  proficiency: number; max_hp: number; hp: number; ac: number; speed: number; saves: string[]; skills: string[]
  names: { class: string; species: string; background: string; subclass?: string | null }
  skill_bonuses: Record<string, { name: string; ability: string; bonus: number; proficient: boolean }>
  attribution: string; growth?: SheetGrowth
  /** XP that reaches the next level (null at 20), the class's features so far, and the caster's spells. */
  next_xp: number | null; features?: string[]; spell_list: Srd52Spells | null
}
export interface Srd52Spells {
  ability: string; attack: number; dc: number; cantrips: string[]; prepared: { name: string; level: number }[]
  slots: { level: number; left: number; of: number }[]
}
/** What a 5E character is built from at campaign start (dungeon/campaign.py srd52_choices). */
export interface Srd52Choices {
  classes: { id: string; name: string; hit_die: number; primary: string; skills: { count: number; from: string[] } }[]
  species: { id: string; name: string }[]
  backgrounds: { id: string; name: string; skills: string[]; abilities: string[] }[]
  abilities: { id: string; name: string }[]; skills: { id: string; name: string; ability: string }[]
  array: number[]; attribution: string
}
/** Someone the user has met in their story (dungeon/story_people.py), with where their rules put them now. */
export interface StoryPerson {
  key: string; name: string; role: string; city: string; meetings: number; last_met_at: string; notes: string[]
  doing: string; place: { id: string; name: string; city_id: string } | null
  /** How they feel about your character, while the dice are shown (dungeon/feelings.py). */
  feelings: string
  /** How they are bonded to your character, if they are (dungeon/bonds.py). */
  bond?: 'earned' | 'sworn' | null
  /** Whether they travel with your character (dungeon/party.py). */
  party?: boolean
}
/** The character's purse and pack, and the shop window where the story is (dungeon/inventory.py). Money is in hundredths. */
/** `icon`: the world's picture of the thing (dungeon/icons.py), null when it has none. */
export interface GearItem { id: string; item_id: string; name: string; category: string; qty: number; slots: number; stolen?: boolean; condition?: 'sound' | 'damaged' | 'broken'; icon?: string | null }
export interface ShopRow { item_id: string; name: string; category: string; price: number; qty: number; slots: number; icon?: string | null }
/** `haggled`: today's prices after a haggle, in percent off (negative) or on; 0 without one. */
/** `fence`: buys stolen goods; `cash`: what the keeper has to buy with (null: unlimited); `market`: prices moved by events. */
export interface Shop { place_id: string; open: boolean; keeper: string; haggled: number; stock: ShopRow[]; offers: Record<string, number>; fence?: boolean; cash?: number | null; market?: string }
/** How the character looks (dungeon/appearance.py): cleanliness with its marks, clothes, layers not worn, weapons on show. */
export interface Looks { cleanliness: string; grime: string; marks: string[]; clothes: string; dress: Record<string, string>; on_show: string[] }
export interface Gear {
  coins: number; currency: { code: string; symbol?: string; name?: string }; slots: { used: number; max: number | null }
  items: GearItem[]; shop: Shop | null
  /** How the character looks right now (dungeon/appearance.py). */
  looks?: Looks
}
/** A character a town ships to play as (dungeon/campaign.py). */
export interface Premade { id: string; name: string; gender: PersonaGender; age: number | null; about: string; stats: Record<string, number> }
/** Campaign start: the town's premades and the point-buy for making your own. */
export type StoryArc = 'grounded' | 'classic' | 'epic'
export type StoryPace = 'slow' | 'steady' | 'fast'
export type StoryHand = 'soft' | 'guiding' | 'firm'
/** Another world's story that can come into a new campaign as history (dungeon/legacy.py). */
export interface LegacyCandidate { world_id: string; world: string; name: string; dead: boolean; chapters: number }
export type LegacyRole = 'legend' | 'villain' | 'corpse'
export interface StoryStart { rulesets?: { id: Ruleset; name: string }[]; ruleset?: Ruleset; srd52?: Srd52Choices; ironsworn?: IronswornChoices; brp?: BrpChoices; narrative?: { hint: string }; fate?: FateChoices; legacy?: LegacyCandidate[]; presets?: TablePreset[]; table?: TableRules; premades: Premade[]; points: number; range: [number, number]; stat_names: string[]; meanings: Record<string, string>; arc?: { arc: StoryArc; pace: StoryPace; hand?: StoryHand } | null }
/** The character's tier on the shared ladder and its track (dungeon/tiers.py); the numbers only with the dice shown. */
/** Growth by use and the dark tracks (dungeon/growth.py); points only with the dice shown. */
export interface SheetGrowth {
  marked: string[]; dark: { id: string; name: string; word: string; changes: string[]; points?: number; top?: number }[]
  /** The Bonds track (dungeon/bonds.py); the count only with the dice shown. */
  bonds?: SheetBonds
}
export interface SheetBonds { word: string; count?: number; bonds: { key: string; name: string; how: 'earned' | 'sworn'; state: 'whole' | 'broken' | 'lost' }[] }
export interface StoryTier { tier: string; words: string; track: string; arc: StoryArc; pace: StoryPace; points?: number; next?: number | null }
/** A fact the game keeps that the player's character knows (dungeon/record.py). */
/** `world` (hidden truth) and `pulled` (a fact the model took from the story) show only in the GM view. */
export interface JournalEntry { id: string; kind: string; subject: string; text: string; truth: 'world' | 'belief' | 'both'; source: 'code' | 'narrator' | 'player'; pulled?: boolean; faded?: boolean; created_at: string }
export interface JournalQuest { id: string; title: string; hook: string; status: 'open' | 'done' | 'failed' | 'missed'; outcome: string; left: string; kind?: 'authored' | 'job' | 'oath' | 'coursework' }
export type ArtKind = 'portrait' | 'place' | 'scene' | 'passage'
export interface StoryArt { id: string; kind: ArtKind; subject: string; chapter_id: string | null; status: 'queued' | 'running' | 'done' | 'failed' | 'refused'; error: string | null; reference: boolean; url: string | null; width: number | null; height: number | null; created_at: string; stale: boolean }
export interface InstitutionGrades { average: number; letter: string; gpa: number; attended: number; missed: number }
export interface JournalInstitution { id: string; name: string; term: string | null; classes: { id: string; name: string }[]; today: { id: string; name: string; at: string; place_id: string | null; soon: boolean }[]; grades: InstitutionGrades | null }
/** A thread in the director's notebook the character has come across, as they understand it (dungeon/director.py). */
export interface JournalThread { id: string; kind: 'mystery' | 'grudge' | 'lead' | 'promise'; title: string; seen: string }
export interface Journal { entries: JournalEntry[]; quests: JournalQuest[]; institutions?: JournalInstitution[]; threads?: JournalThread[]; gm?: boolean; summary?: string }
export type FeelingAxis = 'trust' | 'affection' | 'respect' | 'fear' | 'desire'
/** The GM view (dungeon/gm.py): what the game keeps behind the story, secrets included. */
export interface GmView {
  quests: { id: string; title: string; status: string; known: boolean; truth: string; kind: string }[]
  people: { key: string; name: string; feelings: Record<FeelingAxis, number>; impressions: string[] }[]
  arcs: { id: string; title: string; stage: number; stages: number; bite: number; truth: string; antagonist: string }[]
  threads: { id: string; kind: string; title: string; truth: string; known: boolean; heat: number }[]
  nemeses: { name: string; grudge: string; remembers: string; status: string }[]
  factions: { faction_id: string; value: number }[]
  dark: { id: string; name: string; word: string; points?: number; top?: number }[]
  corrections: { before: string; after: string | null; subject: string | null; created_at: string }[]
  /** The director's Chekhov list and each arc's planned beats (dungeon/plotting.py). */
  seeds: { id: string; text: string; truth: string; status: 'planted' | 'reached' | 'asked' | 'paid' | 'retired'; arc_id: string | null }[]
  plans: { arc_id: string; stage: number; beats: { id: string; text: string; cut: boolean; used: boolean; source: 'model' | 'world' }[] }[]
}
/** One way the story went (dungeon/timeline.py); `playing` is the one on screen. */
/** A chapter of a branch (dungeon/chapters.py): `open` while it is still being played. */
export interface StoryChapter { id: string; number: number; title: string; summary: string; hook?: string; open: boolean; turns: number; ended_by: 'place' | 'time' | 'fight' | 'quest' | 'player' | null; branch_id: string; seq: number }
/** A branch in the tree: where it forked, how it ended if the character died or was lost, and its own chapters. */
export interface StoryTreeBranch { id: string; parent_id: string | null; fork_seq: number | null; playing: boolean; ending: '' | 'death' | 'lost'; chapters: StoryChapter[] }
export interface StoryBookmark { id: string; name: string; message_id: string; branch_id: string; text: string; created_at: string }
export interface StoryCampaign { chapters: StoryChapter[]; tree: StoryTreeBranch[]; bookmarks: StoryBookmark[]; ironman: boolean; pending: { reason: string; title: string } | null }
export interface NotebookNote { id: string; text: string; created_at: string; updated_at: string }
export interface StoryBranch { id: string; playing: boolean; turns: number; last_line: string; last_at: string; started_at: string }
export type Zone = 'engaged' | 'near' | 'far'
/** The fight and the character's wounds (dungeon/combat.py); a foe's `wound` level (and 5E hit points) only with the dice shown. */
export interface StoryFight {
  condition: string; dead: boolean; injuries?: string[]; stress?: string
  /** Who holds the character prisoner, if anyone. */
  captors?: string | null
  /** Hit points, under 5E. */
  hp?: number; max_hp?: number
  /** `area`: where the character fights from ("the stairs"); each foe's `zone` is its range band. */
  fight: { round: number; area?: string | null; foes: { name: string; state: string; wound: number | null; zone?: Zone | null; hp?: number; max_hp?: number }[]
    /** Companions fighting beside the character (dungeon/allies.py). */
    allies?: { name: string; state: 'unhurt' | 'hurt' | 'down' }[]
    /** Under 5E, the fight on five-foot squares around the character at 0, 0 (dungeon/battlemap.py). */
    grid?: BattleGrid | null } | null
}
export interface BattleGrid {
  square_feet: number; area?: string | null
  foes: { name: string; x: number; y: number; feet: number; down: boolean }[]
  allies: { name: string; x: number; y: number; down: boolean }[]
}
export type IntensityPreset = 'world' | 'restrained' | 'mature' | 'unflinching'
/** How far the story goes: `preset` in play, the player's `chosen` one ('world' follows the world), the world's own. */
export interface StoryIntensity {
  preset: Exclude<IntensityPreset, 'world'>; chosen: IntensityPreset; world: Exclude<IntensityPreset, 'world'>; voice: string
  /** Each category's level in play (0 off the page to 3 unflinching), whether any moved off the preset, the veils. */
  levels?: Record<ToneCategory, number>; custom?: boolean; veils?: VeilTopic[]; voice_chosen?: ToneVoice; voice_world?: string
  /** How eventful the story is (dungeon/happenings.py): the level in play, the player's choice, the world's own. */
  drama: Exclude<DramaLevel, 'world'>; drama_chosen: DramaLevel; drama_world: Exclude<DramaLevel, 'world'>
  /** "Meanwhile" cutaways of off-page beats (dungeon/beats.py). */
  cutaways?: boolean
  /** A 5E defeat (dungeon/combat.py fall): death saves as written, or what the foes were after. */
  defeat?: DefeatRule; ruleset?: Ruleset
}
export type DefeatRule = 'as_written' | 'by_aim'
export type DramaLevel = 'world' | 'quiet' | 'uneasy' | 'eventful' | 'merciless'
/** A session zero preset (dungeon/table.py PRESETS): the tone it sets and the director's hand (null: the world's). */
export interface TablePreset { id: string; name: string; about: string; hand: StoryHand | null; rules: Pick<TableRules, 'intensity' | 'drama' | 'injury_persistence'> }
/** The Table (dungeon/table.py): this campaign's rules. Tone starts as the world's; what is shown, as you last left it. */
export interface TableRules {
  intensity: IntensityPreset; drama: DramaLevel; injury_persistence: InjuryPersistence
  show_odds: boolean; roll_dice: boolean; show_adult_side: boolean; gm_view: boolean; cutaways: boolean; defeat?: DefeatRule
  /** dungeon/tone.py: categories moved off the preset, veiled topics (null: the world's), the narrator's voice. */
  levels?: Partial<Record<ToneCategory, number>> | null; veils?: VeilTopic[] | null; voice?: ToneVoice
  /** The narration format (dungeon/narration/prompt.py Format): point of view, tense and length. */
  pov?: NarrationPov; tense?: NarrationTense; length?: NarrationLength
  /** Whether shopkeepers have finite cash to buy with (dungeon/inventory.py). */
  shop_cash?: 'finite' | 'unlimited'
  /** Whether carrying is limited by slots (dungeon/inventory.py). */
  carry_limit?: 'slots' | 'off'
  /** Whether the narrator gets the rule text that fits the turn (dungeon/rules/passages.py). */
  rule_text?: 'on' | 'off'
  leaving?: 'anyone' | 'fights' | 'nobody'
  /** How much local politics goes on (dungeon/politics.py). */
  politics?: PoliticsLevel
  /** Story time, or real time while the app is closed too ('world': the world's own; dungeon/story_clock.py). */
  clock?: 'world' | 'story' | 'real_time'
}
export type NarrationPov = 'first' | 'second' | 'third'
export type NarrationTense = 'past' | 'present'
export type NarrationLength = 'short' | 'medium' | 'long'
export type ToneCategory = 'violence' | 'sex' | 'horror' | 'cruelty' | 'drugs'
export type VeilTopic = 'execution' | 'slavery' | 'mutilation' | 'disease' | 'self-harm' | 'addiction' | 'torture' | 'sexual-violence' | 'sacrifice' | 'child-harm'
export type ToneVoice = 'world' | 'grim' | 'wry' | 'romantic' | 'hopeful' | 'lyrical' | 'plain'
export interface Story { scene: StoryScene; messages: StoryMessage[]; people: StoryPerson[]; ready: boolean; dice_shown: boolean; bands?: BandStep[] | null; branches: StoryBranch[]; fight: StoryFight; intensity: StoryIntensity; map: StoryMap | null; interior?: StoryInterior | null; injury_persistence: InjuryPersistence; table?: TableRules; factions?: StoryFaction[]; tier?: StoryTier | null; politics?: boolean; campaign?: StoryCampaign; message_id?: string }
/** A faction the character knows of (dungeon/factions.py): standing in words, with the number when the dice are shown,
 * and its emblem (dungeon/icons.py) when the world has one. */
export interface StoryFaction { id: string; name: string; summary: string; standing: string; emblem?: string | null }
export type InjuryPersistence = 'permanent' | 'temporary' | 'none'
/** The travel map as far as the character knows it (dungeon/travel.py); positions run 0 to 1 across the world map. */
export interface StoryMap {
  places: { id: string; name: string; x: number; y: number; visited: boolean; here: boolean }[]
  roads: { from: string; to: string; hours: number; danger: 'none' | 'low' | 'medium' | 'high'; terrain: string }[]
  /** On a hex crawl (dungeon/hexes.py): the hexes the character has seen, and the hex they believe they are in. */
  hexes?: MapHex[]
  at?: { q: number; r: number; lost: boolean }
}
/** The interior the character is inside (dungeon/delving.py view): the rooms they have seen, the passages they know,
 * and where they are. A room's `map` is where it was drawn (0 to 1 across and down), when it was. */
export interface StoryInterior {
  id: string; name: string; style: string
  levels: { id: string; name: string }[]
  rooms: { id: string; name: string; level: string | null; kind: string; map: { x: number; y: number } | null; here: boolean; cleared: boolean }[]
  passages: { between: [string, string]; kind: string; to_known: boolean }[]
}
export type HexTerrain = 'water' | 'plains' | 'forest' | 'hills' | 'mountains' | 'waste' | 'marsh'
/** A seen hex in axial coordinates: its land, whether a road runs through it, the place or found site on it. */
export interface MapHex {
  q: number; r: number; terrain: HexTerrain; road: boolean; place: string | null; site: string | null; visited: boolean
  /** A river through the hex: its name, the next hex downstream (none at its mouth) and how much water it carries (0-1). */
  river?: { name: string; down: [number, number] | null; flow: number } | null
}
/** The story after going back, with the line that was taken back to send again. */
export interface StoryBack extends Story { draft: string }

/** Record model calls (dungeon/model_calls.py), Settings > Developer. */
export interface ModelCallLog { recording: boolean; folder: string; keep_days: number; files: number; bytes: number }

/** Worlds and personas (dungeon/worlds.py): the user as someone in particular, and the worlds they live in. */
export interface WorldHome { city_id: string; city: string; region: string; neighbourhood: string; neighbourhood_name: string; set_by: 'app' | 'you' }
/** The persona form's "Where you live": the cities the persona can live in from this world, and one city's neighbourhoods. */
export interface HomeChoices { home: WorldHome | null; cities: CitySummary[]; city_id: string; neighbourhoods: { id: string; name: string }[] }
export interface World {
  id: string; name: string; persona_id: string; folder: string; city_id: string; created_at: string; used_at: string
  active: boolean
  /** The first world holds the others, so it cannot be deleted. */
  first: boolean
  /** Where the persona lives in this world (dungeon/life/where.py); the app picks it until the user changes it. */
  home: WorldHome | null
}
export type PersonaGender = 'woman' | 'man' | 'nonbinary' | ''
export interface Persona {
  id: string; name: string; gender: PersonaGender; age: number | null; about: string; birthday: string; created_at: string
  /** Kind and How long they live as picked on the Persona page ('' and null: read from About you). */
  kind?: string; lifespan?: number | null
  /** What applies, the app's pick from their words, and what the pickers offer (dungeon/worlds.py `kind_shown`). */
  kind_shown?: KindShown & KindChoices & { found: string; found_label: string; picked: string }
  active: boolean
  worlds: World[]
}
/** A world on the title screen (dungeon/world_select.py): `here` when the story is in it, `yours` when the persona
 * has a world there already; `art` is its key art's address. */
export interface TitleWorld { id: string; name: string; genre: string; pitch: string; here: boolean; yours: boolean; art: string | null }
export interface TitleWorlds { worlds: TitleWorld[]; here: string | null }
export interface Worlds {
  active_world_id: string; active_persona_id: string; world: World; persona: Persona; personas: Persona[]
}

/** Worlds > Townsfolk mix (dungeon/world/mix.py): the shares the townsfolk rolls use. */
export interface MixValues {
  nonbinary: number; women: number; height_woman: number; height_man: number
  slender: number; middle: number; heavier: number; beard: number
  gay: number; bisexual: number; bolder: number; drive: number
}
export interface MixTown {
  city: string; people: number
  genders: Record<'woman' | 'man' | 'nonbinary', number>
  heights: Record<'woman' | 'man' | 'nonbinary', number | null>
  builds: Record<'slender' | 'middle' | 'heavier', number>
  beard: number; gay: number; bisexual: number
  levels: Record<string, number>; drives: Record<string, number>
}
export interface TownsfolkMix {
  mix: MixValues; defaults: MixValues; limits: Record<keyof MixValues, [number, number, number]>
  bands: { ages: string; gay: number; bisexual_women: number; bisexual_men: number }[]
  levels: Record<string, Record<string, number>>; drives: Record<string, Record<string, number>>
  adult_side: boolean; town: MixTown | null
}
/** What the story's stage shows (dungeon/art.py stage): the place's picture and portraits of who is here. */
export interface ArtStage {
  /** A made picture of the place, or the world's default backdrop (`default`) in the hour's `light`. */
  background: { url: string; width: number | null; height: number | null; default?: boolean; light?: 'dawn' | 'day' | 'dusk' | 'night' } | null
  /** `default`: the world's stock portrait of their kind of person, until one of them is made. */
  portraits: { key: string; name: string; url: string; width: number | null; height: number | null; default?: boolean }[]
}

/** Local politics (dungeon/politics.py): what people in the town argue about, the factions behind each side and where
 * the people the character has met there stand. Views run from 2 (strongly for the first side) to -2 (strongly for
 * the second); `by` says whether the game or the player set it. */
export type PoliticsLevel = 'off' | 'quiet' | 'true_to_life' | 'lively'
export type PoliticsStage = 'whispers' | 'open' | 'heated' | 'settled' | 'ended'
export interface PoliticsSide { name: string; stand: string }
export interface PoliticsBeat { on: string; text: string; stage?: string; favors?: number | null }
export interface PoliticsView { view: number; by: 'world' | 'you' }
export interface PoliticsIssue {
  id: string
  kind: 'era' | 'local'
  title: string
  question: string
  sides: PoliticsSide[]
  stage: PoliticsStage
  beats: PoliticsBeat[]
  /** How many of the townsfolk who stand for the town are on each side, or don't much care. */
  split: { first: number; second: number; neither: number }
  /** How a local issue went; each way's odds and reasons only with the odds shown. */
  settled: { options: { option: number; label: string; odds?: number; reasons?: string[] }[]; picked: number; picked_by: 'dice' | 'user' } | null
  settled_on: string | null
  /** A real question of the city's year: it never settles against history. */
  real: boolean
  origin: 'seeded' | 'user'
  started: string | null
  /** 'you' when the player set how far a local issue has got. */
  stage_by: 'you' | null
  /** The side each faction takes: 0 or 1, null when it stays out. */
  lines: Record<string, number | null>
  edited: boolean
}
export interface PoliticsFaction {
  id: string
  name: string
  kind: string
  about: string
  /** 1 to 5; `change` is how far recent wins or losses moved it from `base_pull`. */
  pull: number
  base_pull: number
  change: number
  /** 'world': one of the world's powers holding the town (dungeon/factions.py); 'era': a town group of its times. */
  origin: 'world' | 'city' | 'era' | 'user'
  power: boolean
  /** The people the character has met who belong. */
  members: string[]
  /** The sides the player told it to take, by issue. */
  sides: Record<string, number>
}
export interface PoliticsRelation { a: string; b: string; stance: number; by: 'world' | 'you' }
export interface PoliticsPerson { key: string; name: string; role: string; factions: string[]; views: Record<string, PoliticsView> }
export interface TownPolitics {
  level: number
  level_name: PoliticsLevel
  city: { id: string; name: string }
  issues: PoliticsIssue[]
  factions: PoliticsFaction[]
  relations: PoliticsRelation[]
  people: PoliticsPerson[]
}
