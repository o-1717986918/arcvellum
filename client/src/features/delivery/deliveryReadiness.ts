export interface DeliveryReadiness {
  allowed: boolean;
  label: string;
  message: string;
}

export function deliveryReadiness(
  formalCharacters: number,
  readerUnits: number,
  blockerCount: number,
  incompleteIntegrityChecks = 0,
): DeliveryReadiness {
  if (blockerCount > 0) {
    return {
      allowed: false,
      label: "先完成交付前检查",
      message: `还有 ${blockerCount} 项交付条件需要处理。`,
    };
  }
  if (formalCharacters <= 0 && readerUnits <= 0) {
    return {
      allowed: false,
      label: "等待正式正文",
      message: "当前还没有通过门禁的正式正文，暂时不能生成交付包。",
    };
  }
  if (incompleteIntegrityChecks > 0) {
    return {
      allowed: false,
      label: "等待作品完成",
      message: `还有 ${incompleteIntegrityChecks} 项作品完整度检查尚未完成。`,
    };
  }
  return { allowed: true, label: "准备正式交付", message: "交付前检查已满足，可以生成正式文件。" };
}
