"""Model profiles and which one does each job (Settings > Models).

Adapted from prosperos-study server/profiles.py, profile_routes.py and roles.py at bbcbde4. A
profile is one provider, model, address and saved key, as in the Study. Changes: profiles are
edited in place with a revision check instead of versioned (no Dungeon record needs an exact
earlier profile), and the Study's per-story step overrides become workspace job assignments. The
conversation profile plays the Study's Primary Writer: every other job uses it until the user
assigns another profile.

Saving a profile never contacts the service. A saved key stays with its provider and address:
changing either drops it, so a key is never sent somewhere it was not entered for.
"""
import random
import sqlite3
from urllib.parse import urlsplit

from dungeon.database import decode, encode, identifier, many, one, optional
from dungeon.errors import require
from dungeon.providers.builtin_recall import recall_config
from dungeon.providers.config import (
    CLI_PROVIDERS,
    DEFAULT_URLS,
    PROVIDER_NAMES,
    ProfileConfig,
    ProfileCreate,
    ProfileUpdate,
    decisions_ready,
    is_recall,
    profile_ready,
    ready_for,
    recall_ready,
)
from dungeon.providers.urls import is_loopback, validate_compatible_url
from dungeon.providers.vault import credential_for

CHAT = 'chat'
JOBS = [
    {'key': CHAT, 'name': 'Default', 'detail': 'Every job uses this profile unless you choose another.'},
    {'key': 'story', 'name': 'Story narrator', 'detail': 'Tells your story.'},
    {'key': 'referee', 'name': 'Referee', 'detail': 'Splits what you do into actions and picks the stat and '
     'difficulty of each roll. Off unless you choose a profile here: without one, keyword rules decide, and the '
     'narrator\'s model is never asked. A small, fast model is plenty.'},
    {'key': 'decisions', 'name': 'Referee decisions', 'detail': 'Decides, for each action, whether it needs a roll, '
     'which stat and how hard, from the odds a decision model gives each answer: Jev or OpenAI Decisions, or a model '
     'on a local or compatible server, such as the narrator\'s own. The Referee profile still splits the turn into '
     'actions when you choose one. Off unless you choose a profile here.'},
    {'key': 'continuity', 'name': 'Continuity', 'detail': 'After each turn, lists the new facts the narrator brought '
     'in for the record, and now and then folds older turns into the story so far. Facts are only kept when you choose '
     'a profile here; the story so far uses the Default without one. A small, fast model is plenty.'},
    {'key': 'director', 'name': 'Director', 'detail': 'Drafts the next beats of each story arc as it moves a stage, and '
     'gives a meaning to a detail you took an interest in. Off unless you choose a profile here: without one, beats '
     'come from the world\'s own arcs and code ties the detail to a thread.'},
    {'key': 'importer', 'name': 'World importer', 'detail': 'Drafts the sections of a world package (its places, '
     'factions, people, hidden truths and planned arcs) from the documents you import, for you to review. Uses the '
     'Default without a profile here. A large, careful model is worth it.'},
    {'key': 'recall', 'name': 'Semantic recall', 'detail': 'Embeddings that find related parts of the story, from a '
     'recall profile (Settings > Models > Recall) or built-in recall when it is on. Without either, recall matches '
     'keywords only.'},
]
JOB_KEYS = {job['key'] for job in JOBS}


def same_connection(first: dict, second: dict) -> bool:
    return first['provider'] == second['provider'] and (first['base_url'] == second['base_url'] or not first['base_url'])


def profile_view(row: dict, key_shared_with: list[str] | None = None) -> dict:
    config = decode(row['config'])
    return {'id': row['id'], 'name': row['name'], 'revision': row['revision'], 'config': config,
            'provider_name': PROVIDER_NAMES[config['provider']], 'has_saved_key': bool(row['credential_ref']),
            'key_shared_with': key_shared_with or [],
            'ready': profile_ready(config), 'recall_ready': recall_ready(config),
            'decisions_ready': decisions_ready(config), 'updated_at': row['updated_at']}


