
class UserDAO:
    def __init__(self, connector):
        self.connector = connector

    def get_user_by_username(self, username):
        """
        Tim thong tin tai khoan theo username.
        Tra ve dictionary neu tim thay, None neu khong.
        """
        sql = """
            SELECT user_id, username, password_hash,
                   full_name, created_at
            FROM users
            WHERE username = %s
            LIMIT 1
        """

        df = self.connector.queryDataset(sql, (username,))

        if df.empty:
            return None

        return df.iloc[0].to_dict()

    def get_user_by_id(self, user_id):
        """
        Tim thong tin nguoi dung theo user_id.
        """
        sql = """
            SELECT user_id, username, full_name, created_at
            FROM users
            WHERE user_id = %s
            LIMIT 1
        """

        df = self.connector.queryDataset(sql, (user_id,))

        if df.empty:
            return None

        return df.iloc[0].to_dict()

    def get_all_users(self):
        """
        Lay danh sach nguoi dung.
        Khong tra ve password_hash.
        """
        sql = """
            SELECT user_id, username, full_name, created_at
            FROM users
            ORDER BY user_id
        """

        return self.connector.queryDataset(sql)
