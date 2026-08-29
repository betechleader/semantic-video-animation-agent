(() => {
  'use strict';

  const translations = {
    'zh-CN': {
      documentTitle: '帧语工坊 · 本地 AI 创作平台', skipToContent: '跳到主要内容', primaryNavigation: '主导航', closeNavigation: '关闭导航', openNavigation: '打开导航',
      brandName: '帧语工坊', brandTagline: 'LOCAL AI STUDIO', localRunning: '本地运行', localData: '数据保存在本机', platformLabel: 'AI 视频与内容创作平台', languageLabel: '界面语言',
      navWorkspace: '工作空间', navHome: '创作首页', navTools: '功能工具', navManagement: '任务与设置', navTasks: '最近任务', navSettings: '设置',
      pageHomeTitle: '创作工作台', pageHomeDescription: '在本机完成从素材到成片的 AI 创作流程。', pageToolTitle: '语义视频动画', pageToolDescription: '上传口播原片，生成语义画面与动态包装。', pageTasksTitle: '最近任务', pageTasksDescription: '继续本机已有任务，查看真实处理状态。', pageSettingsTitle: '设置', pageSettingsDescription: '管理本地工作台的界面偏好。',
      homeEyebrow: '本地优先 · 创作工具箱', homeTitle: '让内容生产更专注，把繁琐流程交给本地 AI。', homeDescription: '从口播视频的语义包装开始，在统一工作台中组织素材、处理任务和审核成片。', startCreating: '开始创作', viewTasks: '查看最近任务',
      toolboxEyebrow: '创作工具', toolboxTitle: '从一个成熟模块开始', toolboxDescription: '功能目录由配置驱动，后续模块可在同一平台外壳中扩展。', available: '可用', planned: '规划中', openTool: '打开工作台', notAvailable: '尚未开放', availableNow: '已可使用',
      semanticToolName: '语义视频动画', semanticToolSummary: '口播转写、语义规划、动态字幕、视觉素材与成片审核。', scriptToolName: '内容脚本助手', scriptToolSummary: '围绕选题、结构和口播表达组织创作脚本。', assetToolName: '内容素材整理', assetToolSummary: '在本机整理创作素材、来源和使用记录。',
      continueEyebrow: '快速继续', continueTitle: '最近任务', viewAll: '查看全部', noRecentTask: '还没有本机任务。创建第一个语义视频后，可从这里快速继续。', continueTask: '继续任务', recentSemanticTask: '语义视频动画任务',
      privacyEyebrow: '本地优先', privacyTitle: '创作素材留在你的电脑上', privacyDescription: '任务文件、转写和成片保存在本机存储目录。只有在你选择外部素材源时，相关搜索才会访问对应服务。',
      semanticTitle: '语义视频动画', semanticDescription: '识别口播内容，生成动态字幕、语义画面和知识型视觉包装。', newCreation: '新建创作', workflowSteps: '创作步骤', stepUpload: '上传素材', stepUploadHint: '选择视频与处理方式', stepProcess: '本地处理', stepProcessHint: '转写、规划与渲染', stepReview: '预览审核', stepReviewHint: '检查成片与高级内容',
      readyTitle: '准备开始', ready: '请选择一个 MP4 视频开始处理。', sourceEyebrow: '第一步', uploadTitle: '添加口播原片', uploadDescription: '支持最大 100 MB 的 MP4 文件。素材将保存在本地任务目录。', dropTitle: '拖放视频到这里，或点击选择', noFileChosen: '尚未选择文件', dropHint: 'MP4 · 最大 100 MB', generationSettings: '生成设置', settingsHint: '推荐配置适合正式本地处理', workflowMode: '工作流模式', workflowStandard: '标准工作流（稳定）', workflowAgent: 'Agent 工作流', directorInstruction: '导演指令（可选）', directorInstructionPlaceholder: '例如：前三秒更抓人，减少全屏素材', approvalPolicy: '审批策略', approvalNever: '无需审批', approvalOnRisk: '遇到风险时审批', approvalAlways: '始终审批', agentSettingsHelp: 'Agent 将按真实节点执行；导演指令只进入 Agent 状态，审批会在渲染前暂停。', processingMode: '处理模式', profileReal: '真实转写 + 语义规划（推荐）', profileMock: 'Mock 测试文案', profileConfigured: '使用服务端环境变量', externalMedia: '素材来源', providerKnowledge: '知识素材组合（推荐）', providerWikimedia: '仅 Wikimedia Commons', providerPexels: 'Pexels（需要 API Key）', providerMock: '本地原创信息图', providerManual: '仅人工候选 URL', settingPrivacyNote: '语音识别与渲染在本机完成；外部素材模式可能访问所选素材服务。', uploadButton: '上传并开始生成', invalidFile: '请选择有效的 MP4 文件。',
      processingEyebrow: '任务进行中', processingTitle: '正在本地生成视频', taskProgress: '任务进度', processCreated: '任务已创建', processTranscribe: '转写与语义规划', processRender: '动画渲染与合成', processComplete: '质量检查完成', cancelTask: '取消任务', agentExecutionEyebrow: '真实执行状态', agentExecutionTitle: 'Agent 节点轨迹', agentExecutionHelp: '状态直接来自持久工作流的 SSE 节点事件，不使用估算百分比。', agentRetries: '重试 {count} 次', nodeStatusNotStarted: '未开始', nodeStatusStarted: '执行中', nodeStatusResumed: '已恢复', nodeStatusCompleted: '已完成', nodeStatusFailed: '失败', node_upload_probe: '上传与探测', node_audio_asr: '音频与转写', node_correction: '转写校正', node_planning: '语义规划', node_validation: '计划校验', node_render: '动画渲染', node_quality: '质量检查', node_complete: '完成任务',
      resultEyebrow: '生成完成', resultTitle: '成片已准备好', resultDescription: '先检查播放效果，再进入下方高级审核区调整转写、动画或素材。', downloadResult: '下载成片', summaryTitle: '本地生成完成', summaryDescription: '成片已通过技术质量检查，可下载或继续审核。', durationLabel: '时长', resolutionLabel: '分辨率', taskLabel: '任务编号', secondsUnit: '秒',
      advancedEyebrow: '高级审核', advancedTitle: '检查并微调生成内容', advancedDescription: '这些内容不会占据初始创作界面，仅在成片完成后按需展开。', reviewTabs: '审核内容', transcriptTab: '转写文本', planTab: '动画计划', mediaTab: '素材审核', evidenceTab: '知识证据', agentTraceTab: 'Agent 轨迹', activityTab: '任务记录', transcriptTitle: '转写文本 JSON', transcriptHelp: '修改分段文本后保存，后端会沿用原时间区间并重新规划动画。', planTitle: '动画计划 JSON', planHelp: '可检查时间轴、模板参数和已选素材。无效修改会由后端安全校验拒绝。', evidenceTitle: '知识证据与引用', evidenceHelp: '显示 Agent 采用的本地知识片段、来源和实时索引状态；失效引用不能进入审批或重渲染。', evidenceValid: '全部引用有效（{count}）', evidenceInvalid: '存在失效引用（{count}）', evidenceEmpty: '本计划没有采用知识证据，事实视觉会安全降级。', evidenceSource: '来源：{source}', evidenceCitedBy: '引用动画：{animations}', evidenceStatus: '索引状态：{status}', agentTraceTitle: 'Agent 审计摘要', agentTraceHelp: '仅展示节点、工具、重试、耗时和结构化错误，不展示内部思维链或内容正文。', traceStatus: '状态：{status}', tracePlanner: '规划器：{planner}', traceRetries: '重试：{count}', traceEntry: '{node} · {type} · {status}', traceDuration: '耗时 {duration} ms', traceViolations: '问题：{codes}', noAgentTrace: 'Agent Trace 尚未生成。',
      approvalEyebrow: '需要人工决策', approvalTitle: '审核 Agent 动画计划', approvalHelp: '确认后从持久 Checkpoint 继续；编辑会再次经过服务端 schema、规划规则与安全区校验。', approvalPlanLabel: '待审批动画计划 JSON', approvePlan: '批准并继续', editPlan: '验证修改并继续', rejectPlan: '拒绝任务', approvalReasonFallback: '该计划需要人工确认。', approval_reason_policy_always: '当前策略要求在渲染前进行人工审核。', approval_reason_plan_repair_exhausted: '自动修复次数已耗尽，需要提交一份通过校验的编辑计划。', approval_reason_media_relevance_unverified: '外部素材与内容的相关性尚未由审核者确认。', approval_reason_external_media_rights_review: '外部素材来源与权利信息需要人工审核。', approvalSubmittingTitle: '正在提交审批', approvalSubmitting: '正在保存人工决策…', approvalResumingTitle: '正在恢复 Agent', approvalResuming: '决策已保存，Agent 将从渲染节点继续。', approvalFailedTitle: '审批失败', approvalFailed: '无法提交审批：{message}', rejectedTitle: '任务已拒绝', event_rejected: '人工已拒绝该计划，任务不会进入渲染。', awaitingApprovalTitle: '等待人工审批', event_awaiting_approval: 'Agent 已在渲染前暂停，请审核下方计划。', event_approved: '计划已批准，准备从 Checkpoint 恢复。', event_edited: '修改后的计划已通过校验，准备恢复。', event_resumed: 'Agent 已从持久 Checkpoint 恢复。',
      reviewTitle: '外部 B-roll 素材审核', reviewNote: '外部素材仅用于效果验证原型。商业发布前必须人工审核来源、权利、准确性和适用性。', searchQueryLabel: '搜索词', searchPlaceholder: '例如：supermarket product', mediaTypeLabel: '类型', imageKind: '图片', videoKind: '视频', searchButton: '搜索素材', manualUrlLabel: '人工候选 URL', manualUrlPlaceholder: 'https://...', addManualButton: '添加候选', activityTitle: '任务事件', activityHelp: '记录当前浏览器会话中收到的创建、处理、渲染和审核状态。', replanNote: '修改转写后保存时，后端会根据修改后的文本自动重建动画计划，并清理旧素材派生数据。', saveReview: '保存修改并重新渲染',
      tasksEyebrow: '本机任务', tasksTitle: '最近任务', tasksDescription: '这里仅显示此浏览器在本机创建或恢复过的真实任务，不生成示例数据。', restoreTitle: '恢复已有任务', restoreDescription: '输入本机任务编号，可重新打开仍保存在 storage 目录中的任务。', taskIdPlaceholder: '任务编号', restoreButton: '恢复任务', restoringTask: '正在查找本机任务…', restoreFailed: '无法恢复该任务：{message}', noTasks: '没有可显示的最近任务。', openTask: '打开任务', unknownFile: '未记录文件名', unavailableTask: '任务已不在本机存储中',
      settingsEyebrow: '平台设置', settingsTitle: '设置', settingsDescription: '当前仅提供与本地工作台真实能力相关的偏好。', interfaceLanguage: '界面语言', interfaceLanguageDescription: '语言偏好会保存在浏览器中，刷新后继续生效。', storageTitle: '本地数据', storageDescription: '上传素材、任务数据库、转写、计划与成片由 FastAPI 服务保存在本机 storage 目录。本页面不提供云同步或账户功能。', localStorageActive: '本地存储已启用',
      statusPending: '等待处理', statusProcessing: '正在处理', statusRendering: '正在渲染', statusAwaitingApproval: '等待审批', statusRejected: '已拒绝', statusCompleted: '已完成', statusFailed: '失败', statusCancelled: '已取消', statusUnavailable: '不可用',
      uploadingTitle: '正在上传', uploading: '正在把视频保存到本机任务目录…', uploadFailedTitle: '上传失败', uploadFailed: '上传失败：{message}', taskCreatedTitle: '任务已创建', event_created: '任务已创建，正在等待本地处理。', processingStatusTitle: '正在分析内容', event_processing: '正在提取音频、转写语音并进行语义规划…', renderingStatusTitle: '正在合成成片', event_rendering: '正在生成动画并合成视频…', event_review_rendering: '正在根据审核修改重新渲染…', cancelRequestedTitle: '正在取消', event_cancel_requested: '已请求取消任务，正在等待当前安全步骤结束。', completedTitle: '处理完成', completed: '处理完成：{seconds} 秒，{width} × {height}。', failedTitle: '任务失败', event_failed: '任务失败：{message}', cancelledTitle: '任务已取消', event_cancelled: '任务已取消。你可以重新选择素材开始。', cancelFailed: '无法取消任务：{message}', taskLoadFailed: '无法加载任务。', downloadFallback: '{message}\n视频已可下载，但无法加载转写文本和动画计划：{error}',
      validatingReviewTitle: '正在保存审核', validatingReview: '正在校验修改并重新渲染…', reviewFailedTitle: '审核失败', reviewFailed: '审核重渲染失败：{message}', replanned: '已根据修改后的转写重建动画计划，正在渲染…', searchingTitle: '正在搜索素材', searching: '正在搜索外部 B-roll 候选…', searchFailedTitle: '素材搜索失败', searchFailed: '素材搜索失败：{message}', foundCandidatesTitle: '候选已更新', foundCandidates: '找到 {count} 个候选。选择素材后保存审核修改。', manualFailed: '添加人工候选失败：{message}', manualVisual: '人工素材', unknownError: '未知错误', invalidJson: 'JSON 格式无效：{message}',
      chooseTarget: '替换 B-roll 前，请先选择要应用的语义画面。', selectedCandidateTitle: '已选择候选', selectedCandidate: '已选择“{title}”。保存审核修改后会下载并渲染任务内副本。', brollDisabledTitle: '素材已更新', brollDisabled: '已禁用该 B-roll。保存审核修改后重新渲染。', generatedOriginal: '本地原创信息图', pendingSelection: '等待选择或渲染', disabled: '已禁用', disable: '禁用', enable: '启用', useFor: '用于：{title}', useThis: '使用此素材', imageAsset: '外部图片', videoAsset: '外部视频', sourceLink: '查看来源', noMediaVisuals: '当前动画计划没有 B-roll 画面。', noCandidates: '尚未搜索或添加候选素材。',
      event_created_label: '创建任务', event_processing_label: '内容处理', event_rendering_label: '动画渲染', event_review_rendering_label: '审核重渲染', event_cancel_requested_label: '请求取消', event_agent_node_label: 'Agent 节点', event_awaiting_approval_label: '等待审批', event_approved_label: '计划已批准', event_edited_label: '计划已编辑', event_resumed_label: 'Agent 已恢复', event_rejected_label: '计划已拒绝', event_completed_label: '处理完成', event_failed_label: '任务失败', event_cancelled_label: '任务取消', eventGeneric: '任务状态更新',
    },
    en: {
      documentTitle: 'Frame Studio · Local AI Creation Platform', skipToContent: 'Skip to main content', primaryNavigation: 'Primary navigation', closeNavigation: 'Close navigation', openNavigation: 'Open navigation',
      brandName: 'Frame Studio', brandTagline: 'LOCAL AI STUDIO', localRunning: 'Running locally', localData: 'Data stays on this device', platformLabel: 'AI video and content creation platform', languageLabel: 'Language',
      navWorkspace: 'Workspace', navHome: 'Creation home', navTools: 'Tools', navManagement: 'Tasks and settings', navTasks: 'Recent tasks', navSettings: 'Settings',
      pageHomeTitle: 'Workspace', pageHomeDescription: 'Take local AI workflows from source media to finished output.', pageToolTitle: 'Semantic video', pageToolDescription: 'Turn talking-head footage into semantically enhanced video.', pageTasksTitle: 'Recent tasks', pageTasksDescription: 'Continue real tasks stored on this device.', pageSettingsTitle: 'Settings', pageSettingsDescription: 'Manage preferences for the local workspace.',
      homeEyebrow: 'Local first · Creative toolkit', homeTitle: 'Focus on the story. Let local AI handle the production steps.', homeDescription: 'Start with semantic enhancement for talking-head videos, then organize sources, processing, and review in one workspace.', startCreating: 'Start creating', viewTasks: 'View recent tasks',
      toolboxEyebrow: 'Creative tools', toolboxTitle: 'Start with one production-ready module', toolboxDescription: 'The tool catalog is configuration-driven, ready for future modules in the same shell.', available: 'Available', planned: 'Planned', openTool: 'Open workspace', notAvailable: 'Not available yet', availableNow: 'Available now',
      semanticToolName: 'Semantic video animation', semanticToolSummary: 'Transcription, semantic planning, dynamic captions, visual media, and final review.', scriptToolName: 'Content script assistant', scriptToolSummary: 'Plan topics, structure, and spoken delivery for future productions.', assetToolName: 'Content asset organizer', assetToolSummary: 'Organize local creative assets, sources, and usage records.',
      continueEyebrow: 'Quick continue', continueTitle: 'Recent task', viewAll: 'View all', noRecentTask: 'No local tasks yet. Create your first semantic video to continue it here.', continueTask: 'Continue task', recentSemanticTask: 'Semantic video task',
      privacyEyebrow: 'Local first', privacyTitle: 'Your creative material stays on your computer', privacyDescription: 'Task files, transcripts, and results live in local storage. Requests leave the device only when you choose an external media provider.',
      semanticTitle: 'Semantic video animation', semanticDescription: 'Understand spoken content and generate dynamic captions, semantic visuals, and knowledge-style packaging.', newCreation: 'New creation', workflowSteps: 'Creation steps', stepUpload: 'Upload source', stepUploadHint: 'Choose video and settings', stepProcess: 'Local processing', stepProcessHint: 'Transcribe, plan, and render', stepReview: 'Preview and review', stepReviewHint: 'Inspect output and advanced data',
      readyTitle: 'Ready to begin', ready: 'Choose an MP4 video to begin processing.', sourceEyebrow: 'Step one', uploadTitle: 'Add talking-head footage', uploadDescription: 'Supports MP4 files up to 100 MB. The source stays in the local task directory.', dropTitle: 'Drop a video here, or click to choose', noFileChosen: 'No file selected', dropHint: 'MP4 · Up to 100 MB', generationSettings: 'Generation settings', settingsHint: 'Recommended defaults suit full local processing', workflowMode: 'Workflow mode', workflowStandard: 'Standard workflow (Stable)', workflowAgent: 'Agent workflow', directorInstruction: 'Director instruction (Optional)', directorInstructionPlaceholder: 'e.g. Make the first three seconds stronger and reduce full-screen media', approvalPolicy: 'Approval policy', approvalNever: 'Never require approval', approvalOnRisk: 'Require approval on risk', approvalAlways: 'Always require approval', agentSettingsHelp: 'Agent runs on real workflow nodes. Director instructions stay Agent-only, and approval pauses before rendering.', processingMode: 'Processing mode', profileReal: 'Real transcription + semantic planning (Recommended)', profileMock: 'Mock test transcript', profileConfigured: 'Use server environment settings', externalMedia: 'Media source', providerKnowledge: 'Knowledge media mix (Recommended)', providerWikimedia: 'Wikimedia Commons only', providerPexels: 'Pexels (API key required)', providerMock: 'Local original infographic', providerManual: 'Manual candidate URLs only', settingPrivacyNote: 'Speech recognition and rendering run locally; external media modes may contact the selected provider.', uploadButton: 'Upload and generate', invalidFile: 'Choose a valid MP4 file.',
      processingEyebrow: 'Task in progress', processingTitle: 'Generating video locally', taskProgress: 'Task progress', processCreated: 'Task created', processTranscribe: 'Transcription and planning', processRender: 'Animation and compositing', processComplete: 'Quality check complete', cancelTask: 'Cancel task', agentExecutionEyebrow: 'Real execution state', agentExecutionTitle: 'Agent node trace', agentExecutionHelp: 'States come directly from persistent-workflow SSE node events; no estimated percentage is used.', agentRetries: '{count} retries', nodeStatusNotStarted: 'Not started', nodeStatusStarted: 'Running', nodeStatusResumed: 'Resumed', nodeStatusCompleted: 'Completed', nodeStatusFailed: 'Failed', node_upload_probe: 'Upload and probe', node_audio_asr: 'Audio and ASR', node_correction: 'Transcript correction', node_planning: 'Semantic planning', node_validation: 'Plan validation', node_render: 'Animation render', node_quality: 'Quality check', node_complete: 'Complete task',
      resultEyebrow: 'Generation complete', resultTitle: 'Your video is ready', resultDescription: 'Review playback first, then use the advanced area below to adjust the transcript, animation, or media.', downloadResult: 'Download video', summaryTitle: 'Generated locally', summaryDescription: 'The result passed technical quality checks and is ready to download or review.', durationLabel: 'Duration', resolutionLabel: 'Resolution', taskLabel: 'Task ID', secondsUnit: 'sec',
      advancedEyebrow: 'Advanced review', advancedTitle: 'Inspect and refine generated content', advancedDescription: 'Advanced data stays out of the initial workflow and appears only after the result is ready.', reviewTabs: 'Review content', transcriptTab: 'Transcript', planTab: 'Animation plan', mediaTab: 'Media review', evidenceTab: 'Evidence', agentTraceTab: 'Agent trace', activityTab: 'Task activity', transcriptTitle: 'Transcript JSON', transcriptHelp: 'Edit segment text and save; the backend reuses the original time span and rebuilds the plan.', planTitle: 'Animation plan JSON', planHelp: 'Inspect the timeline, template parameters, and selected media. Backend validation rejects unsafe edits.', evidenceTitle: 'Knowledge evidence and citations', evidenceHelp: 'Shows local knowledge excerpts, sources, and live index status used by the Agent. Invalid citations cannot pass approval or re-render.', evidenceValid: 'All citations are valid ({count})', evidenceInvalid: 'Invalid citations found ({count})', evidenceEmpty: 'This plan uses no knowledge evidence; factual visuals are safely downgraded.', evidenceSource: 'Source: {source}', evidenceCitedBy: 'Cited by: {animations}', evidenceStatus: 'Index status: {status}', agentTraceTitle: 'Agent audit summary', agentTraceHelp: 'Shows nodes, tools, retries, durations, and structured errors only—never private chain of thought or content bodies.', traceStatus: 'Status: {status}', tracePlanner: 'Planner: {planner}', traceRetries: 'Retries: {count}', traceEntry: '{node} · {type} · {status}', traceDuration: 'Duration {duration} ms', traceViolations: 'Issues: {codes}', noAgentTrace: 'Agent Trace is not available yet.',
      approvalEyebrow: 'Human decision required', approvalTitle: 'Review the Agent animation plan', approvalHelp: 'A decision resumes from the durable checkpoint. Edits repeat server-side schema, planning-rule, and safe-area validation.', approvalPlanLabel: 'Animation plan awaiting approval (JSON)', approvePlan: 'Approve and continue', editPlan: 'Validate edits and continue', rejectPlan: 'Reject task', approvalReasonFallback: 'This plan requires human confirmation.', approval_reason_policy_always: 'The current policy requires human review before rendering.', approval_reason_plan_repair_exhausted: 'Automatic repair is exhausted; submit an edited plan that passes validation.', approval_reason_media_relevance_unverified: 'External media relevance has not been confirmed by a reviewer.', approval_reason_external_media_rights_review: 'External media source and rights information requires human review.', approvalSubmittingTitle: 'Submitting approval', approvalSubmitting: 'Saving the human decision…', approvalResumingTitle: 'Resuming Agent', approvalResuming: 'Decision saved. The Agent will continue from the render node.', approvalFailedTitle: 'Approval failed', approvalFailed: 'Could not submit approval: {message}', rejectedTitle: 'Task rejected', event_rejected: 'A reviewer rejected the plan, so the task will not render.', awaitingApprovalTitle: 'Awaiting human approval', event_awaiting_approval: 'The Agent paused before render. Review the plan below.', event_approved: 'Plan approved and ready to resume from checkpoint.', event_edited: 'The edited plan passed validation and is ready to resume.', event_resumed: 'The Agent resumed from its durable checkpoint.',
      reviewTitle: 'External B-roll review', reviewNote: 'External material is an effect-validation prototype only. Review source, rights, accuracy, and suitability before commercial publication.', searchQueryLabel: 'Search query', searchPlaceholder: 'e.g. supermarket product', mediaTypeLabel: 'Type', imageKind: 'Image', videoKind: 'Video', searchButton: 'Search media', manualUrlLabel: 'Manual candidate URL', manualUrlPlaceholder: 'https://...', addManualButton: 'Add candidate', activityTitle: 'Task events', activityHelp: 'Events received by this browser session for creation, processing, rendering, and review.', replanNote: 'When transcript text changes, saving rebuilds the animation plan and removes stale media-derived data.', saveReview: 'Save edits and re-render',
      tasksEyebrow: 'On-device tasks', tasksTitle: 'Recent tasks', tasksDescription: 'Only real tasks created or restored by this browser are shown. No sample data is generated.', restoreTitle: 'Restore an existing task', restoreDescription: 'Enter a local task ID to reopen a task that still exists in the storage directory.', taskIdPlaceholder: 'Task ID', restoreButton: 'Restore task', restoringTask: 'Looking for the local task…', restoreFailed: 'Could not restore this task: {message}', noTasks: 'No recent tasks to show.', openTask: 'Open task', unknownFile: 'Filename not recorded', unavailableTask: 'Task is no longer available in local storage',
      settingsEyebrow: 'Platform settings', settingsTitle: 'Settings', settingsDescription: 'Only preferences backed by real local workspace capabilities are shown.', interfaceLanguage: 'Interface language', interfaceLanguageDescription: 'The language preference is stored in this browser and persists after refresh.', storageTitle: 'Local data', storageDescription: 'Uploads, the task database, transcripts, plans, and results are stored by FastAPI in the local storage directory. There is no cloud sync or account feature.', localStorageActive: 'Local storage enabled',
      statusPending: 'Pending', statusProcessing: 'Processing', statusRendering: 'Rendering', statusAwaitingApproval: 'Awaiting approval', statusRejected: 'Rejected', statusCompleted: 'Completed', statusFailed: 'Failed', statusCancelled: 'Cancelled', statusUnavailable: 'Unavailable',
      uploadingTitle: 'Uploading', uploading: 'Saving the video to the local task directory…', uploadFailedTitle: 'Upload failed', uploadFailed: 'Upload failed: {message}', taskCreatedTitle: 'Task created', event_created: 'Task created and waiting for local processing.', processingStatusTitle: 'Analyzing content', event_processing: 'Extracting audio, transcribing speech, and planning semantic visuals…', renderingStatusTitle: 'Compositing video', event_rendering: 'Rendering animation and compositing the final video…', event_review_rendering: 'Re-rendering the reviewed changes…', cancelRequestedTitle: 'Cancelling', event_cancel_requested: 'Cancellation requested. Waiting for the current safe step to finish.', completedTitle: 'Processing complete', completed: 'Completed: {seconds} seconds, {width} × {height}.', failedTitle: 'Task failed', event_failed: 'Task failed: {message}', cancelledTitle: 'Task cancelled', event_cancelled: 'Task cancelled. You can choose another source and start again.', cancelFailed: 'Could not cancel the task: {message}', taskLoadFailed: 'Could not load the task.', downloadFallback: '{message}\nThe video is downloadable, but the transcript and plan could not be loaded: {error}',
      validatingReviewTitle: 'Saving review', validatingReview: 'Validating edits and re-rendering…', reviewFailedTitle: 'Review failed', reviewFailed: 'Review re-render failed: {message}', replanned: 'The animation plan was rebuilt from the edited transcript; rendering now…', searchingTitle: 'Searching media', searching: 'Searching external B-roll candidates…', searchFailedTitle: 'Media search failed', searchFailed: 'Media search failed: {message}', foundCandidatesTitle: 'Candidates updated', foundCandidates: 'Found {count} candidates. Choose one, then save review edits.', manualFailed: 'Could not add the manual candidate: {message}', manualVisual: 'manual visual', unknownError: 'Unknown error', invalidJson: 'Invalid JSON: {message}',
      chooseTarget: 'Choose a target visual before replacing its B-roll.', selectedCandidateTitle: 'Candidate selected', selectedCandidate: 'Selected “{title}”. Saving the review will download and render the task-local copy.', brollDisabledTitle: 'Media updated', brollDisabled: 'B-roll disabled. Save review edits to re-render.', generatedOriginal: 'Generated original', pendingSelection: 'Pending selection or render', disabled: 'Disabled', disable: 'Disable', enable: 'Enable', useFor: 'Use for: {title}', useThis: 'Use this media', imageAsset: 'external image', videoAsset: 'external video', sourceLink: 'View source', noMediaVisuals: 'The current animation plan has no B-roll visuals.', noCandidates: 'No candidates have been searched or added yet.',
      event_created_label: 'Task created', event_processing_label: 'Content processing', event_rendering_label: 'Animation render', event_review_rendering_label: 'Review re-render', event_cancel_requested_label: 'Cancellation requested', event_agent_node_label: 'Agent node', event_awaiting_approval_label: 'Awaiting approval', event_approved_label: 'Plan approved', event_edited_label: 'Plan edited', event_resumed_label: 'Agent resumed', event_rejected_label: 'Plan rejected', event_completed_label: 'Processing complete', event_failed_label: 'Task failed', event_cancelled_label: 'Task cancelled', eventGeneric: 'Task status updated',
    },
  };

  translations['zh-CN'].settingPrivacyNote = '默认语音识别与渲染在本机完成；外部素材模式会访问所选素材服务，配置为 DeepSeek 时会把校正后转录与可选 Agent 指令发送给 DeepSeek。';
  translations.en.settingPrivacyNote = 'Speech recognition and rendering stay local by default; external media modes contact their provider, and configured DeepSeek planning sends the corrected transcript and optional Agent instruction to DeepSeek.';

  window.APP_I18N = translations;

  const NAV_ITEMS = [
    {sectionKey: 'navWorkspace', labelKey: 'navHome', route: '#/home', icon: 'grid'},
    {labelKey: 'navTools', route: '#/tools/semantic-video', icon: 'spark'},
    {sectionKey: 'navManagement', labelKey: 'navTasks', route: '#/tasks', icon: 'clock'},
    {labelKey: 'navSettings', route: '#/settings', icon: 'settings'},
  ];

  const TOOL_CATALOG = [
    {id: 'semantic-video', nameKey: 'semanticToolName', summaryKey: 'semanticToolSummary', icon: 'video', route: '#/tools/semantic-video', available: true},
    {id: 'script-assistant', nameKey: 'scriptToolName', summaryKey: 'scriptToolSummary', icon: 'file', available: false},
    {id: 'asset-organizer', nameKey: 'assetToolName', summaryKey: 'assetToolSummary', icon: 'grid', available: false},
  ];

  window.APP_TOOL_CATALOG = TOOL_CATALOG;

  const ROUTES = {
    '#/home': {view: 'home', titleKey: 'pageHomeTitle', descriptionKey: 'pageHomeDescription'},
    '#/tools/semantic-video': {view: 'semantic-video', titleKey: 'pageToolTitle', descriptionKey: 'pageToolDescription'},
    '#/tasks': {view: 'tasks', titleKey: 'pageTasksTitle', descriptionKey: 'pageTasksDescription'},
    '#/settings': {view: 'settings', titleKey: 'pageSettingsTitle', descriptionKey: 'pageSettingsDescription'},
  };

  const AGENT_NODES = ['upload_probe', 'audio_asr', 'correction', 'planning', 'validation', 'render', 'quality', 'complete'];

  const STORAGE_KEYS = {
    language: 'semantic-video-language',
    currentTask: 'semantic-video-current-task',
    recentTasks: 'semantic-video-recent-tasks',
  };

  const $ = (selector) => document.querySelector(selector);
  const refs = {
    sidebar: $('#sidebar'), navScrim: $('#nav-scrim'), menuButton: $('#menu-button'), primaryNav: $('#primary-nav'),
    pageTitle: $('#page-title'), pageDescription: $('#page-description'), languageSelect: $('#language-select'), settingsLanguage: $('#settings-language'),
    toolGrid: $('#tool-grid'), homeRecent: $('#home-recent'),
    form: $('#upload-form'), input: $('#video-file'), dropZone: $('#drop-zone'), fileName: $('#file-name'), workflowMode: $('#workflow-mode'), agentUploadFields: $('#agent-upload-fields'), directorInstruction: $('#director-instruction'), directorCount: $('#director-count'), approvalPolicy: $('#approval-policy'), processingProfile: $('#processing-profile'), uploadMediaProvider: $('#upload-media-provider'), uploadButton: $('#upload-button'),
    statusBanner: $('#status-banner'), statusTitle: $('#status-title'), status: $('#status'), uploadPanel: $('#upload-panel'), processingPanel: $('#processing-panel'),
    progressBar: $('#progress-bar'), progressTrack: $('#standard-progress-track'), progressPercent: $('#progress-percent'), standardProcessingStages: $('#standard-processing-stages'), activeTaskId: $('#active-task-id'), cancelTask: $('#cancel-task'), newTaskButton: $('#new-task-button'),
    agentExecutionPanel: $('#agent-execution-panel'), agentNodeList: $('#agent-node-list'), agentRetryBadge: $('#agent-retry-badge'), approvalPanel: $('#approval-panel'), approvalReasons: $('#approval-reasons'), approvalEvidence: $('#approval-evidence'), approvalPlan: $('#approval-plan'), approvalError: $('#approval-error'), approvePlan: $('#approve-plan'), editPlan: $('#edit-plan'), rejectPlan: $('#reject-plan'),
    result: $('#result'), preview: $('#preview'), download: $('#download'), resultDuration: $('#result-duration'), resultResolution: $('#result-resolution'), resultTaskId: $('#result-task-id'),
    transcript: $('#transcript'), plan: $('#plan'), saveReview: $('#save-review'), mediaList: $('#media-list'), mediaQuery: $('#media-query'), mediaKind: $('#media-kind'), searchMedia: $('#search-media'), manualMediaUrl: $('#manual-media-url'), addManualMedia: $('#add-manual-media'), candidateList: $('#candidate-list'), evidenceSummary: $('#evidence-summary'), evidenceList: $('#evidence-list'), eventList: $('#event-list'), agentTraceSummary: $('#agent-trace-summary'), agentTraceList: $('#agent-trace-list'),
    tasksList: $('#tasks-list'), restoreForm: $('#restore-form'), restoreTaskId: $('#restore-task-id'), restoreError: $('#restore-error'),
  };

  const state = {
    language: localStorage.getItem(STORAGE_KEYS.language) || 'zh-CN',
    taskId: localStorage.getItem(STORAGE_KEYS.currentTask) || null,
    currentTask: null,
    loadedTaskId: null,
    lastEventId: 0,
    events: [],
    candidates: [],
    agentNodes: Object.fromEntries(AGENT_NODES.map((node) => [node, {status: 'not_started'}])),
    agentTrace: null,
    evidence: null,
    approval: null,
    eventSource: null,
    statusKey: 'ready',
    statusParams: {},
    statusTitleKey: 'readyTitle',
    statusTone: 'neutral',
    activeTab: 'transcript',
    previewVersion: 'stored',
    taskRenderToken: 0,
    route: null,
  };

  const pretty = (value) => JSON.stringify(value, null, 2);
  const t = (key, params = {}) => {
    const template = translations[state.language]?.[key] ?? translations['zh-CN'][key] ?? key;
    return Object.entries(params).reduce((value, [name, replacement]) => value.replaceAll(`{${name}}`, String(replacement)), template);
  };

  function svgIcon(id) {
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('aria-hidden', 'true');
    const use = document.createElementNS('http://www.w3.org/2000/svg', 'use');
    use.setAttribute('href', `#icon-${id}`);
    svg.append(use);
    return svg;
  }

  function renderNavigation() {
    refs.primaryNav.replaceChildren();
    NAV_ITEMS.forEach((item) => {
      if (item.sectionKey) {
        const label = document.createElement('div');
        label.className = 'nav-section-label';
        label.textContent = t(item.sectionKey);
        refs.primaryNav.append(label);
      }
      const link = document.createElement('a');
      link.className = 'nav-link';
      link.href = item.route;
      link.dataset.route = item.route;
      link.append(svgIcon(item.icon));
      const text = document.createElement('span');
      text.textContent = t(item.labelKey);
      link.append(text);
      refs.primaryNav.append(link);
    });
  }

  function renderToolCatalog() {
    refs.toolGrid.replaceChildren();
    TOOL_CATALOG.forEach((tool) => {
      const card = document.createElement(tool.available ? 'a' : 'article');
      card.className = `tool-card ${tool.available ? 'is-available' : 'is-planned'}`;
      if (tool.available) card.href = tool.route;
      else card.setAttribute('aria-disabled', 'true');
      const top = document.createElement('div');
      top.className = 'tool-card-top';
      const icon = document.createElement('span');
      icon.className = `feature-icon ${tool.available ? 'feature-icon-accent' : ''}`;
      icon.append(svgIcon(tool.icon));
      const badge = document.createElement('span');
      badge.className = 'tool-badge';
      badge.textContent = t(tool.available ? 'available' : 'planned');
      top.append(icon, badge);
      const title = document.createElement('h3');
      title.textContent = t(tool.nameKey);
      const summary = document.createElement('p');
      summary.textContent = t(tool.summaryKey);
      const footer = document.createElement('div');
      footer.className = 'tool-card-footer';
      const footerText = document.createElement('span');
      footerText.textContent = t(tool.available ? 'openTool' : 'notAvailable');
      footer.append(footerText, svgIcon(tool.available ? 'arrow' : 'clock'));
      card.append(top, title, summary, footer);
      refs.toolGrid.append(card);
    });
  }

  function setStatus(key, params = {}, options = {}) {
    state.statusKey = key;
    state.statusParams = params;
    state.statusTitleKey = options.titleKey || state.statusTitleKey || 'readyTitle';
    state.statusTone = options.tone || 'neutral';
    refs.statusTitle.textContent = t(state.statusTitleKey);
    refs.status.textContent = t(key, params);
    refs.statusBanner.dataset.tone = state.statusTone;
  }

  function isAgentTask() {
    return state.currentTask?.workflow_mode === 'agent';
  }

  function updateDirectorCount() {
    refs.directorCount.textContent = `${refs.directorInstruction.value.length} / 2000`;
  }

  function updateWorkflowModeUI(mode = refs.workflowMode.value) {
    const agent = mode === 'agent';
    refs.agentUploadFields.hidden = !agent;
    refs.progressPercent.hidden = agent;
    refs.progressTrack.hidden = agent;
    refs.standardProcessingStages.hidden = agent;
    refs.agentExecutionPanel.hidden = !agent || !state.taskId;
    document.querySelectorAll('[data-tab="agent"], [data-tab="evidence"]').forEach((tab) => { tab.hidden = !agent; });
    if (!agent) document.querySelectorAll('[data-tab-panel="agent"], [data-tab-panel="evidence"]').forEach((panel) => { panel.hidden = true; });
    if (!agent && ['agent', 'evidence'].includes(state.activeTab)) selectTab('transcript');
    if (agent) renderAgentExecution();
  }

  function resetAgentState() {
    state.agentNodes = Object.fromEntries(AGENT_NODES.map((node) => [node, {status: 'not_started'}]));
    state.agentTrace = null;
    state.evidence = null;
    state.approval = null;
    refs.approvalPanel.hidden = true;
    refs.approvalPlan.value = '';
    refs.approvalError.textContent = '';
    refs.approvalEvidence.replaceChildren();
    refs.evidenceSummary.replaceChildren();
    refs.evidenceList.replaceChildren();
    renderAgentExecution();
    renderAgentTrace();
  }

  function nodeStatusText(status) {
    const key = {not_started: 'nodeStatusNotStarted', started: 'nodeStatusStarted', resumed: 'nodeStatusResumed', completed: 'nodeStatusCompleted', failed: 'nodeStatusFailed'}[status] || 'nodeStatusNotStarted';
    return t(key);
  }

  function renderAgentExecution() {
    refs.agentNodeList.replaceChildren();
    AGENT_NODES.forEach((node) => {
      const detail = state.agentNodes[node] || {status: 'not_started'};
      const item = document.createElement('li');
      item.dataset.status = detail.status;
      const title = document.createElement('strong');
      title.textContent = t(`node_${node}`);
      const status = document.createElement('small');
      status.textContent = detail.error_category ? `${nodeStatusText(detail.status)} · ${detail.error_category}` : nodeStatusText(detail.status);
      item.append(title, status);
      refs.agentNodeList.append(item);
    });
    const retries = Number(state.agentTrace?.summary?.retry_count || 0);
    refs.agentRetryBadge.textContent = t('agentRetries', {count: retries});
    refs.agentRetryBadge.dataset.status = retries ? 'rendering' : 'pending';
  }

  function renderAgentTrace() {
    refs.agentTraceSummary.replaceChildren();
    refs.agentTraceList.replaceChildren();
    const trace = state.agentTrace;
    if (!trace) {
      const item = document.createElement('li');
      const copy = document.createElement('div');
      copy.textContent = t('noAgentTrace');
      item.append(document.createElement('span'), copy);
      refs.agentTraceList.append(item);
      return;
    }
    const chips = [
      t('traceStatus', {status: trace.summary?.status || 'running'}),
      t('traceRetries', {count: trace.summary?.retry_count || 0}),
      t('tracePlanner', {planner: trace.planner?.planner_id || trace.planner?.model_id || '—'}),
    ];
    chips.forEach((value) => {
      const chip = document.createElement('span');
      chip.className = 'trace-chip';
      chip.textContent = value;
      refs.agentTraceSummary.append(chip);
    });
    (trace.entries || []).forEach((entry) => {
      const item = document.createElement('li');
      const copy = document.createElement('div');
      const title = document.createElement('strong');
      title.textContent = t('traceEntry', {node: t(`node_${entry.node}`), type: entry.event_type, status: entry.status});
      copy.append(title);
      if (entry.duration_ms !== undefined) {
        const duration = document.createElement('small');
        duration.textContent = t('traceDuration', {duration: entry.duration_ms});
        copy.append(duration);
      }
      const codes = (entry.violations || []).map((item) => item.code).filter(Boolean);
      if (codes.length) {
        const violations = document.createElement('small');
        violations.textContent = t('traceViolations', {codes: [...new Set(codes)].join(', ')});
        copy.append(violations);
      }
      item.append(document.createElement('span'), copy);
      refs.agentTraceList.append(item);
    });
  }

  async function loadAgentTrace(id) {
    const response = await fetch(`/api/videos/${encodeURIComponent(id)}/agent-trace`);
    if (response.status === 404) return;
    if (!response.ok) throw new Error(await responseError(response));
    if (state.taskId !== id) return;
    state.agentTrace = await response.json();
    renderAgentExecution();
    renderAgentTrace();
  }

  function renderEvidenceCards(container, payload) {
    container.replaceChildren();
    if (!payload?.items?.length) {
      const empty = document.createElement('p');
      empty.className = 'evidence-empty';
      empty.textContent = t('evidenceEmpty');
      container.append(empty);
      return;
    }
    payload.items.forEach((evidence) => {
      const card = document.createElement('article');
      card.className = 'evidence-card';
      card.dataset.status = evidence.status || 'missing';
      const heading = document.createElement('div');
      heading.className = 'evidence-card-heading';
      const source = document.createElement('strong');
      source.textContent = t('evidenceSource', {source: evidence.source || '—'});
      const status = document.createElement('span');
      status.className = 'status-pill';
      status.dataset.status = evidence.status === 'valid' ? 'completed' : 'failed';
      status.textContent = t('evidenceStatus', {status: evidence.status || 'missing'});
      heading.append(source, status);
      const excerpt = document.createElement('p');
      excerpt.textContent = evidence.excerpt || '';
      const metadata = document.createElement('small');
      metadata.textContent = `${evidence.chunk_id} · ${t('evidenceCitedBy', {animations: (evidence.cited_by || []).join(', ') || '—'})}`;
      card.append(heading, excerpt, metadata);
      container.append(card);
    });
  }

  function renderEvidence() {
    refs.evidenceSummary.replaceChildren();
    const payload = state.evidence;
    if (payload) {
      const chip = document.createElement('span');
      chip.className = 'trace-chip';
      chip.textContent = t(payload.valid ? 'evidenceValid' : 'evidenceInvalid', {count: payload.count || 0});
      refs.evidenceSummary.append(chip);
    }
    renderEvidenceCards(refs.evidenceList, payload);
    if (!refs.approvalPanel.hidden) renderEvidenceCards(refs.approvalEvidence, payload);
  }

  async function loadEvidence(id) {
    const response = await fetch(`/api/videos/${encodeURIComponent(id)}/evidence`);
    if (response.status === 404) return;
    if (!response.ok) throw new Error(await responseError(response));
    if (state.taskId !== id) return;
    state.evidence = await response.json();
    renderEvidence();
  }

  function setApprovalButtonsDisabled(disabled) {
    [refs.approvePlan, refs.editPlan, refs.rejectPlan].forEach((button) => { button.disabled = disabled; });
  }

  function renderApproval(approval) {
    state.approval = approval;
    refs.approvalReasons.replaceChildren();
    (approval.reasons || []).forEach((reason) => {
      const item = document.createElement('div');
      item.className = 'approval-reason';
      const code = document.createElement('strong');
      code.textContent = reason.code || 'approval_required';
      const message = document.createElement('span');
      const reasonKey = `approval_reason_${reason.code}`;
      message.textContent = translations[state.language][reasonKey] ? t(reasonKey) : (reason.message || t('approvalReasonFallback'));
      item.append(code, message);
      refs.approvalReasons.append(item);
    });
    refs.approvalPlan.value = pretty(approval.candidate_plan || state.currentTask?.plan || {});
    refs.approvePlan.disabled = !approval.candidate_plan;
    refs.editPlan.disabled = false;
    refs.rejectPlan.disabled = false;
    refs.approvalError.textContent = '';
    refs.approvalPanel.hidden = approval.status !== 'pending';
  }

  async function loadApproval(id) {
    const response = await fetch(`/api/videos/${encodeURIComponent(id)}/approval`);
    if (!response.ok) throw new Error(await responseError(response));
    const approval = await response.json();
    if (state.taskId === id) {
      renderApproval(approval);
      await loadEvidence(id).catch(() => {});
    }
    return approval;
  }

  async function submitApproval(action) {
    if (!state.taskId) return;
    refs.approvalError.textContent = '';
    setApprovalButtonsDisabled(true);
    setStatus('approvalSubmitting', {}, {titleKey: 'approvalSubmittingTitle', tone: 'info'});
    const options = {method: 'POST'};
    if (action === 'edit') {
      try {
        options.headers = {'Content-Type': 'application/json'};
        options.body = JSON.stringify({plan: JSON.parse(refs.approvalPlan.value)});
      } catch (error) {
        refs.approvalError.textContent = t('invalidJson', {message: error.message});
        setStatus('approvalFailed', {message: error.message}, {titleKey: 'approvalFailedTitle', tone: 'error'});
        setApprovalButtonsDisabled(false);
        return;
      }
    }
    try {
      const response = await fetch(`/api/videos/${encodeURIComponent(state.taskId)}/approval/${action}`, options);
      if (!response.ok) throw new Error(await responseError(response));
      state.approval = {...(state.approval || {}), status: action === 'approve' ? 'approved' : action === 'edit' ? 'edited' : 'rejected'};
      refs.approvalPanel.hidden = true;
      setStatus(action === 'reject' ? 'event_rejected' : 'approvalResuming', {}, {titleKey: action === 'reject' ? 'rejectedTitle' : 'approvalResumingTitle', tone: action === 'reject' ? 'warning' : 'info'});
    } catch (error) {
      refs.approvalError.textContent = t('approvalFailed', {message: error.message});
      setStatus('approvalFailed', {message: error.message}, {titleKey: 'approvalFailedTitle', tone: 'error'});
      setApprovalButtonsDisabled(false);
    }
  }

  function applyLanguage(language) {
    state.language = translations[language] ? language : 'zh-CN';
    localStorage.setItem(STORAGE_KEYS.language, state.language);
    document.documentElement.lang = state.language;
    document.title = t('documentTitle');
    refs.languageSelect.value = state.language;
    refs.settingsLanguage.value = state.language;
    document.querySelectorAll('[data-i18n]').forEach((element) => { element.textContent = t(element.dataset.i18n); });
    document.querySelectorAll('[data-i18n-placeholder]').forEach((element) => { element.placeholder = t(element.dataset.i18nPlaceholder); });
    document.querySelectorAll('[data-i18n-aria-label]').forEach((element) => { element.setAttribute('aria-label', t(element.dataset.i18nAriaLabel)); });
    renderNavigation();
    renderToolCatalog();
    updateFileName();
    setStatus(state.statusKey, state.statusParams, {titleKey: state.statusTitleKey, tone: state.statusTone});
    renderRoute({loadTask: false});
    renderHomeRecent();
    renderEventList();
    updateWorkflowModeUI(state.currentTask?.workflow_mode || refs.workflowMode.value);
    updateDirectorCount();
    renderAgentExecution();
    renderAgentTrace();
    renderEvidence();
    if (refs.plan.value.trim()) {
      try { renderMediaReview(currentPlan(), state.candidates); } catch (_error) { /* The editor can temporarily contain invalid JSON. */ }
    }
  }

  function normalizedRoute() {
    return ROUTES[window.location.hash] ? window.location.hash : '#/home';
  }

  function closeNavigation() {
    document.body.classList.remove('nav-open');
    refs.menuButton.setAttribute('aria-expanded', 'false');
    refs.navScrim.tabIndex = -1;
  }

  function renderRoute(options = {loadTask: true}) {
    const routeKey = normalizedRoute();
    const route = ROUTES[routeKey];
    const routeChanged = state.route !== routeKey;
    state.route = routeKey;
    document.querySelectorAll('[data-route-view]').forEach((view) => { view.hidden = view.dataset.routeView !== route.view; });
    refs.pageTitle.textContent = t(route.titleKey);
    refs.pageDescription.textContent = t(route.descriptionKey);
    refs.primaryNav.querySelectorAll('[data-route]').forEach((link) => {
      if (link.dataset.route === routeKey) link.setAttribute('aria-current', 'page');
      else link.removeAttribute('aria-current');
    });
    closeNavigation();
    if (routeChanged) window.scrollTo({top: 0, left: 0});
    if (route.view === 'home') renderHomeRecent();
    if (route.view === 'tasks') renderRecentTasks();
    if (route.view === 'semantic-video' && options.loadTask !== false && state.taskId && state.loadedTaskId !== state.taskId) {
      loadTask(state.taskId).catch(handleTaskLoadFailure);
    }
  }

  function readRecentTasks() {
    try {
      const parsed = JSON.parse(localStorage.getItem(STORAGE_KEYS.recentTasks) || '[]');
      return Array.isArray(parsed) ? parsed.filter((item) => item && typeof item.id === 'string').slice(0, 8) : [];
    } catch (_error) {
      return [];
    }
  }

  function saveRecentTasks(tasks) {
    localStorage.setItem(STORAGE_KEYS.recentTasks, JSON.stringify(tasks.slice(0, 8)));
  }

  function rememberTask(id, updates = {}) {
    const existing = readRecentTasks();
    const previous = existing.find((item) => item.id === id) || {};
    const entry = {...previous, id, createdAt: previous.createdAt || new Date().toISOString(), ...updates};
    saveRecentTasks([entry, ...existing.filter((item) => item.id !== id)]);
    renderHomeRecent();
  }

  function formatDate(value) {
    try { return new Intl.DateTimeFormat(state.language, {month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'}).format(new Date(value)); }
    catch (_error) { return ''; }
  }

  function statusText(status) {
    const key = {
      pending: 'statusPending', processing: 'statusProcessing', rendering: 'statusRendering', awaiting_approval: 'statusAwaitingApproval', rejected: 'statusRejected', completed: 'statusCompleted', failed: 'statusFailed', cancelled: 'statusCancelled', unavailable: 'statusUnavailable',
    }[status] || 'statusPending';
    return t(key);
  }

  function renderHomeRecent() {
    const recent = readRecentTasks();
    refs.homeRecent.replaceChildren();
    if (!recent.length) {
      const empty = document.createElement('div');
      empty.className = 'empty-state';
      empty.append(svgIcon('clock'));
      const copy = document.createElement('p');
      copy.textContent = t('noRecentTask');
      empty.append(copy);
      refs.homeRecent.append(empty);
      return;
    }
    const task = recent[0];
    const card = document.createElement('div');
    card.className = 'quick-task';
    const copy = document.createElement('div');
    const title = document.createElement('h3');
    title.textContent = task.name || t('recentSemanticTask');
    const detail = document.createElement('p');
    detail.textContent = `${statusText(task.status)} · ${formatDate(task.createdAt)} · ${task.id}`;
    copy.append(title, detail);
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'button button-secondary';
    button.textContent = t('continueTask');
    button.addEventListener('click', () => openTask(task.id));
    card.append(copy, button);
    refs.homeRecent.append(card);
  }

  async function renderRecentTasks() {
    const token = ++state.taskRenderToken;
    const recent = readRecentTasks();
    refs.tasksList.replaceChildren();
    if (!recent.length) {
      renderTasksEmpty();
      return;
    }
    const results = await Promise.all(recent.map(async (entry) => {
      try {
        const response = await fetch(`/api/videos/${encodeURIComponent(entry.id)}`);
        if (!response.ok) return {...entry, status: 'unavailable'};
        const task = await response.json();
        return {...entry, status: task.status, metadata: task.metadata};
      } catch (_error) {
        return {...entry, status: 'unavailable'};
      }
    }));
    if (token !== state.taskRenderToken || normalizedRoute() !== '#/tasks') return;
    results.forEach(renderTaskCard);
  }

  function renderTasksEmpty() {
    const empty = document.createElement('div');
    empty.className = 'empty-state';
    empty.append(svgIcon('clock'));
    const copy = document.createElement('p');
    copy.textContent = t('noTasks');
    empty.append(copy);
    refs.tasksList.append(empty);
  }

  function renderTaskCard(task) {
    const card = document.createElement('article');
    card.className = 'task-card';
    const icon = document.createElement('span');
    icon.className = 'task-card-icon';
    icon.append(svgIcon('video'));
    const copy = document.createElement('div');
    const title = document.createElement('h3');
    title.textContent = task.name || t('recentSemanticTask');
    const id = document.createElement('p');
    id.textContent = task.status === 'unavailable' ? t('unavailableTask') : task.id;
    const meta = document.createElement('div');
    meta.className = 'task-card-meta';
    const pill = document.createElement('span');
    pill.className = 'status-pill';
    pill.dataset.status = task.status || 'pending';
    pill.textContent = statusText(task.status);
    const date = document.createElement('span');
    date.textContent = formatDate(task.createdAt);
    meta.append(pill, date);
    copy.append(title, id, meta);
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'button button-secondary button-small';
    button.textContent = t('openTask');
    button.disabled = task.status === 'unavailable';
    button.addEventListener('click', () => openTask(task.id));
    card.append(icon, copy, button);
    refs.tasksList.append(card);
  }

  function openTask(id) {
    closeEventSource();
    resetAgentState();
    state.taskId = id;
    state.loadedTaskId = null;
    state.currentTask = null;
    state.lastEventId = 0;
    state.events = [];
    localStorage.setItem(STORAGE_KEYS.currentTask, id);
    if (window.location.hash !== '#/tools/semantic-video') window.location.hash = '#/tools/semantic-video';
    else renderRoute();
  }

  function updateFileName() {
    refs.fileName.textContent = refs.input.files?.[0]?.name || t('noFileChosen');
  }

  function setWorkflowStage(stage, options = {}) {
    document.querySelectorAll('.workflow-steps li').forEach((item) => {
      const order = {upload: 0, processing: 1, review: 2};
      const itemOrder = order[item.dataset.step];
      const stageOrder = order[stage];
      item.classList.toggle('is-complete', itemOrder < stageOrder);
      item.classList.toggle('is-current', itemOrder === stageOrder);
    });
    if (stage === 'upload') {
      refs.uploadPanel.hidden = false;
      refs.processingPanel.hidden = true;
      refs.result.hidden = true;
    } else if (stage === 'processing') {
      refs.uploadPanel.hidden = true;
      refs.processingPanel.hidden = false;
      if (!options.preserveResult) refs.result.hidden = true;
    } else {
      refs.uploadPanel.hidden = true;
      refs.processingPanel.hidden = true;
      refs.result.hidden = false;
    }
  }

  const PROCESS_PROGRESS = {created: 12, processing: 42, rendering: 76, review_rendering: 76, completed: 100, cancel_requested: 80};
  function updateProgress(eventType) {
    const progress = PROCESS_PROGRESS[eventType] ?? 8;
    refs.progressBar.style.width = `${progress}%`;
    refs.progressPercent.textContent = `${progress}%`;
    refs.progressTrack.setAttribute('aria-valuenow', String(progress));
    const order = {created: 0, processing: 1, rendering: 2, review_rendering: 2, completed: 3, cancel_requested: 2};
    const current = order[eventType] ?? 0;
    document.querySelectorAll('[data-process-step]').forEach((item, index) => {
      item.classList.toggle('is-complete', index < current || eventType === 'completed');
      item.classList.toggle('is-active', index === current && eventType !== 'completed');
    });
  }

  function eventLabel(type) {
    return t(`event_${type}_label`) === `event_${type}_label` ? t('eventGeneric') : t(`event_${type}_label`);
  }

  function recordEvent(detail) {
    if (detail.id && state.events.some((event) => event.id === detail.id)) return;
    state.events.push(detail);
    state.events = state.events.slice(-30);
    renderEventList();
  }

  function renderEventList() {
    refs.eventList.replaceChildren();
    if (!state.events.length) {
      const item = document.createElement('li');
      const spacer = document.createElement('span');
      const copy = document.createElement('div');
      const title = document.createElement('strong');
      title.textContent = t('readyTitle');
      const description = document.createElement('p');
      description.textContent = t('ready');
      copy.append(title, description);
      item.append(spacer, copy);
      refs.eventList.append(item);
      return;
    }
    [...state.events].reverse().forEach((event) => {
      const item = document.createElement('li');
      const copy = document.createElement('div');
      const title = document.createElement('strong');
      title.textContent = eventLabel(event.type);
      const description = document.createElement('p');
      const statusKey = `event_${event.type}`;
      if (event.type === 'agent_node' && event.payload?.node) {
        description.textContent = `${t(`node_${event.payload.node}`)} · ${nodeStatusText(event.payload.status)}`;
      } else {
        description.textContent = translations[state.language][statusKey] ? t(statusKey, {message: event.message || t('unknownError')}) : (event.message || t('eventGeneric'));
      }
      copy.append(title, description);
      const time = document.createElement('time');
      time.textContent = event.created_at ? formatDate(event.created_at) : '';
      item.append(document.createElement('span'), copy, time);
      refs.eventList.append(item);
    });
  }

  function closeEventSource() {
    if (state.eventSource) state.eventSource.close();
    state.eventSource = null;
  }

  function watchTask(id, options = {}) {
    closeEventSource();
    const source = new EventSource(`/api/videos/${encodeURIComponent(id)}/events?after_event_id=${state.lastEventId}`);
    state.eventSource = source;
    const readEvent = (event, type) => {
      const detail = JSON.parse(event.data);
      detail.type = detail.type || type;
      state.lastEventId = Math.max(state.lastEventId, detail.id || 0);
      recordEvent(detail);
      if (!isAgentTask()) updateProgress(type);
      return detail;
    };
    ['created', 'processing', 'rendering', 'review_rendering', 'cancel_requested'].forEach((name) => {
      source.addEventListener(name, (event) => {
        readEvent(event, name);
        if (options.terminalReplay) return;
        const preserveResult = name === 'review_rendering' && !refs.result.hidden;
        setWorkflowStage('processing', {preserveResult});
        const config = {
          created: ['event_created', 'taskCreatedTitle'], processing: ['event_processing', 'processingStatusTitle'], rendering: ['event_rendering', 'renderingStatusTitle'], review_rendering: ['event_review_rendering', 'renderingStatusTitle'], cancel_requested: ['event_cancel_requested', 'cancelRequestedTitle'],
        }[name];
        setStatus(config[0], {}, {titleKey: config[1], tone: name === 'cancel_requested' ? 'warning' : 'info'});
        rememberTask(id, {status: name === 'review_rendering' ? 'rendering' : name});
      });
    });
    source.addEventListener('agent_node', (event) => {
      const detail = readEvent(event, 'agent_node');
      const payload = detail.payload || {};
      if (AGENT_NODES.includes(payload.node)) {
        state.agentNodes[payload.node] = {
          status: payload.status || 'started',
          checkpoint_version: payload.checkpoint_version,
          error_category: payload.error_category,
        };
        renderAgentExecution();
      }
      if (['planning', 'validation'].includes(payload.node) && payload.status === 'completed') {
        loadAgentTrace(id).catch(() => {});
      }
    });
    source.addEventListener('awaiting_approval', (event) => {
      readEvent(event, 'awaiting_approval');
      if (options.terminalReplay) return;
      setWorkflowStage('processing');
      setStatus('event_awaiting_approval', {}, {titleKey: 'awaitingApprovalTitle', tone: 'warning'});
      rememberTask(id, {status: 'awaiting_approval', workflowMode: 'agent'});
      loadApproval(id).catch((error) => setStatus('approvalFailed', {message: error.message}, {titleKey: 'approvalFailedTitle', tone: 'error'}));
      loadAgentTrace(id).catch(() => {});
    });
    ['approved', 'edited', 'resumed'].forEach((name) => {
      source.addEventListener(name, (event) => {
        readEvent(event, name);
        if (options.terminalReplay) return;
        refs.approvalPanel.hidden = true;
        setWorkflowStage('processing');
        setStatus(name === 'resumed' ? 'event_resumed' : `event_${name}`, {}, {titleKey: 'approvalResumingTitle', tone: 'info'});
      });
    });
    source.addEventListener('rejected', (event) => {
      const detail = readEvent(event, 'rejected');
      closeEventSource();
      refs.approvalPanel.hidden = true;
      state.currentTask = {...(state.currentTask || {}), status: 'rejected'};
      setWorkflowStage('processing');
      setStatus('event_rejected', {message: detail.message || t('unknownError')}, {titleKey: 'rejectedTitle', tone: 'warning'});
      rememberTask(id, {status: 'rejected', workflowMode: 'agent'});
      loadAgentTrace(id).catch(() => {});
    });
    source.addEventListener('completed', async (event) => {
      const detail = readEvent(event, 'completed');
      closeEventSource();
      if (options.terminalReplay) {
        await loadAgentTrace(id).catch(() => {});
        return;
      }
      try { await loadTask(id, detail.id || state.lastEventId); }
      catch (error) {
        setStatus('downloadFallback', {message: detail.message || t('completedTitle'), error: error.message}, {titleKey: 'completedTitle', tone: 'warning'});
      }
    });
    ['failed', 'cancelled'].forEach((name) => {
      source.addEventListener(name, (event) => {
        const detail = readEvent(event, name);
        closeEventSource();
        state.currentTask = {...(state.currentTask || {}), status: name};
        setWorkflowStage('upload');
        setStatus(`event_${name}`, {message: detail.message || t('unknownError')}, {titleKey: name === 'failed' ? 'failedTitle' : 'cancelledTitle', tone: name === 'failed' ? 'error' : 'warning'});
        rememberTask(id, {status: name});
        if (isAgentTask()) loadAgentTrace(id).catch(() => {});
      });
    });
  }

  function showResult(id, version) {
    const sourceVersion = version || 'stored';
    const sourceKey = `${id}:${sourceVersion}`;
    if (refs.preview.dataset.sourceKey !== sourceKey) {
      refs.preview.src = `/api/videos/${encodeURIComponent(id)}/download?preview=true&version=${encodeURIComponent(sourceVersion)}`;
      refs.preview.dataset.sourceKey = sourceKey;
    }
    refs.download.href = `/api/videos/${encodeURIComponent(id)}/download`;
    setWorkflowStage('review');
  }

  async function loadTask(id, version = state.previewVersion) {
    const response = await fetch(`/api/videos/${encodeURIComponent(id)}`);
    if (!response.ok) throw new Error(await responseError(response));
    const task = await response.json();
    if (state.taskId !== id) return task;
    state.currentTask = task;
    state.loadedTaskId = id;
    refs.workflowMode.value = task.workflow_mode || 'standard';
    refs.directorInstruction.value = task.director_instruction || '';
    refs.approvalPolicy.value = task.approval_policy || 'never';
    updateDirectorCount();
    updateWorkflowModeUI(task.workflow_mode || 'standard');
    refs.activeTaskId.textContent = id;
    rememberTask(id, {status: task.status, metadata: task.metadata, workflowMode: task.workflow_mode});
    if (task.status === 'completed') {
      refs.transcript.value = pretty(task.transcript);
      refs.plan.value = pretty(task.plan);
      state.previewVersion = version || 'stored';
      showResult(id, state.previewVersion);
      refs.resultDuration.textContent = `${Number(task.metadata.duration_seconds).toFixed(2)} ${t('secondsUnit')}`;
      refs.resultResolution.textContent = `${task.metadata.width} × ${task.metadata.height}`;
      refs.resultTaskId.textContent = id;
      setStatus('completed', {seconds: Number(task.metadata.duration_seconds).toFixed(2), width: task.metadata.width, height: task.metadata.height}, {titleKey: 'completedTitle', tone: 'success'});
      updateProgress('completed');
      await loadMediaReview(id);
      if (task.workflow_mode === 'agent') {
        await loadEvidence(id).catch(() => {});
        await loadAgentTrace(id).catch(() => {});
        if (!state.events.length) watchTask(id, {terminalReplay: true});
      }
    } else if (task.status === 'awaiting_approval') {
      setWorkflowStage('processing');
      setStatus('event_awaiting_approval', {}, {titleKey: 'awaitingApprovalTitle', tone: 'warning'});
      await loadApproval(id);
      await loadEvidence(id).catch(() => {});
      await loadAgentTrace(id).catch(() => {});
      watchTask(id);
    } else if (['pending', 'processing', 'rendering'].includes(task.status)) {
      setWorkflowStage('processing');
      const eventType = task.status === 'pending' ? 'created' : task.status;
      updateProgress(eventType);
      const config = task.status === 'rendering' ? ['event_rendering', 'renderingStatusTitle'] : task.status === 'processing' ? ['event_processing', 'processingStatusTitle'] : ['event_created', 'taskCreatedTitle'];
      setStatus(config[0], {}, {titleKey: config[1], tone: 'info'});
      watchTask(id);
    } else if (task.status === 'rejected') {
      setWorkflowStage('processing');
      refs.approvalPanel.hidden = true;
      setStatus('event_rejected', {}, {titleKey: 'rejectedTitle', tone: 'warning'});
      await loadAgentTrace(id).catch(() => {});
      if (!state.events.length) watchTask(id, {terminalReplay: true});
    } else {
      setWorkflowStage('upload');
      const failed = task.status === 'failed';
      setStatus(failed ? 'event_failed' : 'event_cancelled', {message: task.error || t('unknownError')}, {titleKey: failed ? 'failedTitle' : 'cancelledTitle', tone: failed ? 'error' : 'warning'});
      if (task.workflow_mode === 'agent') await loadAgentTrace(id).catch(() => {});
    }
    return task;
  }

  function handleTaskLoadFailure(error) {
    state.taskId = null;
    state.currentTask = null;
    state.loadedTaskId = null;
    localStorage.removeItem(STORAGE_KEYS.currentTask);
    setWorkflowStage('upload');
    setStatus('taskLoadFailed', {message: error.message}, {titleKey: 'failedTitle', tone: 'error'});
  }

  async function responseError(response) {
    try {
      const payload = await response.json();
      return payload.detail || payload.error?.message || t('unknownError');
    } catch (_error) {
      return `${response.status} ${response.statusText}`.trim();
    }
  }

  function currentPlan() {
    return JSON.parse(refs.plan.value);
  }

  function writePlan(value) {
    refs.plan.value = pretty(value);
  }

  function findMediaAnimation(plan, assetId) {
    return plan.animations.find((item) => item.type === 'media_visual' && item.parameters.asset_id === assetId);
  }

  function useCandidate(candidate, targetAssetId) {
    try {
      const editable = currentPlan();
      const animation = findMediaAnimation(editable, targetAssetId);
      if (!animation) { setStatus('chooseTarget', {}, {titleKey: 'reviewFailedTitle', tone: 'warning'}); return; }
      animation.parameters.selected_candidate_id = candidate.id;
      animation.parameters.enabled = true;
      editable.media_assets = (editable.media_assets || []).filter((asset) => asset.asset_id !== animation.parameters.asset_id);
      editable.media_placements = (editable.media_placements || []).filter((item) => item.animation_id !== animation.id);
      writePlan(editable);
      renderMediaReview(editable, []);
      setStatus('selectedCandidate', {title: candidate.title}, {titleKey: 'selectedCandidateTitle', tone: 'success'});
    } catch (error) {
      setStatus('invalidJson', {message: error.message}, {titleKey: 'reviewFailedTitle', tone: 'error'});
    }
  }

  function toggleMedia(assetId, enabled) {
    try {
      const editable = currentPlan();
      const animation = findMediaAnimation(editable, assetId);
      if (!animation) return;
      animation.parameters.enabled = enabled;
      if (!enabled) {
        editable.media_assets = (editable.media_assets || []).filter((asset) => asset.asset_id !== assetId);
        editable.media_placements = (editable.media_placements || []).filter((item) => item.animation_id !== animation.id);
      }
      writePlan(editable);
      renderMediaReview(editable, []);
      setStatus('brollDisabled', {}, {titleKey: 'brollDisabledTitle', tone: 'warning'});
    } catch (error) {
      setStatus('invalidJson', {message: error.message}, {titleKey: 'reviewFailedTitle', tone: 'error'});
    }
  }

  function sourceSummary(card, audit, fallback) {
    const line = document.createElement('small');
    if (!audit) { line.textContent = fallback; card.append(line); return; }
    line.textContent = `${audit.provider} · ${audit.search_query} · ${audit.license}`;
    card.append(line);
    if (audit.source_url) {
      const source = document.createElement('small');
      const link = document.createElement('a');
      link.href = audit.source_url;
      link.target = '_blank';
      link.rel = 'noreferrer';
      link.textContent = t('sourceLink');
      source.append(link);
      card.append(source);
    }
  }

  function renderMediaReview(editablePlan, candidates) {
    state.candidates = candidates;
    const visuals = (editablePlan.animations || []).filter((item) => item.type === 'media_visual');
    const audits = new Map((editablePlan.media_assets || []).map((asset) => [asset.asset_id, asset]));
    refs.mediaList.replaceChildren();
    if (!visuals.length) {
      const empty = document.createElement('div');
      empty.className = 'empty-state';
      const copy = document.createElement('p');
      copy.textContent = t('noMediaVisuals');
      empty.append(copy);
      refs.mediaList.append(empty);
    }
    visuals.forEach((animation) => {
      const audit = audits.get(animation.parameters.asset_id);
      const card = document.createElement('article');
      card.className = 'media-card';
      const header = document.createElement('div');
      header.className = 'media-card-header';
      const copy = document.createElement('div');
      const title = document.createElement('strong');
      title.textContent = `${animation.parameters.title} · ${animation.start_ms}–${animation.end_ms} ms`;
      copy.append(title);
      sourceSummary(copy, audit, animation.parameters.enabled ? t('pendingSelection') : t('disabled'));
      const toggle = document.createElement('button');
      toggle.type = 'button';
      toggle.className = 'button button-secondary button-small';
      toggle.textContent = animation.parameters.enabled ? t('disable') : t('enable');
      toggle.addEventListener('click', () => toggleMedia(animation.parameters.asset_id, !animation.parameters.enabled));
      header.append(copy, toggle);
      card.append(header);
      refs.mediaList.append(card);
    });
    refs.candidateList.replaceChildren();
    if (!candidates.length) {
      const empty = document.createElement('div');
      empty.className = 'empty-state';
      const copy = document.createElement('p');
      copy.textContent = t('noCandidates');
      empty.append(copy);
      refs.candidateList.append(empty);
    }
    candidates.forEach((candidate) => {
      const card = document.createElement('article');
      card.className = 'media-card';
      const title = document.createElement('strong');
      const kindLabel = candidate.asset_kind === 'external_video' ? t('videoAsset') : t('imageAsset');
      title.textContent = `${candidate.title} · ${kindLabel}`;
      const source = document.createElement('small');
      source.textContent = `${candidate.provider} · ${candidate.author_or_provider} · ${candidate.license}`;
      const actions = document.createElement('div');
      actions.className = 'media-card-actions';
      const target = document.createElement('select');
      target.setAttribute('aria-label', t('mediaTab'));
      visuals.filter((item) => item.parameters.enabled).forEach((item) => {
        const option = document.createElement('option');
        option.value = item.parameters.asset_id;
        option.textContent = t('useFor', {title: item.parameters.title});
        target.append(option);
      });
      const use = document.createElement('button');
      use.type = 'button';
      use.className = 'button button-primary button-small';
      use.textContent = t('useThis');
      use.disabled = !target.options.length;
      use.addEventListener('click', () => useCandidate(candidate, target.value));
      actions.append(target, use);
      card.append(title, source, actions);
      refs.candidateList.append(card);
    });
  }

  async function loadMediaReview(id) {
    const response = await fetch(`/api/videos/${encodeURIComponent(id)}/media`);
    if (!response.ok) return;
    const payload = await response.json();
    if (state.taskId === id) renderMediaReview(currentPlan(), payload.candidates || []);
  }

  function selectTab(name, focus = false) {
    const requested = document.querySelector(`[data-tab="${name}"]`);
    if (!requested || requested.hidden) name = 'transcript';
    state.activeTab = name;
    document.querySelectorAll('[data-tab]').forEach((tab) => {
      const selected = tab.dataset.tab === name;
      tab.setAttribute('aria-selected', String(selected));
      tab.tabIndex = selected ? 0 : -1;
      if (selected && focus) tab.focus();
    });
    document.querySelectorAll('[data-tab-panel]').forEach((panel) => { panel.hidden = panel.dataset.tabPanel !== name; });
  }

  function resetCreation() {
    closeEventSource();
    state.taskId = null;
    state.currentTask = null;
    state.loadedTaskId = null;
    state.lastEventId = 0;
    state.events = [];
    state.candidates = [];
    state.previewVersion = 'stored';
    resetAgentState();
    localStorage.removeItem(STORAGE_KEYS.currentTask);
    refs.input.value = '';
    refs.transcript.value = '';
    refs.plan.value = '';
    refs.preview.removeAttribute('src');
    delete refs.preview.dataset.sourceKey;
    refs.preview.load();
    updateFileName();
    updateProgress('created');
    setWorkflowStage('upload');
    setStatus('ready', {}, {titleKey: 'readyTitle', tone: 'neutral'});
    renderEventList();
    updateWorkflowModeUI(refs.workflowMode.value);
  }

  refs.form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const file = refs.input.files?.[0];
    if (!file || !file.name.toLowerCase().endsWith('.mp4')) {
      setStatus('invalidFile', {}, {titleKey: 'uploadFailedTitle', tone: 'error'});
      return;
    }
    closeEventSource();
    state.events = [];
    state.lastEventId = 0;
    setWorkflowStage('processing');
    updateProgress('created');
    setStatus('uploading', {}, {titleKey: 'uploadingTitle', tone: 'info'});
    refs.uploadButton.disabled = true;
    const data = new FormData();
    data.append('file', file);
    data.append('workflow_mode', refs.workflowMode.value);
    data.append('processing_profile', refs.processingProfile.value);
    data.append('media_provider', refs.uploadMediaProvider.value);
    if (refs.workflowMode.value === 'agent') {
      data.append('director_instruction', refs.directorInstruction.value.trim());
      data.append('approval_policy', refs.approvalPolicy.value);
    }
    try {
      const response = await fetch('/api/videos', {method: 'POST', body: data});
      if (!response.ok) throw new Error(await responseError(response));
      const body = await response.json();
      state.taskId = body.task_id;
      state.loadedTaskId = body.task_id;
      state.currentTask = body;
      localStorage.setItem(STORAGE_KEYS.currentTask, state.taskId);
      refs.activeTaskId.textContent = state.taskId;
      updateWorkflowModeUI(body.workflow_mode);
      rememberTask(state.taskId, {name: file.name, status: 'pending', metadata: body.metadata, workflowMode: body.workflow_mode});
      watchTask(state.taskId);
    } catch (error) {
      setWorkflowStage('upload');
      setStatus('uploadFailed', {message: error.message}, {titleKey: 'uploadFailedTitle', tone: 'error'});
    } finally {
      refs.uploadButton.disabled = false;
    }
  });

  refs.saveReview.addEventListener('click', async () => {
    if (!state.taskId) return;
    let body;
    try { body = {transcript: JSON.parse(refs.transcript.value), plan: JSON.parse(refs.plan.value)}; }
    catch (error) { setStatus('invalidJson', {message: error.message}, {titleKey: 'reviewFailedTitle', tone: 'error'}); return; }
    const keepResult = !refs.result.hidden;
    try {
      refs.saveReview.disabled = true;
      setWorkflowStage('processing', {preserveResult: keepResult});
      updateProgress('review_rendering');
      setStatus('validatingReview', {}, {titleKey: 'validatingReviewTitle', tone: 'info'});
      const response = await fetch(`/api/videos/${encodeURIComponent(state.taskId)}/review`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
      if (!response.ok) throw new Error(await responseError(response));
      const payload = await response.json();
      if (payload.replanned) setStatus('replanned', {}, {titleKey: 'renderingStatusTitle', tone: 'info'});
      rememberTask(state.taskId, {status: 'rendering'});
      watchTask(state.taskId);
    } catch (error) {
      if (keepResult) setWorkflowStage('review');
      else setWorkflowStage('upload');
      setStatus('reviewFailed', {message: error.message}, {titleKey: 'reviewFailedTitle', tone: 'error'});
    } finally {
      refs.saveReview.disabled = false;
    }
  });

  refs.searchMedia.addEventListener('click', async () => {
    if (!state.taskId || !refs.mediaQuery.value.trim()) return;
    try {
      refs.searchMedia.disabled = true;
      setStatus('searching', {}, {titleKey: 'searchingTitle', tone: 'info'});
      const response = await fetch(`/api/videos/${encodeURIComponent(state.taskId)}/media/search`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({query: refs.mediaQuery.value.trim(), asset_kind: refs.mediaKind.value})});
      if (!response.ok) throw new Error(await responseError(response));
      const payload = await response.json();
      renderMediaReview(currentPlan(), payload.candidates || []);
      setStatus('foundCandidates', {count: (payload.candidates || []).length}, {titleKey: 'foundCandidatesTitle', tone: 'success'});
    } catch (error) {
      setStatus('searchFailed', {message: error.message}, {titleKey: 'searchFailedTitle', tone: 'error'});
    } finally {
      refs.searchMedia.disabled = false;
    }
  });

  refs.addManualMedia.addEventListener('click', async () => {
    if (!state.taskId || !refs.manualMediaUrl.value.trim()) return;
    try {
      refs.addManualMedia.disabled = true;
      const query = refs.mediaQuery.value.trim() || t('manualVisual');
      const response = await fetch(`/api/videos/${encodeURIComponent(state.taskId)}/media/candidates`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({query, source_url: refs.manualMediaUrl.value.trim(), title: query, asset_kind: refs.mediaKind.value, mime_type: refs.mediaKind.value === 'external_video' ? 'video/mp4' : 'image/jpeg'})});
      if (!response.ok) throw new Error(await responseError(response));
      const payload = await response.json();
      renderMediaReview(currentPlan(), [payload.candidate]);
      refs.manualMediaUrl.value = '';
      setStatus('foundCandidates', {count: 1}, {titleKey: 'foundCandidatesTitle', tone: 'success'});
    } catch (error) {
      setStatus('manualFailed', {message: error.message}, {titleKey: 'searchFailedTitle', tone: 'error'});
    } finally {
      refs.addManualMedia.disabled = false;
    }
  });

  refs.cancelTask.addEventListener('click', async () => {
    if (!state.taskId) return;
    try {
      refs.cancelTask.disabled = true;
      const response = await fetch(`/api/videos/${encodeURIComponent(state.taskId)}/cancel`, {method: 'POST'});
      if (!response.ok) throw new Error(await responseError(response));
      setStatus('event_cancel_requested', {}, {titleKey: 'cancelRequestedTitle', tone: 'warning'});
    } catch (error) {
      setStatus('cancelFailed', {message: error.message}, {titleKey: 'failedTitle', tone: 'error'});
    } finally {
      refs.cancelTask.disabled = false;
    }
  });

  refs.restoreForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    const id = refs.restoreTaskId.value.trim();
    if (!id) return;
    refs.restoreError.textContent = t('restoringTask');
    try {
      const response = await fetch(`/api/videos/${encodeURIComponent(id)}`);
      if (!response.ok) throw new Error(await responseError(response));
      const task = await response.json();
      rememberTask(id, {status: task.status, metadata: task.metadata});
      refs.restoreError.textContent = '';
      refs.restoreTaskId.value = '';
      openTask(id);
    } catch (error) {
      refs.restoreError.textContent = t('restoreFailed', {message: error.message});
    }
  });

  refs.input.addEventListener('change', updateFileName);
  refs.workflowMode.addEventListener('change', () => updateWorkflowModeUI(refs.workflowMode.value));
  refs.directorInstruction.addEventListener('input', updateDirectorCount);
  refs.approvePlan.addEventListener('click', () => submitApproval('approve'));
  refs.editPlan.addEventListener('click', () => submitApproval('edit'));
  refs.rejectPlan.addEventListener('click', () => submitApproval('reject'));
  ['dragenter', 'dragover'].forEach((name) => refs.dropZone.addEventListener(name, (event) => { event.preventDefault(); refs.dropZone.classList.add('is-dragging'); }));
  ['dragleave', 'drop'].forEach((name) => refs.dropZone.addEventListener(name, (event) => { event.preventDefault(); refs.dropZone.classList.remove('is-dragging'); }));
  refs.dropZone.addEventListener('drop', (event) => {
    if (event.dataTransfer?.files?.length) {
      refs.input.files = event.dataTransfer.files;
      updateFileName();
    }
  });

  document.querySelectorAll('[data-tab]').forEach((tab) => {
    tab.addEventListener('click', () => selectTab(tab.dataset.tab));
    tab.addEventListener('keydown', (event) => {
      const tabs = [...document.querySelectorAll('[data-tab]:not([hidden])')];
      const index = tabs.indexOf(tab);
      let next = null;
      if (event.key === 'ArrowRight') next = tabs[(index + 1) % tabs.length];
      if (event.key === 'ArrowLeft') next = tabs[(index - 1 + tabs.length) % tabs.length];
      if (event.key === 'Home') next = tabs[0];
      if (event.key === 'End') next = tabs[tabs.length - 1];
      if (next) { event.preventDefault(); selectTab(next.dataset.tab, true); }
    });
  });

  refs.menuButton.addEventListener('click', () => {
    const open = !document.body.classList.contains('nav-open');
    document.body.classList.toggle('nav-open', open);
    refs.menuButton.setAttribute('aria-expanded', String(open));
    refs.navScrim.tabIndex = open ? 0 : -1;
  });
  refs.navScrim.addEventListener('click', closeNavigation);
  document.addEventListener('keydown', (event) => { if (event.key === 'Escape') closeNavigation(); });
  refs.languageSelect.addEventListener('change', () => applyLanguage(refs.languageSelect.value));
  refs.settingsLanguage.addEventListener('change', () => applyLanguage(refs.settingsLanguage.value));
  refs.newTaskButton.addEventListener('click', resetCreation);
  window.addEventListener('hashchange', () => renderRoute());
  window.addEventListener('beforeunload', closeEventSource);

  if (!ROUTES[window.location.hash]) history.replaceState(null, '', '#/home');
  selectTab('transcript');
  applyLanguage(state.language);
  renderRoute();
})();
