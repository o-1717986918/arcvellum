export const archiveAssetLabels: Record<string, string> = {
  character: "人物",
  scene: "场景",
  "world-rule": "世界规则",
  "location-catalog": "地点",
  "organization-catalog": "组织",
  "promise-ledger": "承诺与兑现",
  "reader-question-ledger": "读者问题",
};

export const archiveFieldLabels: Record<string, string> = {
  name: "姓名",
  aliases: "别名",
  importance: "角色权重",
  role: "叙事角色",
  background_story: "背景故事",
  psychology: "心理结构",
  bdi: "信念、欲望与意图",
  state: "当前状态",
  chapter_id: "所属章节",
  location: "地点",
  participants: "出场人物",
  participant_refs: "人物引用",
  scene_goal: "场景目标",
  conflict: "冲突",
  reader_experience: "读者体验",
  word_count_target: "目标字数",
  world_name: "世界名称",
  rules: "规则",
  constraints: "约束",
  taboos: "禁区",
  open_questions: "开放问题",
  locations: "地点目录",
  organizations: "组织目录",
  promises: "承诺条目",
  reader_questions: "问题条目",
};

export function archiveAssetLabel(assetType: unknown): string {
  const key = String(assetType || "");
  return archiveAssetLabels[key] || key || "作品资料";
}

export function archiveFieldLabel(field: unknown): string {
  const key = String(field || "");
  return archiveFieldLabels[key] || key.replaceAll("_", " ");
}
