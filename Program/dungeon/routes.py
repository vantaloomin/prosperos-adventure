"""Local HTTP API for the Dungeon backbone: health, settings, the model connection, prompts and backups."""
from fastapi import APIRouter, Request

from dungeon import auto_backup, backup, data_folder, logs, prompt_library, restore, text_models, workspace
from dungeon.identity import APP_ID, VERSION
from dungeon.models import ConnectionUpdate, PromptUpdate, SettingsUpdate

router = APIRouter(prefix='/api')


def db(request: Request):
    return request.app.state.database


@router.get('/health')
def health():
    return {'app_id': APP_ID, 'version': VERSION}


@router.post('/logs/open-folder')
def open_log_folder():
    """Show the folder holding the log on the PC, for "Open the log folder" under an error."""
    folder = logs.file_path().parent
    logs.open_folder(folder)
    return {'folder': str(folder)}


@router.get('/settings')
def read_settings(request: Request):
    return workspace.read(db(request))


@router.put('/settings')
def update_settings(request: Request, body: SettingsUpdate):
    return workspace.update(db(request), body)


@router.get('/connection')
def read_connection(request: Request):
    """The story narrator's model profile, in the shape of the single connection before profiles."""
    with db(request).connect() as connection:
        return {'connection': text_models.connection_summary(connection)}


@router.put('/connection')
def save_connection(request: Request, body: ConnectionUpdate):
    """Quick setup: point the app at an OpenAI-compatible or local server. Saving never contacts it."""
    return text_models.quick_save(db(request), request.app.state.vault, body)


@router.get('/prompts')
def read_prompts(request: Request):
    return prompt_library.views(db(request))


@router.put('/prompts/{name}')
def save_prompt(request: Request, name: str, body: PromptUpdate):
    return prompt_library.save(db(request), name, body.text)


@router.delete('/prompts/{name}')
def reset_prompt(request: Request, name: str):
    return prompt_library.reset(db(request), name)


@router.post('/backups')
def create_backup(request: Request):
    return backup.create(db(request), db(request).path.parent / 'backups')


@router.get('/backups')
def list_backups(request: Request):
    return restore.listing(db(request).path.parent) | auto_backup.status(db(request))


@router.post('/backups/{name}/restore')
def schedule_restore(request: Request, name: str):
    """The restore runs the next time the Dungeon starts; the running app keeps its workspace."""
    return restore.schedule(db(request).path.parent, name, db(request).now())


@router.delete('/backups/restore')
def cancel_restore(request: Request):
    return restore.cancel(db(request).path.parent)


@router.get('/backups/data-folder')
def read_data_folder(request: Request):
    return data_folder.status(db(request).root)


@router.post('/backups/data-folder/move')
def schedule_data_move(request: Request):
    """The move runs the next time the Dungeon starts; the open workspace cannot be copied safely."""
    return data_folder.schedule(db(request).root, db(request).now())


@router.delete('/backups/data-folder/move')
def cancel_data_move(request: Request):
    return data_folder.cancel(db(request).root)


@router.post('/backups/data-folder/open')
def open_data_folder(request: Request):
    return data_folder.open_folder(db(request).root)
