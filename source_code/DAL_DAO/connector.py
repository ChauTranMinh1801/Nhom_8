import mysql.connector
import pandas as pd
import traceback


class Connector:
    def __init__(self, server="localhost", port=3306,
                 database=None, username="root", password=""):
        self.server = server
        self.port = port
        self.database = database
        self.username = username
        self.password = password
        self.conn = None

    def connect(self):
        try:
            self.conn = mysql.connector.connect(
                host=self.server,
                port=self.port,
                database=self.database,
                user=self.username,
                password=self.password
            )
            return self.conn

        except mysql.connector.Error:
            traceback.print_exc()
            return None

    def disConnect(self):
        if self.conn is not None:
            if self.conn.is_connected():
                self.conn.close()
            self.conn = None

    def queryDataset(self, sql, params=None):
        if self.conn is None or not self.conn.is_connected():
            raise ConnectionError("Chua ket noi MySQL")

        cursor = self.conn.cursor()

        try:
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            columns = cursor.column_names

            return pd.DataFrame(rows, columns=columns)

        finally:
            cursor.close()

    def getTablesName(self):
        if self.conn is None or not self.conn.is_connected():
            raise ConnectionError("Chua ket noi MySQL")

        cursor = self.conn.cursor()

        try:
            cursor.execute("SHOW TABLES")
            tables = cursor.fetchall()
            return [table[0] for table in tables]

        finally:
            cursor.close()

    # Thực hiện INSERT, UPDATE, DELETE
    def executeQuery(self, sql, params=None):
        if self.conn is None or not self.conn.is_connected():
            raise ConnectionError("Chua ket noi MySQL")

        cursor = self.conn.cursor()

        try:
            cursor.execute(sql, params)
            self.conn.commit()

            return cursor.lastrowid

        except mysql.connector.Error:
            self.conn.rollback()
            raise

        finally:
            cursor.close()