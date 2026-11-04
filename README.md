# XRD Refinement Skill

**v0.1.0-alpha.3 — experimental / 公开测试版**

**仅适用于 HighScore Plus。** 已在作者本机的 HighScore Plus **3.0.5（完整文件版本 3.0.5.15611）** 环境验证过原生精修运行；其他版本的兼容性尚未验证。

**For HighScore Plus only.** Native refinement has been tested in the author's local **v3.0.5 environment (file version 3.0.5.15611)**. Compatibility with other versions has not been verified.

A Codex skill for supervised, local Rietveld refinement of existing HighScore Plus projects. It confirms the operator's background settings, target phases, quantification method and mass basis, internal standard and CIF completeness, then locks those settings for the task, chooses refinement parameters from the actual model, and saves HPF results under `Refined/`.

用于在Windows上调用HighScore进行XRD精修。使用者提供已经包含实测扫描与拟合晶体结构的HPF；正式操作前必须向操作人确认背景方式与参数、目标晶相、定量方式及报告质量基准、内标种类与加入量、计算设置及CIF完整性；不能直接套用作者个人参数。结果默认仅交付HPF，结论在聊天中汇报。

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

1. For automatic-background tasks, save a native automatic background preset with `Add to net scan = Nothing`. The launcher derives a unique temporary preset and writes the bending factor, granularity and smoothing choice explicitly confirmed by the operator. Unrecognized ancillary fields are rejected. Available-background mode preserves the existing curve and does not need a background preset.
2. Save a native user batch containing the background-determination action. The launcher validates and uses the native serialization header; it replaces the actions in a temporary batch with a controlled solve/save sequence. Normalization uses save only.
3. Set the executable path and the actual saved preset names (XRD_BACKGROUND_TEMPLATE is needed only for automatic estimation). The following values are examples to replace with your own:

```powershell
$env:XRD_HIGHSCORE_EXE = "C:\Program Files\PANalytical\X'Pert HighScore Plus\HighScorePlus.exe"
$env:XRD_BATCH_TEMPLATE = "My Rietveld Batch"
$env:XRD_BACKGROUND_TEMPLATE = "My Automatic Background"
```

These environment variables apply to the current terminal process and its children. Start Codex from that environment or pass `--highscore`, `--batch-template` and `--background-template` explicitly when invoking helper scripts. Optional `XRD_POWERSHELL` / `--powershell` selects a PowerShell executable; otherwise PATH discovery is used. Preset names need not match the author's former names.

This alpha still depends on the supported HighScore version's registry preset format. A missing or incompatible preset produces an error rather than inventing registry data. The native batch calls the version-specific `Clinker` entry while the project is in semi-automatic mode; the log's actual parameter count must match the selected model. This does not mean the sample must be clinker.

Close or finish the existing HighScore session before a background job; the launcher does not terminate another session. Windows/agent permissions must allow local process execution and temporary current-user registry presets. Only temporary presets created by the job are removed after normal completion; a timed-out process must be inspected before dispatching more jobs or deleting its temporary input.

Native solving runs locally: the launcher starts HighScore Plus with `/Q /B` and a hidden window, waits for completion, and checks the solver log and saved HPF. Codex selects each stage's parameters, inspects results and decides the next stage. This requires an active Codex task and the configured local software; hidden-window launch does not establish that every vendor dialog is suppressed.

## Use

In Codex, say for example:

```text
xrd精修 C:\XRD\sample.HPF。内标是刚玉，占混合后总质量的10%。
```

Codex reads the actual phases and asks the required pre-refinement questions below. A standard amount alone is not enough to start. It then operates on temporary copies after the operator has explicitly answered all applicable questions. It reuses complete answers within the same unchanged task rather than repeating them every refinement cycle. An explicit "no internal standard" is valid; results then describe relative crystalline composition and must not claim absolute amorphous content.

Internal-standard percentages use:

`100 * standard_mass / (original_sample_mass + standard_mass)`

An addition percentage relative to the original sample is a different basis and must be converted.

Output when the original file path is verified:

```text
C:\XRD\sample.HPF
C:\XRD\Refined\sample_refined.HPF
```

