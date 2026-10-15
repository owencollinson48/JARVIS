/* Local Windows controls UI. No path or action payload is sent to the AI model. */
'use strict';
window.JarvisComputer = (() => {
  const get = id => document.getElementById(id);
  let hooks, selected = null;
  const text = (tag, value, cls) => {const el=document.createElement(tag);el.textContent=value;if(cls)el.className=cls;return el;};
  function render(data) {
    selected=data.pending;
    get('computer-preview').hidden=!selected;
    get('computer-preview-text').textContent=selected?.preview||'';
    get('computer-enabled').checked=data.enabled;
    get('computer-enabled').disabled=!data.supported;
    get('computer-platform').textContent=data.supported ? `Windows controls ${data.enabled?'enabled':'off'}. Playback and volume are immediate; apps/files/searches need confirmation.` : 'This running machine is not Windows. Configure and test computer controls on your Windows PC.';
    get('computer-target-form').querySelector('button').disabled=!data.supported;
    get('computer-targets').replaceChildren(...data.targets.map(target=>{
      const row=text('div','', 'memory-row'),detail=text('div','');
      detail.append(text('strong',`${target.alias} · ${target.kind}`),text('p',target.path,'memory-text'));
      const remove=text('button','Remove approval');remove.onclick=()=>{
        if(confirm(`Remove approval for ${target.alias}?`))hooks.action(async()=>{await hooks.api('/api/computer/targets/'+encodeURIComponent(target.alias),'DELETE');await reload();});
      };
      row.append(detail,remove);return row;
    }));
    get('computer-history').replaceChildren(...(data.recent.length?data.recent.map(item=>{
      const row=text('div','','computer-log');row.append(text('strong',`${item.status.toUpperCase()} · ${item.preview}`),text('p',item.result||'Awaiting confirmation.'));return row;
    }):[text('p','No computer actions recorded.','empty')]));
  }
  async function reload() {
    try {render(await hooks.api('/api/computer/state'));}
    catch {get('computer-platform').textContent='Computer-control status could not be loaded. Refresh the page.';selected=null;get('computer-preview').hidden=true;}
  }
  return {
    get pendingId(){return selected?.id;},
    init(options) {
      hooks=options;
      get('confirm-computer').onclick=()=>hooks.command('confirm action');
      get('cancel-computer').onclick=()=>hooks.command('cancel action');
      get('computer-enabled').onchange=()=>hooks.action(async()=>{
        const enabled=get('computer-enabled').checked;get('computer-enabled').disabled=true;
        try {await hooks.api('/api/computer/settings','PUT',{enabled});}finally{await reload();}
      });
      get('computer-target-form').onsubmit=event=>{event.preventDefault();hooks.action(async()=>{
        await hooks.api('/api/computer/targets','POST',{alias:get('target-alias').value,kind:get('target-kind').value,path:get('target-path').value});
        get('computer-target-form').reset();await reload();hooks.notify('Target approved locally. Opening it will still require confirmation.');
      });};
    },
    refresh:reload
  };
})();
