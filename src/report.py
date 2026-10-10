"""Generate narrative reports and workbook input from computed outputs."""
from pathlib import Path
import json
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs'
WORK=ROOT/'work'

def pct(v):return f'{v*100:.2f}%'
def main():
    m=json.loads((OUT/'metrics.json').read_text())
    monthly=pd.read_csv(OUT/'monthly_trends.csv')
    regions=pd.read_csv(OUT/'regional_analysis.csv')
    mix=pd.read_csv(OUT/'monthly_region_mix.csv')
    tiers=pd.read_csv(OUT/'risk_tiers.csv')
    sample=pd.read_csv(OUT/'sample_reconciliation.csv')
    audit=pd.read_csv(OUT/'source_audit.csv')
    hand=pd.read_csv(OUT/'handover_crosstab.csv')
    mar=monthly.set_index('purchase_month').loc['2018-03'];apr=monthly.set_index('purchase_month').loc['2018-04']
    sp_mar=mix.set_index(['purchase_month','customer_state']).loc[('2018-03','SP')]
    sp_apr=mix.set_index(['purchase_month','customer_state']).loc[('2018-04','SP')]
    rj_mar=mix.set_index(['purchase_month','customer_state']).loc[('2018-03','RJ')]
    rj_apr=mix.set_index(['purchase_month','customer_state']).loc[('2018-04','RJ')]
    key={
      'source_orders':m['source_orders'],'valid_orders':m['delivered_valid'],'late_orders':m['late_orders'],
      'late_rate':pct(m['late_rate']),'calendar_late_rate':pct(m['calendar_late_rate']),
      'march_late_rate':pct(m['march_2018_late_rate']),'march_n':m['march_2018_delivered_n'],
      'handover_difference_pp':f"{m['risk_difference_pp']:.2f}",
      'relative_risk':f"{m['relative_risk']:.2f}",
      'risk_found':m['risk_late_found'],'fifo_found':m['fifo_late_found'],
      'top_k':m['top_k'],'high_tier_rate':pct(float(tiers.set_index('risk_tier').loc['High','late_rate']))}
    readme=f'''# Order Fulfillment & Delivery Risk Analysis | Olist E-Commerce Dataset

## Business Problem
For a supply chain planning interview, this project examines customer delivery performance, the handover stage, regional differences, and an order follow-up queue. It is a public Olist e-commerce case study, **not TCL operating data or factory experience**.

## Dataset & Provenance
The original Olist Brazilian E-Commerce public dataset was supplied as `archive.zip` by the project owner. Four source tables are retained in `data/raw/`; V1 is retained in `v1_reference/`. The source contains {m['source_orders']:,} orders purchased from {m['purchase_min']} to {m['purchase_max']}. No synthetic orders were created. `outputs/source_audit.csv` records row counts, keys, missing cells and duplicates.

## Methodology
- Order is the KPI grain. Item rows are aggregated before joining; there are {m['item_rows']:,} item rows across the valid delivered sample.
- The historical denominator is {m['delivered_valid']:,} orders with `delivered` status, actual and promised delivery dates, and no chronology anomaly. `outputs/sample_reconciliation.csv` gives every exclusion. Other statuses are not counted as on-time.
- Primary late definition compares full timestamps: actual delivery **after** estimated delivery. A calendar-day check compares normalized dates. Late days are positive days only among late orders.
- `order_delivered_carrier_date` is an **order-level proxy**. Seller handover analysis uses {m['single_seller_comparison']:,} single-seller delivered orders with valid carrier date and item deadline. For multi-item orders with one seller, the latest item deadline is the order-level rule. Multi-seller orders are excluded because seller-specific actual handover is unavailable. Among {m['multi_seller_valid_n']:,} multi-seller orders, the late-handover proxy varies from {pct(m['multi_seller_late_last_deadline_rate'])} (last deadline) to {pct(m['multi_seller_late_first_deadline_rate'])} (first deadline).
- Monthly cohorts use purchase month. The comparable chart covers Jan 2017–Jun 2018, delivered sample n≥100 and ≥90% observed delivery; later months are shown in the CSV but excluded from the main trend. This threshold limits, but cannot eliminate, cohort-selection bias.
- Grouped handover comparisons mark cells below n={100} as ineligible. Association is descriptive, not causal.
- The offline follow-up decision is each Monday after the prior week's purchases. This is a **first-review intake**, not a rolling backlog: older open orders are not reconsidered. The candidate pool uses only orders already created and not yet delivered at that Monday; it does **not** filter on final order status. Both rules see the same weekly pool and capacity: ceil(10% of that week's not-yet-due candidates). FIFO sorts by purchase time; the risk rule scores customer state and days remaining to promise. State rates use only orders delivered before 2018-01-01, strictly earlier than every review, with a 200-order empirical-Bayes prior. There are {m['candidate_n']:,} unique candidates: {m['candidate_overdue_n']:,} already overdue and {m['candidate_not_due_n']:,} not yet due. The zero overdue count reflects this intake design and must not be read as zero overdue orders in the full live backlog. Of the latter, {m['candidate_not_due_observed_n']:,} have valid observed delivery outcomes and {m['candidate_unknown_n']:,} have no valid delivery label. Unknown outcomes are never counted as on-time. Each order enters exactly one purchase-week batch, so repeated selection is zero. Final status and future delivery time are absent from scoring; the delivery event timestamp is used only to establish whether delivery had already occurred by Monday and for retrospective labels.

## Key Findings
1. {m['late_orders']:,} of {m['delivered_valid']:,} valid delivered orders were late: {pct(m['late_rate'])}; on-time was {pct(m['on_time_rate'])}. Calendar-day late rate was {pct(m['calendar_late_rate'])}.
2. Single-seller customer late rates were {pct(m['late_rate_handover_on_time'])} after on-time handover (n={m['handover_on_time_n']:,}) and {pct(m['late_rate_handover_late'])} after late handover (n={m['handover_late_n']:,}): +{m['risk_difference_pp']:.2f} percentage points, relative risk {m['relative_risk']:.2f}×.
3. March 2018 had {m['march_2018_late_n']:,} late among {m['march_2018_delivered_n']:,} valid deliveries ({pct(m['march_2018_late_rate'])}), versus {pct(float(apr.late_rate))} in April. The other prominent comparable peaks were February 2018 ({pct(float(monthly.set_index('purchase_month').loc['2018-02','late_rate']))}) and November 2017 ({pct(float(monthly.set_index('purchase_month').loc['2017-11','late_rate']))}).
4. March carrier-to-customer mean was {mar.carrier_to_customer_days:.2f} days versus April {apr.carrier_to_customer_days:.2f}; pre-carrier was {mar.pre_carrier_days:.2f} versus {apr.pre_carrier_days:.2f}. March's promised window was {mar.promised_window_days:.2f} versus April {apr.promised_window_days:.2f} days. This points to post-handover transit and promise-window pressure as stronger **descriptive** signals than a March spike in late handovers ({pct(float(mar.handover_late_rate))}). SP's cohort share was {pct(float(sp_mar.cohort_share))} in March and {pct(float(sp_apr.cohort_share))} in April; within-state late rates also rose (SP {pct(float(sp_mar.late_rate))} vs {pct(float(sp_apr.late_rate))}, RJ {pct(float(rj_mar.late_rate))} vs {pct(float(rj_apr.late_rate))}), so the March peak is not explained by a simple shift toward RJ.
5. In {m['weekly_batches']} matched weekly offline reviews of not-yet-due orders (n={m['test_n']:,}), both rules received {m['top_k']:,} slots. The risk rule found {m['risk_late_found']:,} unique observed late orders; FIFO found {m['fifo_late_found']:,}. Late hits per slot were {pct(m['risk_hits_per_slot'])} vs {pct(m['fifo_hits_per_slot'])}; among selected orders with valid delivery labels, late rates were {pct(m['risk_precision'])} (n={m['risk_selected_observed_n']:,}) and {pct(m['fifo_precision'])} (n={m['fifo_selected_observed_n']:,}). The high tier's late rate among labeled orders was {key['high_tier_rate']}.

## Operational Recommendations
- **High:** daily review; confirm seller shipment readiness and carrier booking; escalate when the shipping deadline is close or passed.
- **Medium:** review every 2–3 days and confirm promise-window slack.
- **Low:** standard queue and exception alerts.
- For late handovers, reconcile seller deadline against order-level carrier event before contacting a seller. For transit delays, review carrier lane and customer-state patterns with logistics partners. Test any intervention prospectively before claiming delivery improvement.

## Limitations
This is e-commerce, not manufacturing. There are no production, inventory, capacity, ERP, real-time order events, carrier route, or intervention outcomes. The carrier timestamp cannot establish individual seller handover on multi-seller orders. Chronology anomalies ({m['chronological_anomalies']:,} source orders) are flagged; {int(sample.loc[sample.reason.eq('Observed delivery, chronological anomaly excluded'),'orders'].iloc[0]):,} observed deliveries are excluded. V1 retained these 188, yielding 96,470 delivered orders; 165 have carrier time before purchase and 23 have customer delivery before carrier handover. `outputs/timestamp_anomalies.csv` lists the IDs, timestamps and rule. Delivered-only monthly rates can reflect selection, and later cohorts have shorter observation; no causal or realized KPI improvement is claimed. The weekly pool includes orders without an eventual valid delivery label; their fulfillment outcomes cannot be evaluated. Final cancellation time is unavailable, so "not delivered" cannot prove every candidate was still an active, uncanceled order on Monday.

## Reproducibility
Install `requirements.txt`, then run `./run.sh` from the project root. It rebuilds analysis CSVs, PNGs, narrative reports and the workbook. `python -m unittest discover -s tests -v` runs the validation tests. The workbook builder requires Node.js and `@oai/artifact-tool` in `node_modules` (the provided environment contains both). No personal absolute paths appear in code.

## Project Structure
`data/raw/` original four CSVs · `src/` analysis and report code · `tests/` checks · `outputs/` final workbook, reports, charts and audit tables · `v1_reference/` previous V1.
'''
    cn=f'''# 真实订单履约分析与交付延期风险预警

## 业务问题
以 Olist 巴西电商真实订单为案例，建立订单履约 KPI、交运异常定位和跟进优先级，展示供应链计划岗位所需的数据分析思路。该项目不是 TCL 或工厂实际业务。

## 数据范围
原始订单 {m['source_orders']:,} 笔；有效已交付订单 {m['delivered_valid']:,} 笔；采购时间 {m['purchase_min']} 至 {m['purchase_max']}。历史交付及时率仅以有实际和预计送达时间、且无时间先后异常的 delivered 订单为分母。主口径是完整时间戳，按日历日的延期率为 {pct(m['calendar_late_rate'])}。原始数据、排除原因与字段解释见工作簿。

## 主要发现
1. 客户延期 {m['late_orders']:,} 笔，延期率 {pct(m['late_rate'])}，准时率 {pct(m['on_time_rate'])}。
2. 单卖家订单中，按时交承运商组延期率 {pct(m['late_rate_handover_on_time'])}（n={m['handover_on_time_n']:,}），晚交运组 {pct(m['late_rate_handover_late'])}（n={m['handover_late_n']:,}），差 {m['risk_difference_pp']:.2f} 个百分点，相对风险 {m['relative_risk']:.2f} 倍；这仅是相关性。
3. 同样只看有效已交付订单，2018 年 3 月延期率 {pct(m['march_2018_late_rate'])}（n={m['march_2018_delivered_n']:,}），2 月 {pct(float(monthly.set_index('purchase_month').loc['2018-02','late_rate']))}，4 月 {pct(float(apr.late_rate))}。2017 年 11 月也是明显高峰。
4. 以每周一为共同决策时点，两种方法面对同一批已创建、尚未送达且承诺交期未到的订单，每周分配相同 10% 跟进名额。26 周合计 {m['top_k']:,} 个名额，风险排序识别 {m['risk_unique_late_n']:,} 笔唯一历史延期订单，FIFO 识别 {m['fifo_unique_late_n']:,} 笔；每名额延期命中率分别为 {pct(m['risk_hits_per_slot'])}、{pct(m['fifo_hits_per_slot'])}。没有重复计数，也不代表真实交付改善。

## 异常定位
3 月交运后平均 {mar.carrier_to_customer_days:.2f} 天，4 月 {apr.carrier_to_customer_days:.2f} 天；交运前分别 {mar.pre_carrier_days:.2f} 与 {apr.pre_carrier_days:.2f} 天。3 月承诺窗口 {mar.promised_window_days:.2f} 天，也短于 4 月的 {apr.promised_window_days:.2f} 天。3 月晚交运率 {pct(float(mar.handover_late_rate))}，并非同期最高；因此交运后耗时与承诺窗口是更强的描述性线索。SP 客户占比 3 月 {pct(float(sp_mar.cohort_share))}、4 月 {pct(float(sp_apr.cohort_share))}；SP 自身延期率分别 {pct(float(sp_mar.late_rate))}、{pct(float(sp_apr.late_rate))}，RJ 分别 {pct(float(rj_mar.late_rate))}、{pct(float(rj_apr.late_rate))}，因此异常不能简单归因于客户地区占比变化。仍不能据此断言物流拥堵、天气或卖家失责。分组表设置每组至少 100 笔门槛。

## 建议的跟进措施
- 高风险：每日核对承诺交期与商品发货期限，提前确认卖家交接和承运安排；超期限单升级处理。
- 中风险：每 2–3 天复核，重点检查交期余量。
- 低风险：常规队列与异常提醒。
- 针对重点客户地区，联合物流伙伴复核运输时效；针对晚交运，先核实订单级时间戳与商品级期限是否可比。实际方案须经真实干预验证。

## 结论局限性
Olist 无生产、库存、产能、ERP 和实际干预数据；交承运商时间是订单级，不能证明多卖家各自交运。V1 的 96,470 笔未排除 188 笔时间先后异常（165 笔交承运商时间早于下单，23 笔客户送达时间早于交承运商），新版逐笔记录在 `timestamp_anomalies.csv`。按月已交付样本存在选择偏差；2018 年 7 月之后观察期较短，未纳入可比月度趋势。周一候选共 {m['candidate_n']:,} 笔，其中已逾期 {m['candidate_overdue_n']:,} 笔、尚未到期 {m['candidate_not_due_n']:,} 笔；后者 {m['candidate_unknown_n']:,} 笔无有效交付标签，未计为准时。已逾期为 0 是因只纳入上周新单首轮审查，不能说明整个在途订单池没有逾期。评分只使用决策时已知字段及更早已完成历史。数据无取消时间，无法证明未送达订单当时均为活跃订单。
'''
    resume=f'''# 简历素材（中文）

- 围绕订单交付监控目标，基于 Olist 四张原始业务表构建订单级履约分析；对 {m['source_orders']:,} 笔订单完成字段审计、粒度校验和排除样本对账，形成 {m['delivered_valid']:,} 笔有效已交付订单的 KPI 工作簿与可复现脚本。
- 针对交付延期定位，区分商品级发货期限与订单级交承运商日期，筛选 {m['single_seller_comparison']:,} 笔可比单卖家订单；量化晚交运组与按时交运组客户延期率差 {m['risk_difference_pp']:.2f} 个百分点，并发现 2018 年 3 月延期率达 {pct(m['march_2018_late_rate'])}，提出交运后耗时与承诺窗口复核建议。
- 设计仅使用周一决策时可得信息及此前已完成订单历史的上周新单首轮跟进优先级，在 {m['test_n']:,} 笔已创建、未送达且尚未到期订单上完成 26 周同批次离线回测；相同 {m['top_k']:,} 个名额下识别 {m['risk_unique_late_n']:,} 笔唯一历史延期订单，FIFO 为 {m['fifo_unique_late_n']:,} 笔，并明确 {m['candidate_unknown_n']:,} 笔候选无有效交付标签、结果不代表真实交付改善。
'''
    (ROOT/'README.md').write_text(readme,encoding='utf-8')
    (OUT/'README.md').write_text(readme,encoding='utf-8')
    (OUT/'business_report_cn.md').write_text(cn,encoding='utf-8')
    (OUT/'resume_bullets_cn.md').write_text(resume,encoding='utf-8')
    review=f'''# 审阅说明：V1 口径与风险排序修订

## 96,470 与 96,282 的差异
V1 的规则是 `order_status == delivered` 且实际送达时间存在，得到 96,470 笔；新版还要求预计送达时间存在，并排除时间先后异常。实际差额恰为 188 笔：165 笔订单级交承运商时间早于下单，23 笔客户送达时间早于交承运商。188 笔均为 delivered 且有实际及预计送达时间，其中 3 笔按时间戳口径延期。因此 V1 的 7,826 笔延期减去 3 笔，得到新版 7,823 笔。逐笔订单 ID、四个关键时间和排除规则见 `timestamp_anomalies.csv`。原始四表未改动，异常未静默删除。

## 27.44% 对 4.88% 为何撤回
此前把 2018 年 1–6 月订单放在一个总池：风险排序取总池分数最高的 10%，FIFO 则取最早购买的 10%。两者虽在同一测试集，FIFO 却集中在 1 月，而月度延期率波动很大；这不是公平的共同决策时点。原先的 27.44% 对 4.88% **不应写进简历，也不应作为有效的排序改善证据**。

最终审计又修正了候选池：不能先按最终 `delivered` 状态筛选。现在 26 个共同周一时点只依据上周已创建且当时尚无送达事件建池，共 {m['candidate_n']:,} 笔唯一订单；已超过承诺交期 {m['candidate_overdue_n']:,} 笔（表现不适用），尚未到期 {m['candidate_not_due_n']:,} 笔，其中 {m['candidate_not_due_observed_n']:,} 笔有有效送达结果、延期 {m['candidate_not_due_late_n']:,} 笔，{m['candidate_unknown_n']:,} 笔没有可用交付标签。已逾期为 0 是“上周新单首轮审查”设计的结果，并不代表全部未完成订单无逾期；较早周的未完成订单不会再次入池。未交付者没有被当作准时。所有候选的下单时间早于周一，且没有周一前送达事件；但由于缺少历史取消时间，不能断言每笔当时仍为活跃订单。

两种规则每周面对完全相同的尚未到期订单池，各取 10%（向上取整），合计 {m['top_k']:,} 个名额。FIFO 用下单先后排序；风险规则仅用客户地区、周一时距预计交期的天数，以及 2018-01-01 前已送达订单的客户地区历史延期率。该历史截止早于所有周一决策点。风险规则选中 {m['risk_selected_unique_n']:,} 笔唯一订单，识别 {m['risk_unique_late_n']:,} 笔唯一延期订单；FIFO 分别为 {m['fifo_selected_unique_n']:,}、{m['fifo_unique_late_n']:,}。每笔只进入自己的购买周，重复计数 {m['selection_repeat_count']} 次。按全部名额计，延期命中率为 {pct(m['risk_hits_per_slot'])} 与 {pct(m['fifo_hits_per_slot'])}；仅对有有效交付标签的被选订单，延期率为 {pct(m['risk_precision'])}（n={m['risk_selected_observed_n']:,}）与 {pct(m['fifo_precision'])}（n={m['fifo_selected_observed_n']:,}）。这仍只是离线识别，不是干预后的交付提升。

## 可执行跟进动作及触发条件
1. 每周一先剔除已送达订单，对未送达订单按客户地区历史率及剩余承诺天数排序；在固定 10% 跟进能力下建立清单。
2. 高优先级且尚无交承运商记录：核对订单商品的最晚发货期限；到期或已过期时先与卖家确认能否交接，并记录原因与新的预计时间。多卖家订单逐卖家核实，不能用订单级承运日期归责单个卖家。
3. 已交承运商但距承诺交期很近：向物流方核对追踪状态与预计送达时间；对高延期客户地区优先复核承运路线和异常节点。数据支持这些地区的历史风险差异，但不证明某条线路或某个承运商失效。
4. 对客户承诺可能无法满足的订单，提前标记并升级给订单服务团队确认客户沟通方案。记录实际处理动作、处理时点和结果，才能进一步评估是否改善交付。

## 简历边界
可以写：四表审计、订单级有效样本 {m['delivered_valid']:,} 笔、单卖家交运关联、2018 年 3 月异常定位、同批次离线排序指标、可复现工作簿与测试。须同时说明 Olist 电商案例、相关性和离线回测。不要写 TCL 实际项目、工厂生产/库存/ERP 经历、真实跨部门协调，或“准时交付率提升”。
'''
    (OUT/'review_notes_cn.md').write_text(review,encoding='utf-8')
    data={
      'metrics':m,'monthly':monthly.fillna('').to_dict(orient='records'),
      'regions':regions.fillna('').to_dict(orient='records'),
      'mix':mix.to_dict(orient='records'),
      'tiers':tiers.to_dict(orient='records'),
      'sample':sample.to_dict(orient='records'),'audit':audit.to_dict(orient='records'),
      'handover':hand.to_dict(orient='records'),
      'by_month':pd.read_csv(OUT/'handover_by_month.csv').to_dict(orient='records'),
      'by_customer':pd.read_csv(OUT/'handover_by_customer_state.csv').to_dict(orient='records'),
      'by_seller':pd.read_csv(OUT/'handover_by_seller_state.csv').to_dict(orient='records'),
      'high':pd.read_csv(OUT/'high_risk_examples.csv').fillna('').to_dict(orient='records')}
    WORK.mkdir(exist_ok=True)
    (WORK/'workbook_data.json').write_text(json.dumps(data,default=str),encoding='utf-8')
    (OUT/'report_values.json').write_text(json.dumps(key,indent=2),encoding='utf-8')

if __name__=='__main__':main()
