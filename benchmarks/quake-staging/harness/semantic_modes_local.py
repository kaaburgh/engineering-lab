#!/usr/bin/env python3
"""Check guest semantics under three DOSBox instrumentation states, LOCAL host.

Scenarios: completely compiled out, compiled in but recording inactive,
and compiled in with lifecycle recording active. NO FPS measurements.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time


def terminate(proc):
    if proc.poll() is not None:
        return
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.wait(timeout=3)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ('off', 'on', 'libraries', 'smc', 'xpg', 'wrap', 'verifier_dir', 'cwd', 'output'):
        p.add_argument('--' + key.replace('_', '-'), required=True, type=Path)
    p.add_argument('--display', default=':181')
    a = p.parse_args()
    root = a.output.resolve()
    root.mkdir(parents=True, exist_ok=False)
    variants = [('off', a.off, False),
                ('inactive', a.on, False),
                ('active', a.on, True)]
    probes = [('SMC.COM', 'SMC.OK', a.smc),
              ('XPG.COM', 'XPG.OK', a.xpg),
              ('WRAP.COM', 'WRAP.OK', a.wrap)]
    config = ('[dosbox]\nmemsize=32\n[cpu]\ncore=dynamic\n'
              'cputype=pentium\ncpu_cycles=3000\n[sdl]\n'
              'output=texture\ntexture_renderer=software\n')
    sys.path.insert(0, str(a.verifier_dir.resolve()))
    from analyze_trace import events_from_csv, classify, reject_recorder_io_errors
    with (root / 'xvfb.log').open('w') as log:
        xvfb = subprocess.Popen(['Xvfb', a.display, '-screen', '0',
                                 '1280x720x24', '-nolisten', 'tcp'],
                                stdout=log, stderr=subprocess.STDOUT,
                                start_new_session=True)
    results = []
    try:
        for _ in range(100):
            if subprocess.run(['xdpyinfo', '-display', a.display],
                              stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL).returncode == 0:
                break
            time.sleep(.05)
        else:
            raise RuntimeError('Xvfb did not start')
        for label, binary, active in variants:
            for program, marker, source in probes:
                folder = root / (label + '-' + program.lower()[:-4])
                folder.mkdir()
                shutil.copy2(source, folder / program)
                (folder / 'dosbox.conf').write_text(config)
                env = dict(os.environ, DISPLAY=a.display,
                           SDL_AUDIODRIVER='dummy', SDL_VIDEODRIVER='x11',
                           SDL_RENDER_DRIVER='software',
                           LD_LIBRARY_PATH=str(a.libraries.resolve()))
                env.pop('DOSBOX_JIT_BLOCK_TRACE', None)
                if active:
                    env['DOSBOX_JIT_BLOCK_TRACE'] = str(folder / 'jit-blocks.csv')
                cmd = [str(binary.resolve()), '--noprimaryconf',
                       '--nolocalconf', '--noautoexec', '--conf',
                       str(folder / 'dosbox.conf'),
                       '-c', f'mount c "{folder}"', '-c', 'c:',
                       '-c', program, '-c', 'exit']
                with (folder / 'dosbox.log').open('w') as log:
                    proc = subprocess.Popen(cmd, cwd=a.cwd.resolve(), env=env,
                                            stdout=log, stderr=subprocess.STDOUT,
                                            start_new_session=True)
                    try:
                        code = proc.wait(timeout=90)
                    except subprocess.TimeoutExpired:
                        terminate(proc)
                        raise RuntimeError(f'{label}/{program} timed out')
                assert code == 0, (label, program, code)
                assert (folder / marker).read_bytes() == b'OK\r\n', (label, program)
                trace = folder / 'jit-blocks.csv'
                assert trace.exists() == active, (label, program, 'unexpected logging')
                created = cleared = None
                if active:
                    reject_recorder_io_errors(folder / 'dosbox.log')
                    summary, _ = classify(events_from_csv(trace), [])
                    created, cleared = summary['creates'], summary['invalidations']
                results.append({'variant': label, 'program': program,
                                'guest_checksum_correct': True,
                                'trace_present': active,
                                'created': created, 'invalidated': cleared,
                                'binary_sha256': sha256(binary)})
                print(results[-1], flush=True)
    finally:
        terminate(xvfb)
    assert len(results) == 9
    (root / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
    print('All 9 local guest-semantic equivalence tests passed.')


if __name__ == '__main__':
    main()
