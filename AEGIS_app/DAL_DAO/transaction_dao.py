
class TransactionDAO:
    def __init__(self, connector):
        self.connector = connector

    def insert_transaction(
        self,
        user_id,
        step,
        transaction_type,
        amount,
        oldbalance_org,
        newbalance_orig,
        oldbalance_dest,
        newbalance_dest,
        fraud_score,
        threshold,
        prediction
    ):
        """
        Luu giao dich va ket qua du doan vao MySQL.
        Tra ve transaction_id vua duoc tao.
        """

        valid_types = {
            "CASH_IN", "CASH_OUT", "DEBIT",
            "PAYMENT", "TRANSFER"
        }

        if transaction_type not in valid_types:
            raise ValueError("Loai giao dich khong hop le")

        if prediction not in ("Fraud", "Legitimate"):
            raise ValueError("Prediction khong hop le")

        if not 0 <= fraud_score <= 1:
            raise ValueError("Fraud score phai nam trong [0, 1]")

        if not 0 <= threshold <= 1:
            raise ValueError("Threshold phai nam trong [0, 1]")

        sql = """
            INSERT INTO transactions (
                user_id,
                step,
                type,
                amount,
                oldbalance_org,
                newbalance_orig,
                oldbalance_dest,
                newbalance_dest,
                fraud_score,
                threshold,
                prediction
            )
            VALUES (
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s
            )
        """

        params = (
            user_id,
            step,
            transaction_type,
            amount,
            oldbalance_org,
            newbalance_orig,
            oldbalance_dest,
            newbalance_dest,
            fraud_score,
            threshold,
            prediction
        )

        return self.connector.executeQuery(sql, params)

    def get_transactions_by_user(self, user_id):
        """
        Lay lich su du doan theo user_id.
        Sap xep giao dich moi nhat len dau.
        """

        sql = """
            SELECT
                transaction_id,
                user_id,
                step,
                type,
                amount,
                fraud_score,
                threshold,
                prediction,
                created_at
            FROM transactions
            WHERE user_id = %s
            ORDER BY created_at DESC, transaction_id DESC
        """

        return self.connector.queryDataset(sql, (user_id,))

    def get_transaction_by_id(self, transaction_id):
        """
        Lay chi tiet mot giao dich.
        """

        sql = """
            SELECT *
            FROM transactions
            WHERE transaction_id = %s
            LIMIT 1
        """

        df = self.connector.queryDataset(
            sql, (transaction_id,)
        )

        if df.empty:
            return None

        return df.iloc[0].to_dict()
