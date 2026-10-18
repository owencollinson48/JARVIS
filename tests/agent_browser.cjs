/* Developer-only offline integration against tests/agent_browser_server.py. */
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');const {chromium}=require('playwright');
const base=process.env.JARVIS_TEST_URL||'http://127.0.0.1:5041',fixture=path.resolve('.ui-check',process.env.JARVIS_AGENT_FIXTURE_DIR||'master-agent','engineering_notes.txt');
const run=Date.now(),fileGoal=`Could you fix my engineering notes, please? ${run}`,screenGoal=`Please inspect my screen. ${run}`,commandGoal=`Run the test command for me. ${run}`;
(async()=>{fs.writeFileSync(fixture,'Draft engineering notes.');const browser=await chromium.launch({executablePath:'/usr/bin/chromium',args:['--no-sandbox']});try{
 const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];page.setDefaultTimeout(15000);page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.accept());
 await page.goto(base);await page.waitForFunction(()=>document.getElementById('agent-service').textContent.length>0);
 await page.locator('.main-nav [data-page="agent"]').click();await page.locator('#agent-enabled').check();await page.locator('#agent-consent').check();await page.locator('#agent-settings button.primary').click();await page.waitForFunction(()=>document.getElementById('agent-service').textContent.includes('enabled'));
 await page.keyboard.press('Escape');await page.locator('#command-input').fill(fileGoal);await page.locator('#send-command').click();await page.locator('.main-nav [data-page="agent"]').click();
 const fileJob=page.locator('.agent-job').filter({hasText:fileGoal});await fileJob.locator('.agent-approval').waitFor();
 assert.equal(fs.readFileSync(fixture,'utf8'),'Draft engineering notes.');assert.match(await fileJob.textContent(),/Share|Send this specific/);
 await fileJob.getByRole('button',{name:'Approve this action'}).click();await page.waitForFunction(()=>document.getElementById('panel-notice').textContent.includes('tick its checkbox'));
 await fileJob.locator('.agent-approval input[type=checkbox]').check();await page.waitForTimeout(1800);assert.equal(await fileJob.locator('.agent-approval input[type=checkbox]').isChecked(),true,'Polling preserves owner review state');
 await fileJob.getByRole('button',{name:'Approve this action'}).click();await fileJob.getByText(/saved bytes verified/).waitFor();
 assert.equal(fs.readFileSync(fixture,'utf8'),'Reviewed engineering notes.');await fileJob.getByRole('button',{name:'Inspect activity'}).click();await page.waitForFunction(()=>document.getElementById('agent-audit').textContent.includes('files_patch'));
 assert.match(await page.locator('#agent-recoveries').textContent(),/engineering_notes.txt/);
 await page.locator('#agent-goal').fill(screenGoal);await page.locator('#agent-goal-form button').click();const screenJob=page.locator('.agent-job').filter({hasText:screenGoal});await screenJob.locator('.agent-screen-preview').waitFor();await screenJob.locator('.agent-screen-preview').evaluate(img=>img.decode());assert.equal(await screenJob.locator('.agent-screen-preview').evaluate(img=>img.naturalWidth>0),true);
 await screenJob.locator('.agent-approval input[type=checkbox]').check();await screenJob.getByRole('button',{name:'Approve this action'}).click();await screenJob.getByText(/approved test snapshot/).waitFor();
 await page.locator('#agent-goal').fill(commandGoal);await page.locator('#agent-goal-form button').click();const commandJob=page.locator('.agent-job').filter({hasText:commandGoal});await commandJob.locator('.agent-approval').waitFor();assert.match(await commandJob.locator('.agent-approval').textContent(),/offline command fixture/);await commandJob.getByRole('button',{name:'Cancel task'}).click();await commandJob.getByText(/CANCELLED ·/).waitFor();
 for(const width of [1440,390,320]){await page.setViewportSize({width,height:900});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),true,`No agent overflow at ${width}`);}
 await page.setViewportSize({width:1440,height:1000});await page.keyboard.press('Escape');await page.keyboard.press('Alt+Shift+s');await page.waitForFunction(()=>document.getElementById('agent-live').textContent.includes('off'));
 const state=await page.evaluate(async()=>await(await fetch('/api/agent/state')).json());assert.equal(state.policy.enabled,false);assert.deepEqual(errors,[]);
 console.log('PASS Existing HUD + natural chat -> real background worker, specific owner approval, automatic backed-up patch, screenshot preview/approval, activity/recovery, command cancellation, responsive UI and keyboard emergency stop. Model and native Windows IO were mocked; no paid request.');
 }finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
