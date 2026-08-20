<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { Bot, Check, KeyRound, Unplug } from "lucide-vue-next";
import { settingsClient, type PiCatalog } from "@/features/settings/services/settingsClient";
import { saveCreativeRuntime } from "@/services/runtimePreference";

const catalog = ref<PiCatalog | null>(null);
const credential = reactive({ provider_id: "deepseek", credential: "" });
const selectedModel = ref("");
const busy = ref(false);
const feedback = ref("");
const providers = computed(() => catalog.value?.providers || []);
const connectedProviders = computed(() => providers.value.filter((provider) => provider.connected));
const models = computed(() => connectedProviders.value.flatMap((provider) => provider.models || []));

onMounted(loadCatalog);

async function loadCatalog(): Promise<void> {
  feedback.value = "";
  try {
    catalog.value = await settingsClient.piCatalog();
    selectedModel.value = catalog.value.selected_model || "";
  } catch (cause) {
    feedback.value = cause instanceof Error ? cause.message : "内置 Pi 主创暂时不可用。";
  }
}

async function connectProvider(): Promise<void> {
  if (!credential.credential || busy.value) return;
  busy.value = true;
  feedback.value = "";
  try {
    catalog.value = await settingsClient.savePiCredential(credential);
    credential.credential = "";
    selectedModel.value = catalog.value.selected_model || "";
    feedback.value = "Pi 主创已连接模型服务；请选择它执行正式创作时使用的模型。";
  } catch (cause) {
    feedback.value = cause instanceof Error ? cause.message : "Pi 主创连接失败。";
  } finally {
    busy.value = false;
  }
}

async function saveModel(): Promise<void> {
  if (!selectedModel.value || busy.value) return;
  busy.value = true;
  feedback.value = "";
  try {
    catalog.value = await settingsClient.selectPiModel({ model: selectedModel.value, role: "worker" });
    selectedModel.value = catalog.value.selected_model || "";
    saveCreativeRuntime("pi-worker");
    feedback.value = "内置 Pi 主创已经设为正式创作执行器，重启后仍会保持。";
  } catch (cause) {
    feedback.value = cause instanceof Error ? cause.message : "Pi 主创模型没有保存成功。";
  } finally {
    busy.value = false;
  }
}

async function disconnectProvider(providerId: string): Promise<void> {
  if (busy.value) return;
  busy.value = true;
  try {
    catalog.value = await settingsClient.disconnectPiProvider(providerId);
    selectedModel.value = catalog.value.selected_model || "";
    feedback.value = "Pi 主创与该模型服务的连接已移除。";
  } catch (cause) {
    feedback.value = cause instanceof Error ? cause.message : "连接没有移除。";
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <section class="settings-section pi-worker-connection">
    <header>
      <span class="section-icon pi"><Bot :size="18" /></span>
      <div><span class="eyebrow">内置创作执行器</span><h2>ArcVellum Pi 主创</h2><p>随客户端安装的受控文学 Agent。它只读取当前任务允许的资料，只写指定成果，不拥有终端和任意文件权限。</p></div>
      <span class="pi-runtime-state" :data-ready="Boolean(catalog?.selected_model)"><i></i>{{ catalog?.selected_model ? "已就绪" : "等待模型" }}</span>
    </header>
    <div class="pi-worker-controls">
      <form @submit.prevent="connectProvider">
        <label class="field"><span>模型服务</span><select v-model="credential.provider_id"><option v-for="provider in providers" :key="provider.id" :value="provider.id">{{ provider.name }}</option></select></label>
        <label class="field"><span>API 密钥</span><input v-model="credential.credential" type="password" autocomplete="new-password" placeholder="只写入本机 Pi 凭证库" /></label>
        <button class="secondary-button" :disabled="busy || !credential.credential"><KeyRound :size="15" />连接服务</button>
      </form>
      <div class="pi-model-choice">
        <label class="field"><span>正式创作模型</span><select v-model="selectedModel" :disabled="busy || !models.length"><option value="">连接服务后选择模型</option><option v-for="model in models" :key="model.qualified_id" :value="model.qualified_id">{{ model.name }} · {{ model.qualified_id }}</option></select></label>
        <button class="primary-button" :disabled="busy || !selectedModel" @click="saveModel"><Check :size="15" />设为主创</button>
      </div>
    </div>
    <div v-if="connectedProviders.length" class="pi-provider-strip">
      <span v-for="provider in connectedProviders" :key="provider.id"><i></i>{{ provider.name }} · {{ provider.models?.length || 0 }} 个模型<button class="icon-button" title="断开 Pi 模型服务" @click="disconnectProvider(provider.id)"><Unplug :size="13" /></button></span>
    </div>
    <p v-if="feedback" class="inline-feedback">{{ feedback }}</p>
  </section>
</template>
