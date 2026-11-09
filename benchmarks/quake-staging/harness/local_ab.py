#!/usr/bin/env python3
"""Local interleaved A/B/C Quake 1.06 timedemo with fixed renderer.

No benchmark timing is taken from GitHub CI: run only on the target host.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import time

FPS = re.compile(r'(\d+)\s+frames\s+([\d.]+)\s+seconds\s+([\d.]+)\s+fps', re.I)
ORDERS = [
    ('off','inactive','trace'),('trace','inactive','off'),
    ('inactive','off','trace'),('off','trace','inactive'),
    ('trace','off','inactive'),('inactive','trace','off'),
]


def sha256(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stop(proc):
    if proc.poll() is not None: return
    try: os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError: pass
    try: proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        try: os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError: pass
        proc.wait(timeout=2)


def run_one(label, number, batch, a):
    folder=a.out/f'{number:02d}-{label}'
    folder.mkdir(parents=True,exist_ok=False)
    game=folder/'game'
    shutil.copytree(a.game,game)
    for p in game.rglob('*'):
        if p.is_file() and p.name.casefold()=='qconsole.log': p.unlink()
    config=folder/'dosbox.conf'
    config.write_text('[dosbox]\nmemsize = 32\n[cpu]\ncore = dynamic\n'
                      'cputype = pentium\ncpu_cycles = 3000\n'
                      'cpu_cycles_protected = max\n[sdl]\noutput = texture\n'
                      'texture_renderer = software\n')
    binary=a.off if label=='off' else a.on
    cmd=[str(binary),'--noprimaryconf','--nolocalconf','--noautoexec',
         '--conf',str(config),'-c',f'mount c "{game}"','-c','c:',
         '-c','quake.exe -nosound -nocdaudio -condebug -width 320 '
              '-height 200 +timedemo demo1']
    env=dict(os.environ, SDL_AUDIODRIVER='dummy',SDL_VIDEODRIVER='x11',
             SDL_RENDER_DRIVER='software',DISPLAY=a.display,
             LD_LIBRARY_PATH=str(a.libs))
    env.pop('DOSBOX_JIT_BLOCK_TRACE',None)
    env.pop('LD_PRELOAD',None)
    if label=='trace':env['DOSBOX_JIT_BLOCK_TRACE']=str(folder/'jit-blocks.csv')
    t0=time.monotonic()
    result={'run':number,'batch':batch,'condition':label,'fps':None,
            'quake_seconds':None,'frames':None,'wall_seconds':None,
            'status':'no-result'}
    with (folder/'dosbox.log').open('w') as log:
        proc=subprocess.Popen(cmd,cwd=a.cwd,env=env,stdout=log,
                              stderr=subprocess.STDOUT,start_new_session=True)
        try:
            while time.monotonic()-t0<a.timeout:
                if proc.poll() is not None:break
                path=game/'ID1'/'QCONSOLE.LOG'
                if path.exists():
                    matches=FPS.findall(path.read_bytes().decode('latin1','replace'))
                    if matches:
                        frames,secs,fps=matches[-1]
                        result.update(fps=float(fps),quake_seconds=float(secs),
                                      frames=int(frames),status='ok')
                        break
                time.sleep(.09)
        finally: stop(proc)
    result['wall_seconds']=round(time.monotonic()-t0,3)
    trace=folder/'jit-blocks.csv'
    result['trace_bytes']=trace.stat().st_size if trace.exists() else 0
    (folder/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--off',type=Path,required=True)
    p.add_argument('--on',type=Path,required=True)
    p.add_argument('--libs',type=Path,required=True)
    p.add_argument('--game',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--cwd',type=Path,required=True)
    p.add_argument('--rounds',type=int,default=6)
    p.add_argument('--timeout',type=int,default=90)
    p.add_argument('--display',default=':161')
    a=p.parse_args()
    for key in ('off','on','libs','game','cwd'):
        setattr(a,key,getattr(a,key).resolve())
    a.out=a.out.resolve()
    a.out.mkdir(parents=True,exist_ok=True)
    manifest={'host':list(os.uname()),'off_sha256':sha256(a.off),
              'on_sha256':sha256(a.on),
              'quake_sha256':sha256(a.game/'QUAKE.EXE'),
              'rounds':a.rounds,'orders':[ORDERS[b%len(ORDERS)] for b in range(a.rounds)],
              'cpu_quota':Path('/sys/fs/cgroup/cpu.max').read_text().strip()}
    (a.out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    with (a.out/'xvfb.log').open('w') as log:
        xvfb=subprocess.Popen(['Xvfb',a.display,'-screen','0','1280x720x24',
                               '-nolisten','tcp'],stdout=log,
                              stderr=subprocess.STDOUT,start_new_session=True)
        try:
            env=dict(os.environ,DISPLAY=a.display)
            for _ in range(100):
                if subprocess.run(['xdpyinfo','-display',a.display],env=env,
                                  stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL).returncode==0:break
                time.sleep(.08)
            else:raise RuntimeError('Xvfb did not start')
            rows=[]
            for batch in range(a.rounds):
                for label in ORDERS[batch%len(ORDERS)]:
                    row=run_one(label,len(rows)+1,batch+1,a)
                    rows.append(row)
                    with (a.out/'results.csv').open('w',newline='') as f:
                        w=csv.DictWriter(f,fieldnames=list(rows[0]))
                        w.writeheader()
                        w.writerows(rows)
                    print(json.dumps(row),flush=True)
                    if row['status']!='ok' or row['frames']!=969:
                        raise RuntimeError('Invalid timedemo result: '+repr(row))
        finally:stop(xvfb)


if __name__=='__main__':main()
