# Order Fulfillment & Delivery Risk Analysis | Olist E-Commerce Dataset

## Business Problem
For a supply chain planning interview, this project examines customer delivery performance, the handover stage, regional differences, and an order follow-up queue. It is a public Olist e-commerce case study, **not TCL operating data or factory experience**.

## Dataset & Provenance
The original Olist Brazilian E-Commerce public dataset was supplied as `archive.zip` by the project owner. Four source tables are retained in `data/raw/`. The source contains 99,441 orders purchased from 2016-09-04 to 2018-10-17. No synthetic orders were created. `outputs/source_audit.csv` records row counts, keys, missing cells and duplicates.

## Methodology
- Order is the KPI grain. Item rows are aggregated before joining; there are 109,953 item rows across the valid delivered sample.
- The historical denominator is 96,282 orders with `delivered` status, actual and promised delivery dates, and no chronology anomaly. `outputs/sample_reconciliation.csv` gives every exclusion. Other statuses are not counted as on-time.
- Primary late definition compares full timestamps: actual delivery **after** estimated delivery. A calendar-day check compares normalized dates. Late days are positive days only among late orders.
- `order_delivered_carrier_date` is an **order-level proxy**. Seller handover analysis uses 95,029 single-seller delivered orders with valid carrier date and item deadline. For multi-item orders with one seller, the latest item deadline is the order-level rule. Multi-seller orders are excluded because seller-specific actual handover is unavailable. Among 1,252 multi-seller orders, the late-handover proxy varies from 3.27% (last deadline) to 4.15% (first deadline).
- Monthly cohorts use purchase month. The comparable chart covers Jan 2017–Jun 2018, delivered sample n≥100 and ≥90% observed delivery; later months are shown in the CSV but excluded from the main trend. This threshold limits, but cannot eliminate, cohort-selection bias.
- Grouped handover comparisons mark cells below n=100 as ineligible. Association is descriptive, not causal.
- The offline follow-up decision is each Monday after the prior week's purchases. This is a **first-review intake**, not a rolling backlog: older open orders are not reconsidered. The candidate pool uses only orders already created and not yet delivered at that Monday; it does **not** filter on final order status. Both rules see the same weekly pool and capacity: ceil(10% of that week's not-yet-due candidates). FIFO sorts by purchase time; the risk rule scores customer state and days remaining to promise. State rates use only orders delivered before 2018-01-01, strictly earlier than every review, with a 200-order empirical-Bayes prior. There are 37,934 unique candidates: 0 already overdue and 37,934 not yet due. The zero overdue count reflects this intake design and must not be read as zero overdue orders in the full live backlog. Of the latter, 36,953 have valid observed delivery outcomes and 981 have no valid delivery label. Unknown outcomes are never counted as on-time. Each order enters exactly one purchase-week batch, so repeated selection is zero. Final status and future delivery time are absent from scoring; the delivery event timestamp is used only to establish whether delivery had already occurred by Monday and for retrospective labels.

## Key Findings
1. 7,823 of 96,282 valid delivered orders were late: 8.13%; on-time was 91.87%. Calendar-day late rate was 6.78%.
2. Single-seller customer late rates were 6.58% after on-time handover (n=86,374) and 24.54% after late handover (n=8,655): +17.96 percentage points, relative risk 3.73×.
3. March 2018 had 1,496 late among 7,003 valid deliveries (21.36%), versus 5.32% in April. The other prominent comparable peaks were February 2018 (15.99%) and November 2017 (14.31%).
4. March carrier-to-customer mean was 12.97 days versus April 8.67; pre-carrier was 3.33 versus 2.83. March's promised window was 22.03 versus April 23.68 days. This points to post-handover transit and promise-window pressure as stronger **descriptive** signals than a March spike in late handovers (8.62%). SP's cohort share was 42.42% in March and 44.16% in April; within-state late rates also rose (SP 11.68% vs 2.10%, RJ 36.92% vs 5.96%), so the March peak is not explained by a simple shift toward RJ.
5. In 26 matched weekly offline reviews of not-yet-due orders (n=37,934), both rules received 3,807 slots. The risk rule found 845 unique observed late orders; FIFO found 487. Late hits per slot were 22.20% vs 12.79%; among selected orders with valid delivery labels, late rates were 23.03% (n=3,669) and 13.18% (n=3,694). The high tier's late rate among labeled orders was 18.24%.

## Operational Recommendations
- **High:** daily review; confirm seller shipment readiness and carrier booking; escalate when the shipping deadline is close or passed.
- **Medium:** review every 2–3 days and confirm promise-window slack.
- **Low:** standard queue and exception alerts.
- For late handovers, reconcile seller deadline against order-level carrier event before contacting a seller. For transit delays, review carrier lane and customer-state patterns with logistics partners. Test any intervention prospectively before claiming delivery improvement.

## Limitations
This is e-commerce, not manufacturing. There are no production, inventory, capacity, ERP, real-time order events, carrier route, or intervention outcomes. The carrier timestamp cannot establish individual seller handover on multi-seller orders. Chronology anomalies (189 source orders) are flagged; 188 observed deliveries are excluded. V1 retained these 188, yielding 96,470 delivered orders; 165 have carrier time before purchase and 23 have customer delivery before carrier handover. `outputs/timestamp_anomalies.csv` lists the IDs, timestamps and rule. Delivered-only monthly rates can reflect selection, and later cohorts have shorter observation; no causal or realized KPI improvement is claimed. The weekly pool includes orders without an eventual valid delivery label; their fulfillment outcomes cannot be evaluated. Final cancellation time is unavailable, so "not delivered" cannot prove every candidate was still an active, uncanceled order on Monday.

## Reproducibility
Install `requirements.txt` (`python -m pip install -r requirements.txt`), then run `sh run.sh` from the project root. This rebuilds the analysis CSVs, PNGs, narrative reports and runs six tests. A ready-to-read workbook is provided at `outputs/Olist_Fulfillment_Analysis.xlsx`. Workbook **regeneration is optional** (`sh run.sh --rebuild-workbook`) and requires Node.js and `@oai/artifact-tool` installed separately; the Python analysis does not require Node.js. No personal absolute paths appear in code.

## Project Structure
`data/raw/` original four CSVs · `src/` analysis and report code · `tests/` checks · `outputs/` final workbook, reports, charts and audit tables · `outputs/Olist_Fulfillment_Analysis.xlsx` ready-to-read workbook.
