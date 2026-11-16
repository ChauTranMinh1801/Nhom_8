from PyQt6.QtWidgets import QDialog
from ui.Ui_TransactionDetails import Ui_TransactionDetails

class TransactionDetailsExt(QDialog):
    def __init__(self,row,parent=None):
        super().__init__(parent);self.ui=Ui_TransactionDetails();self.ui.setupUi(self)
        self.transaction_id=row['transaction_id']
        fields=('transaction_id','type','step','amount','oldbalance_org',
                'newbalance_orig','oldbalance_dest','newbalance_dest','fraud_score',
                'threshold','prediction','created_at')
        for key in fields:
            value=row.get(key)
            if key=='fraud_score' and value is not None:value=f'{float(value)*100:.4f}%'
            getattr(self.ui,key+'Value').setText('—' if value is None or value=='' else str(value))
        self.ui.closeButton.clicked.connect(self.reject)

    def set_busy(self,busy):
        self.ui.closeButton.setEnabled(not busy)
