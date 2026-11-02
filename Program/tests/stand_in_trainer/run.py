"""A stand-in for AI Toolkit's run.py, used by the tests. It reads the generated config, prints a
tqdm-style progress bar, saves checkpoints the way AI Toolkit names them, and resumes from the
newest one. Environment variables script failures and hangs."""
import glob
import json
import os
import struct
import sys
import time


def adapter(step: int) -> bytes:
    header = json.dumps({'__metadata__': {'step': str(step)},
                         'a.lokr_w1': {'dtype': 'F16', 'shape': [2, 2], 'data_offsets': [0, 8]}}).encode()
    return struct.pack('<Q', len(header)) + header + bytes(8)


def save(path: str, step: int):
    with open(path + '.tmp', 'wb') as handle:
        handle.write(adapter(step))
    os.replace(path + '.tmp', path)


def main():
    with open(sys.argv[1], encoding='utf-8') as handle:
        config = json.load(handle)
    process = config['config']['process'][0]
    name = config['config']['name']
    steps, every = process['train']['steps'], process['save']['save_every']
    out = os.path.join(process['training_folder'], name)
    os.makedirs(out, exist_ok=True)
    if os.environ.get('FAKE_TRAINER_RECORD'):
        with open(os.environ['FAKE_TRAINER_RECORD'], 'a', encoding='utf-8') as handle:
            handle.write(json.dumps({'cwd': os.getcwd(), 'argv': sys.argv,
                                     'captions': sorted(open(path, encoding='utf-8').read() for path in glob.glob(
                                         os.path.join(process['datasets'][0]['folder_path'], '*.txt')))}) + '\n')
    saved = glob.glob(os.path.join(out, f'{name}_*.safetensors'))
    start = 0
    if saved:
        latest = max(saved, key=os.path.getctime)
        start = int(latest[-21:-12])
        print(f'#### IMPORTANT RESUMING FROM {latest} ####', flush=True)
    fail_at = int(os.environ.get('FAKE_TRAINER_FAIL_AT', '0'))
    hang_at = int(os.environ.get('FAKE_TRAINER_HANG_AT', '0'))
    delay = float(os.environ.get('FAKE_TRAINER_DELAY', '0'))
    for step in range(start + 1, steps + 1):
        time.sleep(delay)
        sys.stdout.write(f'\r{name}:  {step * 100 // steps}%|##| {step}/{steps} [00:01<00:01, loss: 1.0e-01]')
        sys.stdout.flush()
        if step % every == 0 and step != steps:
            save(os.path.join(out, f'{name}_{step:09d}.safetensors'), step)
        if step == fail_at:
            print('\ntorch.OutOfMemoryError: CUDA out of memory', flush=True)
            sys.exit(1)
        if step == hang_at:
            while True:
                time.sleep(0.1)
    save(os.path.join(out, f'{name}.safetensors'), steps)
    print('\nResult:\n - 1 completed job', flush=True)


if __name__ == '__main__':
    main()