def routes(connection) -> dict[str, str]:
    return {row['job']: row['profile_id'] for row in many(connection, 'SELECT job, profile_id FROM model_routes')}


def overview(connection) -> dict:
    rows = many(connection, 'SELECT * FROM model_profiles ORDER BY name COLLATE NOCASE, created_at')
    return {'profiles': [profile_view(row, sharing(rows, row)) for row in rows], 'routes': routes(connection),
            'mix': {job: mix_view(connection, job) for job in MIX_JOBS},
            'jobs': JOBS}


def sharing(rows: list[dict], row: dict) -> list[str]:
    """The other profiles using this profile's saved key."""
    reference = row['credential_ref']
    return [other['name'] for other in rows if reference and other['credential_ref'] == reference and
            other['id'] != row['id']]


def view_of(connection, profile_id: str) -> dict:
    return profile_view(profile_row(connection, profile_id), sharing(many(connection, 'SELECT * FROM model_profiles'),
                                                                     profile_row(connection, profile_id)))


def profile_row(connection, profile_id: str) -> dict:
    return one(connection, 'SELECT * FROM model_profiles WHERE id=?', (profile_id,))


def assigned(connection, job: str) -> dict | None:
    """The profile row doing a job: its own assignment, else the conversation's."""
    assignments = routes(connection)
    profile_id = assignments.get(job) or assignments.get(CHAT)
    return optional(connection, 'SELECT * FROM model_profiles WHERE id=?', (profile_id,)) if profile_id else None


# Jobs whose model calls can come from a Mix: the narrator only, so its voice varies while every other job (the
# Referee, the record, recall) keeps one steady model.
MIX_JOBS = ('story',)
MIX_MODES = ('random', 'in_turn')


def mix_state(connection, job: str) -> dict:
    row = optional(connection, 'SELECT * FROM model_mix_state WHERE job=?', (job,))
    return row or {'job': job, 'enabled': 0, 'mode': 'random', 'turn': 0}


def mix_view(connection, job: str) -> dict:
    state = mix_state(connection, job)
    ids = [row['profile_id'] for row in many(connection, 'SELECT profile_id FROM model_mix WHERE job=? ORDER BY position',
                                             (job,))]
    return {'enabled': bool(state['enabled']), 'mode': state['mode'], 'profile_ids': ids}


def mixed(connection, job: str) -> list[dict]:
    """The finished profiles in a job's Mix while it is on and has at least two; otherwise none."""
    if job not in MIX_JOBS or not mix_state(connection, job)['enabled']:
        return []
    rows = many(connection, 'SELECT p.* FROM model_mix m JOIN model_profiles p ON p.id=m.profile_id WHERE m.job=? '
                'ORDER BY m.position', (job,))
    ready = [row for row in rows if ready_for(decode(row['config']), job)]
    return ready if len(ready) > 1 else []


def set_mix(database, job: str, profile_ids: list[str], mode: str, enabled: bool) -> dict:
    require(job in MIX_JOBS, 'Only the story narrator can mix models.', 422)
    require(mode in MIX_MODES, 'Unknown mix order.', 422)
    with database.connect(write=True) as connection:
        for profile_id in profile_ids:
            require(ready_for(decode(profile_row(connection, profile_id)['config']), job),
                    'Finish this profile: choose a model before adding it to the mix.', 409)
        connection.execute('DELETE FROM model_mix WHERE job=?', (job,))
        connection.executemany('INSERT INTO model_mix (job, profile_id, position) VALUES (?, ?, ?)',
                               [(job, profile_id, index) for index, profile_id in enumerate(dict.fromkeys(profile_ids))])
        connection.execute('INSERT INTO model_mix_state (job, enabled, mode, turn) VALUES (?, ?, ?, 0) ON CONFLICT(job) '
                           'DO UPDATE SET enabled=excluded.enabled, mode=excluded.mode', (job, int(enabled), mode))
        return overview(connection)


