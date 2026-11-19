'use strict';
const $=id=>document.getElementById(id);
const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const today=()=>{const now=new Date();return [now.getFullYear(),String(now.getMonth()+1).padStart(2,'0'),String(now.getDate()).padStart(2,'0')].join('-');};
const currentYear=new Date().getFullYear();
let savedSnapshot=null;
const uid=()=>crypto.randomUUID();
const sum=(rows,key)=>rows.reduce((s,r)=>s+Number(r[key]||0),0);
const COMPANY={name:'Siamsil Technologies, Inc.',short:'Siamsil',product:'Church Hub',version:'2.1.0',year:2026};
let currencyCode='USD';
const money=cents=>{try{return new Intl.NumberFormat('en-US',{style:'currency',currency:currencyCode}).format(cents/100);}catch{return new Intl.NumberFormat('en-US',{style:'currency',currency:'USD'}).format(cents/100);}};
const date=value=>value?new Date(value+'T12:00:00').toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'}):'—';
const cents=value=>{
  if(!/^\d+(\.\d{1,2})?$/.test(String(value)))throw new Error('Enter an amount with up to two decimal places.');
  const [whole,fraction='']=String(value).split('.');
  const amount=Number(whole)*100+Number(fraction.padEnd(2,'0'));
  if(!Number.isSafeInteger(amount)||amount<=0)throw new Error('Enter a positive amount within the supported range.');
  return amount;
};
const icon=name=>'<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'+({
  church:'<path d="M12 2v7m-3-4h6M3 21V11l9-5 9 5v10zM9 21v-7h6v7"/>',
  home:'<path d="m3 10 9-7 9 7v11H3zM9 21v-8h6v8"/>',
  people:'<circle cx="8" cy="8" r="3"/><path d="M2 21v-3a6 6 0 0 1 12 0v3m2-16a3 3 0 0 1 0 6m2 3a5 5 0 0 1 4 5v2"/>',
  giving:'<rect x="2" y="5" width="20" height="14" rx="2"/><circle cx="12" cy="12" r="3"/><path d="M5 9h1m12 6h1"/>',
  file:'<path d="M6 3h8l4 4v14H6zM13 3v5h5M9 12h6m-6 4h6"/>',
  calendar:'<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v5m8-5v5"/>',
  check:'<path d="m4 12 5 5L20 6"/>',add:'<path d="M12 5v14M5 12h14"/>',
  settings:'<circle cx="12" cy="12" r="3"/><path d="m9 3-1 3-3 1-2 4 2 2v4l4 2 3-1 3 1 4-2v-4l2-2-2-4-3-1-1-3z"/>',
  print:'<path d="M7 8V3h10v5m0 9h4V8H3v9h4m0-4h10v8H7z"/>',
  book:'<path d="M4 4h6a2 2 0 0 1 2 2v14a2 2 0 0 0-2-2H4zM20 4h-6a2 2 0 0 0-2 2v14a2 2 0 0 1 2-2h6z"/>',
  mail:'<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m4 7 8 6 8-6"/>'
}[name]||'<path d="M4 6h16M4 12h16M4 18h16"/>')+'</svg>';
const btn=(text,action,key='',style='secondary',glyph)=>'<button type="button" class="btn '+style+'" data-action="'+action+'" data-key="'+esc(key)+'">'+(glyph?icon(glyph):'')+esc(text)+'</button>';
const submit=(text='Save Record')=>'<button type="submit" class="btn gold">'+icon('check')+esc(text)+'</button>';
const field=(label,name,value='',opts={})=>{
  const required=opts.required?' required':'';
  let input='<input name="'+name+'" value="'+esc(value)+'" type="'+(opts.type||'text')+'"'+required+(opts.min!==undefined?' min="'+opts.min+'"':'')+(opts.step?' step="'+opts.step+'"':'')+'>';
  if(opts.options)input='<select name="'+name+'"'+required+'>'+opts.options.map(opt=>{const [id,text]=Array.isArray(opt)?opt:[opt,opt];return '<option value="'+esc(id)+'"'+(String(id)===String(value)?' selected':'')+'>'+esc(text)+'</option>';}).join('')+'</select>';
  if(opts.area)input='<textarea name="'+name+'" rows="3"'+required+'>'+esc(value)+'</textarea>';
  return '<label class="'+(opts.full?'full':'')+'">'+esc(label)+(opts.required?' *':'')+input+'</label>';
};
const form=(kind,fields,button='Save Record',extra='')=>'<form data-form="'+kind+'"><div class="fields">'+fields+'</div><div class="actions spaced">'+submit(button)+extra+'</div></form>';
const delBtn=(kind,id,small)=>id?'<button type="button" class="btn danger'+(small?' small':'')+'" data-action="delete" data-kind="'+kind+'" data-key="'+esc(id)+'">Delete</button>':'';
const title=(heading,note,actions='')=>'<div class="title-row"><div><h1>'+esc(heading)+'</h1><small>'+esc(note)+'</small></div><div class="actions">'+actions+'</div></div>';
const panel=(heading,body)=>'<section class="card"><h3>'+esc(heading)+'</h3>'+body+'</section>';
const stat=(label,value,note,tone='')=>'<div class="stat"><span class="label">'+esc(label)+'</span><strong class="'+tone+'">'+esc(value)+'</strong><small>'+esc(note)+'</small></div>';
const table=(head,rows)=>'<div class="table-wrap"><table><thead><tr>'+head.map(h=>'<th scope="col">'+esc(h)+'</th>').join('')+'</tr></thead><tbody>'+(rows.length?rows.map(row=>'<tr>'+row.map(cell=>'<td>'+cell+'</td>').join('')+'</tr>').join(''):'<tr><td class="empty" colspan="'+head.length+'">No records for this selection.</td></tr>')+'</tbody></table></div>';
const note=text=>'<p class="muted">'+esc(text)+'</p>';
const badge=(text,style='')=>'<span class="tag '+style+'">'+esc(text)+'</span>';

