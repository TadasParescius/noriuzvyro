import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import ts from 'typescript';

const source=readFileSync(new URL('../src/api.ts',import.meta.url),'utf8');
const javascript=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022}}).outputText;
let instance=0;
const freshClient=()=>import('data:text/javascript;base64,'+Buffer.from(javascript).toString('base64')+'#'+instance++);
const user={id:1,name:'Test administrator',email:'test@example.com',role:'admin'};
const response=(status,body)=>new Response(JSON.stringify(body),{status,headers:{'Content-Type':'application/json'}});

for(const [path,method,body] of [
 ['/api/auth/users','GET',undefined],
 ['/api/auth/me','GET',undefined],
 ['/api/auth/users/2/role','PATCH',{role:'quarry'}],
]){
 test(`Expired access token is refreshed for ${method} ${path}`,async t=>{
  const original=globalThis.fetch;
  t.after(()=>{globalThis.fetch=original;});
  const calls=[];
  globalThis.fetch=async(url,options)=>{
   calls.push({url,...options});
   if(calls.length===1)return response(401,{error:{message:'Expired access token'}});
   if(url==='/api/auth/refresh')return response(200,{accessToken:'new-access',user});
   return response(200,{saved:true});
  };
  const client=await freshClient();client.acceptSession({accessToken:'old-access',user});
  assert.deepEqual(await client.api(path,method,body),{saved:true});
  assert.deepEqual(calls.map(c=>c.url),[path,'/api/auth/refresh',path]);
  assert.equal(calls[0].headers.Authorization,'Bearer old-access');
  assert.equal(calls[2].headers.Authorization,'Bearer new-access');
  assert.equal(calls[2].method,method);
  assert.equal(calls[2].body,body===undefined?undefined:JSON.stringify(body));
 });
}

test('Invalid login does not trigger a refresh or retry',async t=>{
 const original=globalThis.fetch;t.after(()=>{globalThis.fetch=original;});
 const calls=[];
 globalThis.fetch=async url=>{calls.push(url);return response(401,{error:{message:'Invalid credentials'}});};
 const client=await freshClient();
 await assert.rejects(client.api('/api/auth/login','POST',{email:user.email,password:'wrong'}),/Invalid credentials/);
 assert.deepEqual(calls,['/api/auth/login']);
});

test('Expired refresh token ends the session without repeating a role change',async t=>{
 const originalFetch=globalThis.fetch,originalWindow=globalThis.window;
 t.after(()=>{globalThis.fetch=originalFetch;if(originalWindow===undefined)delete globalThis.window;else globalThis.window=originalWindow;});
 const events=[],calls=[];
 globalThis.window={dispatchEvent:event=>events.push(event.type)};
 globalThis.fetch=async url=>{calls.push(url);return response(401,{error:{message:'Session expired'}});};
 const client=await freshClient();client.acceptSession({accessToken:'expired-access',user});
 await assert.rejects(client.api('/api/auth/users/2/role','PATCH',{role:'driver'}),/Session expired/);
 assert.deepEqual(calls,['/api/auth/users/2/role','/api/auth/refresh']);
 assert.deepEqual(events,['session-ended']);
});
