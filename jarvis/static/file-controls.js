/* Files stay local. Edits use versioned previews and the existing confirmation gate. */
'use strict';
window.JarvisFiles = (()=>{
 const get=id=>document.getElementById(id);
 let hooks,selected=null,folder='',root='';
 const text=(tag,value)=>{const n=document.createElement(tag);n.textContent=value;return n;};
 function button(label,fn){const b=text('button',label);b.type='button';b.onclick=()=>hooks.action(fn);return b;}
 function selection(){return {root:get('files-root').value,relative:get('files-relative').value};}
 function clear(){selected=null;get('file-editor').value='';get('edit-preview').textContent='';get('editor-filename').textContent='No file loaded';get('preview-text-edit').disabled=true;}
 async function prepared(data){get('edit-preview').textContent=data.diff||data.action.preview;await window.JarvisComputer.refresh();hooks.notify('Preview ready. Review the changes, close this panel and use Confirm action on the dashboard.');}
 async function browse(){
  clear();const chosen=selection();const data=await hooks.api('/api/files/browse','POST',chosen);root=chosen.root;folder=chosen.relative;
  get('files-status').textContent=data.limited?'Showing up to 300 entries. Open a subfolder or use filename search for more.':'Folder loaded locally. No file content was sent to AI.';
  const rows=data.items.map(item=>{const row=text('div','');row.className='upgrade-row';row.append(text('strong',(item.directory?'Folder · ':'File · ')+item.name));
   if(item.directory)row.append(button('Browse',async()=>{get('files-relative').value=item.relative;await browse();}));
   else row.append(button('Edit text',async()=>{const data=await hooks.api('/api/files/load','POST',{root,relative:item.relative});selected={root,relative:item.relative,version:data.version};get('file-editor').value=data.content;get('editor-filename').textContent=root+':'+item.relative;get('preview-text-edit').disabled=false;get('edit-preview').textContent='';}));
   row.append(button('Preview open',async()=>prepared(await hooks.api('/api/workspace/preview','POST',{root,relative:item.relative,kind:'open'}))));return row;
  });
  if(data.parent!==null)rows.unshift(button('↑ Parent folder',async()=>{get('files-relative').value=data.parent;await browse();}));
  get('files-list').replaceChildren(...rows);
 }
 async function revisions(){const data=await hooks.api('/api/files/revisions');get('file-revisions').replaceChildren(...data.items.map(item=>{
  const row=text('div','');row.className='upgrade-row';row.append(text('strong',item.root+':'+item.relative),text('p',item.created+' UTC · '+item.status));
  if(item.status==='saved')row.append(button('Preview undo',async()=>prepared(await hooks.api('/api/files/revisions/'+item.id+'/preview','POST',{}))));return row;
 }));}
 return {async refresh(data){
  const choice=get('files-root').value;get('files-root').replaceChildren(...data.roots.map(x=>new Option(x.alias+(x.allow_edit?' · text editing allowed':''),x.alias)));
  if(data.roots.some(x=>x.alias===choice))get('files-root').value=choice;else{clear();get('files-relative').value='';get('files-list').replaceChildren();}
  await revisions();
 },init(options){hooks=options;
  get('files-root').onchange=()=>{clear();get('files-relative').value='';get('files-list').replaceChildren();};
  get('files-browse').onsubmit=e=>{e.preventDefault();hooks.action(browse);};
  get('preview-text-edit').onclick=()=>hooks.action(async()=>{if(!selected)throw new Error('Load a text file first.');await prepared(await hooks.api('/api/files/preview','POST',{...selected,kind:'edit',content:get('file-editor').value}));});
  get('file-create-form').onsubmit=e=>{e.preventDefault();hooks.action(async()=>prepared(await hooks.api('/api/files/preview','POST',{root:get('files-root').value,relative:get('create-relative').value,kind:get('create-kind').value,content:get('create-content').value})));};
  get('refresh-revisions').onclick=()=>hooks.action(revisions);
  get('website-form').onsubmit=e=>{e.preventDefault();hooks.command('open '+get('website-url').value);};
  document.querySelectorAll('[data-windows-page]').forEach(b=>b.onclick=()=>hooks.command('open windows '+b.dataset.windowsPage));
  hooks.action(async()=>{const data=await hooks.api('/api/files/locations');get('common-location').replaceChildren(new Option('Choose a Windows folder or drive…',''),...data.locations.map(x=>new Option(x.name+' · '+x.path,JSON.stringify(x))));get('common-location').disabled=!data.supported;});
  get('common-location').onchange=()=>{if(!get('common-location').value)return;const item=JSON.parse(get('common-location').value);get('root-alias').value=item.name;get('root-path').value=item.path;};
 }};
})();
