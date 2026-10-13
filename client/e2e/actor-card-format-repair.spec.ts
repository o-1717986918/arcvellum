import {test,expect} from '@playwright/test';

const root=process.env.ARCVELLUM_ACTOR_CARD_REPAIR_ROOT || '';
test.use({trace:'off'});
test.skip(!root,'Use the isolated author-card format fixture. No model requests are issued.');
test('eleven-section author card and preserved legacy card load faithfully on desktop and mobile',async({page,request},info)=>{
  test.setTimeout(90_000);
  const api=`http://127.0.0.1:${process.env.ARCVELLUM_VISUAL_API_PORT || 8791}`;
  expect((await request.post(api+'/projects/open',{data:{project_root:root},timeout:15_000})).ok()).toBeTruthy();
  const setup=await (await request.get(api+'/character-chat/setup?project_root='+encodeURIComponent(root))).json();
  expect(setup.sections).toHaveLength(11);
  expect(setup.card_schema).toBe('arcvellum/actor-character-card/v2');
  await page.addInitScript(value=>{localStorage.setItem('arcvellum.currentProject',value);localStorage.setItem('arcvellum.onboarding-seen','1')},root);
  const errors:string[]=[];let modelRequests=0;
  page.on('pageerror',error=>errors.push(error.stack || error.message));
  await page.route(/\/ask$|\/cards\/draft$/,route=>{modelRequests++;return route.abort()});
  for(const [target,count,schema,width,height] of [
    ['漩涡鸣人',11,'arcvellum/actor-character-card/v2',1440,1000],
    ['铜靴',16,'arcvellum/actor-character-card/v1',390,844],
  ] as const){
    await page.setViewportSize({width,height});await page.goto('#/character-chat',{waitUntil:'domcontentloaded'});
    const panel=page.getByRole('dialog',{name:'与角色交谈'});await expect(panel).toBeVisible();
    const card=setup.cards.find((item:any)=>item.card.target===target);expect(card).toBeTruthy();
    await panel.getByLabel('主创已填写的角色卡').selectOption(card.digest);
    const editor=panel.locator('.character-card-fields');
    if(!await editor.isVisible())await panel.getByRole('button',{name:'查看与编辑角色卡'}).click();
    await expect(editor).toBeVisible();
    expect(await panel.locator('.character-card-fields textarea').count()).toBe(count+1);
    await panel.getByLabel('这段对话的场景').fill('独立的格式核对情境，保留卡的原文。');
    await panel.getByRole('button',{name:'加载并开始新对话'}).click();
    await expect(panel.getByLabel('对角色说')).toBeVisible();
    await panel.getByText('本段加载的上下文与系统角色卡').click();
    const sessions=await (await request.get(api+'/character-chat/setup?project_root='+encodeURIComponent(root))).json();
    const latest=sessions.sessions.find((item:any)=>item.target===target);expect(latest).toBeTruthy();
    const response=await (await request.get(api+'/character-chat/sessions/'+latest.session_id+'?project_root='+encodeURIComponent(root))).json();
    const saved=response.session;
    expect(saved.card.schema).toBe(schema);
    expect(Object.keys(saved.card.sections)).toHaveLength(count);
    for(const content of Object.values(card.card.sections))expect(saved.system_prompt).toContain(content);
    const dimensions=await panel.evaluate(node=>({client:node.clientWidth,scroll:node.scrollWidth}));
    expect(dimensions.scroll).toBeLessThanOrEqual(dimensions.client+1);
    await page.screenshot({path:info.outputPath(`actor-card-${count}-${width}.png`),fullPage:true});
    await panel.getByRole('button',{name:'关闭角色对话'}).click();
    await expect(panel).toBeHidden();
  }
  expect(modelRequests).toBe(0);expect(errors).toEqual([]);
});
