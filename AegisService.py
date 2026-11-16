"""Application logic for the supplied users/transactions schema.
No tables, columns or user accounts are created by the application.
"""
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal,InvalidOperation
from pathlib import Path
import hashlib
import hmac
import math
import os
import re
import mysql.connector
from DAL_DAO.connector import Connector
from DAL_DAO.user_dao import UserDAO
from DAL_DAO.transaction_dao import TransactionDAO

BASE_DIR=Path(__file__).resolve().parent
TYPES=('TRANSFER','CASH_OUT','PAYMENT','CASH_IN','DEBIT')
NUMERIC_FIELDS=('amount','oldbalance_org','newbalance_orig','oldbalance_dest','newbalance_dest')

class ApplicationError(Exception):
    """A message suitable for the UI."""

def load_env_file(path):
    """Read local KEY=VALUE settings without an external dotenv dependency.

    Blank lines and full-line # comments are supported. Matching surrounding
    quotes are removed; values are otherwise literal (no variable expansion).
    Existing OS environment variables take precedence.
    """
    path=Path(path)
    if not path.exists():
        return
    pending={}
    for line_number,line in enumerate(path.read_text(encoding='utf-8-sig').splitlines(),1):
        line=line.strip()
        if not line or line.startswith('#'):
            continue
        name,separator,value=line.partition('=')
        name=name.strip()
        if not separator or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',name):
            raise ValueError(f'File .env sai định dạng ở dòng {line_number}. Dùng KEY=VALUE.')
        value=value.strip()
        if value.startswith(('"',"'")):
            if len(value)<2 or value[-1]!=value[0]:
                raise ValueError(f'File .env thiếu dấu đóng nháy ở dòng {line_number}.')
            value=value[1:-1]
        pending[name]=value
    for name,value in pending.items():
        os.environ.setdefault(name,value)

@dataclass(frozen=True)
class Settings:
    db_host:str
    db_port:int
    db_name:str
    db_user:str
    db_password:str
    db_timeout:int=15
    bundle_dir:str='Models'

    @classmethod
    def from_env(cls,env_path=None):
        load_env_file(env_path or BASE_DIR/'.env')
        name=os.getenv('DB_NAME','').strip();user=os.getenv('DB_USER','').strip()
        if not name or not user:
            raise ValueError('Điền DB_NAME và DB_USER trong .env. Xem .env.example.')
        port=int(os.getenv('DB_PORT','3306'));timeout=int(os.getenv('DB_TIMEOUT','15'))
        if not 1<=port<=65535 or not 1<=timeout<=120:
            raise ValueError('DB_PORT hoặc DB_TIMEOUT không hợp lệ.')
        return cls(os.getenv('DB_HOST','127.0.0.1'),port,name,user,os.getenv('DB_PASSWORD',''),
                   timeout,os.getenv('MODEL_BUNDLE_DIR','Models'))

    def resolve_path(self,value):
        path=Path(value).expanduser()
        return path if path.is_absolute() else BASE_DIR/path

class PasswordVerifier:
    """MySQL SHA2(password,256), using Python's standard library only."""
    def verify(self,stored_hash,password):
        if not isinstance(stored_hash,str) or not isinstance(password,str):
            return False
        if not re.fullmatch(r'[0-9a-fA-F]{64}',stored_hash):
            return False
        digest=hashlib.sha256(password.encode('utf-8')).hexdigest()
        return hmac.compare_digest(stored_hash.lower(),digest)

@dataclass(frozen=True)
class PredictionResult:
    fraud_score:float
    threshold:float
    prediction:str

    @classmethod
    def validate(cls,value):
        data=vars(value) if isinstance(value,cls) else value
        if not isinstance(data,dict):raise ApplicationError('Bộ dự đoán trả kết quả không hợp lệ.')
        try:score=float(data['fraud_score']);threshold=float(data['threshold'])
        except (KeyError,TypeError,ValueError) as exc:
            raise ApplicationError('Kết quả phải có fraud_score và threshold hợp lệ.') from exc
        if not math.isfinite(score) or not math.isfinite(threshold) or not 0<=score<=1 or not 0<=threshold<=1:
            raise ApplicationError('Score và threshold phải nằm trong [0,1].')
        expected='Fraud' if score>=threshold else 'Legitimate'
        if data.get('prediction',expected)!=expected:
            raise ApplicationError('Nhãn không khớp score và threshold; giao dịch chưa được lưu.')
        return cls(score,threshold,expected)


def validate_payload(raw):
    kind=str(raw.get('type','')).strip().upper()
    if kind not in TYPES:raise ApplicationError('Type phải là '+', '.join(TYPES)+'.')
    values={'type':kind}
    try:
        step=Decimal(str(raw.get('step','')).strip())
        if not step.is_finite() or step<0 or step!=step.to_integral_value() or step>2147483647:raise ValueError()
        values['step']=int(step)
        for key in NUMERIC_FIELDS:
            number=Decimal(str(raw.get(key,'')).strip())
            if not number.is_finite() or number<0 or number>Decimal('9999999999999.99') or number!=number.quantize(Decimal('.01')):
                raise ValueError()
            values[key]=number
    except (InvalidOperation,ValueError) as exc:
        raise ApplicationError('Step phải là số nguyên không âm. Số tiền/số dư tối đa 13 chữ số phần nguyên và 2 chữ số thập phân, phù hợp DECIMAL(15,2).') from exc
    return values


