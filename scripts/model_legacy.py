"""Guarded HighScore 3.0.5 HPF adapter; discovers scan and phase/parameter records.
No specimen-specific phase names, wavelength, scan range, step or point count.
Serialization checks are mandatory. Unsupported layouts require the native interface.
"""
from pathlib import Path
import hashlib, math, re, struct, zlib
import numpy as np

PARAMETER = struct.Struct("<IB7dI3BI")
ZERO_LABEL = b"Zero Shift [\xb02Theta]"
CONTROL_SUFFIX = struct.pack("<4I",1,0,1,0)+b"\x01"

class HPF:
 def __init__(self,path=None,raw=None):
  self.path=Path(path).resolve() if path is not None else None
  self.raw=bytearray(raw) if raw is not None else bytearray(zlib.decompress(self.path.read_bytes()))
  if len(self.raw)<100 or struct.unpack_from("<I",self.raw,0)[0]!=6:
   raise ValueError("Unsupported HPF serialization version; use the native HighScore route.")
  self.scan_offset,self.point_count,self.global_offset=self._locate_scan()
  self.parameters=self._parameters()
  self.phase_keys=[p["name"][:-13] for p in self.parameters if p["name"].endswith(" Scale Factor")]
  if not self.phase_keys: raise ValueError("No Rietveld crystal-phase records found.")
  if not self.parameters[-1]["name"].endswith(" Roughness"):
   raise ValueError("Unrecognized phase-record terminator.")
  self.control_count_offset,self.mode_offset=self._control()
  coefficients=[p for p in self.parameters if re.fullmatch(r"Coefficient \d+",p["name"])]
  if not coefficients: raise ValueError("Missing background parameter block.")
  last=coefficients[-1]
  self.background_method_offset=last["offset"]+72+len(last["raw_name"])
  if struct.unpack_from("<I",self.raw,self.background_method_offset)[0] not in range(10):
   raise ValueError("Unrecognized background-method field.")
  self.cycles=struct.unpack_from("<I",self.raw,self.global_offset+250)[0]
  self.profile_base_width=struct.unpack_from("<d",self.raw,self.global_offset+278)[0]
  if not 1<=self.cycles<=999 or not 1<=self.profile_base_width<=100:
   raise ValueError("Unrecognized global refinement settings.")
  self.wavelength=self.resolve("Wavelength [Å]")["value"]

 def _locate_scan(self):
  b=self.raw; zeros=[]
  for m in re.finditer(re.escape(ZERO_LABEL),b):
   q=m.start()-72
   if q>=0 and struct.unpack_from("<IB",b,q)==(1,1) and struct.unpack_from("<I",b,m.start()-4)[0]==len(ZERO_LABEL):
    zeros.append(q)
  counts=np.ndarray((len(b)-8,),dtype="<u4",buffer=b,strides=(1,))
  candidates=np.flatnonzero((counts[:-4]>=2)&(counts[:-4]<=2000000)&(counts[4:]==1))
  found=[]
  for q in zeros:
   for pos in candidates:
    pos=int(pos);n=int(counts[pos]);start=pos+46
    # Native scan-array header and the following global block delimit the array.
    if start+n*66+376!=q: continue
    x=np.ndarray((n,),dtype="<f8",buffer=b,offset=start+8,strides=(66,))
    y=np.ndarray((n,),dtype="<f8",buffer=b,offset=start,strides=(66,))
    if np.isfinite(x).all() and np.isfinite(y).all() and np.all(np.diff(x)>0) and 0<=x[0]<x[-1]<=180:
     found.append((start,n,q))
  if len(found)!=1: raise ValueError("Cannot uniquely locate the anchor scan and refinement block: "+repr(found))
  return found[0]

 def scan(self):
  b=self.raw;n=self.point_count;s=self.scan_offset
  return np.column_stack([np.ndarray((n,),dtype="<f8",buffer=b,offset=s+offset,strides=(66,)) for offset in (8,0,28)])

 def scan_sha256(self):
  return hashlib.sha256(self.scan()[:,:2].astype("<f8").tobytes()).hexdigest()

 def _parameters(self):
  b=self.raw; out=[]
  for m in re.finditer(rb"[\x20-\xff]{8,240}",b[self.global_offset:]):
   pos=self.global_offset+m.start();q=pos-72
   if q<self.global_offset or struct.unpack_from("<I",b,pos-4)[0]!=len(m.group()): continue
   v=PARAMETER.unpack_from(b,q)
   if v[:2]!=(1,1) or v[10] not in (0,1) or v[12] not in (0,1):continue
   out.append({"id":len(out),"name":m.group().decode("cp1252"),"raw_name":m.group(),"offset":q,
               "value":v[2],"ESD":v[3],"shift":v[4],"minimum":v[5],"maximum":v[6],
               "refinement_code":v[8],"free":bool(v[10]),"use_bounds":bool(v[12])})
  if not out or out[0]["name"]!=ZERO_LABEL.decode("cp1252"):
   raise ValueError("Unrecognized parameter-vector start.")
  if sum(p["name"]=="Wavelength [Å]" for p in out)!=1: raise ValueError("Ambiguous wavelength field.")
  return out

 def _control(self):
  b=self.raw;last=self.parameters[-1];start=last["offset"]+72+len(last["raw_name"])
  expected={sum(p["free"] for p in self.parameters),self.independent_count()}
  matches=[]
  for m in re.finditer(re.escape(CONTROL_SUFFIX),b[start:start+5000]):
   count_pos=start+m.start()-4
   if count_pos<start or count_pos+25>len(b):continue
   mode=struct.unpack_from("<I",b,count_pos+21)[0]
   if struct.unpack_from("<I",b,count_pos)[0] in expected and mode in (0,1,2):
    matches.append((count_pos,count_pos+21))
  if len(matches)!=1: raise ValueError("Cannot uniquely validate refinement-control fields: "+repr(matches))
  return matches[0]

 def independent_count(self):
  free=[p for p in self.parameters if p["free"]]
  groups={int(abs(p["refinement_code"])//10) for p in free if int(abs(p["refinement_code"])//10)>0}
  uncoded=sum(int(abs(p["refinement_code"])//10)==0 for p in free)
  return len(groups)+uncoded

 def resolve(self,selector):
  if isinstance(selector,int):
   if not 0<=selector<len(self.parameters): raise ValueError("Parameter id out of range.")
   return self.parameters[selector]
  if isinstance(selector,dict):
   p=self.resolve(selector["id"])
   if selector.get("name",p["name"])!=p["name"]: raise ValueError("Parameter id/name mismatch.")
   return p
  matches=[p for p in self.parameters if p["name"]==selector]
  if len(matches)!=1: raise ValueError("Parameter name missing or ambiguous; supply id/name: "+str(selector))
  return matches[0]

 def metrics(self):
  values=struct.unpack_from("<4d",self.raw,self.global_offset+202)
  if all(v==0 for v in values): return None
  rp,rwp,rexp,gof=values
  if not all(math.isfinite(v) for v in values) or min(values)<=0 or abs((rwp/rexp)**2-gof)>max(1e-6,abs(gof)*2e-6):
   raise ValueError("Native agreement-index cache is not valid.")
  return dict(zip(("Rp","Rwp","Rexp","GOF"),values))

 def phase_weights(self):
  result=[]
  for scale in (p for p in self.parameters if p["name"].endswith(" Scale Factor")):
   key=scale["name"][:-13];rough=self.resolve(key+" Roughness")
   end=rough["offset"]+72+len(rough["raw_name"])
   result.append({"phase":key,"scale_parameter_id":scale["id"],"internal_standard_pct":struct.unpack_from("<d",self.raw,end)[0],
                  "native_weight_pct":struct.unpack_from("<d",self.raw,end+24)[0]})
  return result

 def public_parameters(self):
  return [{k:v for k,v in p.items() if k not in ("offset","raw_name")} for p in self.parameters]

 def info(self):
  a=self.scan();step=np.diff(a[:,0]); metrics=self.metrics()
  return {"file":str(self.path) if self.path else None,"point_count":self.point_count,
          "two_theta_range":[float(a[0,0]),float(a[-1,0])],"median_step":float(np.median(step)),
          "uniform_step":bool(np.allclose(step,np.median(step),rtol=1e-5,atol=1e-8)),
          "wavelength":self.wavelength,"phase_keys":self.phase_keys,"parameter_record_count":len(self.parameters),
          "free_count":self.independent_count(),"selected_parameter_rows":sum(p["free"] for p in self.parameters),"native_metrics":metrics,
          "scan_sha256":self.scan_sha256(),"background_available":bool(np.any(a[:,2]!=0)),
          "background_method_code":struct.unpack_from("<I",self.raw,self.background_method_offset)[0],
          "mode_code":struct.unpack_from("<I",self.raw,self.mode_offset)[0],"max_cycles":self.cycles,
          "profile_base_width":self.profile_base_width,"phase_weights":self.phase_weights()}

 def apply(self,plan):
  original_scan=self.scan_sha256()
  if "refine" in plan:
   selected={self.resolve(s)["id"] for s in plan["refine"]}
   if any(p["id"] in selected and p["name"].startswith("Wavelength") for p in self.parameters):
    raise ValueError("The acquisition wavelength must remain fixed.")
   group_map={}
   for p in self.parameters:
    if p["id"] not in selected:continue
    old=p["refinement_code"];group=int(abs(old)//10)
    key=("existing",group) if group else ("new",p["id"])
    if key not in group_map:group_map[key]=len(group_map)+1
   for p in self.parameters:
    new_free=p["id"] in selected
    self.raw[p["offset"]+65]=int(new_free)
    old=p["refinement_code"];group=int(abs(old)//10)
    key=("existing",group) if group else ("new",p["id"])
    if key in group_map:
     coefficient=abs(old)-group*10 if group else 1
     if coefficient==0 and new_free:raise ValueError("An active parameter has a zero constraint coefficient; inspect it in HighScore.")
     code=(group_map[key]*10+coefficient)*(-1 if old<0 else 1)
     struct.pack_into("<d",self.raw,p["offset"]+53,code)
  for edit in plan.get("edits",[]):
   p=self.resolve(edit["parameter"]);q=p["offset"]
   if p["name"].startswith("Wavelength"): raise ValueError("Instrument wavelength is preserved; correct verified acquisition metadata through the native interface.")
   if "value" in edit:
    value=float(edit["value"])
    if not math.isfinite(value): raise ValueError("Parameter value must be finite.")
    struct.pack_into("<d",self.raw,q+5,value)
   if "bounds" in edit:
    lo,hi=map(float,edit["bounds"])
    if not math.isfinite(lo+hi) or lo>=hi: raise ValueError("Invalid parameter bounds.")
    struct.pack_into("<2d",self.raw,q+29,lo,hi);self.raw[q+67]=1
   if "refinement_code" in edit:
    code=float(edit["refinement_code"])
    if not math.isfinite(code): raise ValueError("Invalid constraint code.")
    struct.pack_into("<d",self.raw,q+53,code)
  for standard in plan.get("standard_weights",[]):
   phase=standard["phase"]
   if phase not in self.phase_keys:raise ValueError("Internal-standard phase is not in this project.")
   value=float(standard["mixed_mass_pct"])
   if not math.isfinite(value) or not (value==-1 or 0<value<100):raise ValueError("Invalid mixed-sample standard percentage; -1 removes a standard designation.")
   rough=self.resolve(phase+" Roughness")
   end=rough["offset"]+72+len(rough["raw_name"])
   struct.pack_into("<d",self.raw,end,value)
  if plan.get("use_available_background"): struct.pack_into("<I",self.raw,self.background_method_offset,1)
  if "max_cycles" in plan:
   value=int(plan["max_cycles"])
   if not 1<=value<=999:raise ValueError("Cycles must be 1..999.")
   struct.pack_into("<I",self.raw,self.global_offset+250,value)
  if "profile_base_width" in plan:
   value=float(plan["profile_base_width"])
   if not 1<=value<=100:raise ValueError("Profile base width must be 1..100 FWHM.")
   struct.pack_into("<d",self.raw,self.global_offset+278,value)
  changed=self._parameters()
  groups={int(abs(p["refinement_code"])//10) for p in changed if p["free"] and int(abs(p["refinement_code"])//10)>0}
  count=len(groups)+sum(p["free"] and int(abs(p["refinement_code"])//10)==0 for p in changed)
  struct.pack_into("<I",self.raw,self.control_count_offset,count)
  struct.pack_into("<I",self.raw,self.mode_offset,1)
  validated=HPF(raw=self.raw)
  if validated.scan_sha256()!=original_scan or validated.phase_keys!=self.phase_keys or validated.wavelength!=self.wavelength:
   raise ValueError("Preparation changed the observed scan, phase inventory or radiation metadata.")
  return validated

 def save(self,path):
  path=Path(path)
  with path.open("xb") as stream: stream.write(zlib.compress(self.raw))
