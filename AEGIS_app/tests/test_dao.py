
from DAL_DAO.connector import Connector
from DAL_DAO.user_dao import UserDAO
from DAL_DAO.transaction_dao import TransactionDAO


def test_dao():
    db = Connector(
        server="localhost",
        port=3306,
        database="fraud_detection",
        username="root",
        password="@Obama123"
    )

    try:
        # Ket noi database
        if db.connect() is None:
            print("Ket noi MySQL that bai!")
            return

        print("Ket noi MySQL thanh cong!")

        # Khoi tao DAO
        user_dao = UserDAO(db)
        transaction_dao = TransactionDAO(db)

        # TEST 1: Lay danh sach user
        print("\nTEST 1: ALL USERS")
        users = user_dao.get_all_users()
        print(users.to_string(index=False))

        if users.empty:
            print("Khong co user de test.")
            return

        # Chon user that tu database
        user_id = int(users.iloc[0]["user_id"])
        username = users.iloc[0]["username"]

        # TEST 2: Tim user theo username
        print("\nTEST 2: USERNAME")
        user = user_dao.get_user_by_username(username)

        if user:
            print("Tim thay user:", user["username"])
            print("User ID:", user["user_id"])
        else:
            print("Khong tim thay user!")

        # TEST 3: Tim user theo ID
        print("\n TEST 3: USER ID")
        user = user_dao.get_user_by_id(user_id)
        print(user)

        # TEST 4: Lay lich su du doan
        print("\nTEST 4: HISTORY")
        history = transaction_dao.get_transactions_by_user(user_id)

        if history.empty:
            print("User chua co lich su du doan.")
        else:
            print(history.to_string(index=False))

            # TEST 5: Lay chi tiet giao dich
            transaction_id = int(
                history.iloc[0]["transaction_id"]
            )

            print("\nTEST 5: TRANSACTION")
            transaction = transaction_dao.get_transaction_by_id(
                transaction_id
            )

            print(transaction)

        print("\nTEST HOAN TAT")

    except Exception as e:
        print("Co loi xay ra:", e)

    finally:
        db.disConnect()
        print("Da dong ket noi MySQL.")


if __name__ == "__main__":
    test_dao()
