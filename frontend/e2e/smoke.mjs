import {chromium} from '@playwright/test';
import {execFileSync} from 'node:child_process';
import {randomUUID} from 'node:crypto';
import {mkdirSync} from 'node:fs';
import {resolve} from 'node:path';
const python=resolve('../.venv/Scripts/python.exe');
const cwd=resolve('..');
const baseUrl=process.env.TEST_BASE_URL || 'http://127.0.0.1:5173';
const email=`ui-${randomUUID()}@example.com`,password=`Ui-${randomUUID()}-aA1!`;
let uid;
const browser=await chromium.launch({channel:'chrome',headless:true});
const context=await browser.newContext({viewport:{width:1440,height:1000}});
const page=await context.newPage();page.setDefaultTimeout(15000);
const errors=[];page.on('pageerror',e=>errors.push(e.message));
mkdirSync('test-results',{recursive:true});
async function fill(label,value){await page.getByLabel(label,{exact:true}).fill(String(value));}
async function save(){await page.getByRole('button',{name:'Išsaugoti',exact:true}).click();await page.locator('dialog').waitFor({state:'hidden'});}
try {
 await page.goto(baseUrl);await page.getByRole('heading',{name:'Karjerų katalogas'}).waitFor();
 await page.locator('.cards .card').first().waitFor();
 // Re-entering the current catalog must fetch again after clearing its rows.
 for(const click of [()=>page.getByRole('button',{name:'Katalogas',exact:true}).click(),()=>page.locator('header .brand').click(),()=>page.locator('footer .brand').click()]){
  await Promise.all([page.waitForResponse(r=>new URL(r.url()).pathname==='/api/quarries'&&r.request().method()==='GET'&&r.ok()),click()]);
  await page.locator('.cards .card').first().waitFor();
 }
 await page.getByRole('button',{name:'Registruotis',exact:true}).click();
 await fill('Vardas ir pavardė','UI administratorius');await fill('El. paštas',email);await fill('Slaptažodis',password);
 await page.locator('dialog').getByRole('button',{name:'Registruotis',exact:true}).click();await page.locator('dialog').waitFor({state:'hidden'});
 uid=Number(execFileSync(python,['-B','-c',"import sys;from app.db import pool,query;pool.open();r=query(\"UPDATE users SET role='admin' WHERE email=%s RETURNING id\",(sys.argv[1],));print(r[0]['id']);pool.close()",email],{cwd,encoding:'utf8'}).trim());
 await page.getByRole('button',{name:'Atsijungti',exact:true}).click();await page.getByRole('button',{name:'Prisijungti',exact:true}).click();
 await fill('El. paštas',email);await fill('Slaptažodis',password);await page.locator('dialog').getByRole('button',{name:'Prisijungti',exact:true}).click();await page.locator('dialog').waitFor({state:'hidden'});
 await page.getByRole('button',{name:'Pridėti karjerą'}).click();
 await fill('Karjero pavadinimas','UI test karjeras');await fill('Miestas','UI miestas');await fill('Adresas','UI gatvė 20');await fill('Telefonas (+370...)','+37060000888');await fill('Aprašymas','UI test karjero aprašymas');await fill('Platuma',54);await fill('Ilguma',25);await save();
 await fill('Ieškoti karjero','UI test');await page.getByRole('heading',{name:'UI test karjeras',exact:true}).waitFor();
 await page.getByRole('button',{name:'Redaguoti UI test karjeras',exact:true}).click();await fill('Karjero pavadinimas','UI test karjeras pakeistas');await save();
 await page.getByRole('button',{name:'Peržiūrėti pasiūlymus'}).click();
 await page.getByRole('button',{name:'Pridėti pasiūlymą'}).click();await fill('Pasiūlymo pavadinimas','UI smėlis');await fill('Frakcija (pvz. 0–2 mm)','0-2 mm');await fill('Aprašymas','UI smėlio aprašymas');await fill('Kaina, €/t',15);await page.getByLabel('Galima užsakyti').check();await save();
 await page.getByRole('button',{name:'Redaguoti',exact:true}).click();await fill('Kaina, €/t',18);await save();
 await page.getByRole('button',{name:'Užsakyti',exact:true}).click();await fill('Telefonas (+370...)','+37060000888');await fill('Pristatymo adresas','UI pristatymo g. 10');await fill('Kiekis, t',2);await save();
 await page.locator('.card').getByRole('button',{name:'Užsakymai',exact:true}).click();await page.locator('.order-card').waitFor();
 await page.getByRole('button',{name:/Redaguoti užsakymą/}).click();await fill('Kiekis, t',3);await save();
 await page.getByRole('button',{name:'Suvestinė',exact:true}).click();await page.getByText('Neatšauktų užsakymų suma').waitFor();await page.getByRole('button',{name:'Uždaryti',exact:true}).click();
 await page.getByRole('button',{name:/Ištrinti užsakymą/}).click();await page.locator('dialog').getByRole('button',{name:'Ištrinti',exact:true}).click();await page.locator('dialog').waitFor({state:'hidden'});
 await page.getByRole('button',{name:'Atgal į pasiūlymus'}).click();await page.getByRole('button',{name:'Ištrinti',exact:true}).click();await page.locator('dialog').getByRole('button',{name:'Ištrinti',exact:true}).click();await page.locator('dialog').waitFor({state:'hidden'});
 await page.getByRole('button',{name:'Visi karjerai'}).click();await page.getByRole('button',{name:'Ištrinti UI test karjeras pakeistas',exact:true}).click();await page.locator('dialog').getByRole('button',{name:'Ištrinti',exact:true}).click();await page.locator('dialog').waitFor({state:'hidden'});
 await fill('Ieškoti karjero','');await page.locator('.card').first().waitFor();
 await page.reload();await page.getByRole('button',{name:'Naudotojai',exact:true}).waitFor();
 await page.locator('.card').first().waitFor();await page.waitForTimeout(350);
 await page.screenshot({path:'test-results/desktop.png',fullPage:true});
 // A protected auth endpoint returning 401 must refresh and retry, too.
 let usersExpired=false;
 await page.route('**/api/auth/users',async route=>{
  if(!usersExpired){usersExpired=true;await route.fulfill({status:401,contentType:'application/json',body:JSON.stringify({error:{message:'Expired access token'}})});}
  else await route.continue();
 });
 await page.setViewportSize({width:390,height:844});await page.getByRole('button',{name:'Atverti meniu'}).click();
 await Promise.all([page.waitForResponse(r=>new URL(r.url()).pathname==='/api/auth/refresh'&&r.ok()),page.getByRole('button',{name:'Naudotojai',exact:true}).click()]);
 await page.locator('table').waitFor();await page.unroute('**/api/auth/users');
 await page.getByRole('button',{name:'Atverti meniu'}).click();await page.getByRole('button',{name:'Katalogas',exact:true}).click();await page.locator('.card').first().waitFor();
 await page.getByRole('button',{name:'Atverti meniu'}).click();
 await Promise.all([page.waitForResponse(r=>new URL(r.url()).pathname==='/api/quarries'&&r.request().method()==='GET'&&r.ok()),page.getByRole('button',{name:'Katalogas',exact:true}).click()]);
 await page.locator('.cards .card').first().waitFor();
 if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw new Error('Mobile horizontal overflow');
 await page.waitForTimeout(350);
 await page.screenshot({path:'test-results/mobile.png',fullPage:true});
 await page.getByRole('button',{name:'Atsijungti',exact:true}).click();await page.reload();await page.getByRole('button',{name:'Prisijungti',exact:true}).waitFor();
 if(errors.length)throw new Error(errors.join('\n'));
 console.log('PASS: UI register/login, all 3 CRUDs, summary, refresh after reload, logout, mobile navigation, no horizontal overflow or JS errors.');
} catch(e){console.error('Browser errors:',errors);await page.screenshot({path:'test-results/failure.png',fullPage:true});throw e;}
finally{
 await browser.close();
 if(uid)execFileSync(python,['-B','-c',"import sys;from app.db import pool;pool.open();c=pool.getconn();u=int(sys.argv[1]);c.execute('DELETE FROM orders WHERE owner_id=%s OR offer_id IN (SELECT o.id FROM offers o JOIN quarries q ON q.id=o.quarry_id WHERE q.owner_id=%s)',(u,u));c.execute('DELETE FROM offers WHERE quarry_id IN (SELECT id FROM quarries WHERE owner_id=%s)',(u,));c.execute('DELETE FROM quarries WHERE owner_id=%s',(u,));c.execute('DELETE FROM users WHERE id=%s',(u,));c.commit();pool.putconn(c);pool.close()",String(uid)],{cwd});
}
