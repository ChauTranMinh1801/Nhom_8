
from DAL_DAO.connector import Connector


def test_connection():
    db = Connector(
        server="localhost",
        port=3306,
        database="fraud_detection",
        username="root",
        password="@Obama123"  # Nhap mat khau MySQL cua ban
    )

    try:
        # 1. Kiem tra ket noi MySQL
        print("1. Kiem tra ket noi MySQL")

        conn = db.connect()

        if conn is None:
            print("Ket noi MySQL that bai!")
            return

        print("Ket noi MySQL thanh cong!")

        # 2. Lay danh sach bang
        print("\n2. Danh sach bang trong database")

        tables = db.getTablesName()

        for table in tables:
            print("-", table)

        # 3. Kiem tra bang users
        print("\n3. Du lieu bang users")

        users = db.queryDataset(
            """
            SELECT user_id, username
            FROM users
            LIMIT 5
            """
        )

        print(users.to_string(index=False))

        # 4. Kiem tra bang transactions
        print("\n4. Du lieu bang transactions")

        transactions = db.queryDataset(
            """
            SELECT transaction_id, user_id,
                   fraud_score, threshold, prediction
            FROM transactions
            LIMIT 5
            """
        )

        print(transactions.to_string(index=False))

        # 5. Kiem tra truy van co tham so
        print("\n5. Kiem tra lich su cua user_id = 1")

        history = db.queryDataset(
            """
            SELECT transaction_id, user_id,
                   fraud_score, prediction
            FROM transactions
            WHERE user_id = %s
            """,
            (1,)
        )

        print(history.to_string(index=False))

        print("\nHoan tat kiem tra DAL!")

    except Exception as e:
        print("\nCo loi xay ra:", e)

    finally:
        db.disConnect()
        print("Da dong ket noi MySQL.")


if __name__ == "__main__":
    test_connection()
