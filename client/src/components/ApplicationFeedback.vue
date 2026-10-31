<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from "vue";
import { CheckCircle2, CircleAlert, RefreshCw, X } from "lucide-vue-next";
import { useAppStore } from "@/stores/app";
const store = useAppStore();
const checking = ref(false);
let timer = 0;
watch(() => store.notice, (notice) => {
  window.clearTimeout(timer);
  if (notice) timer = window.setTimeout(() => { if (store.notice === notice) store.notice = ""; }, 8000);
});
onBeforeUnmount(() => window.clearTimeout(timer));
async function reconnect(): Promise<void> {
  checking.value = true;
  try { await store.recheckConnection(); }
  finally { checking.value = false; }
}
</script>
<template>
  <div class="application-feedback">
    <Transition name="feedback"><div v-if="store.error" class="application-toast error" role="alert"><CircleAlert :size="18" /><div><strong>有一项操作需要处理</strong><p>{{ store.error }}</p><button :disabled="checking" @click="reconnect"><RefreshCw :size="13" />{{ checking ? '正在连接…' : '重新连接' }}</button></div><button title="关闭错误提示" @click="store.error = ''"><X :size="16" /></button></div></Transition>
    <Transition name="feedback"><div v-if="store.notice && !store.error" class="application-toast" role="status"><CheckCircle2 :size="18" /><p>{{ store.notice }}</p><button title="关闭通知" @click="store.notice = ''"><X :size="16" /></button></div></Transition>
  </div>
</template>
<style scoped>
.application-feedback { position:fixed; z-index:120; top:max(20px,env(safe-area-inset-top)); right:20px; width:min(400px,calc(100vw - 32px)); pointer-events:none; }
.application-toast { display:flex; align-items:flex-start; gap:12px; padding:16px; color:#203b33; background:#f4faf5f5; border:1px solid #b3cfc0; border-radius:12px; box-shadow:0 12px 40px #193e5326; backdrop-filter:blur(18px); pointer-events:auto; font:12px/1.8 "Microsoft YaHei UI",sans-serif; }
.application-toast > svg { flex-shrink:0; margin-top:3px; color:#28715d; }
.application-toast.error > svg { color:#a36038; }
.application-toast strong { font-size:13px; }
.application-toast p { margin:0; flex:1; overflow-wrap:anywhere; }
.application-toast > div { flex:1; min-width:0; }
.application-toast button { display:inline-flex; align-items:center; gap:5px; border:0; background:transparent; color:inherit; padding:4px; border-radius:4px; }
.application-toast > div button { margin-top:9px; padding:4px 10px; background:#e0eee4; color:#23654f; }
:global(body:has(.pa-theme-dark)) .application-toast { color:#dce9e2; background:#1f342ff5; border-color:#517368; }
:global(body:has(.pa-theme-dark)) .application-toast > svg { color:#8fceba; }
:global(body:has(.pa-theme-dark)) .application-toast.error > svg { color:#edb38d; }
:global(body:has(.pa-theme-dark)) .application-toast > div button { background:#335548; color:#dce9e2; }
:global(body:has(.pa-theme-contrast)) .application-toast { color:#14251e; background:#fff; border:2px solid #14251e; backdrop-filter:none; }
.application-toast button:focus-visible { outline:2px solid currentColor; outline-offset:2px; }
.feedback-enter-active,.feedback-leave-active { transition:opacity .18s,transform .18s; }
.feedback-enter-from,.feedback-leave-to { opacity:0; transform:translateY(-8px); }
@media(max-width:760px) { .application-feedback { top:12px; right:16px; } }
@media(prefers-reduced-motion:reduce) { .feedback-enter-active,.feedback-leave-active { transition:none; } }
</style>
