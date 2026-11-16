"""Inference with the user's exact trained XGBoost bundle, without refitting."""
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from AegisService import ApplicationError,PredictionResult

class _OriginalTreePreprocessorCompat:
    """Version-independent transform for this exact, checksum-verified artifact.

    State exported from the original fitted sklearn 1.6.1 preprocessor:
    median imputation for 8 numeric columns, no scaling, and a fixed 5-category
    OneHotEncoder. No fitting, weight changes or threshold changes occur.
    """
    SOURCE_SHA256='be48048c8a0e43b96d1fd65e6fe3adbc6daaddef46e9467e452bbf2c1072acc3'
    NUMERIC=('step','amount','oldbalanceOrg','newbalanceOrig',
             'oldbalanceDest','newbalanceDest','errorbalanceOrig','errorbalanceDest')
    MEDIANS=(239.0,74922.0,14215.0,0.0,133017.41999999998,215179.925,5797.92,0.0)
    CATEGORIES=('CASH_IN','CASH_OUT','DEBIT','PAYMENT','TRANSFER')

    def get_feature_names_out(self):
        return np.asarray((*self.NUMERIC,*(f'type_{value}' for value in self.CATEGORIES)),dtype=object)

    def transform(self,frame):
        missing=[name for name in (*self.NUMERIC,'type') if name not in frame.columns]
        if missing:
            raise ValueError('Missing engineered columns: '+str(missing))
        numeric=frame.loc[:,list(self.NUMERIC)].to_numpy(dtype=np.float64,copy=True)
        missing_values=np.isnan(numeric)
        if missing_values.any():
            numeric[missing_values]=np.broadcast_to(np.asarray(self.MEDIANS),numeric.shape)[missing_values]
        if not np.isfinite(numeric).all():
            raise ValueError('Engineered numeric features must be finite')
        types=frame['type']
        if not types.isin(self.CATEGORIES).all():
            raise ValueError('Unknown transaction type')
        encoded=np.column_stack([types.eq(value).to_numpy(dtype=np.float64) for value in self.CATEGORIES])
        return pd.DataFrame(np.concatenate((numeric,encoded),axis=1),
                            columns=self.get_feature_names_out(),index=frame.index)


class _PortableXGBoostModel:
    """Read the native JSON model, not a Python/XGBoost memory snapshot."""
    SOURCE_SHA256='39271fa5fef7ee36cb00cc51df8e0aac077397b20c314dd7323abfc868f2b2c5'
    JSON_SHA256='5c09b940c04eb3fa21489dcc9963f7712e8ac3db2bcb615148e34f2d8dc5ca7d'

    def __init__(self,path):
        import xgboost
        self.xgboost=xgboost
        self.booster=xgboost.Booster()
        self.booster.load_model(str(path))
        if self.booster.attr('aegis_source_model_sha256')!=self.SOURCE_SHA256:
            raise ValueError('Portable JSON does not identify the original model')
        config=json.loads(self.booster.save_config())
        if config['learner']['objective']['name']!='binary:logistic':
            raise ValueError('Expected binary:logistic objective')
        self.n_features_in_=self.booster.num_features()
        self.classes_=np.asarray([0,1])

    def get_booster(self):
        return self.booster

    def predict_proba(self,frame):
        matrix=self.xgboost.DMatrix(frame,feature_names=list(frame.columns))
        score=np.asarray(self.booster.predict(matrix,validate_features=True))
        if score.ndim!=1 or score.shape[0]!=len(frame):
            raise ValueError('Unexpected binary model output shape')
        return np.column_stack((1.0-score,score))