def summarize(rows):
    counts={kind:[0,0] for kind in TYPES};fraud=0
    for row in rows:
        label=row.get('prediction');kind=row.get('type')
        if label not in ('Fraud','Legitimate') or kind not in counts:
            raise ApplicationError('Giao dịch có nhãn hoặc loại không hợp lệ.')
        positive=label=='Fraud';fraud+=positive;counts[kind][0 if positive else 1]+=1
    total=len(rows)
    return dict(total=total,fraud=fraud,legitimate=total-fraud,
                fraud_rate=100*fraud/total if total else 0,counts=counts)


def records(frame):
    if not hasattr(frame,'to_dict'):raise ApplicationError('DAO phải trả pandas.DataFrame.')
    return frame.to_dict(orient='records')

class ManagedConnector(Connector):
    """Keep the supplied Connector intact; set connection timeouts."""
    def __init__(self,settings):
        super().__init__(settings.db_host,settings.db_port,settings.db_name,settings.db_user,settings.db_password)
        self.timeout=settings.db_timeout

    def connect(self):
        self.conn=mysql.connector.connect(host=self.server,port=self.port,database=self.database,
            user=self.username,password=self.password,charset='utf8mb4',
            connection_timeout=self.timeout,read_timeout=self.timeout,
            write_timeout=self.timeout,autocommit=True)
        return self.conn

class TransactionRepository:
    def __init__(self,connector):
        self.connector=connector;self.dao=TransactionDAO(connector)

    def list_for_user(self,user_id):
        rows=records(self.dao.get_transactions_by_user(user_id))
        for row in rows:
            if str(row['user_id'])!=str(user_id):
                raise ApplicationError('DAO trả dữ liệu không thuộc tài khoản hiện tại.')
        return rows

    def get_for_user(self,user_id,transaction_id):
        owned=self.connector.queryDataset('''SELECT transaction_id FROM transactions
            WHERE user_id=%s AND transaction_id=%s LIMIT 1''',(user_id,transaction_id))
        if owned.empty:raise ApplicationError('Không tìm thấy giao dịch thuộc tài khoản hiện tại.')
        row=self.dao.get_transaction_by_id(transaction_id)
        if not row or str(row.get('user_id'))!=str(user_id):
            raise ApplicationError('Không tìm thấy giao dịch thuộc tài khoản hiện tại.')
        return row

    def insert(self,user_id,payload,result):
        return self.dao.insert_transaction(user_id=user_id,step=payload['step'],
            transaction_type=payload['type'],amount=payload['amount'],
            oldbalance_org=payload['oldbalance_org'],newbalance_orig=payload['newbalance_orig'],
            oldbalance_dest=payload['oldbalance_dest'],newbalance_dest=payload['newbalance_dest'],
            fraud_score=result.fraud_score,threshold=result.threshold,prediction=result.prediction)

class ApplicationService:
    def __init__(self,settings,predictor=None):
        self.settings=settings;self.passwords=PasswordVerifier();self.predictor=predictor

    @contextmanager
    def connection(self):
        connector=ManagedConnector(self.settings)
        try:connector.connect();yield connector
        except mysql.connector.Error as exc:
            raise ApplicationError('Không thể đọc/ghi MySQL. Kiểm tra .env và kết nối. Nếu lỗi xảy ra lúc lưu, hãy kiểm tra lịch sử trước khi gửi lại.') from exc
        finally:connector.disConnect()

    def authenticate(self,username,password):
        if not username.strip() or not password:raise ApplicationError('Vui lòng nhập tên đăng nhập và mật khẩu.')
        with self.connection() as connector:
            user=UserDAO(connector).get_user_by_username(username.strip())
            if not user or not self.passwords.verify(user.get('password_hash'),password):
                raise ApplicationError('Tên đăng nhập hoặc mật khẩu không đúng.')
            safe_user={key:user.get(key) for key in ('user_id','username','full_name')}
            rows=TransactionRepository(connector).list_for_user(user['user_id'])
            return dict(user=safe_user,rows=rows,summary=summarize(rows))

    def load_transactions(self,user_id):
        with self.connection() as connector:rows=TransactionRepository(connector).list_for_user(user_id)
        return dict(rows=rows,summary=summarize(rows))

    def get_transaction(self,user_id,transaction_id):
        with self.connection() as connector:return TransactionRepository(connector).get_for_user(user_id,transaction_id)

    def predict_and_save(self,user_id,raw):
        if user_id is None:raise ApplicationError('Phiên đăng nhập không hợp lệ.')
        payload=validate_payload(raw)
        if self.predictor is None:
            from FraudPredictor import BundlePredictor
            self.predictor=BundlePredictor(self.settings)
        result=PredictionResult.validate(self.predictor.predict(payload))
        with self.connection() as connector:
            repository=TransactionRepository(connector)
            transaction_id=repository.insert(user_id,payload,result)
            try:
                rows=repository.list_for_user(user_id)
                return dict(transaction_id=transaction_id,result=result,payload=payload,
                    rows=rows,summary=summarize(rows),refresh_error=None)
            except Exception:
                return dict(transaction_id=transaction_id,result=result,payload=payload,
                    rows=None,summary=None,refresh_error='Giao dịch đã lưu nhưng chưa tải lại được lịch sử. Mở lại Tổng quan để làm mới.')
