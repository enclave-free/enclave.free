import {createRequire} from 'node:module';
import assert from 'node:assert/strict';
import {writeFile} from 'node:fs/promises';
const {chromium}=createRequire('/tmp/px-wlc-browser-tools/package.json')('playwright');
await fetch('http://127.0.0.1:4178/__fixture?mode=enabled&approved=false&fail=false');
const browser=await chromium.launch();
const page=await browser.newPage({viewport:{width:1440,height:900}});
await page.addInitScript(()=>{localStorage.setItem('enclave_language','en');localStorage.setItem('enclave_language_explicit','1');});
try {
await page.goto('http://127.0.0.1:4178/auth');
await page.locator('input[type=email]').waitFor();
const expected=['LIBERATOR','Change language','Sign Up','Log In','text','email','Continue with Email','Sign in with Nostr'];
const results=[];
for(const label of expected) {
 await page.keyboard.press('Tab');
 const detail=await page.evaluate(()=>{const el=document.activeElement; const s=getComputedStyle(el); const p=getComputedStyle(el.parentElement); return {name:el.getAttribute('aria-label')||el.getAttribute('type')==='text'&&'text'||el.getAttribute('type')==='email'&&'email'||el.textContent.trim(),focusVisible:el.matches(':focus-visible'),outline:s.outlineStyle,width:s.outlineWidth,shadow:s.boxShadow,parentShadow:p.boxShadow};});
 assert(detail.name.includes(label),`${label}: ${JSON.stringify(detail)}`);
 assert(detail.focusVisible, `${label}: focus-visible`);
 assert((detail.outline!=='none' && parseFloat(detail.width)>0)||detail.shadow!=='none'||detail.parentShadow!=='none',`${label}: visible focus treatment`);
 results.push({label,...detail});
}
const language=page.getByRole('button',{name:'Change language',exact:true});
await language.focus(); await page.keyboard.press('Enter'); await page.getByRole('menu').waitFor();
await page.keyboard.press('Tab'); assert(await page.evaluate(()=>document.activeElement.getAttribute('role')==='menuitemradio'));
await language.focus(); await page.keyboard.press('Enter'); assert.equal(await page.getByRole('menu').count(),0);
await writeFile(new URL('./keyboard-results.json',import.meta.url),JSON.stringify(results,null,2));
console.log('Eight auth controls have correct tab order and visible keyboard focus; language menu opens and is keyboard reachable.');
} finally {await browser.close();}
