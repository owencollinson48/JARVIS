/* Developer-only Chromium checks against a DISPOSABLE database. Never makes paid requests. */
const assert=require('node:assert/strict');const {chromium}=require('playwright');
const base=process.env.JARVIS_TEST_URL||'http://127.0.0.1:5031',run=Date.now(),memoryLabel=`Morning study preference ${run}`,draftBody=`Browser draft reminder ${run}`;
(async()=>{const b=await chromium.launch({executablePath:process.env.JARVIS_TEST_CHROMIUM||'/usr/bin/chromium',args:['--no-sandbox']});try{
 const p=await b.newPage({viewport:{width:1440,height:1000}}),errors=[];p.on('pageerror',e=>errors.push(e.message));p.on('dialog',d=>d.accept(d.type()==='prompt'?memoryLabel+' edited':undefined));
 await p.goto(base);await p.waitForFunction(()=>document.getElementById('communication-status').textContent.length>0);
 await p.locator('.main-nav [data-page="planning"]').click();
 await p.locator('#plan-zone').fill('Europe/London');await p.locator('#plan-quiet-start').fill('0');await p.locator('#plan-quiet-end').fill('0');
 await p.locator('#planning-settings button.primary').click();await p.waitForFunction(()=>document.getElementById('planning-summary').textContent.includes('Europe/London'));
 const day=new Date(Date.now()+86400000).toISOString().slice(0,10);
 await p.locator('#event-title').fill('Browser saved shift');await p.locator('#event-start').fill(day+'T10:00');await p.locator('#event-end').fill(day+'T14:00');await p.locator('#event-break').fill('30');await p.locator('#event-form button.primary').click();
 await p.waitForFunction(()=>document.getElementById('calendar-events').textContent.includes('Browser saved shift'));
 await p.locator('#panel-switch').selectOption('work');assert.match(await p.locator('#work-events').textContent(),/3.5 paid hours/);
 await p.locator('#panel-switch').selectOption('memory');await p.locator('#memory-content').fill(memoryLabel);await p.locator('#save-memory').click();
 const memory=p.locator('#memory-list .memory-row').filter({hasText:memoryLabel});await memory.waitFor();await memory.getByRole('button',{name:'Edit',exact:true}).click();await p.waitForFunction(label=>document.getElementById('memory-list').textContent.includes(label+' edited'),memoryLabel);
 await p.locator('#panel-switch').selectOption('communications');assert.equal(await p.locator('#paid-voice-toggle').isDisabled(),true);
 await p.locator('#contact-body').fill(draftBody);await p.locator('#contact-form button').click();await p.waitForFunction(label=>document.getElementById('contact-jobs').textContent.includes(label),draftBody);
 assert.match(await p.locator('#contact-jobs').textContent(),/draft/);
 await p.locator('#panel-switch').selectOption('autonomy');if(await p.locator('#auto-open').isChecked())await Promise.all([p.waitForResponse(r=>r.url().includes('/api/workspace/permissions')&&r.request().method()==='PUT'),p.locator('#auto-open').uncheck()]);await Promise.all([p.waitForResponse(r=>r.url().includes('/api/workspace/permissions')&&r.request().method()==='PUT'),p.locator('#auto-open').check()]);
 for(const name of ['planning','autonomy','communications']){
  await p.locator('#panel-switch').selectOption(name);await p.setViewportSize({width:320,height:800});assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),true,`No viewport overflow: ${name}`);await p.setViewportSize({width:1440,height:1000});
 }
 await p.keyboard.press('Escape');await p.locator('#command-input').fill('Remind me to test shared context tomorrow');await p.locator('#send-command').click();await p.waitForFunction(()=>document.getElementById('last-response').textContent.includes('Saved task'));
 await p.locator('#emergency-stop').click();await p.waitForFunction(()=>document.getElementById('notice-text').textContent.includes('stopped'));
 const stopped=await p.evaluate(async()=>({planning:await(await fetch('/api/planning/state')).json(),comm:await(await fetch('/api/communications/state')).json()}));assert.equal(stopped.planning.config.proactive,false);assert.equal(stopped.comm.config.sms,false);assert.equal(stopped.comm.jobs.find(x=>x.body===draftBody).status,'cancelled');assert.deepEqual(errors,[]);
 console.log('PASS Planning, saved shift hours, memory editing, honest disabled paid voice, contact drafts, permissions, mobile layouts, shared tasks and emergency stop');
 await p.screenshot({path:'.ui-check/upgrade-home.png',fullPage:true});
 }finally{await b.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
