#!/usr/bin/env python3
"""Map DOS Quake 1.06 DJGPP guest EIPs to bytes in its embedded COFF .text.

This is a static-binary correspondence, NOT a memory dump. Quake can patch
code bytes at runtime, so use a guest-memory snapshot for instruction-perfect
JIT translation analysis.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
from pathlib import Path
import struct


def find_coff(blob: bytes):
    candidates=[]
    for pos in range(len(blob)-60):
        if blob[pos:pos+2] != b'\x4c\x01':
            continue
        machine,count,timestamp,ptrsym,nsyms,opthdr,flags=struct.unpack_from('<HHIIIHH',blob,pos)
        if not (1 <= count <= 15 and 0 <= opthdr <= 256
                and pos+20+opthdr+40*count <= len(blob)):
            continue
        sections=[]
        for index in range(count):
            sp=pos+20+opthdr+40*index
            name,phys,vaddr,size,raw,relptr,lineptr,nrel,nline,secflags=struct.unpack_from(
                '<8sIIIIIIHHI',blob,sp)
            sections.append(dict(name=name.rstrip(b'\0').decode('ascii','replace'),
                                 vaddr=vaddr,size=size,file_offset=pos+raw,raw=raw))
        if any(sec['name']=='.text' and sec['size']>10000
               and sec['file_offset']+sec['size']<=len(blob)
               for sec in sections):
            candidates.append((pos,sections))
    if len(candidates)!=1:
        raise ValueError(f'Expected one DJGPP COFF image, found {len(candidates)}')
    return candidates[0]


def map_eip(eip,coff_position,sections):
    for sec in sections:
        if (sec['name']=='.text'
            and sec['vaddr'] <= eip < sec['vaddr']+sec['size']):
            return sec, sec['file_offset']+(eip-sec['vaddr'])
    return None,None


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--exe',type=Path,required=True)
    p.add_argument('--hotspots',type=Path,required=True)
    p.add_argument('--csv-out',type=Path,required=True)
    p.add_argument('--top',type=int,default=30)
    args=p.parse_args()
    blob=args.exe.read_bytes()
    off,sections=find_coff(blob)
    print('exe_sha256',hashlib.sha256(blob).hexdigest(),
          'coff_offset',hex(off),'sections',sections)
    with args.hotspots.open(newline='') as f:
        hotspots=list(csv.DictReader(f))[:args.top]
    rows=[]
    for h in hotspots:
        eip=int(h['guest_eip'],0)
        sec,filepos=map_eip(eip,off,sections)
        rows.append(dict(samples=int(h['samples']),
                         guest_eip=f'0x{eip:08x}',
                         section=sec['name'] if sec else 'unmapped',
                         file_offset=f'0x{filepos:08x}' if filepos is not None else '',
                         initial_bytes=blob[filepos:filepos+24].hex()
                             if filepos is not None else ''))
    if not rows:
        raise ValueError('No hotspots')
    with args.csv_out.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)
    print('mapped',sum(x['section']=='.text' for x in rows),
          'of',len(rows),'hotspots')


if __name__=='__main__':
    main()
