import { createApp, h } from "vue";
import UsageEvidence from "../src/features/creative-live/components/UsageEvidence.vue";
import SceneMaterialInspector from "../src/features/creative-live/components/SceneMaterialInspector.vue";
const accounting = {total_tokens:4280,cost_usd:0.0138,catalog_estimate_usd:0.0138,public_estimate_cny:0.091,
  public_estimate_complete:false,outer_invocations:4,recorded_model_turns:7,observed_http_attempts:9,
  unknown_usage_updates:1,unknown_usage_invocations:1,unknown_catalog_cost_updates:1,
  actual_charge:null,price_sources:[{source:"https://api-docs.deepseek.com/zh-cn/quick_start/pricing/",observed_at:"2026-10-11",currency:"CNY"}],
  usage_ids:[],token_details:{},updates:4,cost_source:"offline-fixture"};
document.head.insertAdjacentHTML("beforeend","<style>body{margin:0;background:#f8faf7;color:#263831;font:14px Georgia,'Microsoft YaHei',serif}main{max-width:900px;margin:auto;padding:20px;box-sizing:border-box}h1{font-size:23px;font-weight:500}footer{position:relative;display:flex;justify-content:space-between;gap:12px;border-top:1px solid #bdd7c7;margin-top:18px;padding:14px 0;font-size:12px}footer>span{min-width:0}*{box-sizing:border-box}</style>");
createApp({render:()=>h("main",[
  h("h1","费用与素材记录"),h("p","隔离界面验收 · 以下为测试夹具，不是新一轮扣费记录。"),
  h(SceneMaterialInspector,{projectRoot:"offline-cost-fixture",transactionId:"offline-cost-tx"}),
  h("footer",[h("span","已保存素材与使用记录"),h(UsageEvidence,{accounting,tokens:4280,catalog:0.0138})]),
])}).mount("#cost-ui-root");
