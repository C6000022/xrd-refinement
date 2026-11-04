---
name: xrd-refinement
description: 仅用于HighScore Plus的XRD/Rietveld精修，已在本机3.0.5（3.0.5.15611）环境验证运行，其他版本兼容性未验证。用户要求“xrd精修”“XRD精修”“Rietveld精修”或精修HighScore Plus工程时使用。正式精修前必须向操作人确认本次背景方式与参数、目标晶相、定量方式及质量基准、内标种类与加入量、计算设置和CIF完整性；按本次确认锁定设置后自主精修。结果仅在源HPF文件夹的Refined子文件夹保存，默认在聊天汇报。
---

# XRD精修

公开测试版0.1.0-alpha.2，Windows / HighScore Plus文件版本3.0.5.15611。HPF解析仅支持已核验的部分布局；合成自检不证明原生求解或科学定量正确。首次使用先读仓库README和[原生运行与核查](references/highscore-workflow.md)。

## 先检查，再向操作人确认本次设置

只读检查用户提供的工程，读取真实扫描、辐射/Kα信息、扫描范围和步长、晶相列表、背景、计算设置与内标标记。保持原始数据，不能复制其他样品的扫描或优化数值。材料可为OPC、AAS或其他材料，不预设晶相数量、名称或扫描条件。

正式精修前，将实际晶相列表与下列问题一次呈现给操作人；只问尚未明确的信息。已经在本次任务明确给出的信息可复用，不逐轮重复确认；工程已有值、建议值和历史任务不能代替本次答复。确认未完成时，只能检查或保存转换临时副本，不能准备精修参数、估计背景或运行求解。

1. **背景如何处理？** 选择重新估计Automatic / Sonneveld–Visser背景，还是沿用工程中已接受的背景。重新估计时明确Bending factor、Granularity、Use smoothed input data。2/20/开启平滑仅是可展示的建议，操作人明确接受后才使用；不得自动填入。平滑只用于估计背景。默认支持Accept后把背景纳入模型，保留观察计数、不执行Subtract、Add to net scan=Nothing，并明确告诉操作人。其他算法、背景多项式、实际Subtract或改变观察计数不在此辅助脚本范围内，需要先核实原生接口与统计权重，不静默替换成已支持的方式。
2. **要定量什么？** 确认目标晶相（或全部样品晶相）、晶相相对定量还是内标定量，以及是否要求非晶/未定量余量。目标相清单只是报告范围，不用它删除其他有证据存在的相或仅用几个目标相归一化。目标相质量百分比是计算结果，不让操作人预填期望含量。
3. **内标是什么、加入了多少？** 明确未加内标也是有效答复。有内标时确认物质、对应的工程相、质量分数及分母，或原样/内标称量质量。统一换成内标质量/(原样质量+内标质量)×100%的混合物基准，写明换算。相对于原样的掺量不能直接填作混合后百分比；不能假定刚玉或10%。纯度/结晶度证据不充分时保留定量限制。
4. **结果按哪个质量基准报告？** 晶相相对定量使用样品晶相归一化基准，不能报告绝对非晶含量。内标法可按含内标混合物或扣除外加内标后的原样（As received）报告，必须由操作人明确选择。已知内标加入量、拟合尺度因子和待测相含量是不同量。
5. **计算设置是什么？** 展示工程当前Profile Base Width和最大循环数，确认本次采用的值；12 FWHM、100次仅为建议。最大循环是上限，不保证达到收敛。半自动模式和Use available background用于本工具的受控求解；背景系数固定。
6. **应包含的CIF是否全部导入？** 展示实际列表，明确包含内标对应结构。打开工程成功不等于模型完整。未导齐或不确定时先协助补齐，不正式精修。

将答复汇总为本次设置。批量文件应明确这些答复是否适用于全部文件；不一致时分别记录。相同任务、源文件及已确认设置不变时各轮直接复用；源文件、晶相模型、背景策略、定量要求或内标条件改变时重新核实受影响的内容。不要把公开版的规则变成作者个人固定参数。

## 确认后锁定，再自主精修

本次确认的背景、计算设置、内标加入量及报告基准在方案比较中保持一致。允许根据残差选择尺度因子、零点/位移、晶胞、峰宽、峰形、择优取向等自由参数，分组、联合、回退或复核；不强制7→14→15顺序。波长按真实测量条件固定，保留空间群/晶胞关系与合理约束。弱相与相关参数需要多反射证据，不用过多自由度补偿缺相或背景问题。

自动背景模式每轮按本次确认值重新估计；已有背景模式保持曲线，不重新估计。没有可验证的已有背景时先询问，不擅自切换到自动方式。不得用背景吞掉未解释的峰；出现科学问题时如实说明，不能为降低Rwp偷偷更改已确认条件。

## 阶段工具与请求

scripts/refine.py提供inspect、normalize、prepare、solve、compare、deliver。没有固定全流程run；操作策略和结果审查由Codex承担。inspect只读，可用--parameters和--filter查看实际参数；重复名称用id/name识别，不猜字节地址，也不把Profile Fit参数当作晶相Rietveld参数。

