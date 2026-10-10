import fs from 'node:fs/promises';
import { Workbook, SpreadsheetFile } from '@oai/artifact-tool';

const data=JSON.parse(await fs.readFile('work/workbook_data.json','utf8'));
const m=data.metrics;
const wb=Workbook.create();
const navy='#16324F', teal='#087E8B', pale='#E9F3F5';
function sheet(name,title,subtitle,headers,rows,widths=[]){
  const s=wb.worksheets.add(name);
  const n=Math.max(headers.length,4);
  s.getRange(`A1:${String.fromCharCode(64+n)}1`).format={fill:navy,font:{name:'Arial',size:15,bold:true,color:'#FFFFFF'},rowHeight:32};
  s.getRange('A1').values=[[title]];
  s.getRange('A2').values=[[subtitle]];
  s.getRange(`A2:${String.fromCharCode(64+n)}2`).format={fill:pale,font:{name:'Arial',size:10,color:navy},rowHeight:26};
  s.getRange(`A4:${String.fromCharCode(64+headers.length)}4`).values=[headers];
  s.getRange(`A4:${String.fromCharCode(64+headers.length)}4`).format={fill:teal,font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},rowHeight:26};
  if(rows.length) s.getRange(`A5:${String.fromCharCode(64+headers.length)}${4+rows.length}`).values=rows.map(r=>r.map(v=>v===undefined||v===null||Number.isNaN(v)?'':v));
  s.getRange(`A5:${String.fromCharCode(64+headers.length)}${Math.max(5,4+rows.length)}`).format.font={name:'Arial',size:10,color:navy};
  for(let j=0;j<headers.length;j++)s.getRange(`${String.fromCharCode(65+j)}:${String.fromCharCode(65+j)}`).format.columnWidth=widths[j]||18;
  s.freezePanes.freezeRows(4);
  return s;
}
const summary=[
 ['Source orders',m.source_orders,'Olist order table'],['Valid delivered orders',m.delivered_valid,'Delivered, both dates present, no chronology anomaly'],
 ['Customer on-time rate',m.on_time_rate,'Full timestamp comparison'],['Customer late rate',m.late_rate,'Full timestamp comparison'],
 ['Calendar-day late rate',m.calendar_late_rate,'Sensitivity check'],['March 2018 late rate',m.march_2018_late_rate,'Valid delivered purchase cohort'],
 ['Handover late-rate gap (pp)',m.risk_difference_pp,'Late vs on-time handover, single seller'],
 ['Relative risk',m.relative_risk,'Descriptive association'],['Offline top-K risk found',m.risk_late_found,'K='+m.top_k],
 ['Offline top-K FIFO found',m.fifo_late_found,'Same K; no intervention measured']];
let s=sheet('Executive Summary','Order Fulfillment & Delivery Risk Analysis',
  'Olist e-commerce case study | purchase range '+m.purchase_min+' to '+m.purchase_max+' | not TCL operating data',
  ['Business measure','Value','Interpretation'],summary,[31,18,68]);
s.getRange('B7:B10').format.numberFormat='0.00%';
s.getRange('B11:B12').format.numberFormat='0.00';
const kpis=[
 ['Source orders',m.source_orders],['Not delivered status',data.sample[1].orders],['Delivered missing dates',data.sample[2].orders],
 ['Observed chronology exclusions',data.sample[3].orders],['Valid delivered denominator',m.delivered_valid],
 ['On-time delivered',m.delivered_valid-m.late_orders],['Late delivered',m.late_orders],
 ['On-time rate',m.on_time_rate],['Late rate',m.late_rate],['Calendar-day late rate',m.calendar_late_rate],
 ['Late days, mean among late',m.late_days_mean],['Source chronology anomalies',m.chronological_anomalies],
 ['Item rows in valid sample',m.item_rows]];
s=sheet('KPI Overview','KPI Overview','Order grain unless otherwise stated; full timestamp primary definition',
 ['KPI','Value'],kpis,[42,20]);s.getRange('B12:B14').format.numberFormat='0.00%';
const mm=data.monthly.map(r=>[r.purchase_month,r.delivered,r.late,r.late_rate,r.pre_carrier_days,r.carrier_to_customer_days,r.promised_window_days,r.handover_late_rate,r.observed_share,r.mature_comparable?'Yes':'No']);
s=sheet('Monthly Trends','Monthly Trends','Purchase cohorts | comparable: Jan 2017–Jun 2018, n≥100 and observed share≥90%',
 ['Month','Delivered n','Late n','Late rate','Pre-carrier days','Post-carrier days','Promise days','Late handover rate','Observed share','Comparable'],mm,[16,16,14,16,20,21,18,20,18,16]);
