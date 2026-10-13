import { test,expect } from "@playwright/test";

test("fresh isolated API starts with no model usage and exposes a reconnect snapshot",async({request})=>{
  const api="http://127.0.0.1:"+(process.env.ARCVELLUM_VISUAL_API_PORT || "8791");
  const root=process.env.ARCVELLUM_COST_FIXTURE_ROOT || "";
  test.skip(!root,"Requires the separately prepared offline acceptance project.");
  expect((await request.get(api+"/health")).ok()).toBe(true);
  expect((await request.get(api+"/runtime/adapters")).ok()).toBe(true);
  expect((await request.post(api+"/projects/open",{data:{project_root:root}})).ok()).toBe(true);
  expect((await request.get(api+"/projects")).ok()).toBe(true);
  const snapshot=await request.get(api+"/creative-live?project_root="+encodeURIComponent(root));
  expect(snapshot.ok()).toBe(true);
  const data=await snapshot.json();
  expect(data.usage_accounting.outer_invocations).toBe(0);
  expect(data.usage_accounting.actual_charge).toBeNull();
  const abort=new AbortController();
  const response=await fetch(api+"/creative-live/stream?project_root="+encodeURIComponent(root),{signal:abort.signal});
  const reader=response.body!.getReader();
  const first=await reader.read();
  expect(new TextDecoder().decode(first.value)).toContain("snapshot");
  abort.abort();
});

test("cost and material evidence stay readable on desktop and mobile",async ({page},testInfo)=>{
  await page.route("**/api/creative-live/scene-materials/*?*",async route=>route.fulfill({
    status:200,contentType:"application/json",body:JSON.stringify({ok:true,inspection:{
      transaction_id:"offline-cost-tx",candidate_count:2,intent:null,warnings:[],
      calls:[{call_id:"one",sequence:1,request:{kind:"event-narration",target:"姓名制度",purpose:"尚缺姓氏与劳动的联系；用于本章制度介绍",scene_moment:"章首",
        author_prompt:"从姓氏如何积存展开。"},attachments:[],raw_response:"他攒姓，给未出生的孩子留名字。"}],
      materials:[{candidate_id:"v2:source:1",call_id:"one",kind:"event-narration",target:"姓名制度",
        text:"他攒姓，给未出生的孩子留名字。",decision:"adapt",decision_reason:"保留姓名作为积累物的世界设定",
        usage_evidence:{source_excerpt:"攒姓",prose_excerpt:"他攒姓",source_excerpt_verified:true,prose_excerpt_verified:true,indirect_use:"建立姓名与劳动的关系"}},
        {candidate_id:"v2:source:2",call_id:"one",kind:"event-narration",target:"姓名制度",text:"尚待后章展开的材料。",decision:"defer",decision_reason:"留待后章"}],
    }}),
  }));
  await page.goto("e2e/cost-ui-harness.html",{waitUntil:"domcontentloaded"});
  await expect(page.locator(".material-inspector")).toContainText("攒姓");
  await page.getByText("素材用途与正文落点",{exact:true}).first().click();
  for (const width of [1440,390]) {
    await page.setViewportSize({width,height:width===390?844:900});
    const panel=page.locator(".usage-evidence");await panel.locator("summary").click();
    await expect(panel).toContainText("公开价格估算 ¥0.0910（已知部分）");
    await expect(panel).toContainText("实际扣款尚未核验");
    await expect(panel).toContainText("9 次可观测 HTTP 尝试");
    const bounds=await panel.locator(".usage-evidence-body").boundingBox();
    const summary=await panel.locator("summary").boundingBox();
    expect(bounds!.x).toBeGreaterThanOrEqual(0);
    expect(bounds!.x+bounds!.width).toBeLessThanOrEqual(width+1);
    expect(bounds!.y+bounds!.height).toBeLessThanOrEqual(summary!.y+2);
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
    await page.screenshot({path:testInfo.outputPath("screenshots","cost-evidence-"+width+".png"),fullPage:true});
    await panel.locator("summary").click();
  }
});
