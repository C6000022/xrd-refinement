# XRD Refinement Skill

**v0.1.0-alpha.1 — experimental / 公开测试版**

A Codex skill for supervised, local Rietveld refinement of existing HighScore Plus projects. It confirms the internal standard and CIF completeness, keeps a consistent background/computation baseline, chooses refinement parameters from the actual model, and saves HPF results under `Refined/`.

用于在Windows上调用HighScore进行XRD精修。使用者提供已经包含实测扫描与拟合晶体结构的HPF；正式操作前确认内标种类、加入量及质量基准，以及所需CIF是否已全部导入。结果默认仅交付HPF，结论在聊天中汇报。

This package contains instructions and helper scripts. It does not include HighScore, a commercial crystal database, instrument calibration, private measurements, or a cloud refinement service.

## Status and supported environment

- Native launcher: **Windows + HighScore Plus file version 3.0.5.15611**. Other versions are rejected until explicitly validated.
- Development baseline: **Python 3.12 + NumPy 1.26.4**, with PowerShell on PATH or explicitly configured.
- The binary HPF adapter supports a guarded subset of serialized layouts. Files with the same HighScore version can still have different layouts; unsupported files fail closed.
- The self-check uses synthetic serialization fixtures and a mocked native dispatch. Passing it does **not** demonstrate scientific accuracy or successful native refinement on a new machine.
- Earlier real-file regression checks encountered an unsupported HPF layout. That compatibility issue is not claimed fixed in this release. A clean installation and representative native solves on other computers remain unvalidated.

Treat this release as a workflow and adapter test build. Review the scientific model, difference curves, parameter correlations and quantitative assumptions before using results in research.

## Install in Codex

Clone this repository into the local user skill directory. If a skill with the same name is already installed, use a separate test location; do not overwrite a working copy without reviewing it.

```powershell
git clone https://github.com/C6000022/xrd-refinement.git "$HOME\.agents\skills\xrd-refinement"
$SkillRoot = Join-Path $HOME ".agents\skills\xrd-refinement"
py -3.12 -m venv "$SkillRoot\.venv"
& "$SkillRoot\.venv\Scripts\python.exe" -m pip install -r "$SkillRoot\requirements.txt"
```

You can also ask Codex's skill installer to install from this GitHub repository. If the new skill is not detected, restart Codex. Local skill discovery is documented at https://learn.chatgpt.com/docs/build-skills.

## Configure native execution

The public copy contains no author-specific executable paths or private registry exports. Users must configure their own installed software and **native presets saved through HighScore**:

1. In HighScore, save an automatic background preset with smoothed input and `Add to net scan = Nothing`. The launcher derives a unique temporary preset and enforces Bending factor 2 / Granularity 20 / smoothed input on that copy. Unrecognized ancillary fields are rejected.
2. Save a native user batch containing the background-determination action. The launcher validates and uses the native serialization header; it replaces the actions in a temporary batch with a controlled solve/save sequence. Normalization uses save only.
3. Set the executable path and the actual saved preset names. The following values are examples to replace with your own:

```powershell
$env:XRD_HIGHSCORE_EXE = "C:\Program Files\PANalytical\X'Pert HighScore Plus\HighScorePlus.exe"
$env:XRD_BATCH_TEMPLATE = "My Rietveld Batch"
$env:XRD_BACKGROUND_TEMPLATE = "My Automatic Background"
```

These environment variables apply to the current terminal process and its children. Start Codex from that environment or pass `--highscore`, `--batch-template` and `--background-template` explicitly when invoking helper scripts. Optional `XRD_POWERSHELL` / `--powershell` selects a PowerShell executable; otherwise PATH discovery is used. Preset names need not match the author's former names.

This alpha still depends on the supported HighScore version's registry preset format. A missing or incompatible preset produces an error rather than inventing registry data. The native batch calls the version-specific `Clinker` entry while the project is in semi-automatic mode; the log's actual parameter count must match the selected model. This does not mean the sample must be clinker.

Close or finish the existing HighScore session before a background job; the launcher does not terminate another session. Windows/agent permissions must allow local process execution and temporary current-user registry presets. Only temporary presets created by the job are removed after normal completion; a timed-out process must be inspected before dispatching more jobs or deleting its temporary input.

## Use

In Codex, say for example:

```text
xrd精修 C:\XRD\sample.HPF。内标是刚玉，占混合后总质量的10%。
```

Codex reads the actual phases and asks whether all intended CIF structures, including the internal-standard structure, are imported. It asks for missing standard identity/amount/mass basis, then operates on temporary copies after explicit answers. An explicit "no internal standard" is valid; results then describe relative crystalline composition and must not claim absolute amorphous content.

Internal-standard percentages use:

`100 * standard_mass / (original_sample_mass + standard_mass)`

An addition percentage relative to the original sample is a different basis and must be converted.

Output:

```text
C:\XRD\sample.HPF
C:\XRD\Refined\sample_refined.HPF
```

`Refined` is created when needed. Existing originals and result files are not overwritten. Numerically unconverged candidates use `_candidate_unconverged.HPF`; duplicate result names receive a timestamp/number. Reports, tables and plots are not generated unless requested.

## Fixed comparison baseline

| Setting | Value |
|---|---|
| Background | Automatic / Sonneveld–Visser |
| Bending factor / Granularity | 2 / 20 |
| Smoothed input | Enabled for background estimation only |
| Background handling | Accept, no Subtract; Add to net scan = Nothing |
| Rietveld background | Use available background; coefficients fixed |
| Refinement mode | Semi-automatic |
| Profile Base Width | 12 FWHM |
| Maximum least-squares cycles | 100 |

This is a reproducible workflow baseline, not evidence that these values are optimal for every material. The agent must not change this baseline silently. Radiation, scan range, step and phase inventory come from each project; refined values from another sample are not copied. Refinement strategy is selected from residual evidence, without a mandatory 7/14/15-parameter sequence.

## Helper commands and checks

Read-only inspection does not require HighScore or preset configuration:

```powershell
& "$SkillRoot\.venv\Scripts\python.exe" "$SkillRoot\scripts\refine.py" inspect "C:\XRD\sample.HPF" --parameters
```

Run the isolated self-check without private data or native execution:

```powershell
& "$SkillRoot\.venv\Scripts\python.exe" "$SkillRoot\scripts\check_skill.py"
```

To check compatible files supplied by you:

```powershell
& "$SkillRoot\.venv\Scripts\python.exe" "$SkillRoot\scripts\check_skill.py" --xrd-directory "C:\XRD\compatible-projects"
```

`normalize`, `prepare`, `solve`, `compare`, and `deliver` are stage tools for the agent, not a single unattended pipeline. See [SKILL.md](SKILL.md) for the confirmation/plan schema and [native workflow notes](references/highscore-workflow.md). Normalization opens/saves only a temporary copy. If the adapter still rejects a file, stop or use a verified native interface; do not remove layout assertions or transplant a complete project template.

## Scientific limits

Rwp improvement, numerical convergence and valid phase identification are separate checks. Fixed background settings and an internal standard do not remove systematic errors. A residual unquantified fraction must not automatically be named C–S–H. Instrument calibration, spectral settings, phase completeness, preferred orientation, absorption and standard purity need appropriate evidence. Native curve caches must be verified before being interpreted as the current calculated profile.

## License

MIT; see [LICENSE](LICENSE). The license applies to this repository's code and instructions, not to HighScore or third-party databases/software. No affiliation with or endorsement by the instrument/software vendor is implied.
