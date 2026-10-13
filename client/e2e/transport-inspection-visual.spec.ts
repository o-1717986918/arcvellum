import fs from 'node:fs';
import path from 'node:path';
import {expect,test} from '@playwright/test';
import {prepareVisualProjects,visualProjectRoot} from './orreryVisualFixture';

test.use({trace:'off'});
const evidence=path.resolve(__dirname,'../../work/narrative-range/real-material-inspection.json');
test.skip(!fs.existsSync(evidence),'Saved material evidence required. No model calls.');
test.beforeAll(async({request})=>{await prepareVisualProjects(request)});

for(const width of [1440,390]){
  test(`technical processing records are readable at ${width}px`,async({page},info)=>{
    test.setTimeout(90_000);
    const inspection=JSON.parse(fs.readFileSync(evidence,'utf8'));
    // These explicit fixture counts exercise each display state, not provider billing.
    inspection.transport={model_calls:1,reuse_count:2,local_records:3,records:[
      {record_id:'local',operation:'card',mode:'local',model_calls:0,reuse_count:0,requested_thinking:null},
      {record_id:'reused',operation:'creator',mode:'reused',model_calls:1,reuse_count:2,requested_thinking:'off'},
      {record_id:'repair',operation:'material',mode:'failed',model_calls:0,reuse_count:0,requested_thinking:null,error:'当前原文的言行标注待补充。'},
    ]};
    const summary={transaction_id:inspection.transaction_id,scene_id:inspection.scene_id,status:'committed',
      objective:'界面验收示例 · 保存素材与整理状态',turn_count:2,updated_at:'2026-10-10T12:00:00Z'};
    await page.setViewportSize({width,height:width===390?844:1000});
    await page.addInitScript(root=>{localStorage.setItem('arcvellum.currentProject',root);localStorage.setItem('arcvellum.onboarding-seen','1')},visualProjectRoot(100));
    await page.route('**/api/creative-live/scene-rehearsals?*',r=>r.fulfill({json:{scenes:[summary]}}));
    await page.route('**/api/creative-live/scene-rehearsals/*',r=>r.fulfill({json:{scene:{...summary,turns:[],environment:[]}}}));
    await page.route('**/api/creative-live/scene-materials/*',r=>r.fulfill({json:{inspection}}));
    const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
    await page.goto('#/agent?workspace=rehearsal',{waitUntil:'domcontentloaded'});
    const enter=page.getByRole('button',{name:'进入创作台'});
    await expect.poll(async()=>await enter.isVisible() || !await page.locator('.app-shell').evaluate(n=>n.classList.contains('startup-obscured'))).toBe(true);
    if(await enter.isVisible())await enter.click();
    const records=page.locator('.material-transport');await expect(records).toBeVisible();
    await records.locator('summary').click();
    await expect(records).toContainText('请求非思考');
    await expect(records).toContainText('本地复用');
    await expect(records).toContainText('言行标注待补充');
    const layout=await page.locator('.material-inspector').evaluate(n=>({width:n.clientWidth,scroll:n.scrollWidth}));
    expect(layout.scroll).toBeLessThanOrEqual(layout.width+1);
    await records.scrollIntoViewIfNeeded();
    await page.screenshot({path:info.outputPath(`transport-${width}.png`),fullPage:true});
    expect(errors).toEqual([]);
  });
}