def reply_config(connection, job: str, chooser=random.choice) -> dict | None:
    """Settings for one narration: from the job's Mix when it is on (each profile with its own model and settings),
    else the job's profile. In turn moves on one profile per narration, so it needs a write connection."""
    rows = mixed(connection, job)
    if not rows:
        return config_for(connection, job)
    state = mix_state(connection, job)
    if state['mode'] == 'in_turn':
        row = rows[state['turn'] % len(rows)]
        connection.execute('UPDATE model_mix_state SET turn=? WHERE job=?', ((state['turn'] + 1) % len(rows), job))
    else:
        row = chooser(rows)
    return {**decode(row['config']), 'credential_ref': row['credential_ref'], 'profile_id': row['id'],
            'profile_name': row['name']}


def config_for(connection, job: str) -> dict | None:
    """Settings for a job's model calls, or None when no finished profile does it.

    The result is the profile's settings plus `credential_ref`, `profile_id` and `profile_name`, so
    callers read it the way they read the single connection before profiles. While built-in recall is
    on, it does recall instead of a profile.
    """
    if job == 'recall' and (builtin := recall_config(connection)):
        return builtin
    row = assigned(connection, job)
    if row is None:
        return None
    config = decode(row['config'])
    if not ready_for(config, job):
        return None
    return {**config, 'credential_ref': row['credential_ref'], 'profile_id': row['id'], 'profile_name': row['name']}


def key_for(vault, config: dict) -> str | None:
    return credential_for(vault, config.get('credential_ref'), config.get('provider'))


def probe_key(database, vault, body) -> str | None:
    """The key a connection test uses: the one typed, else the profile's saved key if it still applies, else a key
    another profile saved for the same service."""
    if body.api_key:
        return body.api_key
    config = body.config.model_dump()
    reference = None
    with database.connect() as connection:
        if body.profile_id:
            row = profile_row(connection, body.profile_id)
            if same_connection(decode(row['config']), config):
                reference = row['credential_ref']
        if reference is None:
            reference = (reusable_key(connection, config) or {}).get('credential_ref')
    return credential_for(vault, reference, config['provider'])


def same_service(first: dict, second: dict) -> bool:
    """The same provider at the same address, so a key saved for one is meant for the other."""
    return first['provider'] == second['provider'] and \
        (first.get('base_url') or '').rstrip('/') == (second.get('base_url') or '').rstrip('/')


def reusable_key(connection, config: dict, excluding: str | None = None) -> dict | None:
    """The profile whose saved key a new or keyless profile on the same service uses, most recently changed first.

    One key per service is what people expect (an OpenAI key for chat also does recall), so the app reuses it
    instead of asking for it again. The key never travels to another provider or address."""
    if config['provider'] in CLI_PROVIDERS:
        return None
    for row in many(connection, 'SELECT * FROM model_profiles WHERE credential_ref IS NOT NULL AND id IS NOT ? '
                    'ORDER BY updated_at DESC, created_at DESC', (excluding,)):
        if same_service(decode(row['config']), config):
            return row
    return None


def default_name(config: dict) -> str:
    model = (config.get('embedding_model') or '').strip() if is_recall(config) else config.get('model')
    if model:
        return f"{PROVIDER_NAMES[config['provider']]} · {model}"
    return f"{PROVIDER_NAMES[config['provider']]} {'recall' if is_recall(config) else 'connection'}"


def store_key(vault, body, reference: str | None) -> str | None:
    if not body.api_key:
        return reference
    require(body.config.provider not in CLI_PROVIDERS, 'This provider uses its own CLI login; do not enter a key here.', 422)
    reference = reference or identifier()
    vault.put(reference, body.api_key)
    return reference


def create(database, vault, body: ProfileCreate) -> dict:
    config = body.config.model_dump()
    profile_id = identifier()
    reference = store_key(vault, body, None)
    with database.connect(write=True) as connection:
        if reference is None:
            reference = (reusable_key(connection, config) or {}).get('credential_ref')
        timestamp = database.now()
        connection.execute('INSERT INTO model_profiles (id, name, config, credential_ref, revision, created_at, '
                           'updated_at) VALUES (?, ?, ?, ?, 1, ?, ?)',
                           (profile_id, body.name or default_name(config), encode(config), reference, timestamp,
                            timestamp))
        # The first finished profile answers in chat, so a new user is ready to talk after one form.
        if CHAT not in routes(connection) and profile_ready(config):
            assign(connection, CHAT, profile_id, timestamp)
        # The first finished recall profile does recall, unless the user already chose one for it.
        elif recall_ready(config) and 'recall' not in routes(connection):
            assign(connection, 'recall', profile_id, timestamp)
        return view_of(connection, profile_id)


