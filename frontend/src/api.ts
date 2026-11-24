import {formatApiError} from './errors';

export type User = { id: number; name: string; email: string; role: 'buyer'|'quarry'|'driver'|'admin' };
let access = '';
let refreshPromise: Promise<User | null> | null = null;
const sessionEndpoints = new Set(['/api/auth/login', '/api/auth/register', '/api/auth/refresh', '/api/auth/logout']);
export function clearToken() { access = ''; }
export function acceptSession(data: {accessToken:string;user:User}) { access=data.accessToken; return data.user; }
export async function refresh(): Promise<User|null> {
  if (!refreshPromise) refreshPromise = fetch('/api/auth/refresh', {method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:'{}'})
    .then(async r => { if(!r.ok){access='';return null;} return acceptSession(await r.json()); })
    .finally(()=>{refreshPromise=null;});
  return refreshPromise;
}
export async function api(path:string, method='GET', body?:unknown, retry=true): Promise<any> {
  const res=await fetch(path,{method,credentials:'same-origin',headers:{...(access?{Authorization:`Bearer ${access}`} : {}),...(body!==undefined?{'Content-Type':'application/json'}:{})},body:body===undefined?undefined:JSON.stringify(body)});
  if(res.status===401 && retry && !sessionEndpoints.has(path.split('?')[0])) {
    if(await refresh()) return api(path,method,body,false);
    window.dispatchEvent(new Event('session-ended'));
  }
  if(res.status===204)return null;
  const data=await res.json();
  if(!res.ok)throw new Error(formatApiError(data, path));
  return data;
}