s.getRange(`D5:D${4+mm.length}`).format.numberFormat='0.00%';s.getRange(`H5:I${4+mm.length}`).format.numberFormat='0.00%';
s.getRange(`E5:G${4+mm.length}`).format.numberFormat='0.00';
const hh=[['On-time handover',m.handover_on_time_n,data.handover[0]['Customer on-time'],data.handover[0]['Customer late'],m.late_rate_handover_on_time],
 ['Late handover',m.handover_late_n,data.handover[1]['Customer on-time'],data.handover[1]['Customer late'],m.late_rate_handover_late],
 ['Difference, percentage points','', '', '',m.risk_difference_pp],['Relative risk','','','',m.relative_risk],
 ['Multi-seller first deadline',m.multi_seller_valid_n,'','',''+(m.multi_seller_late_first_deadline_rate*100).toFixed(2)+'%'],
 ['Multi-seller last deadline',m.multi_seller_valid_n,'','',''+(m.multi_seller_late_last_deadline_rate*100).toFixed(2)+'%']];
s=sheet('Handover Analysis','Handover Analysis','Single-seller valid delivered orders; order-level carrier timestamp vs latest item deadline',
  ['Group','Orders','Customer on-time','Customer late','Customer late rate / statistic'],hh,[34,18,22,20,34]);s.getRange('E5:E6').format.numberFormat='0.00%';
const seg=[];
for(const [type,rows,key] of [['Month',data.by_month,'purchase_month'],['Seller state',data.by_seller,'seller_state'],['Customer state',data.by_customer,'customer_state']])
  for(const r of rows) if(r.eligible) seg.push([type,r[key],r.handover_late?'Late':'On-time',r.n,r.late,r.late_rate]);
s=sheet('Handover Segments','Handover Segments','Valid single-seller comparison | each displayed group n≥100',
 ['Dimension','Group','Handover','Orders','Customer late','Late rate'],seg,[20,20,18,16,19,18]);
s.getRange(`F5:F${4+seg.length}`).format.numberFormat='0.00%';
const rr=data.regions.map(r=>[r.customer_state,r.n,r.late,r.late_rate,r.eligible?'Yes':'No']);
s=sheet('Regional Analysis','Regional Analysis','Customer destination state | minimum reporting n=100',
 ['Customer state','Delivered n','Late n','Late rate','Eligible'],rr,[22,18,16,18,16]);s.getRange(`D5:D${4+rr.length}`).format.numberFormat='0.00%';
const mix=data.mix.filter(r=>r.n>=100).map(r=>[r.purchase_month,r.customer_state,r.n,r.cohort_share,r.late,r.late_rate]);
s=sheet('Regional Mix','Regional Mix | Feb–Apr 2018','Customer-state composition by purchase month; displayed cells n≥100',
 ['Month','Customer state','Delivered n','Cohort share','Late n','Late rate'],mix,[17,22,18,19,16,18]);
s.getRange(`D5:D${4+mix.length}`).format.numberFormat='0.00%';s.getRange(`F5:F${4+mix.length}`).format.numberFormat='0.00%';
const riskRows=[
 ['All Monday candidates',m.candidate_n,m.candidate_observable_n,'','',''],
 ['Already overdue',m.candidate_overdue_n,m.candidate_overdue_observed_n,m.candidate_overdue_late_n,'',''],
 ['Not yet due',m.candidate_not_due_n,m.candidate_not_due_observed_n,m.candidate_not_due_late_n,
  m.candidate_not_due_late_n/m.candidate_not_due_observed_n,''],
 ...data.tiers.map(r=>[r.risk_tier,r.n,r.observed_n,r.late,r.late_rate,'']),
 ['Top 10% scored',m.risk_selected_unique_n,m.risk_selected_observed_n,m.risk_unique_late_n,m.risk_precision,m.risk_hits_per_slot],
 ['Top 10% FIFO',m.fifo_selected_unique_n,m.fifo_selected_observed_n,m.fifo_unique_late_n,m.fifo_precision,m.fifo_hits_per_slot]
];
s=sheet('Risk Prioritization','Risk Prioritization','First Monday review of prior-week purchases, not rolling backlog; same pool/capacity; no future status filter',
 ['Pool / tier / rule','Unique orders / slots','Labeled n','Unique late hits','Late / labeled','Hits / slot'],riskRows,[29,23,18,19,20,18]);
