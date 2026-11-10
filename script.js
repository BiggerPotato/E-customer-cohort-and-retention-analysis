(() => {
  const $ = (id) => document.getElementById(id);
  const norm = (value) => String(value ?? '').trim().toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '');
  const aliases = {
    month:['month','order_month','ordermonth','purchase_month','year_month','cohort_month','cohortmonth'],
    revenue:['revenue','total_revenue','monthly_revenue','sales','amount'],
    orders:['orders','order_count','valid_orders','total_orders','number_of_orders'],
    customers:['customers','unique_customers','customer_count','n_customers'],
    repeat:['repeat_customers','returning_customers','customers_with_repeat_orders'],
    rate:['repeat_rate','repeat_customer_rate','retention_rate'],
    aov:['average_order_value','avg_order_value','aov'],
    days:['median_days_between_orders','median_days_between','median_days','days_between_orders'],
    customer:['customer_id','customerid','customer','customer_number'],
    order:['invoice','invoiceno','invoice_no','invoice_number','order_id','transaction_id'],
    date:['date','order_date','invoicedate','invoice_date','transaction_date'],
    quantity:['quantity','qty'], price:['unit_price','unitprice','price'], amount:['line_total','order_value','total','sales_amount']
  };
  function col(row, key) { const found=Object.keys(row).find(k=>aliases[key].includes(norm(k))); return found ?? null; }
  function number(value) { if(value===null||value===undefined||value==='')return NaN; const n=Number(String(value).replace(/[$,%\s,]/g,'')); return Number.isFinite(n)?n:NaN; }
  function parseCSV(text) {
    const rows=[]; let row=[],cell='',quoted=false;
    for(let i=0;i<text.length;i++){const c=text[i];if(quoted){if(c==='"'&&text[i+1]==='"'){cell+='"';i++;}else if(c==='"')quoted=false;else cell+=c;}else if(c==='"')quoted=true;else if(c===','){row.push(cell);cell='';}else if(c==='\n'){row.push(cell);if(row.some(v=>v.trim()))rows.push(row);row=[];cell='';}else if(c!=='\r')cell+=c;}
    row.push(cell);if(row.some(v=>v.trim()))rows.push(row);if(rows.length<2)return [];
    const heads=rows.shift().map(v=>v.trim());return rows.map(values=>Object.fromEntries(heads.map((h,i)=>[h,(values[i]??'').trim()])));
  }
  async function csv(name, optional=false) { const response=await fetch(name,{cache:'no-store'});if(!response.ok){if(optional)return [];throw Error(`${name} could not be loaded. Start this page using the instructions in README_DASHBOARD.md.`);}return parseCSV(await response.text()); }
  const fmt=(n)=>Number.isFinite(n)?Math.round(n).toLocaleString('en-US'):'—';
  const money=(n)=>Number.isFinite(n)?'$'+n.toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2}):'—';
  const median=(values)=>{if(!values.length)return NaN;values.sort((a,b)=>a-b);const m=Math.floor(values.length/2);return values.length%2?values[m]:(values[m-1]+values[m])/2;};
  function setStatus(message,type='info'){const box=$('status');box.className=`notice show ${type}`;box.lastElementChild.textContent=message;}
  function setMetric(id,val){$(id).textContent=val;}

  function drawRevenue(rows){
    const canvas=$('revenueChart'),wrap=canvas.parentElement,ctx=canvas.getContext('2d');
    const month=rows.length?col(rows[0],'month'):null,rev=rows.length?col(rows[0],'revenue'):null;
    if(!month||!rev){$('revenue-empty').textContent='Monthly summary needs month and revenue columns to draw this chart.';return false;}
    const points=rows.map(r=>({label:r[month],value:number(r[rev])})).filter(p=>Number.isFinite(p.value));
    if(!points.length){$('revenue-empty').textContent='No monthly revenue values were found.';return false;}
    $('revenue-empty').textContent='';
    const dpr=window.devicePixelRatio||1,w=wrap.clientWidth,h=wrap.clientHeight;canvas.width=w*dpr;canvas.height=h*dpr;ctx.scale(dpr,dpr);
    const pad={l:45,r:10,t:10,b:35},cw=w-pad.l-pad.r,ch=h-pad.t-pad.b,max=Math.max(...points.map(p=>p.value),1),min=Math.min(0,...points.map(p=>p.value));
    ctx.font='10px DM Sans, sans-serif';ctx.textBaseline='middle';
    for(let i=0;i<4;i++){const y=pad.t+ch*i/3;ctx.strokeStyle='#edf1f6';ctx.beginPath();ctx.moveTo(pad.l,y);ctx.lineTo(w-pad.r,y);ctx.stroke();ctx.fillStyle='#9aa8ba';const tick=max-(max-min)*i/3;ctx.textAlign='right';ctx.fillText(tick>=1000?'$'+(tick/1000).toFixed(0)+'k':'$'+tick.toFixed(0),pad.l-7,y);}
    const coords=points.map((p,i)=>({x:pad.l+(points.length===1?cw/2:cw*i/(points.length-1)),y:pad.t+ch-(p.value-min)/(max-min||1)*ch,...p}));
    const grad=ctx.createLinearGradient(0,pad.t,0,pad.t+ch);grad.addColorStop(0,'rgba(57,119,232,.20)');grad.addColorStop(1,'rgba(57,119,232,0)');ctx.beginPath();coords.forEach((p,i)=>i?ctx.lineTo(p.x,p.y):ctx.moveTo(p.x,p.y));ctx.lineTo(coords.at(-1).x,pad.t+ch);ctx.lineTo(coords[0].x,pad.t+ch);ctx.closePath();ctx.fillStyle=grad;ctx.fill();
    ctx.beginPath();coords.forEach((p,i)=>i?ctx.lineTo(p.x,p.y):ctx.moveTo(p.x,p.y));ctx.strokeStyle='#3977e8';ctx.lineWidth=2.5;ctx.lineJoin='round';ctx.stroke();
    coords.forEach((p,i)=>{ctx.beginPath();ctx.arc(p.x,p.y,3.4,0,Math.PI*2);ctx.fillStyle='#fff';ctx.fill();ctx.lineWidth=2;ctx.strokeStyle='#3977e8';ctx.stroke();if(i===0||i===coords.length-1||i%Math.ceil(coords.length/5)===0){ctx.fillStyle='#8795a9';ctx.textAlign=i===0?'left':i===coords.length-1?'right':'center';ctx.textBaseline='top';ctx.fillText(String(p.label).slice(0,12),p.x,pad.t+ch+11);}});
    canvas._points=coords;canvas.onmousemove=(e)=>{const r=canvas.getBoundingClientRect(),x=e.clientX-r.left;const p=coords.reduce((a,b)=>Math.abs(b.x-x)<Math.abs(a.x-x)?b:a);canvas.title=`${p.label}: ${money(p.value)}`;};return true;
  }
  function drawHeatmap(rows){
    const host=$('heatmap');if(!rows.length){host.innerHTML='<div class="empty-chart">No cohort rows found.</div>';return false;}
    const headers=Object.keys(rows[0]),cohortKey=headers.find(h=>aliases.month.includes(norm(h))||norm(h).includes('cohort'));
    const periodKey=headers.find(h=>['period','month_number','month_index','months_since_first_purchase','months_since_cohort'].includes(norm(h)));
    const valueKey=headers.find(h=>['retention','retention_rate','retention_pct','retention_percentage','customers_retained','retained_customers'].includes(norm(h)));
    let cohorts=[];
    if(cohortKey&&periodKey&&valueKey){
      cohorts=rows.map(r=>({name:r[cohortKey],vals:Object.fromEntries(rows.filter(x=>x[cohortKey]===r[cohortKey]).map(x=>[number(x[periodKey]),number(x[valueKey])]))}));
      const unique=new Map(cohorts.map(c=>[c.name,c]));cohorts=[...unique.values()];
    }else if(cohortKey){
      const periodCols=headers.filter(h=>{const n=norm(h);return /^\d+$/.test(n)||/^month_?\d+$/.test(n)||/^m\d+$/.test(n);});
      cohorts=rows.map(r=>({name:r[cohortKey],vals:Object.fromEntries(periodCols.map((h,i)=>[Number((norm(h).match(/\d+/)||[])[0]??i),number(r[h])]))}));
    }
    if(!cohorts.length||!Object.values(cohorts[0].vals).length){host.innerHTML='<div class="empty-chart">Cohort format not recognized. Existing heatmap shown below if available.</div>';fallbackImage('cohort_retention_heatmap.png',host);return false;}
    const maxPeriod=Math.max(...cohorts.flatMap(c=>Object.keys(c.vals).map(Number)).filter(Number.isFinite),0);let html='<table class="heatmap"><thead><tr><th>First-purchase month</th>'+Array.from({length:maxPeriod+1},(_,i)=>`<th>Month ${i}</th>`).join('')+'</tr></thead><tbody>';
    for(const cohort of cohorts){html+=`<tr><th>${escapeHTML(cohort.name)}</th>`;for(let i=0;i<=maxPeriod;i++){let v=cohort.vals[i];if(i===0&&(!Number.isFinite(v)||v===0))v=1;if(Number.isFinite(v)){const rate=v>1.5?v/100:v;const alpha=Math.max(.08,Math.min(.95,rate));html+=`<td title="${escapeHTML(cohort.name)} · month ${i}: ${(rate*100).toFixed(1)}%" style="background:rgba(57,119,232,${alpha})">${(rate*100).toFixed(0)}%</td>`;}else html+='<td style="background:#f3f6fa"></td>'; }html+='</tr>';}
    html+='</tbody></table>';host.innerHTML=html;return true;
  }
  function escapeHTML(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
  function fallbackImage(src,host){const img=new Image();img.src=src;img.alt=src.replaceAll('_',' ').replace('.png','');img.style.maxWidth='100%';img.style.maxHeight='290px';img.style.height='auto';img.style.objectFit='contain';img.onerror=()=>{};img.onload=()=>host.replaceChildren(img);}
  function sourceMetrics(rows){
    if(!rows.length)return null;const cust=col(rows[0],'customer'),order=col(rows[0],'order');if(!cust||!order)return null;
    const date=col(rows[0],'date'),qty=col(rows[0],'quantity'),price=col(rows[0],'price'),amount=col(rows[0],'amount');
    const valid=rows.filter(r=>{if(!String(r[cust]??'').trim()||!String(r[order]??'').trim())return false;if(String(r[order]).trim().toUpperCase().startsWith('C'))return false;if(date&&!Number.isFinite(Date.parse(r[date])))return false;if(qty&&(!Number.isFinite(number(r[qty]))||number(r[qty])<=0))return false;if(price&&(!Number.isFinite(number(r[price]))||number(r[price])<=0))return false;return true;});const ordersByCustomer=new Map(),orders=new Map();
    for(const r of valid){const key=`${r[cust]}::${String(r[order]).trim()}`;if(!orders.has(key))orders.set(key,{customer:r[cust],date:date?Date.parse(r[date]):NaN,revenue:0});let rev=amount?number(r[amount]):qty&&price?number(r[qty])*number(r[price]):NaN;if(Number.isFinite(rev)&&rev>0)orders.get(key).revenue+=rev;ordersByCustomer.set(r[cust],(ordersByCustomer.get(r[cust])||new Set()).add(key));}
    const customerCounts=[...ordersByCustomer.values()],repeat=customerCounts.filter(s=>s.size>1).length,rev=[...orders.values()].reduce((s,o)=>s+o.revenue,0);let intervals=[];
    if(date){for(const [customer,set] of ordersByCustomer){const dates=[...set].map(id=>orders.get(id).date).filter(Number.isFinite).sort((a,b)=>a-b);for(let i=1;i<dates.length;i++)intervals.push((dates[i]-dates[i-1])/86400000);}}
    return{orders:orders.size,customers:customerCounts.length,repeat,rate:customerCounts.length?repeat/customerCounts.length:NaN,revenue:rev,aov:orders.size?rev/orders.size:NaN,days:median(intervals)};
  }
  function summaryMetrics(rows){if(!rows.length)return{};const first=rows[0],sum=(key)=>key?rows.reduce((a,r)=>a+(number(r[key])||0),0):NaN;const k={orders:col(first,'orders'),revenue:col(first,'revenue')};let revenue=sum(k.revenue),orders=sum(k.orders);return{orders,customers:NaN,repeat:NaN,rate:NaN,revenue,aov:revenue/orders,days:NaN};}
  async function load(){
    setStatus('Loading project CSV files…');
    try{
      const [monthly,cohorts]=await Promise.all([csv('monthly_summary.csv'),csv('cohort_retention.csv')]);
      let source=[];for(const name of ['Online Retail.csv','orders.csv','online_retail.csv','data.csv','retail.csv']){source=await csv(name,true);if(source.length&&col(source[0],'customer')&&col(source[0],'order'))break;source=[];}
      if(!source.length){for(const name of ['retention_data.csv','ecommerce_data.csv','customer_orders.csv']){source=await csv(name,true);if(source.length&&col(source[0],'customer')&&col(source[0],'order'))break;source=[];}}
      const m=source.length?sourceMetrics(source):summaryMetrics(monthly);
      setMetric('orders',fmt(m.orders));setMetric('customers',fmt(m.customers));setMetric('repeat',fmt(m.repeat));setMetric('rate',Number.isFinite(m.rate)?`${(m.rate*100).toFixed(1)}%`:'—');setMetric('aov',money(m.aov));setMetric('revenue',money(m.revenue));setMetric('days',Number.isFinite(m.days)?`${fmt(m.days)} days`:'—');setMetric('days-callout',Number.isFinite(m.days)?`${fmt(m.days)} days`:'—');
      if(!source.length){$('repeat-foot').textContent='Calculated when represented in the summary';setStatus('Showing metrics available in the generated summaries. Add the source order CSV to calculate customer-level metrics and order intervals.','info');}else setStatus('Project data loaded successfully.','info');
      drawRevenue(monthly);drawHeatmap(cohorts);fallbackImage('days_between_orders.png',$('gap-image'));
    }catch(err){setStatus(err.message||'Could not load the project data.','error');$('revenue-empty').textContent='Start a local web server and refresh this page.';$('heatmap').innerHTML='<div class="empty-chart">Start a local web server and refresh this page.</div>';}
  }
  async function runTestSuite(endpoint,buttonId,buttonLabel,suiteLabel){
    const button=$(buttonId),summary=$('test-summary'),results=$('test-results');
    button.disabled=true;button.textContent='Running…';summary.textContent=`Running ${suiteLabel}…`;results.innerHTML='<div class="test-loading">Checking test cases</div>';
    try{
      const response=await fetch(endpoint,{cache:'no-store'});if(!response.ok)throw Error(`Test runner returned HTTP ${response.status}`);
      const data=await response.json();
      summary.textContent=`${data.passed} passed · ${data.failed} failed · ${data.skipped} skipped`;
      results.innerHTML='';
      if(data.cases.length){for(const item of data.cases){const row=document.createElement('div');row.className='test-row';const name=document.createElement('span');name.className='test-name';name.textContent=item.name;const badge=document.createElement('span');badge.className=`test-badge ${item.status==='passed'?'pass':item.status==='failed'?'fail':'skip'}`;badge.textContent=item.status.toUpperCase();row.append(name,badge);results.append(row);}}
      else{summary.textContent=data.success?'Test command completed, but no individual test cases were reported.':'Test run could not report individual cases.';}
      if(!data.success||data.output.includes('FAILED')||!data.cases.length){const detail=document.createElement('pre');detail.className='test-error';detail.textContent=data.output||'No test output was returned.';results.append(detail);}
    }catch(error){summary.textContent='Could not retrieve test results.';results.innerHTML='';const detail=document.createElement('pre');detail.className='test-error';detail.textContent=`${error.message}\nStart the site with: python dashboard_server.py`;results.append(detail);}
    finally{button.disabled=false;button.textContent=buttonLabel;}
  }
  $('run-tests').addEventListener('click',()=>runTestSuite('/api/tests','run-tests','▶  Run Python tests','Python test suite'));
  $('run-browser-tests').addEventListener('click',()=>runTestSuite('/api/browser-tests','run-browser-tests','◉  Run browser tests','Playwright browser suite'));
  $('refresh').addEventListener('click',load);window.addEventListener('resize',()=>{csv('monthly_summary.csv',true).then(drawRevenue).catch(()=>{});});load();
})();
