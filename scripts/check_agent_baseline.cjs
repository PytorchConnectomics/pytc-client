// Browser check of continuity and chat-to-editor navigation. No label edits or compute.
const {chromium}=require('playwright');
const fs=require('fs');
(async()=>{
 const b=await chromium.launch({headless:true,executablePath:process.env.PYTC_BROWSER_PATH||'/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge'});
 const p=await b.newPage({viewport:{width:1600,height:1000}});p.setDefaultTimeout(30000);
 const errors=[];p.on('pageerror',e=>errors.push(e.message));
 const origin=process.env.PYTC_CHECK_UI||'http://127.0.0.1:3001';
 const api=process.env.PYTC_CHECK_API||'http://127.0.0.1:4242';
 try {
  const before=await (await p.request.get(api+'/api/workflows/current')).json();
  await p.goto(origin);
  await p.getByText('Proofread',{exact:true}).first().waitFor();
  await p.waitForTimeout(2000);
  await p.reload();await p.getByText('Proofread',{exact:true}).first().waitFor();
  await p.waitForTimeout(1500);
  const after=await (await p.request.get(api+'/api/workflows/current')).json();
  if(before.workflow.id!==after.workflow.id)throw Error('Reload created a new workflow');
  await p.getByRole('button',{name:'What next?',exact:true}).click();
  await p.getByRole('region',{name:'assistant-action-show-workflow-status',exact:true}).last().waitFor();
  await p.getByPlaceholder('Message',{exact:true}).fill('Start proofreading');
  const[r]=await Promise.all([p.waitForResponse(r=>r.url().endsWith('/agent/query')&&r.request().method()==='POST'&&r.request().postDataJSON()?.query==='Start proofreading'),p.getByPlaceholder('Message',{exact:true}).press('Enter')]);
  const data=await r.json();if(!r.ok())throw Error(JSON.stringify(data));
  const action=data.actions?.find(a=>a.client_effects?.navigate_to==='mask-proofreading');
  if(!action)throw Error('No proofreading action: '+JSON.stringify(data));
  await p.getByRole('region',{name:'assistant-action-'+action.id,exact:true}).last().getByRole('button').click();
  await p.getByRole('button',{name:'Approve',exact:true}).last().click();
  await p.getByRole('button',{name:'Close assistant',exact:true}).click();
  await p.getByText('23 instances',{exact:true}).waitFor();
  await p.screenshot({path:'.logs/agent-prototype/baseline-chat.png'});
  const report={project_id:after.workflow.id,reload_preserved_project:true,proofreader_loaded:true,source:data.source,intent:data.intent,actions:data.actions.map(a=>({label:a.label,effects:a.client_effects})),errors,LLM_delegation_tested:false};
  fs.writeFileSync('.logs/agent-prototype/browser-check.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report));
  if(errors.length)throw Error('Browser errors recorded');
 }catch(e){await p.screenshot({path:'.logs/agent-prototype/browser-error.png'});console.log((await p.locator('body').innerText()).slice(-4000));throw e;}finally{await b.close();}
})().catch(e=>{console.error(e);process.exit(1)});
