/* Offline WebRTC event/state test. No OpenAI media connection is created. */
const assert=require('node:assert/strict');const {chromium}=require('playwright');
(async()=>{const b=await chromium.launch({executablePath:'/usr/bin/chromium',args:['--no-sandbox','--use-fake-device-for-media-stream','--use-fake-ui-for-media-stream']});try{
 const p=await b.newPage({permissions:['microphone']}),errors=[];p.on('pageerror',e=>errors.push(e.message));p.on('dialog',d=>d.accept());
 await p.addInitScript(()=>{window.RTCPeerConnection=class{
  constructor(){this.iceGatheringState='complete';this.connectionState='new';window.fakePeer=this;}
  addTrack(){}createDataChannel(){return window.fakeChannel={readyState:'open',sent:[],send(x){this.sent.push(JSON.parse(x));},close(){this.readyState='closed';}};}
  createOffer(){return Promise.resolve({type:'offer',sdp:'v=0\r\noffline'});}setLocalDescription(x){this.localDescription=x;return Promise.resolve();}
  setRemoteDescription(){this.connectionState='connected';setTimeout(()=>this.onconnectionstatechange?.(),0);return Promise.resolve();}close(){this.connectionState='closed';}
 };});
 await p.route('**/api/realtime/state',r=>r.fulfill({json:{enabled:true,configured:true}}));
 let starts=0,stops=0,commands=0,goals=[],polls=0;
 await p.route('**/api/agent/jobs/offline-goal',r=>r.fulfill({json:++polls<2?{status:'running'}:{status:'completed',summary:'Verified offline agent outcome.',tool_count:2}}));
 await p.route('**/api/realtime/sessions**',r=>{const u=r.request().url(),m=r.request().method();if(u.endsWith('/agent')){goals.push(r.request().postDataJSON().goal);return r.fulfill({json:{job:'offline-goal'}});}if(u.endsWith('/command')){commands++;return r.fulfill({json:{reply:'Test driver accepted the command; no real Windows action occurred.'}});}if(m==='POST'&&u.endsWith('/sessions')){starts++;return r.fulfill({json:{id:'offline-session',sdp:'v=0\r\noffline answer',seconds:20}});}if(m==='DELETE')stops++;return r.fulfill({json:{ok:true}});});
 await p.goto(process.env.JARVIS_TEST_URL||'http://127.0.0.1:5031');await p.locator('.main-nav [data-page="communications"]').click();await p.waitForFunction(()=>!document.getElementById('paid-voice-toggle').disabled);await p.locator('#paid-voice-toggle').click();
 await p.waitForFunction(()=>document.getElementById('paid-voice-status').textContent.includes('connected'));assert.equal(starts,1);
 await p.evaluate(()=>fakeChannel.onmessage({data:JSON.stringify({type:'output_audio_buffer.started'})}));assert.equal(await p.locator('#reactor-state').textContent(),'SPEAKING');
 await p.evaluate(()=>fakeChannel.onmessage({data:JSON.stringify({type:'output_audio_buffer.cleared'})}));assert.equal(await p.locator('#reactor-state').textContent(),'LISTENING');
 await p.evaluate(()=>fakeChannel.onmessage({data:JSON.stringify({type:'conversation.item.input_audio_transcription.completed',transcript:'Open Spotify',event_id:'event_one'})}));assert.equal(await p.locator('#last-utterance').textContent(),'Open Spotify');
 await p.evaluate(()=>fakeChannel.onmessage({data:JSON.stringify({type:'response.function_call_arguments.done',name:'approved_local_command',arguments:JSON.stringify({command:'open Spotify'}),call_id:'call_offline'})}));await p.waitForFunction(()=>fakeChannel.sent.some(x=>x.type==='response.create'));assert.equal(commands,1);
 await p.evaluate(()=>fakeChannel.onmessage({data:JSON.stringify({type:'response.function_call_arguments.done',name:'agent_request',arguments:JSON.stringify({goal:'Could you get the other project ready and chuck my music on?'}),call_id:'call_agent_goal'})}));
 await p.waitForFunction(()=>fakeChannel.sent.some(x=>x.item?.call_id==='call_agent_goal'));
 assert.deepEqual(goals,['Could you get the other project ready and chuck my music on?']);assert.ok(polls>=2);const output=await p.evaluate(()=>JSON.parse(fakeChannel.sent.find(x=>x.item?.call_id==='call_agent_goal').item.output));assert.equal(output.summary,'Verified offline agent outcome.');
 await p.locator('#paid-voice-toggle').click();await p.waitForFunction(()=>document.getElementById('paid-voice-status').textContent.includes('off'));assert.equal(stops,1);assert.equal(await p.evaluate(()=>fakePeer.connectionState),'closed');
 assert.deepEqual(errors,[]);console.log('PASS Mocked paid WebRTC connection, genuine provider-event speaking/listening states, interrupted output, transcripts, bounded tool dispatch, natural agent delegation with observed completion and one-button stop. No paid requests.');
 }finally{await b.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
