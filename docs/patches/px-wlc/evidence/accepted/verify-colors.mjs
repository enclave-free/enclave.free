import {createRequire} from 'node:module';
import {writeFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
const {chromium}=createRequire('/tmp/px-wlc-browser-tools/package.json')('playwright');
const out=new URL('./',import.meta.url).pathname;
const base='http://127.0.0.1:4178';
await fetch(base+'/__fixture?mode=enabled&approved=true&fail=false');
const browser=await chromium.launch();
const checks=[];
const tokens=['--color-surface','--color-surface-raised','--color-surface-overlay','--color-text','--color-text-secondary','--color-text-muted','--color-border','--color-accent','--color-accent-hover','--px-action','--px-action-hover','--px-action-text','--px-action-border'];
const palette=async(page,selector)=>page.locator(selector).evaluate((el,keys)=>Object.fromEntries(keys.map(k=>[k,getComputedStyle(el).getPropertyValue(k).trim()])),tokens);
const lum=c=>{if(c.length===4)c='#'+c.slice(1).split('').map(x=>x+x).join('');let v=c.slice(1).match(/../g).map(x=>parseInt(x,16)/255).map(x=>x<=.04045?x/12.92:((x+.055)/1.055)**2.4);return v.reduce((s,x,i)=>s+x*[.2126,.7152,.0722][i],0)};
const contrast=(a,b)=>(Math.max(lum(a),lum(b))+.05)/(Math.min(lum(a),lum(b))+.05);
try {
for (const theme of ['light','dark']) {
 const context=await browser.newContext({viewport:{width:1440,height:1000},colorScheme:theme,reducedMotion:'reduce'});
 await context.addInitScript(()=>{localStorage.setItem('enclave_language','en');localStorage.setItem('enclave_language_explicit','1')});
 const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(base+'/auth');await page.locator('input[type=email]').waitFor();
 const entry=await palette(page,'.px-welcome');
 assert.equal(entry['--color-surface'],'#f5f9fd');assert.equal(entry['--px-action'],'#062d5c');assert.equal(entry['--color-accent'],'#0759a0');assert.equal(entry['--px-action-border'],'transparent');
 await page.evaluate(()=>localStorage.setItem('enclave_admin_pubkey','fixture-admin'));
 await page.goto(base+'/admin/users');await page.getByRole('heading',{name:'User Configuration',exact:true}).waitFor();
 const app=await palette(page,'body');
 if(theme==='light') assert.deepEqual(app,entry);
 else {assert.equal(app['--color-surface'],'#081f3d');assert.equal(app['--color-accent'],'#87c6ff');assert(contrast(app['--px-action-border'],app['--color-surface-raised'])>=3)}
 for(const key of ['--color-text','--color-text-secondary','--color-text-muted','--color-accent']) {
  for(const bg of ['--color-surface','--color-surface-raised','--color-surface-overlay']) assert(contrast(app[key],app[bg])>=4.5,`${theme} ${key} vs ${bg}`);
 }
 assert(contrast(app['--px-action'],app['--px-action-text'])>=4.5);
 assert.equal(await page.locator('.px-welcome').count(),0);
 if(theme==='dark'){const outline=await page.getByRole('button',{name:'Save user approval',exact:true}).evaluate(el=>{const s=getComputedStyle(el);return [s.outlineStyle,s.outlineWidth,s.outlineColor]});assert.deepEqual(outline,['solid','1px','rgb(105, 138, 172)']);}
 await page.evaluate(()=>document.fonts.ready);
 await page.screenshot({path:out+`admin-${theme}.png`,fullPage:true,animations:'disabled'});
 await page.evaluate(()=>localStorage.removeItem('enclave_admin_pubkey'));
 await page.goto(base+'/verify?token=fixture-valid');await page.waitForURL('**/chat');await page.getByRole('button',{name:'Settings',exact:true}).waitFor();
 await page.screenshot({path:out+`chat-${theme}.png`,fullPage:true,animations:'disabled'});
 await page.getByRole('button',{name:'Settings',exact:true}).click();
 await page.screenshot({path:out+`settings-${theme}.png`,fullPage:true,animations:'disabled'});
 await page.setViewportSize({width:320,height:800});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 assert.deepEqual(errors,[]);checks.push({theme,entry,app,checks:'Palette parity/adaptation, text/link/button/border contrast, admin scope, chat/settings, 320px fit, no uncaught errors'});
 await context.close();
}
await writeFile(out+'color-results.json',JSON.stringify(checks,null,2));console.log('Light/dark application palettes, contrast, admin/chat/settings and 320px checks pass.');
} finally {await browser.close();}