s.getRange('E7:F12').format.numberFormat='0.00%';
const examples=data.high.map(r=>[r.order_id,r.order_purchase_timestamp,r.decision_time,r.customer_state,r.remaining_days,r.historical_state_risk,r.score,r.risk_tier,r.observable_outcome,r.observed_late]);
s=sheet('High Risk Examples','High Risk Examples','Weekly decision examples; actual late flag is retrospective verification only',
 ['Order ID','Purchase time','Review time','Customer state','Days remaining','Historical state risk','Score','Tier','Labeled','Observed late'],examples,
 [39,25,25,19,18,24,18,15,16,18]);
s.getRange(`F5:F${4+examples.length}`).format.numberFormat='0.00%';
const dict=[
 ['order_id','Orders','Unique order key','Order'],['order_item_id','Items','Sequence within order; not an order count','Item'],
 ['seller_id','Items / Sellers','Seller key; one order may have several','Item'],['customer_id','Orders / Customers','Customer record key','Order'],
 ['order_purchase_timestamp','Orders','Order creation / purchase time','Order'],['order_approved_at','Orders','Payment approval time; not production release','Order'],
 ['shipping_limit_date','Items','Seller item shipping deadline; latest deadline used for one-seller multi-item order','Item'],
 ['order_delivered_carrier_date','Orders','Order-level carrier handover event; not each seller actual','Order'],
 ['order_delivered_customer_date','Orders','Recorded customer receipt time','Order'],
 ['order_estimated_delivery_date','Orders','Promised/estimated customer delivery timestamp; may represent calendar date','Order'],
 ['customer_state','Customers','Customer destination state','Customer'],['seller_state','Sellers','Seller location state','Seller'],
 ['late','Derived','Actual delivery timestamp > estimated timestamp, valid delivered only','Order'],
 ['handover_late','Derived','Carrier timestamp > latest item deadline, single seller only','Order proxy'],
 ['pre_carrier_days','Derived','Purchase to carrier timestamp / 86400 seconds','Order'],
 ['carrier_to_customer_days','Derived','Carrier timestamp to customer delivery / 86400 seconds','Order'],
 ['promised_window_days','Derived','Purchase to estimated delivery / 86400 seconds','Order'],
 ['late_days','Derived','Positive overrun days only for late orders','Order']];
s=sheet('Data Dictionary','Data Dictionary','Source: supplied Olist Brazilian E-Commerce Dataset (original CSVs in data/raw)',
 ['Field','Source table','Business meaning / rule','Grain'],dict,[34,24,92,17]);
const ex=data.sample.map(r=>[r.reason,r.orders]);
s=sheet('Data Audit','Data Audit & Exclusions','Chronology anomalies are flagged; 188 observed deliveries excluded from KPI denominator',
 ['Reason','Orders'],ex,[65,18]);
const source=data.audit.map(r=>[r.table,r.rows,r.columns,r.key_duplicates,r.exact_duplicates,r.missing_cells]);
s=sheet('Source Tables','Source Tables','Supplied Olist CSVs; no synthetic raw orders',
 ['Table','Rows','Columns','Key duplicates','Exact duplicates','Missing cells'],source,[23,17,17,20,20,20]);
wb.recalculate();
const preview=await wb.render({sheetName:'Executive Summary',range:'A1:C15',scale:1.4,format:'png'});
await fs.writeFile('work/workbook_preview.png',new Uint8Array(await preview.arrayBuffer()));
for(const [name,range] of [['KPI Overview','A1:B17'],['Monthly Trends','A1:J11'],
  ['Handover Analysis','A1:E10'],['Handover Segments','A1:F10'],
  ['Regional Analysis','A1:E11'],['Regional Mix','A1:F11'],
  ['Risk Prioritization','A1:F12'],['High Risk Examples','A1:J9'],
  ['Data Dictionary','A1:D10'],['Data Audit','A1:B12'],['Source Tables','A1:F8']]){
  const p=await wb.render({sheetName:name,range,scale:1,format:'png'});
  await fs.writeFile('work/preview_'+name.toLowerCase().replaceAll(' ','_')+'.png',new Uint8Array(await p.arrayBuffer()));
}
const xlsx=await SpreadsheetFile.exportXlsx(wb);
await xlsx.save('outputs/Olist_Fulfillment_Analysis.xlsx');
console.log('Workbook saved: outputs/Olist_Fulfillment_Analysis.xlsx');
