"""Checks against the user's actual artifacts, never a replacement trained model."""
from dataclasses import replace
from pathlib import Path
import hashlib
import json
import shutil
import tempfile
import unittest
import joblib
from FraudPredictor import BundlePredictor
from AegisService import Settings
from AegisService import ApplicationError,validate_payload

BASE=Path(__file__).resolve().parents[1]
RAW=dict(step=1,type='TRANSFER',amount='181',
         oldbalance_org='181',newbalance_orig='0',oldbalance_dest='0',newbalance_dest='0')

class ProvidedBundleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.settings=Settings('localhost',3306,'test','test','test')
        cls.predictor=BundlePredictor(cls.settings)

    def test_original_artifact_hashes_and_feature_order(self):
        directory=BASE/'Models';manifest=json.loads((directory/'model_manifest.json').read_text())
        for role,name in manifest['files'].items():
            self.assertEqual(hashlib.sha256((directory/name).read_bytes()).hexdigest(),manifest['sha256'][role])
        self.assertEqual(len(self.predictor.columns),13)
        self.assertEqual(self.predictor.columns,manifest['output_feature_names'])
        self.assertEqual(self.predictor.threshold,.9941363334655762)

    def test_scores_match_original_transformer_and_model(self):
        # Golden vectors/scores exported from the original artifacts under
        # their training sklearn version; no legacy pickle needs loading here.
        import numpy as np
        cases=[('TRANSFER','181','181',.999982476234436,'Fraud',
                [1,181,181,0,0,0,0,181,0,0,0,0,1]),
               ('PAYMENT','181','181',.009388163685798645,'Legitimate',
                [1,181,181,0,0,0,0,0,0,0,0,1,0]),
               ('TRANSFER','10000','20000',.5985722541809082,'Legitimate',
                [1,10000,20000,0,0,0,-10000,10000,0,0,0,0,1])]
        for kind,amount,old,score,label,vector in cases:
            payload=validate_payload(dict(RAW,type=kind,amount=amount,oldbalance_org=old))
            result=self.predictor.predict(payload)
            raw=dict(step=1,type=kind,amount=float(amount),oldbalanceOrg=float(old),newbalanceOrig=0.,oldbalanceDest=0.,newbalanceDest=0.)
            transformed=self.predictor.preprocessing.transform_for_inference(raw,self.predictor.preprocessor,self.predictor.columns)
            np.testing.assert_array_equal(transformed.to_numpy(),np.asarray([vector],dtype=float))
            self.assertAlmostEqual(result.fraud_score,score,places=7)
            self.assertEqual(result.prediction,label)

    def test_selected_threshold_is_not_replaced_with_half(self):
        payload=validate_payload(dict(RAW,amount='10000',oldbalance_org='20000'))
        result=self.predictor.predict(payload)
        self.assertGreater(result.fraud_score,.5)
        self.assertLess(result.fraud_score,result.threshold)
        self.assertEqual(result.prediction,'Legitimate')

    def test_tampered_threshold_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            target=Path(temp)/'models';shutil.copytree(BASE/'Models',target,ignore=shutil.ignore_patterns('__pycache__'))
            path=target/'selected_threshold.json'
            data=json.loads(path.read_text());data['selected_threshold']=.5;path.write_text(json.dumps(data))
            with self.assertRaises(ApplicationError):BundlePredictor(replace(self.settings,bundle_dir=str(target)))

if __name__=='__main__':unittest.main()
