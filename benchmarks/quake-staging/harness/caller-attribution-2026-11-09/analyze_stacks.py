import bisect,collections,json,os,re,struct,subprocess,sys
from pathlib import Path
sys.path.insert(0,'/workspace/dosbox-staging/extras/guest-block-mapping')
from analyze_trace import events_from_csv,LiveMap
from analyze_native_rips import load_snapshots
root=Path(sys.argv[1]); binary=Path(sys.argv[2]).resolve(); r=json.loads((root/'result.json').read_text()); events=events_from_csv(root/'jit-blocks.csv'); snapshots=load_snapshots(root/'snapshots',events)
maps=[]
for line in (root/'maps.txt').read_text().splitlines():
 p=line.split(maxsplit=5);lo,hi=(int(x,16) for x in p[0].split('-'));maps.append((lo,hi,int(p[2],16),p[5] if len(p)>5 else ''))
exe=[m for m in maps if m[3]==str(binary)]
assert exe
def relative(addr):
 for lo,hi,off,path in exe:
  if lo<=addr<hi:return addr-lo+off
 return None
syms=[]
for line in subprocess.check_output(['nm','-n','-S','-C','--defined-only',str(binary)],text=True).splitlines():
 p=line.split(maxsplit=3)
 if len(p)==4 and p[2] in 'tTwW':
  try:syms.append((int(p[0],16),int(p[1],16),p[3]))
  except ValueError:pass
starts=[s[0] for s in syms]
def sym(addr):
 v=relative(addr)
 if v is None:return None
 i=bisect.bisect_right(starts,v)-1
 return syms[i][2] if i>=0 and v<syms[i][0]+syms[i][1] else '[unknown executable]'
raw=(root/'stacks.bin').read_bytes();samp=(root/'samples.bin').read_bytes();S=struct.Struct('<QQII8Q');assert len(raw)%S.size==0 and len(samp)%24==0
records=sorted([x for x in S.iter_unpack(raw) if x[2]==r['pid'] and r['demo_start_observed_ns']<=x[0]<=r['demo_end_observed_ns']]);observed=collections.Counter((t,ip,tid) for t,ip,tid,_ in struct.iter_unpack('<QQII',samp));assert all(observed[(x[0],x[1],x[2])]>0 for x in records)
live=LiveMap();i=0;depths=collections.Counter();totals=collections.Counter();edges=collections.Counter();jit_edges=collections.Counter()
for ts,ip,tid,n,*ret in records:
 assert n<=8
 while i<len(events) and events[i].timestamp_ns<=ts:live.apply(events[i]);i+=1
 depths[n]+=1;name=sym(ip)
 if not name:continue
 totals[name]+=1
 if not n:continue
 caller=sym(ret[0]-1)
 if caller:edges[(name,caller)]+=1;continue
 block=live.locate(ret[0]-1)
 if block:
  if block.generation in snapshots:jit_edges[(name,hex(block.guest_eip),ret[0]-block.host_begin)]+=1
  else:jit_edges[(name,'other JIT',0)]+=1
  continue
 edges[(name,'[unresolved or external]')]+=1
out={'period_us':r['profile_period_us'],'main_window_samples':len(records),'depths':dict(depths),'sampled_executable_symbols':totals.most_common(40),'candidate_top_frame_edges':[{'sampled':a,'caller':b,'samples':n} for (a,b),n in edges.most_common(80)],'candidate_selected_jit_return_offsets':[{'sampled':a,'guest_eip':b,'return_offset':c,'samples':n} for (a,b,c),n in jit_edges.most_common(80)],'caveat':'candidate frame-pointer return addresses only; asynchronous prologues, leafs, tail calls, missing frame pointers, and JIT transitions may break chain; validate machine-code call and control flow before claiming an edge'}
(root/'stack-derived.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
