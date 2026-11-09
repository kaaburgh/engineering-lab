#!/usr/bin/env python3
"""Run deterministic WRAP.COM correctness regression on THIS Linux host.

Build and export DOSBox + NASM COM elsewhere if necessary; ALL game/probe
execution must happen locally. Requires Xvfb/xdpyinfo, DOSBox Staging and
the verify_wrap_trace.py helper from kaaburgh/dosbox-staging.
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


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stop(proc):
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


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dosbox', type=Path, required=True)
    p.add_argument('--libraries', type=Path, required=True)
    p.add_argument('--com', type=Path, required=True)
    p.add_argument('--verifier', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--cwd', type=Path, required=True)
    p.add_argument('--passes', type=int, default=3)
    p.add_argument('--display', default=':176')
    p.add_argument('--require-reuse', action='store_true')
    a = p.parse_args()
    if not 1 <= a.passes <= 9:
        p.error('--passes must be between 1 and 9')
    output = a.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    shutil.copy2(a.com, output / 'WRAP.COM')
    config = output / 'dosbox.conf'
    config.write_text('[dosbox]\nmemsize=32\n[cpu]\ncore=dynamic\n'
                      'cputype=pentium\ncpu_cycles=3000\n[sdl]\n'
                      'output=texture\ntexture_renderer=software\n')
    cmd = [str(a.dosbox.resolve()), '--noprimaryconf', '--nolocalconf',
           '--noautoexec', '--conf', str(config),
           '-c', f'mount c "{output}"', '-c', 'c:']
    for n in range(1, a.passes + 1):
        cmd.extend(['-c', 'WRAP.COM', '-c', f'ren WRAP.OK PASS{n}.OK'])
    cmd.extend(['-c', 'exit'])
    env = dict(os.environ, DISPLAY=a.display, SDL_AUDIODRIVER='dummy',
               SDL_VIDEODRIVER='x11', SDL_RENDER_DRIVER='software',
               LD_LIBRARY_PATH=str(a.libraries.resolve()),
               DOSBOX_JIT_BLOCK_TRACE=str(output / 'jit-blocks.csv'))
    with (output / 'xvfb.log').open('w') as log:
        xvfb = subprocess.Popen(['Xvfb', a.display, '-screen', '0',
                                 '1280x720x24', '-nolisten', 'tcp'],
                                stdout=log, stderr=subprocess.STDOUT,
                                start_new_session=True)
    try:
        for _ in range(100):
            if subprocess.run(['xdpyinfo', '-display', a.display],
                              stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL).returncode == 0:
                break
            time.sleep(.05)
        else:
            raise RuntimeError('Xvfb did not start')
        with (output / 'dosbox.log').open('w') as log:
            proc = subprocess.Popen(cmd, env=env, cwd=a.cwd.resolve(),
                                    stdout=log, stderr=subprocess.STDOUT,
                                    start_new_session=True)
            try:
                proc.wait(timeout=90)
            except subprocess.TimeoutExpired:
                stop(proc)
                raise RuntimeError('DOSBox probe timed out')
    finally:
        stop(xvfb)
    markers = [output / f'PASS{n}.OK' for n in range(1, a.passes + 1)]
    verify = [sys.executable, str(a.verifier.resolve()),
              '--trace', str(output / 'jit-blocks.csv')]
    for marker in markers:
        verify.extend(['--marker', str(marker)])
    if a.require_reuse:
        verify.append('--require-reuse')
    verify.extend(['--dosbox-log', str(output / 'dosbox.log')])
    verify.extend(['--output-json', str(output / 'verified.json')])
    subprocess.run(verify, check=True)
    manifest = {'dosbox_sha256': sha(a.dosbox), 'com_sha256': sha(a.com),
                'trace_sha256': sha(output / 'jit-blocks.csv'),
                'passes': a.passes, 'require_reuse': a.require_reuse,
                'local_platform': list(os.uname())}
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print('Local probe verified; evidence:', output)


if __name__ == '__main__':
    main()
