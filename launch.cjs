'use strict';
const fs=require('node:fs'),os=require('node:os'),path=require('node:path');
function mask(value){if(typeof value==='string'&&value)process.stdout.write('::add-mask::'+value.replace(/%/g,'%25').replace(/\r/g,'%0D').replace(/\n/g,'%0A')+'\n');}
let root;
(async()=>{try{
 const cfg=JSON.parse(process.env.PRIVATE_CONFIGURATION||'{}');mask(process.env.PRIVATE_CONFIGURATION);for(const v of Object.values(cfg))mask(typeof v==='string'?v:JSON.stringify(v));
 root=fs.mkdtempSync(path.join(os.tmpdir(),'runner-private-'));fs.chmodSync(root,0o700);process.env.RUNNER_SECRETS_DIR=root;process.env.RUNNER_STATE_DIR=path.join(root,'state');
 for(const [field,file] of Object.entries({source_uri:'mongo-uri',encryption_key:'encryption-passphrase',remote_identity:'mega-email',remote_key:'mega-password'})){if(!cfg[field])throw Error('missing');fs.writeFileSync(path.join(root,file),cfg[field],{mode:0o600});}
 for(const [field,name] of Object.entries({namespace:'SOURCE_NAMESPACE',collection:'VALIDATION_COLLECTION',archive_prefix:'ARCHIVE_PREFIX',receipt_prefix:'RECEIPT_PREFIX',folder_name:'REMOTE_FOLDER_NAME',folder_handle:'REMOTE_FOLDER_HANDLE'})){if(!cfg[field])throw Error('missing');process.env[name]=cfg[field];}
 process.env.REQUIRED_INDEX_KEYS=JSON.stringify(cfg.required_index_keys||[]);process.env.MONGOMS_DISABLE_POSTINSTALL='1';
 if(process.env.CLOCK_RUN==='true'){if(!cfg.clock_timezone||!cfg.clock_hour)throw Error('missing');const hour=new Intl.DateTimeFormat('en-GB',{timeZone:cfg.clock_timezone,hour:'2-digit',hourCycle:'h23'}).format(new Date());if(hour!==cfg.clock_hour){console.log('Inactive clock slot');return;}}
 delete process.env.PRIVATE_CONFIGURATION;await require('./runner.cjs').main();
}catch{console.error('Private configuration or operation failed');process.exitCode=1;}finally{if(root)fs.rmSync(root,{recursive:true,force:true});}})();
