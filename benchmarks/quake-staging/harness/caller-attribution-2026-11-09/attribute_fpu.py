import sys,pathlib,struct,json,collections
sys.path.insert(0,'/workspace/dosbox-staging/extras/guest-block-mapping')
from analyze_trace import events_from_csv,LiveMap
for folder in map(pathlib.Path,sys.argv[1:]):
 r=json.loads((folder/'result.json').read_text()); exe=[]
 for l in (folder/'maps.txt').read_text().splitlines():
  p=l.split(maxsplit=5)
  if len(p)>5 and p[5]=='/workspace/quake-study/build-trace/dosbox':
   a,b=map(lambda x:int(x,16),p[0].split('-'));exe.append((a,b,int(p[2],16)))
 def v(a):return next((a-lo+off for lo,hi,off in exe if lo<=a<hi),None)
 events=events_from_csv(folder/'jit-blocks.csv');live=LiveMap();i=0;counts=collections.Counter();blocks=collections.Counter();depth=collections.Counter()
 samples=sorted(x for x in struct.iter_unpack('<QQII8Q',(folder/'stacks.bin').read_bytes()) if x[2]==r['pid'] and r['demo_start_observed_ns']<=x[0]<=r['demo_end_observed_ns'])
 for ts,ip,tid,n,*ret in samples:
  while i<len(events) and events[i].timestamp_ns<=ts:live.apply(events[i]);i+=1
  pc=v(ip)
  if not(n and pc is not None and 0x411790<=pc<0x4118db and v(ret[0])==0x1a85e9):continue
  counts['mem_readd_via_FPU_FLD_32']+=1;depth[n]+=1
  if n<2:counts['no_parent_frame']+=1;continue
  b=live.locate(ret[1]-1)
  if b:counts['candidate_jit_parent']+=1;blocks[(hex(b.guest_eip),ret[1]-b.host_begin)]+=1
  else:counts['no_live_jit_parent']+=1
 out={'counts':counts,'depths':depth,'jit_parent_candidates':[{'guest_eip':a,'return_offset':b,'samples':c} for (a,b),c in blocks.most_common(15)],'caveat':'parent return is a candidate until call instruction bytes are validated for the same live generation'}
 (folder/'fpu-derived.json').write_text(json.dumps(out,indent=2)+'\n');print(folder.name,json.dumps(out,indent=2))
