"""Explicit UI fixtures. Never connect to MySQL or merge with production data."""
from datetime import datetime,timedelta
from decimal import Decimal
from AegisService import ApplicationError,summarize

class PreviewService:
    is_preview=True

    def __init__(self,empty=False):
        self.users=[dict(user_id=101,username='preview',full_name='Nguyễn An'),
                    dict(user_id=102,username='preview_b',full_name='Lê Minh'),
                    dict(user_id=103,username='preview_c',full_name='Trần Linh')]
        self.rows=[]
        if empty:return
        kinds=('CASH_IN','CASH_OUT','DEBIT','PAYMENT','TRANSFER')
        now=datetime.now().replace(hour=15,minute=30,second=0,microsecond=0)
        for i in range(38):
            owner=self.users[0] if i%4!=0 else self.users[1+i%2]
            kind=kinds[i%5];positive=i%7 in (0,1) and kind in ('TRANSFER','CASH_OUT','DEBIT')
            score=Decimal('0.99820') if positive else Decimal('0.02310')
            amount=Decimal((i+1)*175000)
            self.rows.append(dict(transaction_id=1001+i,user_id=owner['user_id'],step=i+1,type=kind,
                amount=amount,oldbalance_org=amount*2,newbalance_orig=amount,
                oldbalance_dest=Decimal('100000'),newbalance_dest=amount+Decimal('100000'),
                fraud_score=score,threshold=Decimal('.99414'),prediction='Fraud' if positive else 'Legitimate',
                created_at=now-timedelta(days=i//3,hours=i%3),checked_by=owner['full_name']))

    def authenticate(self,username,password):
        if username!='preview' or password!='preview':
            raise ApplicationError('Tài khoản hoặc mật khẩu không đúng. Chế độ preview dùng preview / preview.')
        return dict(user=dict(self.users[0]),**self.load_transactions(101))

    def load_transactions(self,user_id):
        rows=[dict(row) for row in self.rows if row['user_id']==user_id]
        return dict(rows=rows,summary=summarize(rows))

    def load_history(self,user_id):
        if user_id is None:raise ApplicationError('Cần đăng nhập để xem lịch sử.')
        return dict(rows=[dict(row) for row in self.rows],users=[dict(user) for user in self.users])

    def get_transaction(self,user_id,transaction_id):
        row=next((r for r in self.rows if r['user_id']==user_id and r['transaction_id']==transaction_id),None)
        if row is None:raise ApplicationError('Không tìm thấy giao dịch của tài khoản này.')
        return dict(row)

    def get_history_transaction(self,user_id,transaction_id):
        if user_id is None:raise ApplicationError('Cần đăng nhập để xem lịch sử.')
        row=next((r for r in self.rows if r['transaction_id']==transaction_id),None)
        if row is None:raise ApplicationError('Không tìm thấy giao dịch trong lịch sử.')
        return dict(row)

    def predict_and_save(self,user_id,raw):
        raise ApplicationError('Đây là chế độ xem giao diện. Hãy chạy chế độ thật để dự đoán và lưu MySQL.')