def update(database, vault, profile_id: str, body: ProfileUpdate) -> dict:
    config = body.config.model_dump()
    with database.connect() as connection:
        current = profile_row(connection, profile_id)
    require(current['revision'] == body.expected_revision, 'This profile changed. Reopen it and try again.', 409)
    kept = current['credential_ref'] if same_connection(decode(current['config']), config) else None
    if kept and body.api_key and not body.share_key and shared(database, kept, profile_id):
        kept = None  # Asked for a key of its own: the others keep the shared one.
    reference = store_key(vault, body, kept)
    with database.connect(write=True) as connection:
        row = profile_row(connection, profile_id)
        require(row['revision'] == body.expected_revision, 'This profile changed. Reopen it and try again.', 409)
        if reference is None:
            reference = (reusable_key(connection, config, profile_id) or {}).get('credential_ref')
        connection.execute('UPDATE model_profiles SET name=?, config=?, credential_ref=?, revision=revision+1, '
                           'updated_at=? WHERE id=?',
                           (body.name or default_name(config), encode(config), reference, database.now(), profile_id))
        require_assignable(connection, profile_id)
        result = view_of(connection, profile_id)
    if current['credential_ref'] and current['credential_ref'] != reference:
        release(database, vault, current['credential_ref'])
    return result


def learn_effort(database, config: dict, instead: str | None, levels: list[str] | None):
    """The model turned down the profile's reasoning effort (providers/efforts.py): the profile asks with `instead`
    from now on and, when the service named them, offers only `levels` in Settings. A profile changed meanwhile is
    left as the user made it."""
    profile_id = config.get('profile_id')
    if not profile_id:
        return
    with database.connect(write=True) as connection:
        row = optional(connection, 'SELECT * FROM model_profiles WHERE id=?', (profile_id,))
        saved = decode(row['config']) if row else None
        if not saved or saved.get('model') != config.get('model') or \
                saved.get('reasoning_effort') != config.get('reasoning_effort'):
            return
        saved['reasoning_effort'] = instead
        if levels:
            reported = saved.get('reported_capabilities') or {}
            if reported.get('model_id') != saved['model']:
                reported = {'model_id': saved['model']}
            saved['reported_capabilities'] = {**reported, 'supported_efforts': levels}
        connection.execute('UPDATE model_profiles SET config=?, revision=revision+1, updated_at=? WHERE id=?',
                           (encode(saved), database.now(), profile_id))


def require_assignable(connection, profile_id: str):
    """A profile doing a job, or in a Mix, must stay able to do it."""
    row = profile_row(connection, profile_id)
    jobs = [job for job, assigned_id in routes(connection).items() if assigned_id == profile_id]
    jobs += [item['job'] for item in many(connection, 'SELECT job FROM model_mix WHERE profile_id=?', (profile_id,))]
    require(all(ready_for(decode(row['config']), job) for job in jobs),
            'This profile does a job in Settings > Models. Choose a model (an embedding model, for recall) before '
            'saving it, or assign the job to another profile first.', 409)


def delete(database, vault, profile_id: str) -> dict:
    with database.connect(write=True) as connection:
        row = profile_row(connection, profile_id)
        # Jobs it did fall back to the conversation profile, or wait for one.
        connection.execute('DELETE FROM model_routes WHERE profile_id=?', (profile_id,))
        connection.execute('DELETE FROM model_mix WHERE profile_id=?', (profile_id,))
        connection.execute('DELETE FROM model_profiles WHERE id=?', (profile_id,))
        result = overview(connection)
    if row['credential_ref']:
        release(database, vault, row['credential_ref'])
    return result


