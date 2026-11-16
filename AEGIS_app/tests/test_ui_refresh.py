"""UI/data-scope regression tests; mock fixtures never touch MySQL."""
from datetime import datetime
import math
import unittest
from unittest.mock import patch
from PyQt6.QtCore import Qt,QTimer
from PyQt6.QtWidgets import QApplication,QComboBox,QMessageBox
from PyQt6.QtTest import QTest
from AegisExt import AegisExt
from AegisService import summarize,transaction_activity,PredictionResult,ManagedConnector
from PreviewService import PreviewService
from ChartWidgets import DonutChart,TYPE_ORDER

class DashboardDataTests(unittest.TestCase):
    def test_daily_counts_and_calendar_gaps(self):
        rows=[dict(created_at=datetime(2026,11,1,10)),dict(created_at=datetime(2026,11,1,18)),
              dict(created_at=datetime(2026,11,3,9)),dict(created_at=None)]
        self.assertEqual([item['count'] for item in transaction_activity(rows)],[2,0,1])
        self.assertEqual(transaction_activity([]),[])
        self.assertEqual(transaction_activity([dict(created_at='invalid')]),[])

    def test_mock_is_separate_and_dashboard_is_user_scoped(self):
        with patch.object(ManagedConnector,'connect',side_effect=AssertionError('Mock accessed MySQL')):
            service=PreviewService();own=service.load_transactions(101);history=service.load_history(101)
        self.assertTrue(all(row['user_id']==101 for row in own['rows']))
        self.assertGreater(len(history['rows']),len(own['rows']))
        self.assertEqual(own['summary']['total'],len(own['rows']))
        self.assertEqual(sum(item['count'] for item in own['summary']['activity']),len(own['rows']))
        self.assertEqual(PreviewService(empty=True).load_transactions(101)['summary']['total'],0)

class UIRefreshTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([]);cls.app.setStyle('Fusion')

    def setUp(self):
        self.service=PreviewService();self.window=AegisExt(self.service)
        self.window.resize(1360,860);self.window.start_preview();self.window.show();self.app.processEvents()

    def tearDown(self):
        self.window.close();self.app.processEvents()

    def wait(self):
        for _ in range(1500):
            self.app.processEvents()
            if not self.window._busy and not any(worker.isRunning() for worker in self.window._workers):
                self.app.processEvents();return
            QTest.qWait(10)
        self.fail('Worker timed out')

    def test_dashboard_three_charts_and_latest_five_owned_rows(self):
        window=self.window
        self.assertEqual(window.ui.recordsButton.text(),'Lịch sử dự đoán')
        self.assertTrue(window.ui.previewBanner.isVisible())
        own=self.service.load_transactions(101)
        self.assertEqual(window.ui.totalValue.text(),str(len(own['rows'])))
        self.assertEqual(window.distribution.positive,own['summary']['fraud'])
        self.assertEqual(sum(window.bar_chart.counts.values()),own['summary']['fraud'])
        self.assertEqual(tuple(window.bar_chart.counts),TYPE_ORDER)
        self.assertEqual(len(window._recent_rows),5)
        self.assertTrue(all(row['user_id']==101 for row in window._recent_rows))
        self.assertEqual(window.ui.recentTable.columnCount(),7)
        self.assertEqual(window.ui.recentTable.horizontalHeaderItem(5).text(),'Checked By')
        self.assertTrue(window.activity_chart.activity)

    def test_global_history_and_name_filter_dont_change_dashboard(self):
        total=self.window.ui.totalValue.text();self.window.navigate(3);self.wait()
        self.assertEqual(len(self.window.history_rows),len(self.service.rows))
        self.assertEqual(self.window.ui.recordsTable.columnCount(),8)
        index=self.window.ui.userFilter.findData(102);self.assertGreater(index,0)
        self.window.ui.userFilter.setCurrentIndex(index);self.app.processEvents()
        self.assertTrue(self.window._visible_rows)
        self.assertTrue(all(row['user_id']==102 for row in self.window._visible_rows))
        self.assertEqual(self.window.ui.totalValue.text(),total)
        self.window.ui.predictionFilter.setCurrentText('Fraud');self.app.processEvents()
        self.assertTrue(all(row['prediction']=='Fraud' for row in self.window._visible_rows))
        self.window.reset_filters();self.assertEqual(len(self.window._visible_rows),len(self.service.rows))
        self.assertEqual(self.window.ui.recordsTable.item(0,5).text(),self.window._visible_rows[0]['checked_by'])

    def test_history_detail_is_global_but_recent_detail_is_owned(self):
        others=next(row for row in self.service.rows if row['user_id']!=101)
        self.assertEqual(self.service.get_history_transaction(101,others['transaction_id'])['user_id'],others['user_id'])
        from AegisService import ApplicationError
        with self.assertRaises(ApplicationError):self.service.get_transaction(101,others['transaction_id'])

    def test_global_search_resets_name_filter(self):
        self.window.navigate(3);self.wait()
        self.window.ui.userFilter.setCurrentIndex(self.window.ui.userFilter.findData(102))
        target=next(row for row in self.service.rows if row['user_id']==101)
        self.window.ui.globalSearchEdit.setText(str(target['transaction_id']))
        self.window.global_search();self.wait()
        self.assertIsNone(self.window.ui.userFilter.currentData())
        self.assertTrue(any(row['transaction_id']==target['transaction_id'] for row in self.window._visible_rows))

    def test_type_selector_amount_width_clear_and_result_text(self):
        self.window._show_page(1);self.app.processEvents()
        fields=self.window.forms['success'];selector=fields['type']
        self.assertIsInstance(selector,QComboBox)
        self.assertEqual([selector.itemText(i) for i in range(selector.count())],list(TYPE_ORDER))
        self.assertEqual(selector.currentIndex(),-1)
        self.assertLessEqual(abs(fields['step'].width()-fields['amount'].width()),1)
        self.assertLessEqual(abs(fields['step'].width()-selector.width()),1)
        payload=dict(step=1,type='TRANSFER',amount='2000',oldbalance_org='4000',newbalance_orig='2000',oldbalance_dest='3000',newbalance_dest='5000')
        self.window.show_prediction(dict(result=PredictionResult(.998,.9941363334655762,'Fraud'),payload=payload,transaction_id=1001))
        self.app.processEvents()
        self.assertEqual(self.window.ui.failResultText.text(),'Fraud')
        icon=self.window.ui.failResultIcon;caption=self.window.ui.failResultText
        self.assertGreaterEqual(icon.height(),92)
        self.assertLess(caption.geometry().top()-icon.geometry().bottom(),22)
        self.window.show_prediction(dict(result=PredictionResult(.003,.9941363334655762,'Legitimate'),payload=payload,transaction_id=1001))
        self.assertEqual(self.window.ui.successResultText.text(),'Legitimate')
        self.window.clear_forms();self.assertEqual(selector.count(),5);self.assertEqual(selector.currentIndex(),-1)
        self.assertTrue(all(not field.text() for name,field in fields.items() if name!='type'))

    def test_header_alignment_stays_fixed_after_filter(self):
        self.window.navigate(3);self.wait();table=self.window.ui.recordsTable
        widths=[table.columnWidth(i) for i in range(8)]
        for i in range(7):self.assertEqual(table.item(0,i).textAlignment(),table.horizontalHeaderItem(i).textAlignment())
        self.window.ui.idFilterEdit.setText('not-found');self.app.processEvents();self.window.reset_filters();self.app.processEvents()
        self.assertEqual(widths,[table.columnWidth(i) for i in range(8)])
        for i in range(8):self.assertEqual(table.columnViewportPosition(i),table.horizontalHeader().sectionViewportPosition(i))

    def test_black_login_warning_with_icon(self):
        self.window.logout();captured=[]
        def inspect():
            dialog=self.app.activeModalWidget()
            if isinstance(dialog,QMessageBox):
                captured.append((dialog.icon(),dialog.styleSheet(),dialog.text()));dialog.accept()
            else:QTimer.singleShot(10,inspect)
        QTimer.singleShot(10,inspect)
        self.window.ui.usernameEdit.setText('wrong');self.window.ui.passwordEdit.setText('wrong');self.window.login();self.wait()
        self.assertEqual(len(captured),1)
        self.assertEqual(captured[0][0],QMessageBox.Icon.Warning)
        self.assertIn('#111111',captured[0][1]);self.assertIn('#FFFFFF',captured[0][1])
        self.assertIsNone(self.window.user)

    def test_empty_state_does_not_draw_fake_charts_or_rows(self):
        self.window.close();self.window=AegisExt(PreviewService(empty=True));self.window.start_preview();self.window.show();self.app.processEvents()
        self.assertEqual(self.window.ui.totalValue.text(),'0')
        self.assertTrue(self.window.ui.emptyStatePanel.isVisible())
        for card in (self.window.ui.distributionCard,self.window.ui.activityCard,self.window.ui.typeChartCard,self.window.ui.recentSection):self.assertTrue(card.isHidden())
        self.assertEqual(self.window.rows,[])

    def test_confidence_colored_area_tracks_score(self):
        chart=DonutChart(True);chart.resize(260,240);chart.show();self.app.processEvents()
        def colored_count(value):
            chart.set_probability(value,False);self.app.processEvents();img=chart.grab().toImage();count=0
            for y in range(img.height()):
                for x in range(img.width()):
                    radius=math.hypot(x-img.width()/2,y-img.height()/2)
                    if not 70<radius<100:continue
                    c=img.pixelColor(x,y)
                    if c.red()>150 and c.green()<130 and c.blue()<150:count+=1
            return count
        low=colored_count(.25);high=colored_count(.75)
        self.assertGreater(high,low*2.5);chart.close()

if __name__=='__main__':unittest.main()
