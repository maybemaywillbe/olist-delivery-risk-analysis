import json
import unittest
from pathlib import Path
import pandas as pd
from src.analyze import read_sources, build_orders, summarize, risk_backtest

ROOT=Path(__file__).resolve().parents[1]

class ProjectTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tables,cls.audit=read_sources()
        cls.d=build_orders(cls.tables)
        cls.a,cls.x,cls.ct,cls.monthly,cls.regions,cls.mix,cls.exclusion,cls.metrics,_=summarize(cls.d,cls.audit)
        cls.test,cls.tiers,_,cls.back=risk_backtest(cls.d)

    def test_keys_and_join_grain(self):
        self.assertTrue(self.d.order_id.is_unique)
        self.assertEqual(len(self.d),len(self.tables['orders']))
        self.assertEqual(int(self.audit.key_duplicates.sum()),0)

    def test_kpi_denominator_and_complement(self):
        self.assertEqual(len(self.a),self.metrics['delivered_valid'])
        self.assertEqual(int(self.a.late.sum()),self.metrics['late_orders'])
        self.assertAlmostEqual(self.metrics['on_time_rate']+self.metrics['late_rate'],1)
        self.assertTrue(self.a.observed_delivery.all())

    def test_missing_dates_and_exclusions(self):
        self.assertFalse(self.a.order_delivered_customer_date.isna().any())
        self.assertFalse(self.a.order_estimated_delivery_date.isna().any())
        self.assertEqual(self.exclusion.orders.iloc[0],sum(self.exclusion.orders.iloc[1:4])+self.exclusion.orders.iloc[4])
        self.assertEqual(self.exclusion.orders.iloc[4],sum(self.exclusion.orders.iloc[5:8]))

    def test_group_reconciliation(self):
        self.assertEqual(int(self.monthly.delivered.sum()),len(self.a))
        self.assertEqual(int(self.regions.n.sum()),len(self.a))
        for month in ['2018-02','2018-03','2018-04']:
            self.assertEqual(int(self.mix.loc[self.mix.purchase_month.eq(month),'n'].sum()),
                             int(self.monthly.loc[self.monthly.purchase_month.eq(month),'delivered'].iloc[0]))
        self.assertEqual(int(self.ct.values.sum()),len(self.x))
        self.assertEqual(int(self.tiers.n.sum()),len(self.test))
        self.assertEqual(int(self.tiers.observed_n.sum()),self.back['candidate_not_due_observed_n'])

    def test_temporal_split_and_score_inputs(self):
        self.assertLess(pd.Timestamp(self.back['history_last_delivery']),pd.Timestamp(self.back['test_first_purchase']))
        self.assertTrue(self.test.order_purchase_timestamp.ge(pd.Timestamp('2018-01-01')).all())
        self.assertTrue(self.test.order_purchase_timestamp.lt(pd.Timestamp('2018-07-01')).all())
        formula=(self.test.prior_late+200*float(self.d.loc[self.d.observed_delivery&~self.d.time_anomaly&(self.d.order_delivered_customer_date<pd.Timestamp('2018-01-01')),'late'].mean()))/(self.test.prior_n+200)+0.0015*(15-self.test.remaining_days.clip(-30,60))
        self.assertTrue((formula-self.test.score).abs().lt(1e-12).all())
        self.assertTrue((self.test.order_delivered_customer_date.isna()|
                         self.test.order_delivered_customer_date.ge(self.test.decision_time)).all())
        self.assertTrue(self.test.order_purchase_timestamp.lt(self.test.decision_time).all())
        self.assertTrue(self.back['strict_history_before_first_review'])
        self.assertEqual(self.back['candidate_n'],self.back['candidate_overdue_n']+self.back['candidate_not_due_n'])
        self.assertEqual(self.back['candidate_n'],self.back['candidate_observable_n']+self.back['candidate_unknown_n'])
        self.assertGreater(self.back['candidate_unknown_n'],0)
        self.assertEqual(self.back['candidate_unique_n'],self.back['candidate_n'])
        self.assertEqual(self.back['selection_repeat_count'],0)
        self.assertEqual(self.back['fifo_selected_unique_n'],self.back['risk_selected_unique_n'])
        self.assertEqual(self.back['fifo_selected_unique_n'],self.back['top_k'])
        weekly_k=int(self.test.groupby('decision_time').size().mul(.10).apply(__import__('math').ceil).sum())
        self.assertEqual(self.back['top_k'],weekly_k)
        self.assertEqual(self.back['weekly_batches'],self.test.decision_time.nunique())

    def test_reports_match_outputs(self):
        m=json.loads((ROOT/'outputs/metrics.json').read_text())
        values=json.loads((ROOT/'outputs/report_values.json').read_text())
        readme=(ROOT/'README.md').read_text()
        cn=(ROOT/'outputs/business_report_cn.md').read_text()
        self.assertEqual(values['valid_orders'],m['delivered_valid'])
        self.assertIn(f"{m['delivered_valid']:,}",readme)
        self.assertIn(values['late_rate'],readme)
        self.assertIn(values['march_late_rate'],cn)
        self.assertIn(f"{m['risk_late_found']:,}",cn)
        self.assertNotIn('27.44%',readme)
        self.assertIn('same weekly pool',readme)

if __name__=='__main__':unittest.main()
