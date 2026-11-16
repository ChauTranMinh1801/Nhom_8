"""Opt-in tests using a separate database restored from the user's original dump.
No CREATE/ALTER TABLE or INSERT/UPDATE users is performed by these tests.
Only transactions inserted by a test are deleted during cleanup.
"""
import os
from decimal import Decimal,ROUND_HALF_UP
from dataclasses import replace
from pathlib import Path
import unittest
from unittest.mock import patch
from AegisService import Settings,ApplicationService,ApplicationError,UserDAO
from DAL_DAO.transaction_dao import TransactionDAO

RAW=dict(step=1,type='TRANSFER',amount='181',oldbalance_org='181',
         newbalance_orig='0',oldbalance_dest='0',newbalance_dest='0')

@unittest.skipUnless(os.getenv('AEGIS_TEST_DB_NAME'),'Set AEGIS_TEST_DB_NAME for integration tests')
class MySQLIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        name=os.environ['AEGIS_TEST_DB_NAME']
        if not name.endswith('_test'):raise RuntimeError('Use a separate database ending in _test.')
        cls.settings=Settings(os.getenv('AEGIS_TEST_DB_HOST','127.0.0.1'),int(os.getenv('AEGIS_TEST_DB_PORT','3306')),
            name,os.environ['AEGIS_TEST_DB_USER'],os.environ['AEGIS_TEST_DB_PASSWORD'])
        cls.service=ApplicationService(cls.settings);cls.created=[]
        with cls.service.connection() as connector:
            cls.users=UserDAO(connector).get_all_users().to_dict('records')
        if len(cls.users)<2:raise RuntimeError('Restore the original supplied dump into the test database first.')
        cls.a,cls.b=cls.users[:2]

    @classmethod
    def tearDownClass(cls):
        with cls.service.connection() as connector:
            for uid,transaction_id in cls.created:
                connector.executeQuery('DELETE FROM transactions WHERE user_id=%s AND transaction_id=%s',(uid,transaction_id))

    def save(self,raw):
        result=self.service.predict_and_save(self.a['user_id'],raw)
        self.created.append((self.a['user_id'],result['transaction_id']))
        return result

    def test_exact_original_schema_and_no_extra_tables(self):
        with self.service.connection() as connector:
            self.assertEqual(sorted(connector.getTablesName()),['transactions','users'])
            columns=connector.queryDataset('SHOW COLUMNS FROM transactions').set_index('Field')
        self.assertEqual(columns.loc['amount','Type'],'decimal(15,2)')
        self.assertEqual(columns.loc['fraud_score','Type'],'decimal(6,5)')
        self.assertNotIn('destination_id',columns.index)
        self.assertNotIn('priority',columns.index)

    def test_dataframe_and_user_isolation(self):
        with self.service.connection() as connector:
            df=TransactionDAO(connector).get_transactions_by_user(self.a['user_id'])
        self.assertEqual(type(df).__name__,'DataFrame');self.assertTrue(all(df['user_id']==self.a['user_id']))
        rows=self.service.load_transactions(self.b['user_id'])['rows']
        self.assertTrue(all(row['user_id']==self.b['user_id'] for row in rows))
        self.assertEqual(self.service.load_transactions(2147483647)['summary']['total'],0)

    def test_other_users_cannot_open_detail(self):
        rows=self.service.load_transactions(self.a['user_id'])['rows']
        with self.assertRaises(ApplicationError):self.service.get_transaction(self.b['user_id'],rows[0]['transaction_id'])

    def test_invalid_password_and_sql_username(self):
        for username in (self.a['username'],"' OR 1=1 --"):
            with self.assertRaises(ApplicationError):self.service.authenticate(username,'certainly-not-a-real-password')
        with self.service.connection() as connector:
            actual=connector.queryDataset('SELECT SHA2(%s,256) AS value',('Test-mật-khẩu-123',)).iloc[0]['value']
        self.assertTrue(self.service.passwords.verify(actual,'Test-mật-khẩu-123'))

    def test_model_inference_persistence_and_decimal_precision(self):
        for kind,label in (('TRANSFER','Fraud'),('PAYMENT','Legitimate')):
            result=self.save(dict(RAW,type=kind));detail=self.service.get_transaction(self.a['user_id'],result['transaction_id'])
            self.assertEqual(result['result'].prediction,label);self.assertEqual(detail['prediction'],label)
            self.assertEqual(detail['fraud_score'],Decimal(str(result['result'].fraud_score)).quantize(Decimal('.00001'),rounding=ROUND_HALF_UP))
            self.assertEqual(detail['threshold'],Decimal('.99414'))
            self.assertEqual(result['result'].threshold,.9941363334655762)
            self.assertEqual(str(detail['oldbalance_org']),'181.00')
            self.assertNotIn('destination_id',detail)

    def test_selected_threshold_and_historical_labels(self):
        result=self.save(dict(RAW,amount='10000',oldbalance_org='20000'))
        self.assertGreater(result['result'].fraud_score,.5);self.assertEqual(result['result'].prediction,'Legitimate')
        detail=self.service.get_transaction(self.a['user_id'],result['transaction_id'])
        self.assertEqual(detail['prediction'],'Legitimate')
        # Original historical rows retain their stored threshold/label.
        with self.service.connection() as c:
            row=c.queryDataset('SELECT threshold,prediction FROM transactions WHERE transaction_id=2').iloc[0]
        self.assertEqual(row['threshold'],Decimal('.85000'));self.assertEqual(row['prediction'],'Fraud')

    def test_invalid_inputs_or_missing_model_never_insert(self):
        before=self.service.load_transactions(self.a['user_id'])['summary']['total']
        with self.assertRaises(ApplicationError):self.service.predict_and_save(self.a['user_id'],dict(RAW,amount='10000000000000'))
        missing=ApplicationService(replace(self.settings,bundle_dir='missing-test-models'))
        with self.assertRaises(ApplicationError):missing.predict_and_save(self.a['user_id'],RAW)
        self.assertEqual(self.service.load_transactions(self.a['user_id'])['summary']['total'],before)

    def test_global_history_join_and_checked_by(self):
        history=self.service.load_history(self.a['user_id'])
        self.assertGreaterEqual(len(history['rows']),5)
        names={str(user['user_id']):user['full_name'] or user['username'] for user in history['users']}
        self.assertTrue(all(row['checked_by']==names[str(row['user_id'])] for row in history['rows']))
        others=[row for row in history['rows'] if row['user_id']!=self.a['user_id']]
        self.assertTrue(others)
        detail=self.service.get_history_transaction(self.a['user_id'],others[0]['transaction_id'])
        self.assertEqual(detail['user_id'],others[0]['user_id'])
        private=self.service.load_transactions(self.a['user_id'])['rows']
        self.assertTrue(all(row['user_id']==self.a['user_id'] for row in private))

    def test_gui_seven_inputs_real_columns_and_stable_alignment(self):
        from PyQt6.QtWidgets import QApplication,QMessageBox
        from PyQt6.QtTest import QTest
        from AegisExt import AegisExt
        from TransactionDetailsExt import TransactionDetailsExt
        app=QApplication.instance() or QApplication([]);window=AegisExt(self.service);window.show();app.processEvents()
        def wait():
            for _ in range(1500):
                app.processEvents()
                if not window._busy and not any(worker.isRunning() for worker in window._workers):app.processEvents();return
                QTest.qWait(10)
            self.fail('UI worker timeout')
        self.assertEqual(len(window.forms['success']),7)
        self.assertFalse(hasattr(window.ui,'success_nameDest'))
        self.assertFalse(hasattr(window.ui,'priorityFilter'))
        payload=dict(user=self.a,**self.service.load_transactions(self.a['user_id']))
        with patch.object(self.service,'authenticate',return_value=payload):
            window.ui.usernameEdit.setText('test-ui');window.ui.passwordEdit.setText('test-ui');window.login();wait()
        window.navigate(3);wait()
        table=window.ui.recordsTable;self.assertEqual(table.columnCount(),8)
        self.assertEqual(table.horizontalHeaderItem(4).text(),'Prediction')
        self.assertGreater(window.ui.rootStack.width(),1000)
        for column in range(8):
            self.assertEqual(table.horizontalHeader().sectionViewportPosition(column),table.columnViewportPosition(column))
        for column in range(7):self.assertEqual(table.item(0,column).textAlignment(),table.horizontalHeaderItem(column).textAlignment())
        widths=[table.columnWidth(i) for i in range(8)]
        window.ui.idFilterEdit.setText('not-a-transaction');app.processEvents();window.reset_filters();app.processEvents()
        self.assertEqual(widths,[table.columnWidth(i) for i in range(8)])
        window.ui.predictionFilter.setCurrentText('Legitimate')
        self.assertTrue(all(row['prediction']=='Legitimate' for row in window._visible_rows));window.reset_filters()
        window.navigate(1)
        mapping={'step':'step','type':'type','amount':'amount','oldbalanceOrg':'oldbalance_org',
                 'newbalanceOrig':'newbalance_orig','oldbalanceDest':'oldbalance_dest','newbalanceDest':'newbalance_dest'}
        for key,source in mapping.items():
            field=window.forms['success'][key]
            if key=='type':field.setCurrentText(str(RAW[source]))
            else:field.setText(str(RAW[source]))
        window.submit('success');wait()
        self.assertEqual(window.ui.pageStack.currentIndex(),2)
        self.created.append((self.a['user_id'],window._last_saved_id))
        before=self.service.load_transactions(self.a['user_id'])['summary']['total']
        with patch.object(QMessageBox,'information',return_value=QMessageBox.StandardButton.Ok):window.submit('fail')
        self.assertEqual(self.service.load_transactions(self.a['user_id'])['summary']['total'],before)
        row=self.service.get_transaction(self.a['user_id'],window._last_saved_id)
        detail=TransactionDetailsExt(row);self.assertFalse(hasattr(detail.ui,'saveButton'));detail.close()
        with patch.object(self.service,'load_transactions',side_effect=ApplicationError('test read error')),patch.object(QMessageBox,'warning',return_value=QMessageBox.StandardButton.Ok):
            window.navigate(0);wait()
        self.assertEqual(window.ui.totalValue.text(),'—')
        window.logout();self.assertEqual(window.rows,[]);self.assertIsNone(window.user)
        window.close();app.processEvents()

if __name__=='__main__':unittest.main()