def duplicate(database, profile_id: str) -> dict:
    """A copy of a profile, named "… copy", sharing its saved key. Jobs stay with the original."""
    with database.connect(write=True) as connection:
        row = profile_row(connection, profile_id)
        names = {item['name'] for item in many(connection, 'SELECT name FROM model_profiles')}
        name, number = f"{row['name']} copy"[:120], 2
        while name in names:
            name, number = f"{row['name']} copy {number}"[:120], number + 1
        copy_id, timestamp = identifier(), database.now()
        connection.execute('INSERT INTO model_profiles (id, name, config, credential_ref, revision, created_at, '
                           'updated_at) VALUES (?, ?, ?, ?, 1, ?, ?)',
                           (copy_id, name, row['config'], row['credential_ref'], timestamp, timestamp))
        return view_of(connection, copy_id)


def shared(database, reference: str, profile_id: str) -> bool:
    with database.connect() as connection:
        return optional(connection, 'SELECT 1 FROM model_profiles WHERE credential_ref=? AND id<>? LIMIT 1',
                        (reference, profile_id)) is not None


def release(database, vault, reference: str):
    """Remove a saved key once no profile uses it: a recall profile split from a text profile shares its key."""
    with database.connect() as connection:
        if optional(connection, 'SELECT 1 FROM model_profiles WHERE credential_ref=? LIMIT 1', (reference,)):
            return
    vault.delete(reference)


def assign(connection, job: str, profile_id: str | None, timestamp: str):
    require(job in JOB_KEYS, 'Unknown model job.', 422)
    if profile_id is None:
        connection.execute('DELETE FROM model_routes WHERE job=?', (job,))
        return
    row = profile_row(connection, profile_id)
    config = decode(row['config'])
    if job == 'recall':
        require(recall_ready(config), 'Semantic recall needs a profile with an embedding model.', 409)
    elif job == 'decisions':
        require(decisions_ready(config), 'Referee decisions need a decisions profile, or a text profile with a model '
                'on a local or OpenAI-compatible server.', 409)
    else:
        require(profile_ready(config), 'Finish this profile: choose a model before giving it a job.', 409)
    connection.execute('INSERT INTO model_routes (job, profile_id, updated_at) VALUES (?, ?, ?) ON CONFLICT(job) '
                       'DO UPDATE SET profile_id=excluded.profile_id, updated_at=excluded.updated_at',
                       (job, profile_id, timestamp))


def set_route(database, job: str, profile_id: str | None) -> dict:
    with database.connect(write=True) as connection:
        assign(connection, job, profile_id, database.now())
        return overview(connection)


# --- The single connection from before profiles -------------------------------------------------

def legacy_provider(base_url: str) -> str:
    return 'local' if is_loopback(urlsplit(base_url).hostname) else 'compatible'


def split_recall(connection, timestamp: str):
    """Move embedding models out of text profiles into recall profiles of their own, once.

    Before recall profiles, a text profile could carry an embedding model. Each one becomes a recall
    profile on the same service, sharing its saved key, and recall keeps the model it used. Runs at
    every start, on whatever connection initialization has open.
    """
    factory = connection.row_factory
    connection.row_factory = sqlite3.Row
    try:
        split_profiles(connection, timestamp)
    finally:
        connection.row_factory = factory


