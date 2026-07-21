<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { BookMarked, ExternalLink, FileText, Fingerprint, Github, HardDrive, Scale, ShieldCheck } from "lucide-vue-next";
import { api } from "@/services/api";
import { asList, asRecord, formatCount } from "@/services/presentation";
import { useAppStore } from "@/stores/app";

defineProps<{ embedded?: boolean }>();
const emit = defineEmits<{ navigate: [view: "help" | "legal"] }>();

const store = useAppStore();
const app = ref<Record<string, any>>({});
const quality = ref<Record<string, any> | null>(null);
const summary = computed(() => asRecord(store.dashboard?.summary));
const routes = computed(() => asList<Record<string, unknown>>(store.dashboard?.route_audits));

onMounted(async () => {
  app.value = await api<Record<string, any>>("/application/info");
  if (store.currentProjectPath) quality.value = (await api<Record<string, any>>(`/project/creative-quality?project_root=${encodeURIComponent(store.currentProjectPath)}`)).profile as Record<string, any>;
});
</script>

<template>
  <div class="view details-view">
    <header><span class="eyebrow">详情</span><h1>作品与 ArcVellum</h1><p>这里说明当前作品的规模、规则版本、数据位置和应用身份。</p></header>
    <section v-if="store.currentProject" class="details-project">
      <div class="details-project-title"><BookMarked :size="25" /><div><strong>{{ store.currentProject.title }}</strong><p>{{ store.currentProject.premise || "作品方向仍在形成。" }}</p></div></div>
      <div class="details-metrics"><div><span>目标篇幅</span><strong>{{ formatCount(store.currentProject.target_length) }}</strong></div><div><span>创作路线</span><strong>{{ routes.length }}</strong></div><div><span>待处理事项</span><strong>{{ formatCount(summary.blocking_count) }}</strong></div><div><span>规则版本</span><strong>r{{ quality?.revision || 1 }}</strong></div></div>
    </section>
    <div class="details-grid">
      <section><header><Fingerprint :size="18" /><h2>应用身份</h2></header><dl><div><dt>名称</dt><dd>{{ app.product_name || "ArcVellum" }}</dd></div><div><dt>版本</dt><dd>{{ app.version || "-" }}</dd></div><div><dt>构建</dt><dd>{{ app.build_number || "正式版" }}</dd></div><div><dt>更新通道</dt><dd>{{ app.release_channel || "stable" }}</dd></div></dl></section>
      <section><header><HardDrive :size="18" /><h2>本地数据</h2></header><p>作品与运行记录保存在你的设备上。模型连接只接收当前受控任务所需的资料。</p><dl><div><dt>作品库</dt><dd>{{ app.paths?.projects_root || "由应用管理" }}</dd></div><div><dt>配置位置</dt><dd>{{ app.paths?.configuration || "用户数据目录" }}</dd></div></dl></section>
      <section><header><ShieldCheck :size="18" /><h2>隐私与边界</h2></header><p>ArcVellum 不用宽泛内容过滤替代创作判断。用户需对素材权利、真实人物与公开传播负责；文件与 Shell 权限仍受任务沙箱约束。</p><div class="detail-links"><button v-if="embedded" class="text-button" @click="emit('navigate', 'legal')"><FileText :size="15" />阅读隐私说明</button><RouterLink v-else to="/legal"><FileText :size="15" />阅读隐私说明</RouterLink></div></section>
      <section><header><Scale :size="18" /><h2>许可与第三方</h2></header><p>内置 OpenCode Runner 使用其开源许可。第三方模型、托管服务与账号分别受对应提供商条款约束。</p><div class="detail-links"><template v-if="embedded"><button class="text-button" @click="emit('navigate', 'help')"><FileText :size="15" />使用说明</button><button class="text-button" @click="emit('navigate', 'legal')"><Scale :size="15" />协议与许可</button></template><template v-else><RouterLink to="/help"><FileText :size="15" />使用说明</RouterLink><RouterLink to="/legal"><Scale :size="15" />协议与许可</RouterLink></template><a v-if="app.repository_url" :href="app.repository_url"><Github :size="15" />项目仓库<ExternalLink :size="12" /></a></div></section>
    </div>
  </div>
</template>
