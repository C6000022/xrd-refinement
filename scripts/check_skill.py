"""Read-only HPF regressions and isolated preparation/delivery checks. Never launch HighScore."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import argparse, hashlib, json, struct, tempfile
import numpy as np
from model_legacy import HPF
import refine as tools

def fail(call):
 try:call()
 except (ValueError,RuntimeError):return
 raise AssertionError("Expected rejection")

def variant(original):
 # Synthetic serialization fixture, not a scientifically valid new diffraction experiment.
 raw=bytearray(original.raw);start=original.scan_offset;old_n=original.point_count
 n=1001;x=12.5+np.arange(n)*.035
 records=bytearray(raw[start:start+n*66])
 for index,value in enumerate(x):struct.pack_into("<d",records,index*66+8,float(value))
 struct.pack_into("<I",raw,start-46,n)
 if struct.unpack_from("<I",raw,start-90)[0]==old_n:struct.pack_into("<I",raw,start-90,n)
 raw[start:start+old_n*66]=records
 changed=HPF(raw=raw);wave=changed.resolve("Wavelength [Å]")
 struct.pack_into("<d",raw,wave["offset"]+5,1.5406)
 raw=raw.replace(b"Corundum",b"Quartz_1")
 return HPF(raw=raw)

def phase_fixture(points=101,phase_names=("Crystal_A","Crystal_B","Crystal_C")):
 # Minimal serialized adapter fixture: tests variable phase/parameter counts only.
 # It is deliberately not sent to HighScore and is not a valid scientific HPF.
 from model_legacy import PARAMETER
 start=128;global_start=start+points*66+376
 raw=bytearray(global_start+700)
 struct.pack_into("<I",raw,0,6)
 struct.pack_into("<II",raw,start-46,points,1)
 for i in range(points):
  struct.pack_into("<dd",raw,start+i*66,500+i,10+i*.1)
 def record(name,value=0):
  label=name.encode("cp1252")
  return PARAMETER.pack(1,1,value,0,0,-1e10,1e10,1e10,0,0,0,1,1,len(label))+label
 zero=record("Zero Shift [°2Theta]")
 raw[global_start:global_start+len(zero)]=zero
 struct.pack_into("<I",raw,global_start+250,100)
 struct.pack_into("<d",raw,global_start+278,12)
 raw+=record("Wavelength [Å]",1.5406)
 raw+=record("Coefficient 1")+struct.pack("<I",1)
 for phase in phase_names:
  raw+=record(phase+" Scale Factor",.0001)
  raw+=record(phase+" Roughness")+struct.pack("<4d",-1,0,0,0)
 raw+=bytes(100)+struct.pack("<I",0)+struct.pack("<4I",1,0,1,0)+b"\x01"+struct.pack("<I",1)+bytes(40)
 return HPF(raw=raw)

def check_models(root,synthetic_only=False):
 source_files=tools.inputs(root)
 original_hashes={str(p):tools.sha(p) for p in source_files}
 records=[]
 for path in source_files:
  doc=HPF(path);before=doc.info()
  # Different parameter groups, independent of phase names and a fixed 7/14/15 route.
  scales=[p for p in doc.parameters if p["name"].endswith(" Scale Factor")]
  selected=[{"id":p["id"],"name":p["name"]} for p in scales[:2]]+["Zero Shift [°2Theta]"]
  prepared=doc.apply({"refine":selected,"use_available_background":True,"max_cycles":100})
  assert prepared.independent_count()==3
  assert {int(abs(p["refinement_code"])//10) for p in prepared.parameters if p["free"]}=={1,2,3}
  assert prepared.scan_sha256()==doc.scan_sha256()
  assert prepared.phase_keys==doc.phase_keys and prepared.wavelength==doc.wavelength
  assert prepared.info()["background_method_code"]==1
  if before["free_count"]:
   source_doc=HPF(path);preserved=source_doc.apply({})
   assert [p["refinement_code"] for p in preserved.parameters]==[p["refinement_code"] for p in source_doc.parameters]
  records.append({"file":path.name,"phases":doc.phase_keys,"free_parameters_before":before["free_count"],"selected_in_test":3})
 fixture=phase_fixture()
 assert len(fixture.phase_keys)==3 and len(fixture.parameters)!=2749 and fixture.point_count==101
 assert fixture.apply({"refine":["Crystal_B Scale Factor","Crystal_C Scale Factor"]}).independent_count()==2
 first=HPF(source_files[0]);synthetic=variant(first)
 assert synthetic.point_count==1001 and abs(synthetic.wavelength-1.5406)<1e-9
 assert abs(synthetic.scan()[0,0]-12.5)<1e-9 and abs(synthetic.scan()[-1,0]-47.5)<1e-9
 assert "Quartz_1" in synthetic.phase_keys
 alias_scale=synthetic.resolve("Quartz_1 Scale Factor")
 custom=synthetic.apply({"refine":[{"id":alias_scale["id"],"name":alias_scale["name"]}],"use_available_background":True})
 assert custom.independent_count()==1 and custom.scan_sha256()==synthetic.scan_sha256()
 fail(lambda:HPF(source_files[0]).apply({"edits":[{"parameter":"Wavelength [Å]","value":1.5}]}))
 fail(lambda:HPF(source_files[0]).apply({"edits":[{"parameter":"not a real parameter","value":1}]}))
 fail(lambda:HPF(source_files[0]).apply({"refine":["Profile Fit Shape 2 Left"]}))
 with tempfile.TemporaryDirectory() as temp:
  temp=Path(temp);source=temp/source_files[0].name
  mismatched=bytearray(first.raw)
  struct.pack_into("<I",mismatched,first.global_offset+250,20)
  struct.pack_into("<d",mismatched,first.global_offset+278,4)
  struct.pack_into("<I",mismatched,first.background_method_offset,0)
  for i in range(first.point_count):struct.pack_into("<d",mismatched,first.scan_offset+i*66+28,100.0)
  HPF(raw=mismatched).save(source)
  data={"confirmation":{"confirmed":True,"user_statement":"synthetic local test; no solver executes","projects":{str(source):tools.sha(source)}},
        "standard_confirmation":{"confirmed":True,"user_statement":"synthetic test: no standard added", "source_sha256":tools.sha(source),"added":False,"weights":[]},
        "settings_confirmation":{"confirmed":True,"user_statement":"synthetic confirmation of background and computation", "source_sha256":tools.sha(source),
          "background":{"mode":"automatic","handling":"model_background","bending_factor":2,"granularity":20,"smoothed_input":True},
          "computation":{"max_cycles":100,"profile_base_width":12}},
        "quantification_confirmation":{"confirmed":True,"user_statement":"synthetic confirmation of target and basis", "source_sha256":tools.sha(source),
          "mode":"relative_crystalline","target_phases":[first.phase_keys[-1]],"report_basis":"crystalline_only","include_unquantified_fraction":False},
        "plan":{"reason":"isolated test of arbitrary parameter selection","refine":["Zero Shift [°2Theta]"],"use_available_background":True}}
  args=SimpleNamespace(action="prepare",input=str(source),origin=None)
  fail(lambda:tools.action(args,{}))
  for record in ("standard_confirmation","settings_confirmation","quantification_confirmation"):
   missing={k:v for k,v in data.items() if k!=record}
   fail(lambda:tools.action(args,missing))
  for record in ("settings_confirmation","quantification_confirmation"):
   for field,value in (("confirmed",False),("user_statement",""),("source_sha256","wrong source")):
    invalid=json.loads(json.dumps(data));invalid[record][field]=value
    fail(lambda:tools.action(args,invalid))
  for field,value in (("bending_factor",101),("granularity",0),("smoothed_input",None),("handling","subtract"),("mode","polynomial")):
   invalid=json.loads(json.dumps(data));invalid["settings_confirmation"]["background"][field]=value
   fail(lambda:tools.action(args,invalid))
  for section,field,value in (("background","unknown_option",True),("computation","refine",[]),("computation","max_cycles",True),("computation","profile_base_width",float("inf"))):
   invalid=json.loads(json.dumps(data));invalid["settings_confirmation"][section][field]=value
   fail(lambda:tools.action(args,invalid))
  missing=json.loads(json.dumps(data));missing["settings_confirmation"]["computation"].pop("profile_base_width")
  fail(lambda:tools.action(args,missing))
  for field,value in (("target_phases",[]),("target_phases",["missing target"]),("report_basis","original_sample"),("include_unquantified_fraction",True),("mode","external_standard")):
   invalid=json.loads(json.dumps(data));invalid["quantification_confirmation"][field]=value
   fail(lambda:tools.action(args,invalid))
  for field,value in (("confirmed",False),("user_statement",""),("source_sha256","stale hash"),("added",None)):
   invalid=json.loads(json.dumps(data));invalid["standard_confirmation"][field]=value
   fail(lambda:tools.action(args,invalid))
  for key,value in (("max_cycles",20),("profile_base_width",4),("use_available_background",False)):
   conflicting=json.loads(json.dumps(data));conflicting["plan"][key]=value
   fail(lambda:tools.action(args,conflicting))
  standard_plan=json.loads(json.dumps(data))
  standard_plan["plan"]["standard_weights"]=[{"phase":first.phase_keys[0],"mixed_mass_pct":20}]
  fail(lambda:tools.action(args,standard_plan))
  standard_plan["standard_confirmation"]={"confirmed":True,"user_statement":"synthetic mass-basis confirmation","source_sha256":tools.sha(source),"added":True,"mass_basis":"mixed_total_mass","weights":standard_plan["plan"]["standard_weights"]}
  standard_plan["quantification_confirmation"].update(mode="internal_standard",report_basis="original_sample",include_unquantified_fraction=True)
  wrong_basis=json.loads(json.dumps(standard_plan));wrong_basis["standard_confirmation"]["mass_basis"]="original_sample_mass"
  fail(lambda:tools.action(args,wrong_basis))
  wrong_phase=json.loads(json.dumps(standard_plan));wrong_phase["standard_confirmation"]["weights"][0]["phase"]="missing structure"
  wrong_phase["plan"].pop("standard_weights")
  fail(lambda:tools.action(args,wrong_phase))
  for value in (0,100,float("nan"),float("inf")):
   invalid=json.loads(json.dumps(standard_plan));invalid["standard_confirmation"]["weights"][0]["mixed_mass_pct"]=value
   invalid["plan"].pop("standard_weights")
   fail(lambda:tools.action(args,invalid))
  standard_stage=tools.action(args,standard_plan)
  standard_doc=HPF(standard_stage["prepared_input"])
  assert standard_doc.phase_weights()[0]["internal_standard_pct"]==20
  assert all(w["internal_standard_pct"]==-1 for w in standard_doc.phase_weights()[1:])
  tools.verify_standard(standard_plan,standard_doc)
  assert standard_doc.scan_sha256()==first.scan_sha256()
  standard_work=Path(standard_stage["work_directory"])
  assert standard_work.is_relative_to(Path(tempfile.gettempdir()).resolve()) and standard_work.name.startswith("codex_xrd_step_")
  import shutil;shutil.rmtree(standard_work)
  prepared=tools.action(args,data)
  work=Path(prepared["work_directory"])
  assert HPF(prepared["prepared_input"]).independent_count()==1
  prepared_doc=HPF(prepared["prepared_input"])
  assert prepared_doc.scan_sha256()==first.scan_sha256()
  tools.verify_base(prepared_doc,data)
  tools.verify_standard(data,prepared_doc)
  assert all(w["internal_standard_pct"]==-1 for w in prepared_doc.phase_weights())
  assert HPF(source).phase_weights()==first.phase_weights()
  assert prepared_doc.info()["max_cycles"]==100 and prepared_doc.info()["profile_base_width"]==12
  assert prepared_doc.info()["background_method_code"]==1 and prepared_doc.info()["mode_code"]==1
  assert HPF(source).info()["max_cycles"]==20 and HPF(source).info()["profile_base_width"]==4
  solve_args=SimpleNamespace(action="solve",input=prepared["prepared_input"],origin=str(source),
                            powershell="disabled",highscore="disabled",batch_template="test_batch",background_template="test_background",estimate_background=False)
  with patch.object(tools.subprocess,"run",side_effect=RuntimeError("Native execution intentionally disabled")) as native:
   fail(lambda:tools.action(solve_args,data))
   assert native.call_count==1
   cmd=native.call_args.args[0]
   assert "-EstimateBackground" in cmd and cmd[cmd.index("-BackgroundBendingFactor")+1]=="2"
   assert cmd[cmd.index("-BackgroundGranularity")+1]=="20" and "-NoSmoothedBackground" not in cmd
   native.reset_mock()
   for key,value in (("bending_factor",5),("granularity",30),("smoothed_input",False)):
    conflicting={**data,"background":{key:value}}
    fail(lambda:tools.action(solve_args,conflicting))
   assert native.call_count==0
   conflicting=json.loads(json.dumps(standard_plan));conflicting.pop("plan")
   fail(lambda:tools.action(solve_args,conflicting))
   assert native.call_count==0
  custom=json.loads(json.dumps(data))
  custom["settings_confirmation"]["background"].update(bending_factor=5,granularity=30,smoothed_input=False)
  custom["settings_confirmation"]["computation"].update(max_cycles=180,profile_base_width=16)
  custom_stage=tools.action(args,custom);custom_doc=HPF(custom_stage["prepared_input"])
  assert custom_doc.info()["max_cycles"]==180 and custom_doc.info()["profile_base_width"]==16
  custom_args=SimpleNamespace(**{**vars(solve_args),"input":custom_stage["prepared_input"]})
  with patch.object(tools.subprocess,"run",side_effect=RuntimeError("Native execution intentionally disabled")) as native:
   fail(lambda:tools.action(custom_args,custom));assert native.call_count==1
   cmd=native.call_args.args[0]
   assert cmd[cmd.index("-BackgroundBendingFactor")+1]=="5" and cmd[cmd.index("-BackgroundGranularity")+1]=="30"
   assert "-NoSmoothedBackground" in cmd
  custom_work=Path(custom_stage["work_directory"])
  assert custom_work.is_relative_to(Path(tempfile.gettempdir()).resolve()) and custom_work.name.startswith("codex_xrd_step_")
  shutil.rmtree(custom_work)
  available=json.loads(json.dumps(data));available["settings_confirmation"]["background"]={"mode":"available","handling":"model_background"}
  available_stage=tools.action(args,available);available_doc=HPF(available_stage["prepared_input"])
  assert not available_stage["background_should_be_estimated"]
  assert np.array_equal(available_doc.scan()[:,2],HPF(source).scan()[:,2])
  available_args=SimpleNamespace(**{**vars(solve_args),"input":available_stage["prepared_input"],"background_template":""})
  with patch.object(tools.subprocess,"run",side_effect=RuntimeError("Native execution intentionally disabled")) as native:
   fail(lambda:tools.action(available_args,available));assert native.call_count==1
   cmd=native.call_args.args[0]
   assert "-UseAvailableBackground" in cmd and "-EstimateBackground" not in cmd and "-BackgroundBendingFactor" not in cmd
   native.reset_mock();available_args.estimate_background=True
   fail(lambda:tools.action(available_args,available));assert native.call_count==0
  available_work=Path(available_stage["work_directory"])
  assert available_work.is_relative_to(Path(tempfile.gettempdir()).resolve()) and available_work.name.startswith("codex_xrd_step_")
  shutil.rmtree(available_work)
  changed_background=bytearray(prepared_doc.raw)
  struct.pack_into("<d",changed_background,prepared_doc.scan_offset+28,prepared_doc.scan()[0,2]+1)
  assert not tools.stability(prepared_doc,HPF(raw=changed_background),data)["stable"]
  other=temp/"native_output.HPF";HPF(prepared["prepared_input"]).save(other)
  before={p.relative_to(temp) for p in temp.rglob("*")}
  a=tools.deliver(other,source,True);a_hash=tools.sha(a)
  b=tools.deliver(other,source,True)
  assert a.parent==source.parent/"Refined" and a!=b and tools.sha(a)==a_hash
  assert {p.relative_to(temp) for p in temp.rglob("*")}-before=={Path("Refined"),a.relative_to(temp),b.relative_to(temp)}
  assert all(p.suffix.lower()==".hpf" for p in temp.rglob("*") if p.is_file())
  assert a not in tools.inputs(temp) and b not in tools.inputs(temp)
  # Clean only the exact temporary stage created by this test, after verifying scope.
  assert work.is_relative_to(Path(tempfile.gettempdir()).resolve()) and work.name.startswith("codex_xrd_step_")
  import shutil;shutil.rmtree(work)
 for p,digest in original_hashes.items():assert tools.sha(p)==digest
 profile=json.loads((tools.SKILL/"references/local-profile.json").read_text(encoding="utf-8"))
 assert profile["suggested_background_profile"]["bending_factor"]==2
 assert profile["suggested_background_profile"]["granularity"]==20
 assert profile["suggested_background_profile"]["smoothed_input"] is True
 print(json.dumps({"models_read":records,"synthetic_only":synthetic_only,"variable_grid_wavelength_labels_and_3_phase_count_synthetic_check":True,
                   "arbitrary_3_and_1_parameter_preparation":True,"CIF_gate":True,"mandatory_current_standard_gate":True,
                   "no_standard_clears_stale_tags_and_positive_standard_sets_actual_phase":True,
                   "refined_subfolder_HPF_only_and_no_overwrite":True,"no_native_solver_launched":True,
                   "originals_unchanged":True,"background_suggestion_requires_confirmation":"2/20/smoothed",
                   "confirmed_base_preparation_and_conflict_rejection":True,"operator_confirmed_custom_background_and_computation":True,"available_background_preserved":True,"quantification_gate":True,
                   "different_background_not_same_model_stability":True},ensure_ascii=False,indent=2))
def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument("--xrd-directory",help="Optional directory of user-supplied compatible HPF files. Never runs HighScore.")
 args=p.parse_args()
 if args.xrd_directory:
  check_models(Path(args.xrd_directory).resolve())
 else:
  with tempfile.TemporaryDirectory(prefix="codex_xrd_public_check_") as directory:
   root=Path(directory)
   phase_fixture(points=1201,phase_names=("Crystal_A","Corundum","Crystal_C")).save(root/"Synthetic.HPF")
   check_models(root,synthetic_only=True)

if __name__=="__main__":main()
