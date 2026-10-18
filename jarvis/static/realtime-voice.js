/* Optional paid WebRTC audio. No API key or ephemeral credential enters this code. */
'use strict';
window.JarvisRealtime = (()=>{
 let hooks,pc,stream,audio,channel,identifier,timer,active=false,starting=false,generation=0,meterContext,meterFrame;
 const get=id=>document.getElementById(id);
 function status(value){get('paid-voice-status').textContent=value;}
 async function stop(){
  generation++;active=false;starting=false;clearTimeout(timer);cancelAnimationFrame(meterFrame);meterContext?.close().catch(()=>{});meterContext=null;window.JarvisHUD.voice.callbacks.level(0,Array(24).fill(0));
  channel?.close();pc?.close();stream?.getTracks().forEach(t=>t.stop());if(audio){audio.pause();audio.srcObject=null;}
  const old=identifier;identifier=null;get('paid-voice-toggle').textContent='Start paid voice';
  status('Paid voice off.');get('session-status').textContent='CONVERSATION OFF';
  get('mic-status').textContent='Microphone off';get('reactor').dataset.state='idle';get('reactor-state').textContent='READY';
  if(old)try{await hooks.api('/api/realtime/sessions/'+old,'DELETE');}catch{status('Audio stopped locally. Server stop could not be confirmed; the configured session timer still applies while the server runs.');}
 }
 async function toggle(){
  if(active||starting){await stop();return;}
  starting=true;const version=++generation;
  try{
   const voiceLimits=await hooks.api('/api/realtime/state');if(version!==generation)return;
   if(!confirm('Paid OpenAI audio and transcription charges apply. Microphone audio, saved tasks, memory and recent conversation are shared with OpenAI. Maximum '+(voiceLimits.seconds||180)+' seconds; '+(voiceLimits.daily_limit||2)+' session attempts per 24 hours. Local tools follow your saved computer permissions; previews need the on-screen confirmation. Start?')){starting=false;return;}
   window.JarvisHUD.stop();
   status('Requesting microphone…');const acquired=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true}});
   if(version!==generation){acquired.getTracks().forEach(t=>t.stop());return;}
   stream=acquired;
   const Meter=window.AudioContext||window.webkitAudioContext;if(Meter){meterContext=new Meter();await meterContext.resume();const analyser=meterContext.createAnalyser();analyser.fftSize=512;meterContext.createMediaStreamSource(stream).connect(analyser);const samples=new Uint8Array(512);const measure=()=>{if(version!==generation)return;analyser.getByteTimeDomainData(samples);const rms=Math.min(1,Math.sqrt(samples.reduce((sum,x)=>sum+((x-128)/128)**2,0)/samples.length)*4);window.JarvisHUD.voice.callbacks.level(rms,Array(24).fill(rms));meterFrame=requestAnimationFrame(measure);};measure();}
   if(version!==generation)return;
   pc=new RTCPeerConnection();audio=new Audio();audio.autoplay=true;
   pc.ontrack=e=>{audio.srcObject=e.streams[0];audio.play().catch(()=>status('Browser blocked audio. Stop and restart using this button.'));};
   pc.onconnectionstatechange=()=>{if(version!==generation)return;if(pc.connectionState==='connected'){status('Paid voice connected · speak naturally; you can interrupt.');get('reactor').dataset.state='listening';get('reactor-state').textContent='LISTENING';}if(['failed','disconnected'].includes(pc.connectionState))stop();};
   stream.getTracks().forEach(t=>pc.addTrack(t,stream));channel=pc.createDataChannel('oai-events');
   channel.onmessage=event=>{
    let data;try{data=JSON.parse(event.data);}catch{return;}
    if(data.type==='response.function_call_arguments.done'&&data.name==='agent_request'){
     let args;try{args=JSON.parse(data.arguments);}catch{return;}
     const ownGeneration=generation,ownChannel=channel;
     hooks.api('/api/realtime/sessions/'+identifier+'/agent','POST',{goal:args.goal,call_id:data.call_id}).then(async result=>{
      let outcome=result;if(result.job){window.JarvisAgent.watch(result.job);while(ownGeneration===generation&&ownChannel.readyState==='open'){const job=await hooks.api('/api/agent/jobs/'+result.job);if(['completed','failed','cancelled','interrupted'].includes(job.status)){outcome={status:job.status,summary:job.summary,tool_count:job.tool_count};break;}await new Promise(resolve=>setTimeout(resolve,1000));}}
      if(ownGeneration===generation&&ownChannel.readyState==='open'){ownChannel.send(JSON.stringify({type:'conversation.item.create',item:{type:'function_call_output',call_id:data.call_id,output:JSON.stringify(outcome)}}));ownChannel.send(JSON.stringify({type:'response.create'}));}
     }).catch(error=>status(error.message));
    }
    if(data.type==='response.function_call_arguments.done'&&data.name==='approved_local_command'){
     let args;try{args=JSON.parse(data.arguments);}catch{return;}
     hooks.api('/api/realtime/sessions/'+identifier+'/command','POST',{command:args.command,call_id:data.call_id}).then(async result=>{if(channel?.readyState==='open'){channel.send(JSON.stringify({type:'conversation.item.create',item:{type:'function_call_output',call_id:data.call_id,output:JSON.stringify(result)}}));channel.send(JSON.stringify({type:'response.create'}));}await window.JarvisComputer.refresh();window.dispatchEvent(new Event('jarvis-data-change'));}).catch(error=>{status(error.message);stop();});
    }
    if(data.type==='error'){status('Voice provider reported an error. Check billing/access.');stop();return;}
    const user=data.type==='conversation.item.input_audio_transcription.completed',assistant=data.type==='response.output_audio_transcript.done';
    if(user||assistant){
     const content=data.transcript;if(!content)return;
     if(user&&/^(?:jarvis[, ]+)?(?:please )?(?:stop everything|stop|cancel that|don['’]t do that|do not do that)[.!?]?$/i.test(content.trim())){window.dispatchEvent(new Event('jarvis-emergency'));return;}
     if(user&&/^(?:jarvis[, ]+)?(?:stop listening|end conversation|turn off jarvis)[.!?]?$/i.test(content.trim())){stop();return;}
     get(user?'last-utterance':'last-response').textContent=content;
     if(identifier)hooks.api('/api/realtime/sessions/'+identifier+'/transcript','POST',{role:user?'user':'assistant',content:content.slice(0,8000),event:data.event_id||data.item_id}).then(()=>window.dispatchEvent(new Event('jarvis-data-change'))).catch(()=>status('Voice transcript could not be saved.'));
    }
    if(data.type==='input_audio_buffer.speech_started'){get('reactor').dataset.state='listening';get('reactor-state').textContent='LISTENING';}
    if(data.type==='output_audio_buffer.started'){get('reactor').dataset.state='speaking';get('reactor-state').textContent='SPEAKING';}
    if(['output_audio_buffer.stopped','output_audio_buffer.cleared'].includes(data.type)){get('reactor').dataset.state='listening';get('reactor-state').textContent='LISTENING';}
   };
   await pc.setLocalDescription(await pc.createOffer());
   // Wait for the actual local SDP including gathered candidates.
   if(pc.iceGatheringState!=='complete')await new Promise(resolve=>{const deadline=setTimeout(resolve,1500);pc.addEventListener('icegatheringstatechange',()=>{if(pc?.iceGatheringState==='complete'){clearTimeout(deadline);resolve();}});});
   if(version!==generation)return;
   const result=await hooks.api('/api/realtime/sessions','POST',{sdp:pc.localDescription.sdp,paid_consent:true});
   if(version!==generation){await hooks.api('/api/realtime/sessions/'+result.id,'DELETE');return;}
   identifier=result.id;await pc.setRemoteDescription({type:'answer',sdp:result.sdp});
   active=true;starting=false;get('paid-voice-toggle').textContent='Stop paid voice';status('Negotiating paid voice media connection… Configured session timer is active.');
   get('session-status').textContent='PAID VOICE ON';get('mic-status').textContent='Paid voice microphone active';
   timer=setTimeout(stop,result.seconds*1000);
  }catch(error){if(version===generation){await stop();status(error.message||'Voice connection failed. No automatic retry.');}}
 }
 return {init(options){hooks=options;get('paid-voice-toggle').onclick=()=>hooks.action(toggle);document.addEventListener('keydown',e=>{if(e.key==='Escape')stop();});window.addEventListener('pagehide',()=>stop());},stop,get active(){return active||starting;}};
})();
