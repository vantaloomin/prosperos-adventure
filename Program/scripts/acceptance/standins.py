"""Stand-in model and ComfyUI servers for the end-to-end acceptance pass.

Nothing is downloaded. The model server speaks the OpenAI-compatible chat and embeddings API and
logs every request body to a JSON-lines file, so a run can inspect exactly what reached the model.
The ComfyUI server accepts any workflow and returns a small PNG after a configurable delay.

    python scripts/acceptance/standins.py --log requests.jsonl      # model :1234, ComfyUI :8188

`POST /control` on the model server changes the per-word delay (`{"delay": 0.2}`) at run time.
"""
import argparse
import asyncio
import base64
import hashlib
import json
import threading
import time
from uuid import uuid4

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse

PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==')
STATE = {'delay': 0.05, 'log': None, 'image_seconds': 2.0}


def record(kind, body):
    if STATE['log']:
        with open(STATE['log'], 'a', encoding='utf-8') as handle:
            handle.write(json.dumps({'at': time.time(), 'kind': kind, 'body': body}) + '\n')


def answer_for(system: str, messages: list[dict]) -> str:
    last = messages[-1]['content'] if messages else ''
    if 'Rephrase one ordinary moment' in system:
        facts = json.loads(last)
        return json.dumps({'summary': f"In my words: {facts['summary']}", 'post': 'A small good moment.'})
    if 'suggest' in system.lower() and 'memor' in system.lower():
        return '[]'
    return f'Stand-in reply to: {last[:80]}. Tell me more about your day.'


def model_app() -> FastAPI:
    app = FastAPI()

    @app.post('/control')
    async def control(request: Request):
        STATE.update(await request.json())
        return STATE

    @app.get('/v1/models')
    async def models():
        return {'data': [{'id': 'stand-in'}, {'id': 'stand-in-embed'}]}

    @app.post('/v1/embeddings')
    async def embeddings(request: Request):
        body = await request.json()
        record('embeddings', body)
        inputs = body['input'] if isinstance(body['input'], list) else [body['input']]
        data = []
        for index, text in enumerate(inputs):
            vector = [0.0] * 32
            for word in str(text).lower().split():
                vector[int(hashlib.sha1(word.encode()).hexdigest(), 16) % 32] += 1.0
            data.append({'index': index, 'embedding': vector})
        return {'data': data, 'model': body.get('model')}

    @app.post('/v1/chat/completions')
    async def chat(request: Request):
        body = await request.json()
        record('chat', body)
        system = body['messages'][0]['content'] if body['messages'] and body['messages'][0]['role'] == 'system' else ''
        text = answer_for(system, body['messages'][1:])
        words = text.split(' ')

        async def events():
            for index, word in enumerate(words):
                await asyncio.sleep(STATE['delay'])
                piece = word if index == 0 else ' ' + word
                yield f"data: {json.dumps({'choices': [{'delta': {'content': piece}}]})}\n\n"
            yield f"data: {json.dumps({'choices': [{'delta': {}, 'finish_reason': 'stop'}]})}\n\n"
            yield 'data: [DONE]\n\n'
        return StreamingResponse(events(), media_type='text/event-stream')

    return app


def comfy_app() -> FastAPI:
    app = FastAPI()
    prompts: dict[str, dict] = {}

    @app.get('/object_info')
    async def object_info():
        names = ['UNETLoader', 'CLIPLoader', 'VAELoader', 'CLIPTextEncode', 'KSampler', 'EmptySD3LatentImage',
                 'EmptyLatentImage', 'VAEDecode', 'SaveImage', 'LoraLoaderModelOnly', 'ModelSamplingAuraFlow',
                 'EmptyHunyuanLatentVideo']
        return {name: {'input': {'required': {}}} for name in names}

    @app.post('/prompt')
    async def prompt(request: Request):
        body = await request.json()
        record('comfy', body)
        prompt_id = uuid4().hex
        prompts[prompt_id] = {'started': time.time()}
        return {'prompt_id': prompt_id, 'number': len(prompts), 'node_errors': {}}

    @app.get('/history/{prompt_id}')
    async def history(prompt_id: str):
        entry = prompts.get(prompt_id)
        if entry is None or time.time() - entry['started'] < STATE['image_seconds']:
            return {}
        return {prompt_id: {'status': {'status_str': 'success', 'completed': True},
                            'outputs': {'9': {'images': [{'filename': f'{prompt_id}.png', 'subfolder': '',
                                                          'type': 'output'}]}}}}

    @app.get('/view')
    async def view():
        return Response(PNG, media_type='image/png')

    @app.get('/queue')
    async def queue():
        running = [[0, key] for key, entry in prompts.items() if time.time() - entry['started'] < STATE['image_seconds']]
        return {'queue_running': running, 'queue_pending': []}

    @app.post('/queue')
    async def delete(request: Request):
        return JSONResponse({})

    @app.post('/interrupt')
    async def interrupt(request: Request):
        return JSONResponse({})

    return app


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--log')
    parser.add_argument('--model-port', type=int, default=1234)
    parser.add_argument('--comfy-port', type=int, default=8188)
    arguments = parser.parse_args()
    STATE['log'] = arguments.log
    comfy = uvicorn.Server(uvicorn.Config(comfy_app(), host='127.0.0.1', port=arguments.comfy_port, log_level='warning'))
    threading.Thread(target=comfy.run, daemon=True).start()
    uvicorn.run(model_app(), host='127.0.0.1', port=arguments.model_port, log_level='warning')


if __name__ == '__main__':
    main()