def split_profiles(connection, timestamp: str):
    assignments = routes(connection)
    for row in many(connection, 'SELECT * FROM model_profiles ORDER BY created_at'):
        config = decode(row['config'])
        embedding = (config.get('embedding_model') or '').strip()
        if is_recall(config) or not embedding:
            continue
        recall = {'provider': config['provider'], 'model': '', 'base_url': config['base_url'], 'purpose': 'recall',
                  'embedding_model': embedding, 'timeout_seconds': config.get('timeout_seconds', 180),
                  'max_output_tokens': 800, 'context_tokens': 16000, 'resource_group': config.get('resource_group', '')}
        recall_id = matching_recall(connection, recall, row['credential_ref'])
        if recall_id is None:
            recall_id = identifier()
            connection.execute('INSERT INTO model_profiles (id, name, config, credential_ref, revision, created_at, '
                               'updated_at) VALUES (?, ?, ?, ?, 1, ?, ?)',
                               (recall_id, default_name(recall), encode(ProfileConfig.model_construct(**recall)
                                                                         .model_dump()),
                                row['credential_ref'], timestamp, timestamp))
        connection.execute('UPDATE model_profiles SET config=?, revision=revision+1, updated_at=? WHERE id=?',
                           (encode({**config, 'embedding_model': ''}), timestamp, row['id']))
        # Recall keeps the model it used: the one assigned to it, else the conversation's.
        if assignments.get('recall', assignments.get(CHAT)) == row['id']:
            assignments['recall'] = recall_id
            connection.execute('INSERT INTO model_routes (job, profile_id, updated_at) VALUES (?, ?, ?) ON CONFLICT(job) '
                               'DO UPDATE SET profile_id=excluded.profile_id, updated_at=excluded.updated_at',
                               ('recall', recall_id, timestamp))


def matching_recall(connection, recall: dict, reference: str | None) -> str | None:
    for row in many(connection, 'SELECT * FROM model_profiles WHERE credential_ref IS ?', (reference,)):
        config = decode(row['config'])
        if is_recall(config) and same_connection(config, recall) and config.get('embedding_model') == \
                recall['embedding_model']:
            return row['id']
    return None


def connection_summary(connection) -> dict | None:
    """The conversation profile in the shape of the old single connection (setup checklist, scripts)."""
    row = assigned(connection, CHAT)
    if row is None:
        return None
    config = decode(row['config'])
    return {'profile_id': row['id'], 'name': row['name'], 'provider': config['provider'],
            'provider_name': PROVIDER_NAMES[config['provider']], 'base_url': config['base_url'],
            'model': config['model'], 'has_key': bool(row['credential_ref']), 'ready': profile_ready(config),
            'max_output_tokens': config['max_output_tokens'], 'context_tokens': config['context_tokens'],
            'timeout_seconds': config['timeout_seconds'],
            'embedding_model': (config_for(connection, 'recall') or {}).get('embedding_model') or None,
            'builtin': config.get('resource_group') == 'builtin-chat'}


def quick_save(database, vault, body) -> dict:
    """`PUT /api/connection`: set the conversation to an OpenAI-compatible or local server in one call.

    Updates the conversation profile when it is already such a profile, otherwise adds one.
    """
    base_url = body.base_url.rstrip('/')
    validate_compatible_url(base_url)
    settings = {'provider': legacy_provider(base_url), 'model': body.model, 'base_url': base_url,
                'max_output_tokens': body.max_output_tokens, 'context_tokens': body.context_tokens,
                'timeout_seconds': body.timeout_seconds}
    with database.connect() as connection:
        current = assigned(connection, CHAT)
    if current and decode(current['config'])['provider'] in {'local', 'compatible'}:
        update(database, vault, current['id'], ProfileUpdate(name=current['name'], config=settings,
                                                             api_key=body.api_key, expected_revision=current['revision']))
        profile_id = current['id']
    else:
        profile_id = create(database, vault, ProfileCreate(name='Text model', config=settings,
                                                           api_key=body.api_key))['id']
    with database.connect(write=True) as connection:
        assign(connection, CHAT, profile_id, database.now())
        if body.embedding_model:
            # The old single connection carried its embedding model; it becomes this service's recall profile.
            row = profile_row(connection, profile_id)
            connection.execute('UPDATE model_profiles SET config=? WHERE id=?',
                               (encode({**decode(row['config']), 'embedding_model': body.embedding_model}), profile_id))
            connection.execute("DELETE FROM model_routes WHERE job='recall'")
            split_recall(connection, database.now())
        return connection_summary(connection)


__all__ = ['CHAT', 'reply_config', 'set_mix', 'DEFAULT_URLS', 'JOBS', 'split_recall', 'config_for', 'connection_summary', 'create', 'delete', 'duplicate',
           'key_for', 'overview', 'probe_key', 'quick_save', 'set_route', 'update']
