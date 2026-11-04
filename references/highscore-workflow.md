# Native HighScore workflow and validation

## Scope

Experimental adapter for HighScore Plus file version3.0.5.15611 on Windows. Radiation, material, scan grid and intended phases come from each input project. Unsupported serialization or native preset formats must be rejected. Scientific validity and clean-machine native execution are not established by synthetic tests.

## Before refinement

Ask for the internal-standard identity, amount and mass basis, and confirm all intended CIF structures are imported. Explicitly no added standard is valid. Bind confirmations to each original file hash. The agent must never fabricate a user's statement or infer completeness from the presence of a few structures.

Preparation writes only temporary copies, applies the confirmed standard and clears stale standard designations. Solve/comparison/delivery check the same standard settings. Original files remain unchanged.

## Runtime configuration

Set XRD_HIGHSCORE_EXE, XRD_BATCH_TEMPLATE and XRD_BACKGROUND_TEMPLATE, or pass the corresponding CLI flags. PowerShell is detected on PATH unless XRD_POWERSHELL / --powershell is supplied. See the repository README for creating native presets through HighScore. No private registry export is included.

The launcher derives a native batch header from the explicitly named saved user batch. It requires an actCorrectBackground action in that template. An explicitly named saved background preset supplies the validated serialization structure; the derived temporary preset enforces Automatic, 2/20 and smoothed input, with verified ancillary fields for the supported layout. Unrecognized fields require inspection in the native UI.

Use /Q /B; /G is not supported by this launcher. Controlled solve actions are actEditAutoRefinerSteps;Clinker;actSaveDoc;Default;EndOfBatchItems;. Semi-automatic mode controls the selected parameters. Verify native log/HPF parameter counts so an automatic full strategy cannot be mistaken for the requested model.

Normalization uses save actions only and never estimates background or refines. Each normal solve estimates background with the fixed baseline before solving. Read native History after solving to verify Automatic,2,20,smoothed Yes,Add to net scan=Nothing and unchanged observed counts; the binary adapter does not claim to parse all native History fields.

## Serialization and output

The adapter discovers the embedded scan and typed parameter records and preserves scan values, wavelength and phase inventory. It does not bind to a seven-phase model or a specific range/step. Mode/control blocks and native metrics must validate, and existing crystallographic relationships remain in force.

Some HPF files have a different layout despite the same top-level version number. Native save-only normalization may help but is not guaranteed. Do not relax assertions to make a file parse. An earlier real-file regression failed for this reason; this release records the limitation rather than claiming a fix.

The native saved filename can depend on the anchor scan. Detect the unique saved output in the isolated temporary directory rather than assuming a filename. On successful reviewed delivery, save only the final/candidate HPF in the original folder's Refined subfolder and clean up this job's temporary directory after the native process has exited. On timeout, retain the live process's temporary files and stop new dispatches.

## Scientific review

Compare whole-pattern and multiple-reflection residuals, physical parameter values, constraints, correlations, boundary contacts and quantitative sensitivity. Rwp alone is not an acceptance rule. Background must not swallow missing phases or unexplained broad scattering. Regions must be selected using the project's actual radiation, not a fixed Co-angle lookup.

Consult the HighScore help installed with the user's software for its native interfaces and fields. Relevant topics include command-line batches, native scripting, refinement variables, internal standards and available background. Reference: https://journals.iucr.org/j/issues/1999/01/00/gl0561/index.html .
