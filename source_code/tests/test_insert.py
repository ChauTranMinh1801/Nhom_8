
from DAL_DAO.connector import Connector
from DAL_DAO.transaction_dao import TransactionDAO

db = Connector(
    server="localhost",
    port=3306,
    database="fraud_detection",
    username="root",
    password="@Obama123"
)

try:
    if db.connect() is None:
        raise ConnectionError("Khong the ket noi MySQL")

    dao = TransactionDAO(db)

    # Su dung user_id co that trong bang users
    users = db.queryDataset(
        "SELECT user_id FROM users LIMIT 1"
    )

    if users.empty:
        raise ValueError("Database chua co user")

    user_id = int(users.iloc[0]["user_id"])

    transaction_id = dao.insert_transaction(
        user_id=user_id,
        step=150,
        transaction_type="TRANSFER",
        amount=120000,
        oldbalance_org=80000,
        newbalance_orig=30000,
        oldbalance_dest=10000,
        newbalance_dest=60000,
        fraud_score=0.998,
        threshold=0.994,
        prediction="Fraud"
    )

    print("INSERT thanh cong!")
    print("Transaction ID:", transaction_id)

    saved = dao.get_transaction_by_id(transaction_id)
    print("Du lieu vua luu:", saved)

finally:
    db.disConnect()
