"""HighScore stage tools. Codex chooses each plan from the current project; no fixed fitting pipeline."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import argparse, hashlib, json, math, os, re, shutil, subprocess, sys, tempfile
from model_legacy import HPF
SKILL=Path(__file__).resolve().parents[1]
PROFILE=json.loads((SKILL/"references/local-profile.json").read_text(encoding="utf-8"))

def native_command(args):
 powershell=args.powershell or shutil.which("pwsh") or shutil.which("powershell")
 highscore=args.highscore
 batch=getattr(args,"batch_template","")
 background=getattr(args,"background_template","")
 if not powershell or not highscore or not batch:
  raise ValueError("Set --highscore and --batch-template (or XRD_HIGHSCORE_EXE / XRD_BATCH_TEMPLATE), and install PowerShell.")
 if args.action=="solve" and not background:
  raise ValueError("Set --background-template or XRD_BACKGROUND_TEMPLATE to a native preset verified in HighScore.")
 command=[powershell,"-NoProfile","-File",str(SKILL/"scripts/Run_Native.ps1"),
          "-HighScoreExe",highscore,"-BatchTemplateName",batch]
 if background:command += ["-BackgroundTemplateName",background]
 return command

def fixed_plan(plan):
 fixed=PROFILE["fixed_computation_profile"]
 for key,value in fixed.items():
  if key in plan and (plan[key]!=value or (type(value) is bool and type(plan[key]) is not bool)):
   raise ValueError("The user requires consistent base settings: "+key+"="+str(value))
 return {**plan,**fixed}

def fixed_background(data):
 fixed=PROFILE["background_starting_profile"]
 supplied=data.get("background",{})
 if not isinstance(supplied,dict):raise ValueError("Background settings must be an object.")
 for key in ("bending_factor","granularity","smoothed_input"):
  if key in supplied and (supplied[key]!=fixed[key] or type(supplied[key]) is not type(fixed[key])):
   raise ValueError("The user requires Automatic background, bending 2, granularity 20 and smoothed input.")
 return fixed

def verify_base(doc):
 info=doc.info()
 expected={"mode_code":1,"background_method_code":1,"max_cycles":100,"profile_base_width":12}
 if any(info[key]!=value for key,value in expected.items()):
  raise ValueError("Prepare the consistent semi-automatic / available-background / 100-cycle / 12-FWHM stage first.")
 if any(p["free"] and (re.fullmatch(r"Coefficient \d+",p["name"]) or "background" in p["name"].lower()) for p in doc.parameters):
  raise ValueError("Background parameters must remain fixed when using the accepted background.")

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def request(path):
 if not path: return {}
 return json.loads(sys.stdin.read()) if path=="-" else json.loads(Path(path).read_text(encoding="utf-8-sig"))
def inputs(path):
 p=Path(path).resolve()
 if p.is_file() and p.suffix.lower()==".hpf":return [p]
 if p.is_dir():
  files=sorted(f for f in p.iterdir() if f.is_file() and f.suffix.lower()==".hpf" and not re.search(r"_(refined|candidate_unconverged)(_|$)",f.stem,re.I))
  if files:return files
 raise ValueError("Provide a HighScore HPF containing the observed scan and intended crystal structures.")
def confirm(data,origin):
 record=data.get("confirmation",{})
 if record.get("confirmed") is not True or not record.get("user_statement","").strip():
  raise ValueError("The user's explicit CIF-completeness confirmation is required before preparation or refinement.")
 digest=sha(origin)
 if record.get("projects",{}).get(str(origin))!=digest:
  raise ValueError("CIF confirmation does not cover this exact source project.")
 std=data.get("standard_confirmation",{})
 if std.get("confirmed") is not True or not std.get("user_statement","").strip() or std.get("source_sha256")!=digest:
  raise ValueError("Ask the user to confirm the internal standard, added amount and mass basis for this source before refinement.")
 added=std.get("added");weights=std.get("weights")
 if type(added) is not bool or not isinstance(weights,list):
  raise ValueError("Explicitly confirm an internal standard or no added standard.")
 if not added:
  if weights:raise ValueError("No-standard confirmation must have empty weights.")
 elif not weights or std.get("mass_basis")!="mixed_total_mass":
  raise ValueError("Internal-standard percentages must be confirmed on the mixed-total-mass basis.")
 phases=[];total=0
 for weight in weights:
  if not isinstance(weight,dict) or not isinstance(weight.get("phase"),str) or not weight["phase"].strip():
   raise ValueError("Identify the confirmed standard phase in the actual project.")
  value=weight.get("mixed_mass_pct")
  if type(value) not in (int,float) or not math.isfinite(value) or not 0<value<100:
   raise ValueError("Confirmed standard percentage must be finite and between 0 and 100.")
  phases.append(weight["phase"]);total+=value
 if len(set(phases))!=len(phases) or total>=100:
  raise ValueError("Duplicate standards or invalid total standard percentage.")
 return record

def standard_settings(data,doc):
 declared={w["phase"]:w["mixed_mass_pct"] for w in data["standard_confirmation"]["weights"]}
 if not set(declared).issubset(doc.phase_keys):
  raise ValueError("The confirmed internal-standard structure is missing; import it and reconfirm CIF completeness.")
 return [{"phase":phase,"mixed_mass_pct":declared.get(phase,-1)} for phase in doc.phase_keys]

def verify_standard(data,doc):
 expected={w["phase"]:w["mixed_mass_pct"] for w in standard_settings(data,doc)}
 for phase in doc.phase_weights():
  value=phase["internal_standard_pct"];target=expected[phase["phase"]]
  if not math.isfinite(value) or (target>0 and abs(value-target)>1e-9) or (target<0 and value>0):
   raise ValueError("The stage internal-standard settings differ from the user's current confirmation.")
def identity(stage,origin,data=None):
 try: original=HPF(origin)
 except ValueError:
  bridge=(data or {}).get("origin_snapshot",{})
  path=bridge.get("path")
  if not path or bridge.get("source_sha256")!=sha(origin) or bridge.get("snapshot_sha256")!=sha(path):
   raise ValueError("This older serialization needs a verified native normalization snapshot.")
  original=HPF(path)
 if stage.scan_sha256()!=original.scan_sha256() or stage.phase_keys!=original.phase_keys or stage.wavelength!=original.wavelength:
  raise ValueError("The stage scan, crystal inventory or radiation differs from the confirmed source.")
 return original
def stability(previous,current):
 verify_base(previous);verify_base(current)
 import numpy as np
 if previous.scan_sha256()!=current.scan_sha256() or not np.allclose(previous.scan()[:,2],current.scan()[:,2],rtol=0,atol=1e-9):
  return {"stable":False,"reason":"Observed data or accepted background differs between comparisons."}
 a=previous.parameters;b=current.parameters
 old={p["id"]:p for p in a if p["free"]};free=[p for p in b if p["free"]]
 if not free or {p["id"] for p in free}!=set(old):return {"stable":False,"reason":"Different or empty free-parameter sets."}
 if any(p["name"]!=old[p["id"]]["name"] or not all(math.isfinite(p[k]) for k in ("value","shift","ESD")) or p["ESD"]<=0 for p in free):
  return {"stable":False,"reason":"Invalid standard errors or parameter correspondence."}
 bounds=[p["name"] for p in free if p["use_bounds"] and min(abs(p["value"]-p["minimum"]),abs(p["value"]-p["maximum"]))<1e-8]
 if previous.metrics() is None or current.metrics() is None:return {"stable":False,"reason":"No valid native metrics."}
 delta=current.metrics()["Rwp"]-previous.metrics()["Rwp"]
 last=max(abs(p["shift"]/p["ESD"]) for p in free)
 repeat=max(abs(p["value"]-old[p["id"]]["value"])/p["ESD"] for p in free)
 return {"stable":not bounds and abs(delta)<.005 and last<.2 and repeat<.2,
         "delta_Rwp_pp":delta,"max_last_shift_ESD":last,"max_repeat_shift_ESD":repeat,"at_bounds":bounds}
def deliver(native,origin,stable,output=None):
 root=Path(output).resolve() if output else origin.parent/"Refined"
 root.mkdir(parents=True,exist_ok=True)
 stem=origin.stem+("_refined" if stable else "_candidate_unconverged")
 data=Path(native).read_bytes();target=root/(stem+".HPF")
 stamp=datetime.now(timezone(timedelta(hours=8))).strftime("%Y%m%d_%H%M%S");counter=0
 while True:
  try:
   with target.open("xb") as f:f.write(data)
   break
  except FileExistsError:
   counter+=1;target=root/(stem+"_"+stamp+("" if counter==1 else "_"+str(counter))+".HPF")
 if sha(target)!=hashlib.sha256(data).hexdigest():raise ValueError("Delivered HPF differs from native output.")
 return target
def action(args,data):
 if args.action=="normalize":
  original=Path(args.input).resolve();digest=sha(original)
  directory=Path(tempfile.mkdtemp(prefix="codex_xrd_step_"))
  source=directory/"normalize_input.HPF";shutil.copy2(original,source)
  cmd=native_command(args)+["-InputFile",str(source),"-NormalizeOnly"]
  job=subprocess.run(cmd,capture_output=True,text=True,errors="replace")
  if job.returncode:raise RuntimeError("Native normalization failed; temporary diagnostics: "+str(directory)+"\n"+job.stderr[-1500:])
  status=json.loads(job.stdout.lstrip("\ufeff"));output=Path(status["OutputFile"]);normalized=HPF(output)
  if sha(original)!=digest:raise ValueError("Original changed during normalization.")
  return {"origin_snapshot":{"path":str(output),"source_sha256":digest,"snapshot_sha256":sha(output)},
          "info":normalized.info(),"work_directory":str(directory),"refinement_executed":False}
 if args.action=="inspect":
  result=[]
  for p in inputs(args.input):
   doc=HPF(p);info=doc.info()
   info["free_parameters"]=[v for v in doc.public_parameters() if v["free"]]
   if args.parameters:
    info["parameters"]=[v for v in doc.public_parameters() if not args.filter or re.search(args.filter,v["name"])]
   if args.scan_file:
    observed=doc.scan()[:,:2];import numpy as np
    scan=np.loadtxt(args.scan_file,skiprows=1)
    if scan.shape!=observed.shape or not np.allclose(scan[:,0],observed[:,0],atol=2e-6) or not np.array_equal(scan[:,1],observed[:,1]):
     raise ValueError("External scan does not match the embedded observed data.")
    info["external_scan_verified"]=True
   result.append(info)
  return result
 source=Path(args.input).resolve();origin=Path(args.origin or source).resolve()
 record=confirm(data,origin);digest=sha(origin);doc=HPF(source);original=identity(doc,origin,data)
 if args.action=="prepare":
  plan=data.get("plan")
  if not isinstance(plan,dict) or not plan.get("reason","").strip():
   raise ValueError("Supply a plan with its diagnostic reason; Codex chooses actual parameters.")
  if "standard_weights" in plan and plan["standard_weights"]!=data["standard_confirmation"]["weights"]:
   raise ValueError("The plan standard weights differ from the user's current confirmation.")
  plan=fixed_plan(plan)
  plan["standard_weights"]=standard_settings(data,doc)
  prepared=doc.apply(plan)
  verify_base(prepared)
  verify_standard(data,prepared)
  directory=Path(tempfile.mkdtemp(prefix="codex_xrd_step_"))
  path=directory/"prepared_input.HPF";prepared.save(path)
  result={"prepared_input":str(path),"work_directory":str(directory),"original":str(origin),
          "origin_sha256":digest,"reason":plan["reason"],"parameters":prepared.info(),
          "background_should_be_estimated":True}
 elif args.action=="solve":
  verify_standard(data,doc)
  verify_base(doc)
  background=fixed_background(data)
  directory=source.parent
  if not directory.name.startswith("codex_xrd_step_") or not directory.is_relative_to(Path(tempfile.gettempdir()).resolve()):
   raise ValueError("Native solver must operate on a prepared copy in the system temporary directory.")
  cmd=native_command(args)+["-InputFile",str(source),"-ExpectedParameters",str(doc.independent_count())]
  cmd+=["-EstimateBackground","-BackgroundBendingFactor",str(background["bending_factor"]),
        "-BackgroundGranularity",str(background["granularity"])]
  job=subprocess.run(cmd,capture_output=True,text=True,errors="replace")
  if job.returncode:
   raise RuntimeError("Native stage failed. Stop new jobs; internal diagnostics: "+str(directory)+"\n"+job.stderr[-2000:])
  status=json.loads(job.stdout.lstrip("\ufeff"))
  output=Path(status["OutputFile"]);solved=HPF(output);identity(solved,origin,data)
  verify_base(solved)
  verify_standard(data,solved)
  if solved.metrics() is None or status["SolverParameterCounts"]!=[solved.independent_count()]:
   raise ValueError("Native metrics or log/HPF parameter-count verification failed.")
  result={"native_output":str(output),"native_status":status,"info":solved.info(),
          "free_parameters":[p for p in solved.public_parameters() if p["free"]]}
 elif args.action=="compare":
  if not args.previous:raise ValueError("--previous is required.")
  previous=HPF(args.previous);identity(previous,origin,data)
  verify_standard(data,previous);verify_standard(data,doc)
  result={"stability":stability(previous,doc),"previous":previous.info(),"current":doc.info(),
          "free_parameters":[p for p in doc.public_parameters() if p["free"]]}
 elif args.action=="deliver":
  if not args.previous:raise ValueError("Supply the last same-model comparison before delivery.")
  previous=HPF(args.previous);identity(previous,origin,data)
  verify_standard(data,previous);verify_standard(data,doc)
  checked=stability(previous,doc)
  if sha(origin)!=digest:raise ValueError("Original source changed before delivery.")
  target=deliver(source,origin,checked["stable"],args.output)
  result={"file":str(target),"stability":checked,"info":doc.info(),"original_unchanged":True,
          "phase_model_validated":False,"documents_generated":False}
 else:raise ValueError(args.action)
 if sha(origin)!=digest:raise ValueError("Original source changed during this action.")
 return result

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument("action",choices=("inspect","normalize","prepare","solve","compare","deliver"));p.add_argument("input")
 p.add_argument("--origin",help="Original user-supplied HPF; required when operating on stage copies.")
 p.add_argument("--request",help="JSON containing confirmation and, for preparation, a plan; - reads stdin.")
 p.add_argument("--parameters",action="store_true");p.add_argument("--filter");p.add_argument("--scan-file")
 p.add_argument("--estimate-background",action="store_true");p.add_argument("--previous")
 p.add_argument("--output",help="Explicit user destination override; default delivery is Refined under the original HPF folder.")
 p.add_argument("--powershell",default=os.environ.get("XRD_POWERSHELL", ""),help="PowerShell executable; auto-detected when omitted.")
 p.add_argument("--highscore",default=os.environ.get("XRD_HIGHSCORE_EXE", ""),help="Installed HighScorePlus.exe path.")
 p.add_argument("--batch-template",default=os.environ.get("XRD_BATCH_TEMPLATE", ""),help="Name of a native user batch containing a background action.")
 p.add_argument("--background-template",default=os.environ.get("XRD_BACKGROUND_TEMPLATE", ""),help="Name of a verified native background preset.")
 args=p.parse_args();print(json.dumps(action(args,request(args.request)),ensure_ascii=False))
if __name__=="__main__":main()