function seed(){
  const year=currentYear, mm=new Date().getMonth()+1;
  const settings={church:'Grace Community Church',address:'1200 Community Way, Tulsa, OK 74103',email:'office@gracechurch.example',phone:'(918) 555-0140',contact:'Church Office',funds:['Tithe','General Offering','Missions','Building Fund','Benevolence','Thanksgiving'],methods:['Cash','Check','Bank Transfer','Card'],ministries:['Worship','Children','Youth','Women','Men','Prayer','Outreach'],categories:['Facilities','Ministry Programs','Missions','Benevolence','Office','Utilities']};
  const families=[['Henderson','Michael','Mary'],['Martin','David','Lisa'],['Johnson','James','Sarah'],['Williams','Daniel','Anna'],['Davis','John','Rebecca'],['Thomas','Paul','Rachel'],['Wilson','Luke','Esther'],['Taylor','Peter','Naomi'],['Anderson','Samuel','Ruth'],['Brown','Joseph','Grace'],['Moore','Isaac','Hannah'],['White','Joshua','Miriam']];
  const households=families.map(([name],i)=>({id:'HH-'+String(i+1).padStart(3,'0'),name:name+' Household',address:(1200+i*23)+' Community Lane',city:'Tulsa',state:'OK',zip:'74103',email:name.toLowerCase()+'@mail.example',phone:'(918) 555-'+String(101+i).padStart(4,'0'),contact:'M-'+(1001+i*3),notes:''}));
  const members=families.flatMap(([last,first,spouse],i)=>[[first,last,'Head','Adult'],[spouse,last,'Spouse','Adult'],[['Caleb','Emma','Leah','Noah'][i%4],last,'Child','Youth']].map(([first,last,role,stage],j)=>({id:'M-'+(1001+i*3+j),first,last,household:households[i].id,role,stage,status:'Active',ministry:j===2?'Youth':i%2?'Worship':'Prayer',email:j===2?'':first.toLowerCase()+'.'+last.toLowerCase()+'@mail.example',phone:j===2?'':households[i].phone,joined:(year-2)+'-03-17',birthday:(j===2?year-14:year-40)+'-06-'+String(i+10).padStart(2,'0'),baptism:j===2?'':(year-8)+'-04-16',notes:''})));
  const gifts=[];
  households.forEach((h,i)=>{
    for(let month=1;month<=mm;month++){
      for(const [fund,amount] of [['Tithe',15000+i*1500],['General Offering',2500+i*250]]){
        const day=Math.min(8,new Date().getDate());
        gifts.push({id:'G-'+String(gifts.length+1).padStart(5,'0'),household:h.id,donor:h.contact,donorName:members.find(m=>m.id===h.contact).first+' '+families[i][0],householdName:h.name,date:year+'-'+String(month).padStart(2,'0')+'-'+String(day).padStart(2,'0'),fund,cents:amount,method:i%3===0?'Cash':'Bank Transfer',reference:'',notes:'Sample contribution',status:'Posted',recordedAt:new Date().toISOString()});
      }
    }
    if(i<6)gifts.push({id:'G-'+String(gifts.length+1).padStart(5,'0'),household:h.id,donor:h.contact,donorName:members.find(m=>m.id===h.contact).first+' '+families[i][0],householdName:h.name,date:year+'-03-15',fund:'Missions',cents:10000,method:'Check',reference:'Sample '+(101+i),notes:'',status:'Posted',recordedAt:new Date().toISOString()});
  });
  const attendance=members.slice(0,29).map((m,i)=>({id:'A-'+i,member:m.id,date:today(),service:'Sunday Worship'}));
  const expenses=[['Facilities','Building maintenance',42500],['Utilities','Electricity and water',18600],['Ministry Programs','Children’s ministry materials',9300],['Missions','Community outreach supplies',25000]].map(([category,description,amount],i)=>({id:'E-'+i,date:year+'-'+String(mm).padStart(2,'0')+'-01',category,description,vendor:'Sample Vendor '+(i+1),cents:amount,method:'Bank Transfer',reference:'',notes:''}));
  const events=[{id:'EV-1',name:'Sunday Worship',date:today(),time:'10:00',location:'Main Sanctuary',capacity:200,notes:'',registrations:[]},{id:'EV-2',name:'Community Thanksgiving Dinner',date:year+'-11-26',time:'17:30',location:'Fellowship Hall',capacity:80,notes:'Bring your family and invite a neighbor.',registrations:members.slice(0,16).map(m=>m.id)}];
  return {version:2,sample:true,settings,households,members,gifts,attendance,expenses,events,...seedLearning(members)};
}
const storageKey='church-member-manager-v2';
function readData(){try{savedSnapshot=localStorage.getItem(storageKey);const data=JSON.parse(savedSnapshot);return validBackup(data)?normalize(data):seed();}catch{return seed();}}
let db=readData();
const state={page:'home',search:'',selected:{members:'M-1001',households:'HH-001',gifts:null,events:'EV-2',expenses:null,classes:db.classes[0]?.id||null,lessons:null},classKind:'',year:String(currentYear),month:'',fund:'',household:'HH-001',donor:'',memberFilter:'',voided:false};
const get=(kind,id)=>db[kind].find(r=>r.id===id);
const fullName=m=>m?m.first+' '+m.last:'Anonymous';
const activeMembers=()=>db.members.filter(m=>m.status==='Active');
const householdMembers=id=>db.members.filter(m=>m.household===id);
function giftRows({year=state.year,month='',household='',fund='',includeVoided=false}={}){
  return db.gifts.filter(g=>(!year||g.date.slice(0,4)===String(year))&&(!month||g.date.slice(5,7)===month)&&(!household||g.household===household)&&(!fund||g.fund===fund)&&(includeVoided||g.status==='Posted')).sort((a,b)=>b.date.localeCompare(a.date)||b.id.localeCompare(a.id));
}
function totals(rows){
  return [...new Set(rows.map(g=>g.fund))].map(fund=>[fund,sum(rows.filter(g=>g.fund===fund),'cents')]).sort((a,b)=>b[1]-a[1]);
}
const memberOptions=()=>[['','Anonymous / unassigned'],...db.members.map(m=>[m.id,fullName(m)+' · '+m.id])];
const householdOptions=()=>[['','Unassigned'],...db.households.map(h=>[h.id,h.name+' · '+h.id])];
const filterList=(records,reader)=>records.filter(r=>reader(r).toLowerCase().includes(state.search.toLowerCase()));
const search=placeholder=>'<label class="searchbox">'+icon('file')+'<input type="search" id="record-search" placeholder="'+esc(placeholder)+'" aria-label="Search records" value="'+esc(state.search)+'"></label>';
const recordLink=(text,kind,id)=>'<button type="button" class="record-link" data-action="select" data-kind="'+kind+'" data-key="'+esc(id)+'">'+esc(text)+'</button>';
const selector=(name,value,options,label)=>'<label>'+esc(label)+' <select data-filter="'+name+'">'+options.map(opt=>{const [id,text]=Array.isArray(opt)?opt:[opt,opt];return '<option value="'+esc(id)+'"'+(String(id)===String(value)?' selected':'')+'>'+esc(text)+'</option>';}).join('')+'</select></label>';
const years=()=>[...new Set([currentYear,...db.gifts.map(g=>Number(g.date.slice(0,4)))])].sort((a,b)=>b-a).map(y=>[String(y),String(y)]);
const yearFilter=()=>selector('year',state.year,years(),'Year');
const monthFilter=()=>selector('month',state.month,[['','All months'],...Array.from({length:12},(_,i)=>[String(i+1).padStart(2,'0'),new Date(2000,i,1).toLocaleDateString('en-US',{month:'long'})])],'Month');
const fundFilter=()=>selector('fund',state.fund,[['','All funds'],...new Set([...db.settings.funds,...db.gifts.map(g=>g.fund)])],'Fund');
function barChart(rows){
  const max=Math.max(1,...rows.map(r=>r[1]));
  return '<div class="bar-list">'+rows.map(([label,amount],i)=>'<div class="bar-line"><span>'+esc(label)+'</span><div class="bar-value"><span class="bar" style="width:'+amount/max*65+'%;background:'+['#173f5b','#2b789c','#dcb236','#4e837c'][i%4]+'"></span><b>'+money(amount)+'</b></div></div>').join('')+'</div>';
}
function memberCard(m){
  const h=get('households',m.household);
  return '<article class="church-id"><div><span class="eyebrow">'+esc(db.settings.church)+'</span><h2>'+esc(fullName(m))+'</h2><p>'+esc(m.id)+' · '+esc(m.status)+' member</p><p>'+esc(h?.name||'Household unassigned')+'</p><small>'+esc(m.ministry||'No ministry assigned')+' · Joined '+date(m.joined)+'</small></div><span data-qr="'+esc(m.id)+'"></span></article>';
}
function home(){
  const rows=giftRows(),monthRows=rows.filter(g=>g.date.slice(5,7)===String(new Date().getMonth()+1).padStart(2,'0'));
  const h=get('households',state.household)||db.households[0];
  const hr=h?giftRows({household:h.id}):[];
  const recent=[...rows].slice(0,7);
  const people=activeMembers();
  const present=new Set(db.attendance.filter(a=>a.date===today()).map(a=>a.member));
  const upcoming=db.events.filter(e=>e.date>=today()).sort((a,b)=>a.date.localeCompare(b.date));
  const birthdays=upcomingBirthdays(30).slice(0,6);
  return title('Church home','Members, households and stewardship in one place',yearFilter()+btn('Record Giving','new-gift','','gold','add'))+backupBanner()+
    '<div class="stats" style="--count:6">'+[
      stat('Active members',people.length,'Across '+db.settings.ministries.length+' ministries'),
      stat('Households',db.households.length,'Family records and contact details'),
      stat('Giving · '+state.year,money(sum(rows,'cents')),new Set(rows.map(g=>g.household).filter(Boolean)).size+' contributing households','green'),
      stat('Tithes · '+state.year,money(sum(rows.filter(g=>g.fund==='Tithe'),'cents')),'Recorded contributions'),
      stat('This month',money(sum(monthRows,'cents')),new Date().toLocaleDateString('en-US',{month:'long'})+' '+state.year),
      stat('Attendance today',present.size,'Unique members checked in')
    ].join('')+'</div><div class="church-home-grid">'+
    panel('Household at a glance','<div class="filters">'+selector('household',h?.id||'',db.households.map(h=>[h.id,h.name]),'Household')+'</div>'+(h?'<div class="family-heading"><span class="family-emblem">'+icon('home')+'</span><div><h2>'+esc(h.name)+'</h2><small>'+esc(h.id)+' · '+householdMembers(h.id).length+' members</small></div></div><div class="facts"><div><span class="label">Tithe · '+state.year+'</span><strong>'+money(sum(hr.filter(g=>g.fund==='Tithe'),'cents'))+'</strong></div><div><span class="label">Total giving · '+state.year+'</span><strong>'+money(sum(hr,'cents'))+'</strong></div></div>'+table(['Member','Role'],householdMembers(h.id).map(m=>[recordLink(fullName(m),'members',m.id),esc(m.role)]))+'<div class="actions spaced">'+btn('Open Household','open-household',h.id,'secondary','home')+btn('Giving Statement','statement',h.id,'secondary','file')+'</div>':note('Add your first household to get started.')))+
    panel('Giving by fund · '+state.year,barChart(totals(rows))+'<h3 class="spaced">Birthdays · next 30 days</h3>'+(birthdays.length?'<ul class="plain-list">'+birthdays.map(({m,left,next})=>'<li><span>'+recordLink(fullName(m),'members',m.id)+'</span><small>'+(left===0?'Today 🎂':next.toLocaleDateString('en-US',{month:'short',day:'numeric'}))+'</small></li>').join('')+'</ul>':note('No birthdays recorded for the next 30 days.')))+
    panel('Church life','<div class="facts"><div><span class="label">Children & youth</span><strong>'+people.filter(m=>['Child','Youth'].includes(m.stage)).length+'</strong></div><div><span class="label">Upcoming events</span><strong>'+upcoming.length+'</strong></div><div><span class="label">Active classes</span><strong>'+db.classes.filter(c=>c.status==='Active').length+'</strong></div></div>'+table(['Event','Date'],upcoming.slice(0,4).map(e=>[recordLink(e.name,'events',e.id),date(e.date)]))+'<div class="actions spaced">'+btn('Take Attendance','navigate','attendance','secondary','check')+'</div>')+
    '<section class="card recent-giving"><div class="title-row"><h3>Recent contributions</h3>'+btn('View Giving Ledger','navigate','giving','secondary small')+'</div>'+table(['Date','Household','Donor','Fund','Amount','Method'],recent.map(g=>[date(g.date),esc(g.householdName||'Unassigned'),esc(g.donorName),esc(g.fund),'<strong>'+money(g.cents)+'</strong>',esc(g.method)]))+'</section></div>';
}
function memberFields(m={}){
  return field('First name','first',m.first,{required:true})+field('Last name','last',m.last,{required:true})+field('Household','household',m.household,{options:householdOptions()})+field('Household role','role',m.role,{options:['Head','Spouse','Child','Other']})+field('Membership status','status',m.status,{options:['Active','Visitor','Inactive','Transferred','Deceased']})+field('Life stage','stage',m.stage,{options:['Adult','Youth','Child']})+field('Ministry','ministry',m.ministry,{options:['',...db.settings.ministries]})+field('Joined','joined',m.joined||today(),{type:'date',required:true})+field('Email','email',m.email,{type:'email'})+field('Phone','phone',m.phone,{type:'tel'})+field('Birthday','birthday',m.birthday,{type:'date'})+field('Baptism date','baptism',m.baptism,{type:'date'})+field('Notes','notes',m.notes,{area:true,full:true});
}
function members(){
  const m=get('members',state.selected.members);
  const list=filterList([...db.members].sort((a,b)=>fullName(a).localeCompare(fullName(b))),m=>[fullName(m),m.id,m.household,m.ministry,m.status].join(' '));
  return title('Members','Church directory, household links and ministry involvement',btn('Export CSV','members-csv','','secondary','file')+btn('New Member','new','members','gold','add'))+
    '<div class="workspace"><section>'+search('Name, member ID, ministry or status')+table(['Member','Household','Status'],list.map(m=>[recordLink(fullName(m),'members',m.id),esc(get('households',m.household)?.name||'—'),badge(m.status,m.status==='Active'?'good':'')]))+'</section><section class="editor">'+panel(m?'Member details · '+m.id:'New member',form('members',memberFields(m),'Save Record',delBtn('members',m?.id)))+'</section><aside class="sheet">'+(m?memberCard(m)+'<div class="actions spaced">'+btn('Membership Card','card',m.id,'secondary','print')+btn('Household','open-household',m.household,'secondary','home')+'</div><h3 class="spaced">Classes</h3>'+table(['Class','Status'],db.enrollments.filter(e=>e.member===m.id&&e.status!=='Withdrawn').map(e=>[esc(get('classes',e.class)?.name||'—'),badge(e.status,statusTone(e.status))]))+'<h3 class="spaced">Attendance</h3>'+table(['Date','Service'],db.attendance.filter(a=>a.member===m.id).sort((a,b)=>b.date.localeCompare(a.date)).slice(0,8).map(a=>[date(a.date),esc(a.service)])):note('Create a member to link them to a household.'))+'</aside></div>';
}
function monthlyGiving(rows){
  return table(['Month','Tithe','Total'],Array.from({length:12},(_,i)=>{
    const month=String(i+1).padStart(2,'0');
    const selected=rows.filter(g=>g.date.slice(5,7)===month);
    return [new Date(2000,i,1).toLocaleDateString('en-US',{month:'short'}),money(sum(selected.filter(g=>g.fund==='Tithe'),'cents')),money(sum(selected,'cents'))];
  }));
}
function households(){
  const h=get('households',state.selected.households);
  const list=filterList(db.households,h=>[h.name,h.id,h.email,h.phone,h.address].join(' '));
  const contributions=h?giftRows({household:h.id}):[];
  return title('Households','Family membership, contact information and combined giving',btn('New Household','new','households','gold','add'))+
    '<div class="workspace"><section>'+search('Household name, ID or contact')+table(['Household','Members'],list.map(h=>[recordLink(h.name,'households',h.id),householdMembers(h.id).length]))+'</section><section class="editor">'+panel(h?'Household details · '+h.id:'New household',form('households',
    field('Household name','name',h?.name,{required:true,full:true})+field('Primary contact','contact',h?.contact,{options:[['','Choose a member'],...db.members.filter(m=>m.household===h?.id).map(m=>[m.id,fullName(m)])],full:true})+field('Email','email',h?.email,{type:'email'})+field('Phone','phone',h?.phone,{type:'tel'})+field('Street address','address',h?.address,{full:true})+field('City','city',h?.city)+field('State','state',h?.state)+field('ZIP code','zip',h?.zip)+field('Notes','notes',h?.notes,{area:true,full:true}),'Save Record',delBtn('households',h?.id)))+'</section><aside class="sheet"><h3>Household giving</h3><div class="filters">'+yearFilter()+'</div>'+(h?'<h2>'+esc(h.name)+'</h2><div class="facts"><div><span class="label">Tithes</span><strong>'+money(sum(contributions.filter(g=>g.fund==='Tithe'),'cents'))+'</strong></div><div><span class="label">All contributions</span><strong>'+money(sum(contributions,'cents'))+'</strong></div></div>'+table(['Member','Role'],householdMembers(h.id).map(m=>[recordLink(fullName(m),'members',m.id),esc(m.role)]))+'<div class="actions spaced">'+btn('Record Giving','household-gift',h.id,'gold','add')+btn('Giving Statement','statement',h.id,'secondary','file')+'</div><h3 class="spaced">Monthly household giving</h3>'+monthlyGiving(contributions)+'<p class="muted spaced">Giving stays attributed to the household recorded when the contribution was entered.</p>':note('Save a household, then assign members from the Members screen.'))+'</aside></div>';
}
function giving(){
  const rows=giftRows({month:state.month,fund:state.fund,includeVoided:state.voided}).filter(g=>!state.search||[g.id,g.donorName,g.householdName,g.reference].join(' ').toLowerCase().includes(state.search.toLowerCase()));
  const posted=rows.filter(g=>g.status==='Posted');
  return title('Tithes & donations','Record contributions by donor, household and designated fund',btn('Export CSV','giving-csv','','secondary','file')+btn('Record Giving','new-gift','','gold','add'))+
    '<div class="filters">'+yearFilter()+monthFilter()+fundFilter()+'<label class="check-label"><input type="checkbox" data-filter="voided"'+(state.voided?' checked':'')+'> Show voided entries</label>'+search('Donor, household or reference')+'</div>'+
    '<div class="stats" style="--count:4">'+stat('Total giving',money(sum(posted,'cents')),posted.length+' posted contributions','green')+stat('Tithe',money(sum(posted.filter(g=>g.fund==='Tithe'),'cents')),'In this selection')+stat('Other donations',money(sum(posted.filter(g=>g.fund!=='Tithe'),'cents')),'In this selection')+stat('Contributing households',new Set(posted.map(g=>g.household).filter(Boolean)).size,'In this selection')+'</div>'+
    panel('Contribution ledger',table(['Entry','Date','Household','Donor','Fund','Amount','Method','Reference','Status',''],rows.map(g=>[esc(g.id),date(g.date),esc(g.householdName||'Unassigned'),esc(g.donorName),esc(g.fund),'<strong>'+money(g.cents)+'</strong>',esc(g.method),esc(g.reference||'—'),badge(g.status,g.status==='Posted'?'good':'warn'),g.status==='Posted'?btn('View','gift-view',g.id,'secondary small'):btn('View Void','gift-view',g.id,'secondary small')])))+
    '<p class="muted spaced">Corrections are recorded by voiding an entry with a reason and recording its replacement. Posted contributions stay in the ledger.</p>';
}
function giftFields(household='',donor=''){
  return field('Donor','donor',donor,{options:memberOptions(),full:true})+
    field('Household attribution','household',household,{options:householdOptions(),full:true})+
    field('Contribution date','date',today(),{type:'date',required:true})+field('Fund','fund','Tithe',{options:db.settings.funds,required:true})+
    field('Amount ('+currencyCode+')','amount','',{type:'number',step:'0.01',min:'0.01',required:true})+field('Method','method',db.settings.methods[0],{options:db.settings.methods,required:true})+
    field('Check / transfer reference','reference','',{full:true})+field('Notes','notes','',{area:true,full:true});
}
function openGift(household=''){
  const h=get('households',household);
  modal('Record a contribution',note('Attribute giving to the household and fund it belongs to.')+form('gift',giftFields(h?.id||'',h?.contact||''),'Record Contribution'));
}
function givingDetail(id){
  const g=get('gifts',id);if(!g)return;
  modal('Contribution · '+g.id,table(['Field','Value'],[['Date',date(g.date)],['Household',esc(g.householdName||'Unassigned')],['Donor',esc(g.donorName)],['Fund',esc(g.fund)],['Amount',money(g.cents)],['Method',esc(g.method)],['Reference',esc(g.reference)],['Notes',esc(g.notes)],['Status',badge(g.status)],['Recorded at',esc(new Date(g.recordedAt).toLocaleString())],...(g.status==='Voided'?[['Void reason',esc(g.voidReason)],['Voided at',esc(new Date(g.voidedAt).toLocaleString())]]:[])])+'<div class="actions spaced">'+btn('Print Entry','gift-print',id,'secondary','print')+(g.status==='Posted'?btn('Void Entry','gift-void',id,'danger'):'')+'</div>');
}
function statementContent(h,rows){
  const postal=[h.address,[h.city,h.state,h.zip].filter(Boolean).join(', ')].filter(Boolean);
  return '<div class="statement-heading"><div><h2>'+esc(db.settings.church)+'</h2><p>'+esc(db.settings.address)+'</p><p>'+esc(db.settings.email)+' · '+esc(db.settings.phone)+'</p></div><div><h2>'+esc(h.name)+'</h2>'+postal.map(line=>'<p>'+esc(line)+'</p>').join('')+'<p>'+esc(h.id)+'</p></div></div><div class="stats" style="--count:3">'+stat('Total giving',money(sum(rows,'cents')),state.year+' · '+(state.fund||'All funds'),'green')+stat('Tithes',money(sum(rows.filter(g=>g.fund==='Tithe'),'cents')),'Recorded contributions')+stat('Contributions',rows.length,'Posted entries')+'</div>'+table(['Date','Entry','Donor','Fund','Method','Amount'],rows.map(g=>[date(g.date),esc(g.id),esc(g.donorName),esc(g.fund),esc(g.method),money(g.cents)]))+'<h3 class="spaced">Totals by fund</h3>'+table(['Fund','Amount'],totals(rows).map(([fund,amount])=>[esc(fund),money(amount)]))+'<p class="muted spaced">Household giving summary · Generated '+date(today())+'. Please contact '+esc(db.settings.contact)+' for corrections. Entries are grouped using their recorded household attribution.</p>';
}
function statements(){
  const h=get('households',state.household)||db.households[0];
  const rows=h?giftRows({household:h.id,fund:state.fund}):[];
  return title('Household giving statements','View tithes and donations together for a selected household',h?btn('Print / Save PDF','print-statement',h.id,'gold','print')+btn('Export CSV','statement-csv',h.id,'secondary','file'):'')+
    '<div class="filters">'+selector('household',h?.id,db.households.map(h=>[h.id,h.name]),'Household')+yearFilter()+fundFilter()+'</div>'+
    panel('Giving summary · '+state.year,h?statementContent(h,rows):note('Add a household to create giving statements.'));
}
function attendance(){
  const logs=[...db.attendance].sort((a,b)=>b.date.localeCompare(a.date));
  return title('Attendance','Track worship services, small groups and ministry gatherings')+
    '<div class="two-col">'+panel('Check in a member',form('attendance',field('Member','member','',{options:[['','Choose a member'],...db.members.filter(m=>m.status!=='Deceased').map(m=>[m.id,fullName(m)+' · '+m.id])],required:true,full:true})+field('Date','date',today(),{type:'date',required:true})+field('Service / gathering','service','Sunday Worship',{required:true}),'Record Attendance'))+
    panel('Attendance records',table(['Date','Member','Service'],logs.slice(0,100).map(a=>[date(a.date),esc(fullName(get('members',a.member))),esc(a.service)])))+'</div>';
}
function events(){
  const e=get('events',state.selected.events);
  return title('Church events','Plan services, gatherings and registrations',btn('New Event','new','events','gold','add'))+
    '<div class="two-col">'+panel('Events',search('Event or location')+table(['Date','Event','Registered','Capacity'],filterList(db.events,e=>e.name+' '+e.location).map(e=>[date(e.date),recordLink(e.name,'events',e.id),e.registrations.length,e.capacity])))+
    panel(e?'Event details':'New event',form('events',field('Event name','name',e?.name,{required:true,full:true})+field('Date','date',e?.date||today(),{type:'date',required:true})+field('Time','time',e?.time||'10:00',{type:'time',required:true})+field('Location','location',e?.location,{required:true})+field('Capacity','capacity',e?.capacity||100,{type:'number',min:1,step:1,required:true})+field('Notes','notes',e?.notes,{area:true,full:true}),'Save Record',delBtn('events',e?.id)))+
    (e?panel('Registered members',form('registration',field('Member','member','',{options:[['','Choose a member'],...db.members.filter(m=>!e.registrations.includes(m.id)).map(m=>[m.id,fullName(m)])],required:true,full:true}),'Register Member')+table(['Member',''],e.registrations.map(id=>[esc(fullName(get('members',id))),btn('Cancel Registration','cancel-registration',id,'secondary small')]))):'')+'</div>';
}
function ministries(){
  return title('Ministries','Members grouped by their assigned ministry')+'<div class="ministry-grid">'+db.settings.ministries.map(name=>{
    const list=db.members.filter(m=>m.ministry===name&&m.status==='Active');
    return panel(name,badge(list.length+' active members','good')+'<div class="spaced">'+table(['Member','Household'],list.map(m=>[recordLink(fullName(m),'members',m.id),esc(get('households',m.household)?.name||'—')]))+'</div>');
  }).join('')+'</div>';
}
function expenses(){
  const e=get('expenses',state.selected.expenses);
  const rows=db.expenses.filter(e=>e.date.startsWith(state.year));
  const giving=sum(giftRows(),'cents'),spent=sum(rows,'cents');
  return title('Church expenses','Record payments and compare annual giving with expenses',yearFilter()+btn('New Expense','new','expenses','gold','add'))+
    '<div class="stats" style="--count:3">'+stat('Giving · '+state.year,money(giving),'Posted contributions')+stat('Expenses · '+state.year,money(spent),'Recorded expenses')+stat('Giving less expenses',money(giving-spent),'Selected calendar year',giving>=spent?'green':'red')+'</div>'+
    '<div class="two-col">'+panel('Expense ledger',table(['Date','Description','Category','Amount'],rows.sort((a,b)=>b.date.localeCompare(a.date)).map(e=>[date(e.date),recordLink(e.description,'expenses',e.id),esc(e.category),money(e.cents)])))+
    panel(e?'Expense details':'New expense',form('expenses',field('Date','date',e?.date||today(),{type:'date',required:true})+field('Category','category',e?.category,{options:db.settings.categories,required:true})+field('Description','description',e?.description,{required:true,full:true})+field('Vendor / payee','vendor',e?.vendor,{full:true})+field('Amount ('+currencyCode+')','amount',e?(e.cents/100).toFixed(2):'',{type:'number',min:'0.01',step:'0.01',required:true})+field('Method','method',e?.method,{options:db.settings.methods})+field('Reference','reference',e?.reference)+field('Notes','notes',e?.notes,{area:true,full:true}),'Save Record',delBtn('expenses',e?.id)))+'</div>';
}
function settings(){
  const s=db.settings;
  return title('Church settings','Church details, giving funds and record backups')+'<div class="two-col">'+panel('Church information',form('settings',
    field('Church name','church',s.church,{required:true,full:true})+field('Address','address',s.address,{full:true})+field('Office email','email',s.email,{type:'email'})+field('Office phone','phone',s.phone,{type:'tel'})+field('Statement contact','contact',s.contact,{full:true})+field('Currency','currency',s.currency||'USD',{options:['USD','CAD','GBP','EUR','AUD','NZD','INR','MMK','PHP','NGN','KES','ZAR','BRL','MXN','JPY']})))+
    panel('Funds & lists',form('lists',field('Giving funds · one per line','funds',s.funds.join('\n'),{area:true,required:true,full:true})+field('Ministries · one per line','ministries',s.ministries.join('\n'),{area:true,required:true,full:true})+field('Giving methods · one per line','methods',s.methods.join('\n'),{area:true,required:true,full:true})+field('Expense categories · one per line','categories',s.categories.join('\n'),{area:true,required:true,full:true})))+
    panel('Backup & restore',note('Records are saved in this browser. Download a backup to keep a copy or transfer your records to another browser.')+'<div class="actions spaced">'+btn('Download Backup','backup','','gold','file')+btn('Restore Backup','restore','','secondary')+'</div>')+
    panel('Start your church records',note(db.sample?'You are viewing fictional church records. Start an empty register when you are ready to enter your own.':'Your church register is active.')+'<div class="actions spaced">'+(db.sample?btn('Start Empty Register','empty-confirm','','secondary'):'')+btn('Load Sample Church','sample-confirm','','secondary')+'</div><p class="muted spaced">Your original Membership Manager data uses a separate browser store. Church records use their own backup format.</p>')+'</div>';
}
const pages={home,members,households,giving,statements,attendance,discipleship,events,ministries,expenses,settings};
const navigation=[['home','Home','home'],['members','Members','people'],['households','Households','home'],['giving','Giving','giving'],['statements','Statements','file'],['attendance','Attendance','check'],['discipleship','Discipleship','book'],['events','Events','calendar'],['ministries','Ministries','people'],['expenses','Expenses','giving'],['settings','Settings','settings']];
function hydrate(root){root.querySelectorAll('[data-qr]').forEach(node=>{node.innerHTML=window.makeMemberQR(node.dataset.qr);});}
function render(){
  currencyCode=db.settings.currency||'USD';
  $('navigation').innerHTML=navigation.map(([page,label,glyph])=>'<a href="#'+page+'"'+(page===state.page?' class="active" aria-current="page"':'')+'>'+icon(glyph)+esc(label)+(page==='members'?'<span class="badge">'+db.members.length+'</span>':'')+'</a>').join('');
  $('screen-title').textContent=state.page==='home'?'CHURCH HOME':navigation.find(n=>n[0]===state.page)[1].toUpperCase();
  $('sample').hidden=!db.sample;
  $('session-date').textContent=date(today());
  $('club').textContent=db.settings.church;
  $('screen').innerHTML=pages[state.page]();
  hydrate($('screen'));
  renderFooter();
}
function renderFooter(){
  $('app-footer').innerHTML='<span>&copy; '+COMPANY.year+' <strong>'+esc(COMPANY.name)+'</strong> · '+esc(COMPANY.product)+' v'+COMPANY.version+'</span><button type="button" class="record-link" data-action="about">About</button>';
}
function route(){
  const page=location.hash.slice(1);
  const next=Object.hasOwn(pages,page)?page:'home';
  if(state.page!==next){state.search='';state.page=next;}
  render();
}
function navigate(page){if(state.page===page)render();else location.hash=page;}
let timer;
function notice(message){
  $('toast').hidden=false;$('toast').textContent=message;
  clearTimeout(timer);timer=setTimeout(()=>$('toast').hidden=true,4500);
}
function saveDB(next,message){
  try{
    const stored=localStorage.getItem(storageKey);
    if(stored!==savedSnapshot){
      const fresh=JSON.parse(stored);
      if(validBackup(fresh)){db=normalize(fresh);savedSnapshot=stored;render();}
      notice('Another tab updated these records. Review the refreshed values and try again.');
      return false;
    }
    const encoded=JSON.stringify(next);
    localStorage.setItem(storageKey,encoded);
    savedSnapshot=encoded;
  }
  catch{notice('Could not save to browser storage. Download a backup and free space before trying again.');return false;}
  db=next;render();if(message)notice(message);return true;
}
function modal(heading,content){
  $('dialog-content').innerHTML='<div class="dialog-title"><h2>'+esc(heading)+'</h2>'+btn('Close','close','','secondary small')+'</div>'+content;
  if(!$('dialog').open)$('dialog').showModal();
}
const close=()=>$('dialog').close();
const sequence=(items,prefix)=>prefix+String(Math.max(0,...items.map(r=>Number(r.id.replace(prefix,''))).filter(Number.isFinite))+1).padStart(prefix==='G-'?5:3,'0');
function upsert(next,kind,record){
  const old=get(kind,state.selected[kind]);
  const id=old?.id||sequence(next[kind],{members:'M-',households:'HH-',events:'EV-',expenses:'E-'}[kind]);
  if(old)Object.assign(next[kind].find(r=>r.id===id),record);
  else next[kind].push({id,...record});
  return id;
}
function selectedHousehold(){return get('households',state.household)||db.households[0];}
function printSheet(titleText,body){
  $('print-sheet').innerHTML='<h1>'+esc(titleText)+'</h1><div class="spaced">'+body+'</div><p class="print-credit">Prepared with '+esc(COMPANY.product)+' · Developed by '+esc(COMPANY.name)+'</p>';hydrate($('print-sheet'));window.print();
}
function download(text,name,type){
  const url=URL.createObjectURL(new Blob([text],{type}));
  const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
function csvValue(value){
  let text=String(value??'');
  if(/^[=+@\-\t\r]/.test(text))text="'"+text;
  return '"'+text.replace(/"/g,'""')+'"';
}
function exportGiving(rows,name){
  const data=[['Entry','Date','Household ID','Household','Member ID','Donor','Fund','Amount','Method','Reference','Status','Void reason'],...rows.map(g=>[g.id,g.date,g.household,g.householdName,g.donor,g.donorName,g.fund,(g.cents/100).toFixed(2),g.method,g.reference,g.status,g.voidReason||''])];
  download('\uFEFF'+data.map(row=>row.map(csvValue).join(',')).join('\r\n'),name,'text/csv;charset=utf-8');
}
function isDate(value){return typeof value==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(value)&&!Number.isNaN(Date.parse(value+'T12:00:00'))&&new Date(value+'T12:00:00Z').toISOString().slice(0,10)===value;}
function validBackup(data){
  const text=(x,keys)=>x&&keys.every(k=>typeof x[k]==='string');
  const list=value=>Array.isArray(value)&&value.length>0&&value.every(v=>typeof v==='string'&&v.trim());
  const records=(value,check)=>Array.isArray(value)&&value.every(v=>text(v,['id'])&&check(v))&&new Set(value.map(v=>v.id)).size===value.length;
  const amount=value=>Number.isSafeInteger(value)&&value>0;
  if(!data||data.version!==2||typeof data.sample!=='boolean'||!text(data.settings,['church','address','email','phone','contact']))return false;
  if(!['funds','methods','ministries','categories'].every(k=>list(data.settings[k])))return false;
  return records(data.members,m=>text(m,['first','last','household','role','stage','status','ministry','email','phone','joined','birthday','baptism','notes'])&&isDate(m.joined))&&
    records(data.households,h=>text(h,['name','address','city','state','zip','email','phone','contact','notes']))&&
    records(data.gifts,g=>text(g,['household','donor','householdName','donorName','date','fund','method','reference','notes','status','recordedAt'])&&isDate(g.date)&&amount(g.cents)&&['Posted','Voided'].includes(g.status)&&Number.isFinite(Date.parse(g.recordedAt))&&(g.status!=='Voided'||text(g,['voidReason','voidedAt'])&&g.voidReason.trim()&&Number.isFinite(Date.parse(g.voidedAt))))&&
    records(data.attendance,a=>text(a,['member','date','service'])&&isDate(a.date))&&
    records(data.expenses,e=>text(e,['date','category','description','vendor','method','reference','notes'])&&isDate(e.date)&&amount(e.cents))&&
    records(data.events,e=>text(e,['name','date','time','location','notes'])&&isDate(e.date)&&Number.isSafeInteger(e.capacity)&&e.capacity>0&&Array.isArray(e.registrations)&&e.registrations.every(id=>typeof id==='string')&&new Set(e.registrations).size===e.registrations.length&&e.registrations.length<=e.capacity)&&learningValid(data,records,text,isDate);
}
function postGift(next,data){
  if(!isDate(data.date))throw new Error('Choose a valid contribution date.');
  const donor=next.members.find(m=>m.id===data.donor),household=next.households.find(h=>h.id===data.household);
  if(data.donor&&!donor||data.household&&!household)throw new Error('Choose a valid donor and household.');
  if(donor&&donor.household!==(household?.id||''))throw new Error('The donor and household do not match. Select their household or record anonymous household giving.');
  if(!next.settings.funds.includes(data.fund)||!next.settings.methods.includes(data.method))throw new Error('Choose a configured fund and giving method.');
  const entry={id:sequence(next.gifts,'G-'),household:household?.id||'',donor:donor?.id||'',householdName:household?.name||'',donorName:fullName(donor),date:data.date,fund:data.fund,cents:cents(data.amount),method:data.method,reference:data.reference,notes:data.notes,status:'Posted',recordedAt:new Date().toISOString()};
  if(entry.reference&&next.gifts.some(g=>g.status==='Posted'&&g.reference===entry.reference&&g.date===entry.date&&g.method===entry.method&&g.cents===entry.cents))throw new Error('A posted entry with the same date, method, amount and reference already exists.');
  next.gifts.push(entry);
  return entry;
}
function voidGift(next,id,reason){
  const g=next.gifts.find(g=>g.id===id);
  if(!g||g.status!=='Posted')throw new Error('This contribution is already voided or unavailable.');
  if(!reason.trim())throw new Error('Enter a reason for voiding this entry.');
  Object.assign(g,{status:'Voided',voidReason:reason.trim(),voidedAt:new Date().toISOString()});
}
function upcomingBirthdays(days=30){
  const now=new Date(),start=new Date(now.getFullYear(),now.getMonth(),now.getDate());
  return db.members.filter(m=>m.birthday&&isDate(m.birthday)&&!['Deceased','Transferred'].includes(m.status)).map(m=>{
    const [,mo,d]=m.birthday.split('-').map(Number);
    let next=new Date(start.getFullYear(),mo-1,d);
    if(next<start)next=new Date(start.getFullYear()+1,mo-1,d);
    return {m,next,left:Math.round((next-start)/86400000)};
  }).filter(x=>x.left<=days).sort((a,b)=>a.left-b.left);
}
function backupAge(){
  const last=localStorage.getItem(storageKey+'-last-backup');
  if(!last)return null;
  return Math.floor((Date.now()-Number(last))/86400000);
}
function backupBanner(){
  if(db.sample)return '';
  const age=backupAge();
  if(age!==null&&age<30)return '';
  return '<div class="banner">'+icon('file')+'<span>'+(age===null?'You have not downloaded a backup yet.':'Your last backup was '+age+' days ago.')+' Records live only in this browser — download a backup regularly.</span>'+btn('Download Backup','backup','','gold small')+'</div>';
}
function exportMembers(){
  const data=[['Member ID','First name','Last name','Household ID','Household','Role','Status','Life stage','Ministry','Email','Phone','Birthday','Joined','Baptism'],...db.members.map(m=>[m.id,m.first,m.last,m.household,get('households',m.household)?.name||'',m.role,m.status,m.stage,m.ministry,m.email,m.phone,m.birthday,m.joined,m.baptism])];
  download('\uFEFF'+data.map(row=>row.map(csvValue).join(',')).join('\r\n'),'church-members-'+today()+'.csv','text/csv;charset=utf-8');
}
const actions={
  ...learningActions,
  about(){modal('About '+COMPANY.product,'<div class="about"><div class="about-mark">'+icon('church')+'</div><h3>'+esc(COMPANY.product)+'</h3><p>Version '+COMPANY.version+'</p><p class="spaced">Developed by <strong>'+esc(COMPANY.name)+'</strong>.</p><p class="muted spaced">Members, households, giving, attendance, events, ministries, discipleship classes and expenses for your congregation. Records are stored privately in this browser — nothing is sent to any server.</p><p class="muted spaced">&copy; '+COMPANY.year+' '+esc(COMPANY.name)+'. All rights reserved.</p><p class="muted spaced">QR codes use QRCode for JavaScript &copy; 2009 Kazuhiko Arase (MIT License).</p></div>');},
  'members-csv':exportMembers,
  delete(id,el){
    const kind=el.dataset.kind,rec=get(kind,id);if(!rec)return;
    const label={members:'member',households:'household',events:'event',expenses:'expense',classes:'class',lessons:'lesson',classSessions:'class session'}[kind];
    const name=rec.name||rec.title||rec.description||(rec.first?fullName(rec):'Session · '+rec.date);
    state.deleteTarget={kind,id};
    modal('Delete '+label,note('Delete “'+name+'”? This cannot be undone. Download a backup first if you may need it.')+form('delete','','Delete '+label));
  },
  close,navigate,
  select(key,el){state.selected[el.dataset.kind]=key;state.search='';navigate(el.dataset.kind);},
  new(kind){state.selected[kind]=null;render();},
  'new-gift'(){openGift();},
  'household-gift':openGift,
  'gift-view':givingDetail,
  'gift-print'(id){const g=get('gifts',id);if(g)printSheet('Contribution entry · '+g.id,'<h2>'+esc(db.settings.church)+'</h2>'+table(['Date','Donor','Household','Fund','Amount','Method','Status'],[[date(g.date),esc(g.donorName),esc(g.householdName),esc(g.fund),money(g.cents),esc(g.method),esc(g.status)]])+(g.voidReason?'<p>Void reason · '+esc(g.voidReason)+'</p>':''));},
  'gift-void'(id){const g=get('gifts',id);if(g?.status==='Posted'){state.voidId=id;modal('Void contribution · '+id,note('The entry will stay visible in the ledger and be excluded from giving totals and statements.')+form('void',field('Reason','reason','',{area:true,full:true,required:true}),'Void Entry'));}},
  statement(id){state.household=id;state.fund='';navigate('statements');},
  'open-household'(id){if(!get('households',id)){notice('Assign a household to this member first.');return;}state.selected.households=id;navigate('households');},
  card(id){const m=get('members',id);if(m)printSheet('Member Card',memberCard(m));},
  'print-statement'(){const h=selectedHousehold();if(h)printSheet('Household giving statement · '+state.year,statementContent(h,giftRows({household:h.id,fund:state.fund})));},
  'statement-csv'(){const h=selectedHousehold();if(h)exportGiving(giftRows({household:h.id,fund:state.fund}),'giving-'+h.id+'-'+state.year+'.csv');},
  'giving-csv'(){exportGiving(giftRows({month:state.month,fund:state.fund,includeVoided:state.voided}).filter(g=>!state.search||[g.id,g.donorName,g.householdName,g.reference].join(' ').toLowerCase().includes(state.search.toLowerCase())),'church-giving-'+state.year+'.csv');},
  'cancel-registration'(id){const next=structuredClone(db);const e=next.events.find(e=>e.id===state.selected.events);if(e){e.registrations=e.registrations.filter(m=>m!==id);saveDB(next,'Registration cancelled.');}},
  backup(){download(JSON.stringify(db,null,2),'church-records-'+today()+'.json','application/json');try{localStorage.setItem(storageKey+'-last-backup',String(Date.now()));}catch{}render();},
  restore(){modal('Restore church backup',note('This replaces the church records saved in this browser. Download a current backup first if needed.')+'<form data-form="restore"><label>Backup JSON <input name="backup" type="file" accept=".json,application/json" required></label><div class="actions spaced">'+submit('Restore Records')+'</div></form>');},
  'empty-confirm'(){modal('Start an empty church register',note('Download a backup first to keep the current church records.')+form('empty','', 'Start Empty Register'));},
  'sample-confirm'(){modal('Load sample church',note('This replaces the church register in this browser with fictional sample records. Download a backup first to keep your records.')+form('sample','','Load Sample Church'));}
};
function resetState(){
  state.selected={members:db.members[0]?.id,households:db.households[0]?.id,gifts:null,events:db.events[0]?.id,expenses:null,classes:db.classes[0]?.id||null,lessons:null};
  state.classKind='';
  state.household=db.households[0]?.id||'';state.search='';state.fund='';state.year=String(currentYear);state.month='';state.voided=false;
}
async function handleSubmit(event){
  event.preventDefault();
  const f=event.target,kind=f.dataset.form;
  if(!kind)return;
  const data=Object.fromEntries([...new FormData(f)].map(([k,v])=>[k,typeof v==='string'?v.trim():v]));
  try{
    if(kind==='restore'){
      if(data.backup.size>20000000)throw new Error('Choose a backup smaller than 20 MB.');
      const candidate=JSON.parse(await data.backup.text());
      if(!validBackup(candidate))throw new Error('Choose a valid church records backup.');
      normalize(candidate);
      if(saveDB(candidate,'Church backup restored.')){resetState();close();render();}
      return;
    }
    const next=structuredClone(db);
    let message='Record saved.',id;
    if(kind==='members'){
      if(!isDate(data.joined))throw new Error('Choose a valid joined date.');
      const old=get('members',state.selected.members);
      if(old?.household!==data.household){
        const h=next.households.find(h=>h.id===old?.household&&h.contact===old?.id);
        if(h)h.contact='';
      }
      id=upsert(next,kind,data);
    }else if(kind==='households'){id=upsert(next,kind,data);}
    else if(kind==='events'){
      const old=get('events',state.selected.events);
      data.capacity=Number(data.capacity);
      if(!Number.isSafeInteger(data.capacity)||data.capacity<1)throw new Error('Enter a whole number for capacity.');
      if((old?.registrations.length||0)>data.capacity)throw new Error('Capacity must cover existing registrations.');
      if(!isDate(data.date))throw new Error('Choose a valid event date.');
      id=upsert(next,kind,{...data,registrations:old?.registrations||[]});
    }else if(kind==='expenses'){
      if(!isDate(data.date))throw new Error('Choose a valid expense date.');
      const {amount,...record}=data;
      id=upsert(next,kind,{...record,cents:cents(amount)});
    }else if(kind==='gift'){
      postGift(next,data);
      state.year=data.date.slice(0,4);state.month='';state.fund='';state.search='';
      message='Contribution recorded.';
    }else if(kind==='void'){
      voidGift(next,state.voidId,data.reason);
      message='Contribution voided. The original entry is retained.';
    }else if(kind==='attendance'){
      if(!get('members',data.member)||!isDate(data.date))throw new Error('Choose a member and valid date.');
      if(next.attendance.some(a=>a.member===data.member&&a.date===data.date&&a.service.toLowerCase()===data.service.toLowerCase()))throw new Error('This member is already checked in for this service and date.');
      next.attendance.push({id:uid(),...data});message='Attendance recorded.';
    }else if(kind==='registration'){
      const e=next.events.find(e=>e.id===state.selected.events);
      if(!e||!get('members',data.member))throw new Error('Select an event and member.');
      if(e.registrations.length>=e.capacity)throw new Error('This event has reached capacity.');
      if(e.registrations.includes(data.member))throw new Error('This member is already registered.');
      e.registrations.push(data.member);message='Member registered.';
    }else if(learningForms[kind]){
      const r=learningForms[kind](next,data,f);message=r?.message||message;
    }else if(kind==='delete'){
      const {kind:k,id:rid}=state.deleteTarget||{};
      if(!k||!get(k,rid))throw new Error('This record is no longer available.');
      if(k==='households'){
        if(next.members.some(m=>m.household===rid))throw new Error('Move or remove this household’s members before deleting it.');
        if(next.gifts.some(g=>g.household===rid))throw new Error('This household has giving history. Keep the record so statements stay accurate.');
      }
      if(k==='members'){
        if(next.gifts.some(g=>g.donor===rid))throw new Error('This member has giving history. Set their status to Inactive instead of deleting.');
        next.attendance=next.attendance.filter(a=>a.member!==rid);
        next.events.forEach(e=>{e.registrations=e.registrations.filter(x=>x!==rid);});
        next.households.forEach(h=>{if(h.contact===rid)h.contact='';});
      }
      learningCleanup(next,k,rid);
      next[k]=next[k].filter(r=>r.id!==rid);
      state.selected[k]=['lessons','classSessions'].includes(k)?null:next[k][0]?.id||null;
      state.deleteTarget=null;message='Record deleted.';
    }else if(kind==='settings'){
      if(data.currency&&!/^[A-Z]{3}$/.test(data.currency))throw new Error('Choose a valid currency.');
      Object.assign(next.settings,data);
    }
    else if(kind==='lists'){
      for(const key of ['funds','methods','ministries','categories']){
        const list=[...new Set(data[key].split('\n').map(x=>x.trim()).filter(Boolean))];
        if(!list.length)throw new Error('Enter at least one value in each list.');
        next.settings[key]=list;
      }
    }else if(kind==='empty'){
      if(!db.sample)throw new Error('The register is already active.');
      for(const key of ['members','households','gifts','events','expenses','attendance','classes','lessons','enrollments','classSessions'])next[key]=[];
      next.sample=false;message='Empty church register ready.';
    }else if(kind==='sample'){
      if(saveDB(seed(),'Sample church loaded.')){resetState();close();render();}
      return;
    }else return;
    if(id)state.selected[kind]=id;
    if(saveDB(next,message)){if(['gift','void','empty','delete'].includes(kind))close();if(kind==='empty'){resetState();render();}}
  }catch(error){if(kind==='delete')close();notice(error instanceof SyntaxError?'The backup could not be read.':error.message);}
}
document.addEventListener('submit',handleSubmit);
document.addEventListener('click',event=>{
  const button=event.target.closest('[data-action]');
  if(button)actions[button.dataset.action]?.(button.dataset.key,button);
});
document.addEventListener('change',event=>{
  const el=event.target;
  if(el.dataset.filter){state[el.dataset.filter]=el.type==='checkbox'?el.checked:el.value;render();}
  if(el.name==='donor'&&el.closest('[data-form="gift"]')){
    const donor=get('members',el.value);
    if(donor)el.form.elements.household.value=donor.household;
  }
});
document.addEventListener('input',event=>{
  if(event.target.id==='record-search'){
    const input=event.target,pos=input.selectionStart;
    state.search=input.value;render();
    const next=$('record-search');next.focus();next.setSelectionRange(pos,pos);
  }
});
window.addEventListener('hashchange',route);
window.addEventListener('storage',event=>{
  if(event.key===storageKey){
    try{const fresh=JSON.parse(event.newValue);if(validBackup(fresh)){db=normalize(fresh);savedSnapshot=event.newValue;render();notice('Records refreshed from another tab.');}}catch{}
  }
});
$('brand-icon').innerHTML=icon('church');
route();