class BundlePredictor:
    def __init__(self,settings):
        self.directory=settings.resolve_path(settings.bundle_dir).resolve()
        stage='đọc model_manifest.json'
        try:
            manifest=json.loads((self.directory/'model_manifest.json').read_text(encoding='utf-8-sig'))
            self.manifest=manifest
            files=manifest['files'];digests=manifest['sha256'];paths={}
            for role in ('model','preprocessor','feature_engineering','threshold'):
                stage='kiểm tra '+files[role]
                path=(self.directory/files[role]).resolve()
                if not path.is_relative_to(self.directory):
                    raise ValueError('Artifact path escapes bundle directory')
                if hashlib.sha256(path.read_bytes()).hexdigest()!=digests[role]:
                    raise ValueError('Artifact checksum mismatch: '+role)
                paths[role]=path
            stage='đọc selected_threshold.json'
            threshold_data=json.loads(paths['threshold'].read_text(encoding='utf-8-sig'))
            self.threshold=float(threshold_data['selected_threshold'])
            if not math.isfinite(self.threshold) or not 0<=self.threshold<=1 or self.threshold!=float(manifest['selected_threshold']):
                raise ValueError('Threshold artifacts disagree')
            # software_versions documents the export environment; it is not
            # a hard equality requirement. Validate the actual artifacts and
            # feature contract instead of rejecting installed version numbers.
            stage='nạp fraud_preprocessing.py'
            specification=importlib.util.spec_from_file_location('aegis_bundle_preprocessing',paths['feature_engineering'])
            self.preprocessing=importlib.util.module_from_spec(specification)
            specification.loader.exec_module(self.preprocessing)
            stage='nạp final_preprocessor.joblib'
            if digests['preprocessor']==_OriginalTreePreprocessorCompat.SOURCE_SHA256:
                self.preprocessor=_OriginalTreePreprocessorCompat()
            else:
                # Other artifacts keep their own native preprocessing semantics.
                self.preprocessor=joblib.load(paths['preprocessor'])
            if digests['model']==_PortableXGBoostModel.SOURCE_SHA256:
                stage='nạp ModelPortable.json'
                portable=Path(__file__).resolve().with_name('ModelPortable.json')
                if not portable.exists():
                    raise ValueError('Thiếu ModelPortable.json bên cạnh main.py; chép cả hai file trong bản vá.')
                if hashlib.sha256(portable.read_bytes()).hexdigest()!=_PortableXGBoostModel.JSON_SHA256:
                    raise ValueError('Checksum ModelPortable.json không đúng; giải nén lại bản vá.')
                self.model=_PortableXGBoostModel(portable)
            else:
                stage='nạp '+files['model']
                self.model=joblib.load(paths['model'])
            stage='kiểm tra cột và nhãn mô hình'
            self.columns=list(manifest['output_feature_names'])
            if list(self.preprocessor.get_feature_names_out())!=self.columns:
                raise ValueError('Preprocessor output columns differ from manifest')
            if len(self.columns)!=manifest['transformed_feature_count'] or self.model.n_features_in_!=len(self.columns):
                raise ValueError('Unexpected transformed feature count')
            learned_names=self.model.get_booster().feature_names
            if learned_names is not None and list(learned_names)!=self.columns:
                raise ValueError('Trained feature order differs from manifest')
            classes=list(self.model.classes_)
            if classes!=[0,1]:
                raise ValueError('Expected isFraud binary classes [0,1]')
            self.positive_index=classes.index(1)
        except ApplicationError:
            raise
        except Exception as exc:
            raise ApplicationError('Không tải được mô hình ở bước '+stage+'. Chi tiết: '+str(exc)) from exc

    def predict(self,payload):
        # Map DAO snake_case to the original seven PaySim input names.
        raw=dict(step=payload['step'],type=payload['type'],amount=float(payload['amount']),
                 oldbalanceOrg=float(payload['oldbalance_org']),newbalanceOrig=float(payload['newbalance_orig']),
                 oldbalanceDest=float(payload['oldbalance_dest']),newbalanceDest=float(payload['newbalance_dest']))
        try:
            transformed=self.preprocessing.transform_for_inference(
                raw,self.preprocessor,expected_columns=self.columns)
            probabilities=np.asarray(self.model.predict_proba(transformed),dtype=float)
            if probabilities.shape!=(1,2) or not np.isfinite(probabilities).all() or (probabilities<0).any() or (probabilities>1).any() or not np.isclose(probabilities.sum(),1):
                raise ValueError('Invalid classifier scores')
            return PredictionResult.validate(dict(
                fraud_score=float(probabilities[0,self.positive_index]),threshold=self.threshold))
        except ApplicationError:
            raise
        except Exception as exc:
            raise ApplicationError('Không suy luận được bằng mô hình hiện tại; giao dịch chưa được lưu. Chi tiết: '+str(exc)) from exc