只有收到本次真实答复后才构造请求，通过--request -的标准输入传入。以下均为格式示例，不是用户确认；数值不得直接套用：

~~~json
{
  "confirmation": {
    "confirmed": true,
    "user_statement": "本次操作人确认CIF完整性的实际原话",
    "projects": {"源HPF绝对路径": "当前SHA256"}
  },
  "settings_confirmation": {
    "confirmed": true,
    "user_statement": "本次操作人确认背景与计算设置的实际原话",
    "source_sha256": "当前SHA256",
    "background": {"mode": "automatic", "handling": "model_background", "bending_factor": 2, "granularity": 20, "smoothed_input": true},
    "computation": {"profile_base_width": 12, "max_cycles": 100}
  },
  "standard_confirmation": {
    "confirmed": true,
    "user_statement": "本次操作人确认内标及加入量和质量基准的实际原话",
    "source_sha256": "当前SHA256",
    "added": true,
    "mass_basis": "mixed_total_mass",
    "weights": [{"phase": "实际内标相名称", "mixed_mass_pct": 10.0}]
  },
  "quantification_confirmation": {
    "confirmed": true,
    "user_statement": "本次操作人确认定量目标与报告基准的实际原话",
    "source_sha256": "当前SHA256",
    "mode": "internal_standard",
    "target_phases": ["实际目标相名称"],
    "report_basis": "original_sample",
    "include_unquantified_fraction": true
  },
  "plan": {"reason": "本轮真实诊断目的", "refine": ["实际参数名称或id/name"], "edits": []}
}
~~~

已有背景用background={mode:available,handling:model_background}，不带自动背景参数。明确无内标用added=false、weights=[]。相对定量用mode=relative_crystalline、report_basis=crystalline_only、include_unquantified_fraction=false；内标法基准可为original_sample或mixed_sample。目标相列表必须能映射到实际工程。其他定量方法没有被本辅助脚本实现，不能伪装成内标法。

prepare把本次计算值写入临时副本，按确认设置内标并清除旧内标标记；计划中的冲突设置会被拒绝。refine省略时保留原自由度，显式给出时表示本轮完整自由参数集合。edits只修改明确识别的参数、值和边界，不改变观察数据、辐射或结构库存。

solve的背景动作由settings_confirmation决定：automatic传入确认的参数，available跳过估计；不接受矛盾的--estimate-background。所有正式阶段必须带四类确认，并覆盖同一源文件哈希。结果中的quantification_scope只记录操作人要求，不代表已自动切换软件显示基准或完成质量换算；最终必须核对原生Derived Data/Quantification中相应质量基准，不把未知缓存直接当As received。相对定量的归一分母应包含全部已建模样品晶相，而非仅目标相；内标处理需与该基准匹配。

程序路径和本机预设名通过XRD_HIGHSCORE_EXE、XRD_BATCH_TEMPLATE、XRD_BACKGROUND_TEMPLATE或对应CLI参数指定；已有背景不需要背景预设。PowerShell从PATH读取或由XRD_POWERSHELL指定。优先原生/Q /B，不使用本版不支持的/G。辅助工具在半自动模式调用受支持版本的Clinker入口，并核对实际自由参数数目；它不代表样品必须是熟料。

遇到不支持的HPF布局，normalize只在临时副本执行原生打开另存，返回origin_snapshot供后续身份核验，不估计背景、不精修。仍不兼容时使用经过核验的原生界面/正式接口；不能移除断言或移植整份模板。已有HighScore会话冲突时不强行终止用户未保存的工程。

## 核验、报告与保存

每轮核对退出状态、Solution found、原生输出HPF、日志和项目自由参数数目、观察扫描及辐射不变；已有背景模式还要逐点核对背景不变。原生保存名可能由锚扫描决定，从隔离临时目录识别唯一输出。

同模型复算的数值参考保持为|ΔRwp|<0.005个百分点、所有自由参数有效ESD、最大Last Shift/ESD与跨复算移动/ESD<0.2且无参数撞边界；比较要求相同观察数据、背景曲线和本次计算设置。这些检查不证明物相模型和定量正确。审查全谱、多个反射、参数物理合理性、相关性与含量稳定性，停止无收益的重复求解。

核对原生History中的实际背景动作；图形缓存未经验证不能当作本轮计算曲线。内标不能消除背景误差，未定量余量不能全部称为C–S–H。模型问题、标准纯度和报告基准等限制直接在聊天说明。

保留原始HPF/RAW/TXT/CIF。阶段副本和日志仅用本次系统临时目录；成功交付且进程退出后清理，超时先保留仍被占用的副本并停止新派发。最终只在各源HPF文件夹的Refined子文件夹另存<原名>_refined.HPF；重名添加时间/编号，不覆盖。数值未稳定时标为_candidate_unconverged.HPF。未经要求不生成报告、CSV/Excel、JSON清单、图片或其他结果目录。
