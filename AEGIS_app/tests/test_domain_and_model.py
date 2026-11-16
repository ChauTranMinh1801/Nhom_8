import ast
from contextlib import nullcontext
import hashlib
import io
from pathlib import Path
import unittest
from unittest.mock import patch
from PyQt6 import uic
from AegisService import (
    ApplicationError,ApplicationService,Settings,PasswordVerifier,
    PredictionResult,validate_payload,summarize,UserDAO,TransactionRepository,
)
BASE=Path(__file__).resolve().parents[1]
RAW=dict(step='12',type='TRANSFER',amount='1200.50',oldbalance_org='1500.50',
         newbalance_orig='300',oldbalance_dest='10',newbalance_dest='1210.50')

class DomainTests(unittest.TestCase):
    def test_seven_inputs_and_decimal_15_2_limit(self):
        self.assertEqual(len(validate_payload(RAW)),7)
        self.assertEqual(validate_payload(dict(RAW,type='transfer'))['type'],'TRANSFER')
        self.assertEqual(str(validate_payload(dict(RAW,amount='9999999999999.99'))['amount']),'9999999999999.99')
        for value in ('-1','NaN','Infinity','0.001','10000000000000'):
            with self.subTest(value=value),self.assertRaises(ApplicationError):
                validate_payload(dict(RAW,amount=value))
        with self.assertRaises(ApplicationError):validate_payload(dict(RAW,step='1.2'))

    def test_statistics_and_empty_account(self):
        rows=[dict(type='TRANSFER',prediction='Fraud'),dict(type='TRANSFER',prediction='Legitimate'),dict(type='CASH_OUT',prediction='Fraud')]
        result=summarize(rows)
        self.assertEqual((result['total'],result['fraud'],result['legitimate']),(3,2,1))
        self.assertEqual(result['counts']['TRANSFER'],[1,1])
        self.assertEqual(summarize([])['fraud_rate'],0)
        with self.assertRaises(ApplicationError):summarize([dict(type='INVALID',prediction='Fraud')])

    def test_threshold_and_invalid_prediction(self):
        self.assertEqual(PredictionResult.validate(dict(fraud_score=.5,threshold=.5)).prediction,'Fraud')
        for score in (-.1,1.1,float('nan'),float('inf')):
            with self.assertRaises(ApplicationError):PredictionResult.validate(dict(fraud_score=score,threshold=.5))
        with self.assertRaises(ApplicationError):
            PredictionResult.validate(dict(fraud_score=.9,threshold=.5,prediction='Legitimate'))

    def test_sha256_matches_mysql_sha2_convention(self):
        password='Test-mật-khẩu-123';hashed=hashlib.sha256(password.encode('utf-8')).hexdigest()
        verifier=PasswordVerifier()
        self.assertTrue(verifier.verify(hashed,password))
        self.assertTrue(verifier.verify(hashed.upper(),password))
        self.assertFalse(verifier.verify(hashed,'wrong'))
        self.assertFalse(verifier.verify(password,password))

    def test_login_sanitizes_user_and_rejects_wrong_password(self):
        service=ApplicationService(Settings('localhost',3306,'test','test',''))
        user=dict(user_id=1,username='test',full_name='Test User',password_hash=hashlib.sha256(b'test-password').hexdigest())
        with patch.object(service,'connection',return_value=nullcontext(object())),patch.object(UserDAO,'get_user_by_username',return_value=user),patch.object(TransactionRepository,'list_for_user',return_value=[]):
            result=service.authenticate('test','test-password')
            self.assertNotIn('password_hash',result['user']);self.assertEqual(result['summary']['total'],0)
        with patch.object(service,'connection',return_value=nullcontext(object())),patch.object(UserDAO,'get_user_by_username',return_value=user):
            with self.assertRaises(ApplicationError):service.authenticate('test','wrong')

    def test_ui_python_is_generated_without_logic(self):
        for source,target in (('Aegis.ui','Ui_Aegis.py'),('TransactionDetails.ui','Ui_TransactionDetails.py')):
            output=io.StringIO()
            with (BASE/'ui'/source).open() as stream:uic.compileUi(stream,output)
            self.assertEqual(ast.dump(ast.parse(output.getvalue())),ast.dump(ast.parse((BASE/'ui'/target).read_text())))
            self.assertNotIn('ApplicationService',output.getvalue())
            self.assertFalse(any(isinstance(n,ast.Constant) and isinstance(n.value,str) and n.value.startswith('/workspace/') for n in ast.walk(ast.parse(output.getvalue()))))

    def test_no_sql_or_account_creation_scripts_are_delivered(self):
        self.assertEqual(list(BASE.rglob('*.sql')),[])
        self.assertEqual(sorted(f.name for f in (BASE/'DAL_DAO').glob('*.py')),['connector.py','transaction_dao.py','user_dao.py'])
        self.assertEqual(list(BASE.rglob('create_user.py')),[])

if __name__=='__main__':unittest.main()
