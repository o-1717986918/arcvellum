import { expect, test } from "@playwright/test";
import { prepareVisualProjects, visualProjectRoot } from "./orreryVisualFixture";
import fs from "node:fs";
import path from "node:path";
const project=visualProjectRoot(100);
test.beforeAll(async({request})=>{await prepareVisualProjects(request);});
for(const viewport of [{width:1440,height:900},{width:390,height:844}]) {
  test("cache evidence remains readable at "+viewport.width,async({page})=>{
    await page.setViewportSize(viewport);
    const totals={responses:3,reported_responses:2,unreported_responses:1,inconsistent_responses:0,
      hit_ratio:.8,reporting_coverage:2/3};
    const snapshot={ok:true,schema:"arcvellum/creative-live-snapshot/v1",project_id:"cache-visual",revision:"cache-1",
      status:"idle",controller:null,active_task:null,artifacts:[],sessions:[],activity:[],reviews:[],
      usage:{total_tokens:300,cost_usd:.001,updates:3},usage_accounting:{total_tokens:300,cost_usd:.001,updates:3,
        catalog_estimate_usd:.001,unknown_catalog_cost_updates:0,public_estimate_cny:null,
        outer_invocations:3,recorded_model_turns:3,observed_http_attempts:3,unknown_usage_updates:0,
        price_sources:[],server_cache:{schema:"arcvellum/server-cache-accounting/v1",totals,
          groups:[{provider:"fixture",model:"fixture-model",call_purpose:"review",hit_ratio:.8}]}},
      active_scene_transaction:null,scene_transactions:[],style_provenance:null,events:[],cursor:0};
    await page.route("**/api/creative-live?*",route=>route.fulfill({status:200,contentType:"application/json",body:JSON.stringify(snapshot)}));
    await page.addInitScript(root=>{
      localStorage.setItem("arcvellum.currentProject",root);localStorage.setItem("arcvellum.onboarding-seen","1");
      const native=window.fetch.bind(window);
      window.fetch=(input,init)=>{
        const url=typeof input==="string"?input:input instanceof URL?input.href:input.url;
        if(url.includes("/api/creative-live/stream?")) return Promise.resolve(new Response(new ReadableStream({
          start(c){init?.signal?.addEventListener("abort",()=>c.error(new DOMException("Aborted","AbortError")),{once:true});}
        }),{headers:{"Content-Type":"text/event-stream"}}));
        return native(input,init);
      };
    },project);
    await page.goto("#/agent?workspace=live",{waitUntil:"domcontentloaded"});
    const enter=page.getByRole("button",{name:"进入创作"});if(await enter.isVisible())await enter.click();
    const chooser=page.getByRole("dialog",{name:"这次想写哪部作品？"});
    if(await chooser.isVisible())await chooser.getByRole("button",{name:"关闭",exact:true}).click();
    const panel=page.locator(".usage-evidence");
    await expect(panel).toBeVisible({timeout:30000});
    await panel.locator(":scope > summary").click();
    await expect(panel).toContainText("80.0%");
    await expect(panel).toContainText("缓存字段未报告 1 次");
    const bounds=await panel.locator(".usage-evidence-body").boundingBox();
    expect(bounds).toBeTruthy();expect(bounds!.x).toBeGreaterThanOrEqual(-1);
    expect(bounds!.x+bounds!.width).toBeLessThanOrEqual(viewport.width+1);
    expect(await panel.locator(".usage-evidence-body").evaluate(n=>n.scrollWidth<=n.clientWidth+1)).toBe(true);
    const target=path.resolve("build/cache-visual/usage-"+viewport.width+".png");
    fs.mkdirSync(path.dirname(target),{recursive:true});await page.screenshot({path:target,fullPage:true});
  });
}
