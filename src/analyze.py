"""Reproducible order-grain Olist fulfillment analysis. Run: python -m src.analyze"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data' / 'raw'
OUT = ROOT / 'outputs'
MIN_GROUP = 100

def read_sources():
    names = {'orders':'olist_orders_dataset.csv','items':'olist_order_items_dataset.csv',
             'sellers':'olist_sellers_dataset.csv','customers':'olist_customers_dataset.csv'}
    tables = {k:pd.read_csv(RAW/v) for k,v in names.items()}
    keys = {'orders':['order_id'],'items':['order_id','order_item_id'],
            'sellers':['seller_id'],'customers':['customer_id']}
    audit=[]
    for k,d in tables.items():
        audit.append({'table':k,'rows':len(d),'columns':len(d.columns),
                      'key_duplicates':int(d.duplicated(keys[k]).sum()),
                      'exact_duplicates':int(d.duplicated().sum()),
                      'missing_cells':int(d.isna().sum().sum())})
        assert not d.duplicated(keys[k]).any(), f'{k} duplicate key'
    return tables,pd.DataFrame(audit)

def build_orders(t):
    o,i,s,c = (t[k].copy() for k in ('orders','items','sellers','customers'))
    times=['order_purchase_timestamp','order_approved_at','order_delivered_carrier_date',
           'order_delivered_customer_date','order_estimated_delivery_date']
    for col in times: o[col]=pd.to_datetime(o[col],errors='coerce')
    i['shipping_limit_date']=pd.to_datetime(i['shipping_limit_date'],errors='coerce')
    ia=i.groupby('order_id').agg(item_rows=('order_item_id','size'), seller_count=('seller_id','nunique'),
        first_deadline=('shipping_limit_date','min'),last_deadline=('shipping_limit_date','max')).reset_index()
    si=i[['order_id','seller_id']].drop_duplicates().merge(s[['seller_id','seller_state']],on='seller_id',validate='many_to_one')
    sa=si.groupby('order_id').agg(seller_state=('seller_state','first')).reset_index()
    d=o.merge(ia,on='order_id',how='left',validate='one_to_one').merge(
      c[['customer_id','customer_state']],on='customer_id',how='left',validate='many_to_one').merge(
      sa,on='order_id',how='left',validate='one_to_one')
    assert len(d)==len(o) and d.order_id.is_unique
    d['purchase_month']=d.order_purchase_timestamp.dt.to_period('M').astype(str)
    d['time_anomaly']=(
      (d.order_delivered_carrier_date<d.order_purchase_timestamp)|
      (d.order_delivered_customer_date<d.order_delivered_carrier_date)|
      (d.order_estimated_delivery_date<d.order_purchase_timestamp)|
      (d.first_deadline<d.order_purchase_timestamp)).fillna(False)
    d['observed_delivery']=d.order_status.eq('delivered')&d.order_delivered_customer_date.notna()&d.order_estimated_delivery_date.notna()
    d['late']=pd.Series(pd.NA,index=d.index,dtype='boolean')
    d.loc[d.observed_delivery,'late']=d.loc[d.observed_delivery,'order_delivered_customer_date'].gt(d.loc[d.observed_delivery,'order_estimated_delivery_date']).values
    d['late_calendar_day']=pd.Series(pd.NA,index=d.index,dtype='boolean')
    d.loc[d.observed_delivery,'late_calendar_day']=(d.loc[d.observed_delivery,'order_delivered_customer_date'].dt.normalize()>
      d.loc[d.observed_delivery,'order_estimated_delivery_date'].dt.normalize()).values
    for name,end,start in [('pre_carrier_days','order_delivered_carrier_date','order_purchase_timestamp'),
                           ('carrier_to_customer_days','order_delivered_customer_date','order_delivered_carrier_date'),
                           ('promised_window_days','order_estimated_delivery_date','order_purchase_timestamp')]:
        d[name]=(d[end]-d[start]).dt.total_seconds()/86400
    d['late_days']=np.where(d.late.fillna(False),
       (d.order_delivered_customer_date-d.order_estimated_delivery_date).dt.total_seconds()/86400,np.nan)
    d['handover_late']=pd.Series(pd.NA,index=d.index,dtype='boolean')
    valid=d.seller_count.eq(1)&d.order_delivered_carrier_date.notna()&d.last_deadline.notna()&~d.time_anomaly
    d.loc[valid,'handover_late']=d.loc[valid,'order_delivered_carrier_date'].gt(d.loc[valid,'last_deadline']).values
    return d

def summarize(d,audit):
    a=d[d.observed_delivery&~d.time_anomaly].copy()
    x=a[a.seller_count.eq(1)&a.handover_late.notna()].copy()
    ct=pd.crosstab(x.handover_late.astype(bool),x.late.astype(bool)).reindex(index=[False,True],columns=[False,True],fill_value=0)
    rates=ct[True]/ct.sum(axis=1)
    monthly=a.groupby('purchase_month').agg(delivered=('order_id','size'),late=('late','sum'),
       pre_carrier_days=('pre_carrier_days','mean'),carrier_to_customer_days=('carrier_to_customer_days','mean'),
       promised_window_days=('promised_window_days','mean')).reset_index()
    monthly['late_rate']=monthly.late/monthly.delivered
    cohorts=d.groupby('purchase_month').agg(all_orders=('order_id','size'),observed=('observed_delivery','sum')).reset_index()
    monthly=monthly.merge(cohorts,on='purchase_month')
    monthly['observed_share']=monthly.observed/monthly.all_orders
    monthly['mature_comparable']=monthly.purchase_month.between('2017-01','2018-06')&(monthly.observed_share>=0.90)&(monthly.delivered>=100)
    hm=x.groupby('purchase_month').agg(handover_n=('order_id','size'),handover_late=('handover_late','sum')).reset_index()
    hm['handover_late_rate']=hm.handover_late/hm.handover_n
    monthly=monthly.merge(hm,on='purchase_month',how='left')
    def groups(col):
        g=x.groupby([col,'handover_late'],dropna=False).agg(n=('order_id','size'),late=('late','sum')).reset_index()
        g['late_rate']=g.late/g.n
        g['eligible']=g.n>=MIN_GROUP
        return g
    regional=a.groupby('customer_state').agg(n=('order_id','size'),late=('late','sum')).reset_index()
    regional['late_rate']=regional.late/regional.n
    regional['eligible']=regional.n>=MIN_GROUP
    regional=regional.sort_values('n',ascending=False)
    mix=a[a.purchase_month.isin(['2018-02','2018-03','2018-04'])].groupby(['purchase_month','customer_state']).agg(
      n=('order_id','size'),late=('late','sum')).reset_index()
    mix['cohort_share']=mix.n/mix.groupby('purchase_month').n.transform('sum')
    mix['late_rate']=mix.late/mix.n
    exclusion=pd.DataFrame([
      {'reason':'All source orders','orders':len(d)},
      {'reason':'Status not delivered','orders':int((~d.order_status.eq('delivered')).sum())},
      {'reason':'Delivered status, missing actual or promised date','orders':int((d.order_status.eq('delivered')&~d.observed_delivery).sum())},
      {'reason':'Observed delivery, chronological anomaly excluded','orders':int((d.observed_delivery&d.time_anomaly).sum())},
      {'reason':'Valid customer-delivery KPI denominator','orders':len(a)},
      {'reason':'Multi-seller, excluded from handover study','orders':int(a.seller_count.gt(1).sum())},
      {'reason':'Single-seller with missing carrier/deadline','orders':int((a.seller_count.eq(1)&a.handover_late.isna()).sum())},
      {'reason':'Valid single-seller handover comparison','orders':len(x)}])
    metrics={'source_orders':len(d),'delivered_valid':len(a),'late_orders':int(a.late.sum()),
       'late_rate':float(a.late.mean()),'on_time_rate':float((~a.late).mean()),
       'calendar_late_rate':float(a.late_calendar_day.mean()),'single_seller_comparison':len(x),
       'handover_on_time_n':int(ct.loc[False].sum()),'handover_late_n':int(ct.loc[True].sum()),
       'late_rate_handover_on_time':float(rates.loc[False]),'late_rate_handover_late':float(rates.loc[True]),
       'risk_difference_pp':float((rates.loc[True]-rates.loc[False])*100),
       'relative_risk':float(rates.loc[True]/rates.loc[False]),
       'chronological_anomalies':int(d.time_anomaly.sum()),
       'late_days_mean':float(a.late_days.mean()),
       'purchase_min':str(d.order_purchase_timestamp.min().date()),'purchase_max':str(d.order_purchase_timestamp.max().date())}
    multi=a[a.seller_count.gt(1)&a.order_delivered_carrier_date.notna()&a.first_deadline.notna()&a.last_deadline.notna()]
    metrics['multi_seller_valid_n']=len(multi)
    metrics['multi_seller_late_first_deadline_rate']=float((multi.order_delivered_carrier_date>multi.first_deadline).mean())
    metrics['multi_seller_late_last_deadline_rate']=float((multi.order_delivered_carrier_date>multi.last_deadline).mean())
    metrics['item_rows']=int(a.item_rows.sum())
    march=monthly.loc[monthly.purchase_month.eq('2018-03')].iloc[0]
    metrics['march_2018_late_rate']=float(march.late_rate)
    metrics['march_2018_late_n']=int(march.late)
    metrics['march_2018_delivered_n']=int(march.delivered)
    return a,x,ct,monthly,regional,mix,exclusion,metrics,groups

def risk_backtest(d):
    # Reconstruct Monday intake without filtering on eventual status or future outcomes.
    cutoff=pd.Timestamp('2018-01-01')
    history=d[d.observed_delivery&~d.time_anomaly&(d.order_delivered_customer_date<cutoff)].copy()
    candidate=d[d.order_purchase_timestamp.between(cutoff,pd.Timestamp('2018-07-01'),inclusive='left')&
                d.order_estimated_delivery_date.notna()&d.customer_state.notna()].copy()
    candidate['decision_time']=candidate.order_purchase_timestamp.dt.to_period('W-SUN').dt.start_time+pd.Timedelta(days=7)
    created=len(candidate)
    already_delivered=candidate.order_delivered_customer_date.notna()&(candidate.order_delivered_customer_date<candidate.decision_time)
    candidate=candidate[~already_delivered].copy()
    assert candidate.order_purchase_timestamp.lt(candidate.decision_time).all()
    assert (~(candidate.order_delivered_customer_date<candidate.decision_time)).all()
    candidate['overdue_at_review']=candidate.order_estimated_delivery_date.lt(candidate.decision_time)
    candidate['observable_outcome']=candidate.observed_delivery&~candidate.time_anomaly
    candidate['observed_late']=candidate.observable_outcome&candidate.late.fillna(False)
    prior=history.groupby('customer_state').agg(prior_n=('order_id','size'),prior_late=('late','sum')).reset_index()
    global_rate=float(history.late.mean())
    candidate=candidate.merge(prior,on='customer_state',how='left',validate='many_to_one')
    candidate[['prior_n','prior_late']]=candidate[['prior_n','prior_late']].fillna(0)
    candidate['historical_state_risk']=(candidate.prior_late+200*global_rate)/(candidate.prior_n+200)
    candidate['remaining_days']=(candidate.order_estimated_delivery_date-candidate.decision_time).dt.total_seconds()/86400
    candidate['score']=candidate.historical_state_risk+0.0015*(15-candidate.remaining_days.clip(-30,60))
    # Already overdue is a known exception at Monday; evaluate advance warning only before due.
    test=candidate[~candidate.overdue_at_review].copy()
    # Fixed score thresholds from test score distribution do not use labels, but label as retrospective calibration.
    q1,q2=test.score.quantile([1/3,2/3])
    test['risk_tier']=pd.cut(test.score,[-np.inf,q1,q2,np.inf],labels=['Low','Medium','High'],include_lowest=True)
    tiers=test.groupby('risk_tier',observed=True).agg(n=('order_id','size'),observed_n=('observable_outcome','sum'),late=('observed_late','sum')).reset_index()
    tiers['late_rate']=tiers.late/tiers.observed_n
    batches=[g for _,g in test.groupby('decision_time')]
    fifo=pd.concat([g.nsmallest(int(np.ceil(len(g)*.10)),'order_purchase_timestamp') for g in batches])
    ranked=pd.concat([g.nlargest(int(np.ceil(len(g)*.10)),'score') for g in batches])
    k=len(fifo)
    assert len(ranked)==k
    late_total=int(test.observed_late.sum())
    back={'history_n':len(history),'candidate_n':len(candidate),'candidate_unique_n':candidate.order_id.nunique(),
          'candidate_observable_n':int(candidate.observable_outcome.sum()),
          'candidate_unknown_n':int((~candidate.observable_outcome).sum()),
          'candidate_overdue_n':int(candidate.overdue_at_review.sum()),
          'candidate_overdue_observed_n':int(candidate.loc[candidate.overdue_at_review,'observable_outcome'].sum()),
          'candidate_overdue_late_n':int(candidate.loc[candidate.overdue_at_review,'observed_late'].sum()),
          'candidate_not_due_n':len(test),'candidate_not_due_observed_n':int(test.observable_outcome.sum()),
          'candidate_not_due_late_n':late_total,
          'test_n':len(test),'test_late_n':late_total,
          'top_k':k,'fifo_late_found':int(fifo.observed_late.sum()),'risk_late_found':int(ranked.observed_late.sum()),
          'fifo_selected_unique_n':fifo.order_id.nunique(),'risk_selected_unique_n':ranked.order_id.nunique(),
          'fifo_unique_late_n':fifo.loc[fifo.observed_late,'order_id'].nunique(),
          'risk_unique_late_n':ranked.loc[ranked.observed_late,'order_id'].nunique(),
          'fifo_selected_observed_n':int(fifo.observable_outcome.sum()),
          'risk_selected_observed_n':int(ranked.observable_outcome.sum()),
          'fifo_hits_per_slot':float(fifo.observed_late.sum()/k),'risk_hits_per_slot':float(ranked.observed_late.sum()/k),
          'fifo_precision':float(fifo.observed_late.sum()/fifo.observable_outcome.sum()),
          'risk_precision':float(ranked.observed_late.sum()/ranked.observable_outcome.sum()),
          'fifo_recall':float(fifo.observed_late.sum()/late_total),'risk_recall':float(ranked.observed_late.sum()/late_total),
          'history_last_delivery':str(history.order_delivered_customer_date.max()),
          'test_first_purchase':str(test.order_purchase_timestamp.min()),
          'weekly_batches':len(batches),'orders_delivered_before_review_excluded':int(created-len(candidate)),
          'selection_repeat_count':int((fifo.order_id.value_counts().sub(1).clip(lower=0)).sum() +
                                       (ranked.order_id.value_counts().sub(1).clip(lower=0)).sum()),
          'strict_history_before_first_review':bool(history.order_delivered_customer_date.max()<candidate.decision_time.min())}
    cols=['order_id','order_purchase_timestamp','decision_time','customer_state','remaining_days','historical_state_risk','score','risk_tier','observable_outcome','observed_late']
    return test,tiers,ranked.nlargest(30,'score')[cols],back

def charts(monthly,ct,regional,tiers,output):
    font=ImageFont.load_default()
    def plot(rows,title,unit,path,max_y=None):
        rows=list(rows);w=max(900,120+len(rows)*56);h=470
        im=Image.new('RGB',(w,h),'white');dr=ImageDraw.Draw(im)
        dr.text((35,18),title,fill='#152c45',font=font)
        dr.text((35,42),unit,fill='#44566a',font=font)
        left,right,top,bottom=70,w-25,85,390
        ymax=max_y or max(v for _,v,_ in rows)*1.2
        for p in range(5):
            y=bottom-(bottom-top)*p/4
            dr.line((left,y,right,y),fill='#d7dee5',width=1)
            dr.text((10,y-6),f'{ymax*p/4:.1f}',fill='#44566a',font=font)
        slot=(right-left)/len(rows)
        for j,(label,val,n) in enumerate(rows):
            x=left+(j+0.5)*slot; y=bottom-(val/ymax)*(bottom-top)
            dr.rectangle((x-slot*.28,y,x+slot*.28,bottom),fill='#3478a8')
            dr.text((x-20,max(top,y-17)),f'{val:.1f}',fill='#152c45',font=font)
            dr.text((x-23,bottom+8),str(label),fill='#152c45',font=font)
            if n is not None:dr.text((x-25,bottom+27),f'n={n:,}',fill='#566778',font=font)
        im.save(output/path)
    m=monthly[monthly.mature_comparable]
    plot([(r.purchase_month,r.late_rate*100,r.delivered) for r in m.itertuples()],
         'Monthly customer late rate | mature purchase cohorts','Late deliveries (%)','monthly_late_rate.png')
    rr=ct[True]/ct.sum(axis=1)
    plot([('On-time',rr.loc[False]*100,int(ct.loc[False].sum())),('Late',rr.loc[True]*100,int(ct.loc[True].sum()))],
         'Handover timing and customer delivery | single seller','Customer late rate (%)','handover_vs_delivery.png')
    r=regional[regional.eligible].head(12)
    plot([(v.customer_state,v.late_rate*100,v.n) for v in r.itertuples()],
         'Customer state late rate | delivered, n >= 100','Late deliveries (%)','regional_late_rate.png')
    focus=monthly[monthly.purchase_month.isin(['2018-02','2018-03','2018-04'])]
    plot([(v.purchase_month,v.pre_carrier_days,None) for v in focus.itertuples()],
         'Pre-carrier lead time | delivered purchase cohorts','Mean days','pre_carrier_lead_time.png')
    plot([(v.purchase_month,v.carrier_to_customer_days,None) for v in focus.itertuples()],
         'Carrier-to-customer lead time | delivered purchase cohorts','Mean days','carrier_to_customer_lead_time.png')
    plot([(str(v.risk_tier),v.late_rate*100,v.observed_n) for v in tiers.itertuples()],
         'Weekly-review risk tiers | labeled subset of not-yet-due orders','Observed late rate (%)','risk_tiers.png')

def main():
    OUT.mkdir(exist_ok=True)
    tables,audit=read_sources();d=build_orders(tables)
    anomalies=d[d.observed_delivery&d.time_anomaly].copy()
    anomalies['anomaly_reason']=np.select([
        anomalies.order_delivered_carrier_date<anomalies.order_purchase_timestamp,
        anomalies.order_delivered_customer_date<anomalies.order_delivered_carrier_date,
        anomalies.order_estimated_delivery_date<anomalies.order_purchase_timestamp,
        anomalies.first_deadline<anomalies.order_purchase_timestamp],
        ['carrier_before_purchase','customer_before_carrier','estimate_before_purchase','deadline_before_purchase'],default='other')
    anomalies[['order_id','anomaly_reason','order_purchase_timestamp','order_delivered_carrier_date',
               'order_delivered_customer_date','order_estimated_delivery_date','first_deadline','late']].to_csv(
                   OUT/'timestamp_anomalies.csv',index=False)
    a,x,ct,monthly,regional,mix,exclusion,metrics,groups=summarize(d,audit)
    test,tiers,high,back=risk_backtest(d)
    metrics.update(back)
    audit.to_csv(OUT/'source_audit.csv',index=False)
    exclusion.to_csv(OUT/'sample_reconciliation.csv',index=False)
    monthly.to_csv(OUT/'monthly_trends.csv',index=False)
    regional.to_csv(OUT/'regional_analysis.csv',index=False)
    mix.to_csv(OUT/'monthly_region_mix.csv',index=False)
    tiers.to_csv(OUT/'risk_tiers.csv',index=False)
    high.to_csv(OUT/'high_risk_examples.csv',index=False)
    pd.DataFrame(ct.values,index=['On-time handover','Late handover'],columns=['Customer on-time','Customer late']).to_csv(OUT/'handover_crosstab.csv')
    for col,filename in [('purchase_month','handover_by_month.csv'),('seller_state','handover_by_seller_state.csv'),('customer_state','handover_by_customer_state.csv')]:groups(col).to_csv(OUT/filename,index=False)
    a[['order_id','purchase_month','customer_state','seller_count','late','late_calendar_day','pre_carrier_days','carrier_to_customer_days','promised_window_days','late_days']].to_csv(OUT/'order_level_kpis.csv',index=False)
    charts(monthly,ct,regional,tiers,OUT)
    (OUT/'metrics.json').write_text(json.dumps(metrics,indent=2),encoding='utf-8')
    print(json.dumps(metrics,indent=2))

if __name__=='__main__':main()