`Refined` is created when needed. Existing originals and result files are not overwritten. Numerically unconverged candidates use `_candidate_unconverged.HPF`; duplicate result names receive a timestamp/number. Reports, tables and plots are not generated unless requested.

**Dragged/uploaded files:** first establish whether the accessible HPF is the original file or an attachment copy. With a verified original path, use its neighboring `Refined`. If only an attachment copy or an unknown source location is available, Codex must ask for an absolute, persistent final result folder **before preparation or solving**, and save directly to that confirmed folder. It must not infer the original folder from the filename or silently leave final results beside an attachment cache. The helper requires `input_location` for formal stages and, for attachment/unknown inputs, a source-bound `output_confirmation`; see [SKILL.md](SKILL.md). A later `--output` cannot override the selected folder without renewed confirmation. Completion messages provide a clickable absolute result path.

拖入文件时先核实来源：能确认原始路径，就保存到其下的Refined；只有附件副本或无法确认原始目录时，精修前先问最终保存文件夹，按操作人确认的完整路径直接保存。临时目录在交付完成、HighScore退出后由Codex按技能说明清理；异常或超时可能保留用于排查，脚本尚未提供统一自动清理函数。

## Mandatory operator confirmation before refinement

The public version fixes the **questions and within-task consistency**, not universal scientific parameter values. Missing answers block preparation and native solving. Only read-only inspection and save-only normalization may precede confirmation. Existing project values and suggestions are shown as context; neither counts as the operator's answer.

| Confirm with the operator | Required information |
|---|---|
| Background treatment | Re-estimate automatic background or reuse the accepted project curve? Automatic mode requires bending factor, granularity and smoothing choice. |
| Background handling | Accept/include background in the model, preserve observed counts, no Subtract, Add to net scan = Nothing. Other processing needs a separately validated native workflow. |
| Quantification target | Actual phase names or all sample phases; whether an unquantified/amorphous fraction is requested. |
| Quantification method | Relative crystalline composition or internal-standard quantification. Other methods are not silently mapped to either. |
| Internal standard | Material/structure, actual known added percentage and its denominator, or the two weighed masses; explicit no-standard is valid. |
| Reporting mass basis | Crystalline-only normalization, mixed specimen including added standard, or original specimen excluding the added standard (As received), as appropriate to the chosen method. |
| Computation settings | Profile base width and maximum least-squares cycles for this task. |
| CIF completeness | All intended structures, including the standard, have been imported. |

Chinese first-run questions:

1. **本次背景采用自动重新估计，还是沿用工程已接受的背景？** 自动背景的Bending factor、Granularity、是否使用平滑输入分别是什么？确认Accept后纳入模型，保留原始强度。
2. **要定量哪些晶相？采用晶相相对定量还是内标法？是否需要非晶/未定量余量？**
3. **内标是什么，加入多少？百分比按混合后总质量还是原样质量？** 也可给出称量质量，或明确未加内标。
4. **结果按含内标混合物，还是扣除内标后的原样报告？** 相对定量则明确样品晶相归一化基准。
5. **本次峰形计算宽度（Profile Base Width，FWHM单位）和循环上限采用什么值？所需CIF是否全部导入？**

Automatic 2/20/smoothed, 12 FWHM and 100 cycles may be offered as suggestions, but are used only after explicit acceptance. A custom confirmed choice (for example 5/30/no smoothing) must be respected. Accepted settings stay fixed within that task; changes require renewed confirmation. Quantification target percentages are computed outputs, not desired values to enter before refinement.

The helper enforces operator-confirmed settings and rejects conflicting plans. It uses semi-automatic mode and an accepted background curve. For automatic mode it estimates that curve with the confirmed parameters before each solve. Available mode does not re-estimate it, rejects an estimate flag, and checks the curve remains unchanged. Unsupported background algorithms or actual subtraction are not claimed implemented.

Requests carry `settings_confirmation`, `quantification_confirmation`, `standard_confirmation` and CIF `confirmation`, tied to the original file hash. The exact schema is in [SKILL.md](SKILL.md). `quantification_scope` in a helper result records the requested output, not proof that the native display basis was changed or mass fractions converted. The agent must verify the appropriate native quantification fields before reporting. Selecting target phases changes the reporting scope, not the complete phase model or the crystalline normalization denominator.

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
