# -*- coding: utf-8 -*-
"""
fraud_preprocessing.py  (phiên bản cho quy trình: FE -> Split -> Preprocessing)
==============================================================================
Module tiền xử lý DÙNG CHUNG cho mục 3.2.7, huấn luyện RQ1-RQ3 và Flask.

Quy trình dữ liệu của nhóm:
    3.2.6 Feature Engineering  ->  3.2.8 Train/Val/Test  ->  3.2.7 Preprocessing

Nguyên tắc
----------
- Imputer, scaler, encoder chỉ được fit trên TRAIN; Validation/Test chỉ transform.
- Không SMOTE ở đây. SMOTE chỉ thực hiện ở RQ2, chỉ trên Train.
- `engineer_features` lặp lại ĐÚNG công thức FE01-FE02 của 3.2.6 để Flask dựng
  đặc trưng giống lúc huấn luyện (có kiểm tra đối chiếu với dữ liệu đã lưu).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

# ============================================================
# 1. ĐỊNH NGHĨA ĐẶC TRƯNG (khớp 3.2.5 và 3.2.6)
# ============================================================

BASE_FEATURES = [
    "step",
    "type",
    "amount",
    "oldbalanceOrg",
    "newbalanceOrig",
    "oldbalanceDest",
    "newbalanceDest",
]

# Tên cột viết đúng như file X_features_engineered.parquet (chữ "b" viết thường)
ENGINEERED_FEATURES = [
    "errorbalanceOrig",
    "errorbalanceDest",
]

FEATURES = BASE_FEATURES + ENGINEERED_FEATURES      # 9 đặc trưng đầu vào
TARGET = "isFraud"

# Năm loại giao dịch được giữ nguyên (3.2.5). Khai báo cố định để số cột
# One-Hot luôn như nhau ở mọi tập và Flask từ chối loại lạ.
TRANSACTION_TYPES = ["CASH_IN", "CASH_OUT", "DEBIT", "PAYMENT", "TRANSFER"]

CATEGORICAL_COLUMNS = ["type"]

# Nhóm mô hình -> kiểu preprocessing
#   linear: nhạy với thang đo           -> cần scaling
#   tree  : chỉ so sánh với ngưỡng      -> không cần scaling
MODEL_FAMILY = {
    "logistic_regression": "linear",
    "random_forest": "tree",
    "xgboost": "tree",
}


# ============================================================
# 2. FEATURE ENGINEERING (lặp lại đúng công thức 3.2.6 - FE02)
# ============================================================

def engineer_features(frame: pd.DataFrame) -> pd.DataFrame:
    """
    Tạo hai đặc trưng chênh lệch số dư từ 7 đặc trưng gốc.
    Công thức giống hệt FE02 trong 3.2.6; không dùng nhãn, không học tham số.
    """
    missing = [c for c in BASE_FEATURES if c not in frame.columns]
    if missing:
        raise ValueError(f"Missing columns: {missing}")

    X_fe = frame[BASE_FEATURES].copy()
    tx_type = X_fe["type"]

    # 1. Origin: CASH_IN thì số dư tăng, các loại còn lại thì giảm
    expected_orig = np.where(
        tx_type.eq("CASH_IN"),
        X_fe["oldbalanceOrg"] + X_fe["amount"],
        X_fe["oldbalanceOrg"] - X_fe["amount"],
    )
    X_fe["errorbalanceOrig"] = X_fe["newbalanceOrig"] - expected_orig

    # 2. Destination: TRANSFER/CASH_OUT tăng, CASH_IN giảm,
    #    PAYMENT/DEBIT không áp dụng -> chênh lệch bằng 0 theo quy ước
    expected_dest = np.select(
        [
            tx_type.isin(["TRANSFER", "CASH_OUT"]),
            tx_type.eq("CASH_IN"),
        ],
        [
            X_fe["oldbalanceDest"] + X_fe["amount"],
            X_fe["oldbalanceDest"] - X_fe["amount"],
        ],
        default=X_fe["newbalanceDest"],
    )
    X_fe["errorbalanceDest"] = expected_dest - X_fe["newbalanceDest"]

    return X_fe[FEATURES]


# ============================================================
# 3. PREPROCESSOR (ColumnTransformer)
# ============================================================

def split_columns():
    """Trả về (cột số liên tục, cột phân loại)."""
    categorical = list(CATEGORICAL_COLUMNS)
    numeric = [c for c in FEATURES if c not in categorical]
    return numeric, categorical


def build_preprocessor(model_family: str) -> ColumnTransformer:
    """
    Tạo ColumnTransformer CHƯA FIT.

    model_family = "linear"  (Logistic Regression)
        - 8 biến số : median imputer -> StandardScaler
        - type      : One-Hot (5 loại cố định)

    model_family = "tree"    (Random Forest, XGBoost)
        - 8 biến số : median imputer, KHÔNG scale
        - type      : One-Hot (5 loại cố định)

    Hai nhánh cho cùng 13 cột đầu ra, cùng thứ tự; chỉ khác việc có scale hay không.
    SimpleImputer là lớp an toàn: dữ liệu huấn luyện không có giá trị thiếu (3.2.4).
    """
    if model_family not in {"linear", "tree"}:
        raise ValueError("model_family phải là 'linear' hoặc 'tree'.")

    numeric, categorical = split_columns()

    numeric_steps = [("imputer", SimpleImputer(strategy="median"))]
    if model_family == "linear":
        numeric_steps.append(("scaler", StandardScaler()))

    preprocessor = ColumnTransformer(
        transformers=[
            ("num", Pipeline(numeric_steps), numeric),
            (
                "cat",
                OneHotEncoder(
                    categories=[TRANSACTION_TYPES],
                    handle_unknown="error",   # loại lạ -> báo lỗi, không đoán ngầm
                    sparse_output=False,
                ),
                categorical,
            ),
        ],
        remainder="drop",
        verbose_feature_names_out=False,
    )
    preprocessor.set_output(transform="pandas")
    return preprocessor


# ============================================================
# 4. SUY LUẬN (Flask) - dùng đúng công thức lúc huấn luyện
# ============================================================

_NUMERIC_INPUTS = [
    "step",
    "amount",
    "oldbalanceOrg",
    "newbalanceOrig",
    "oldbalanceDest",
    "newbalanceDest",
]


def prepare_inference_frame(payload) -> pd.DataFrame:
    """
    Chuyển một giao dịch (dict) hoặc nhiều giao dịch (list[dict]) gồm 7 trường gốc
    thành DataFrame 9 đặc trưng, đúng cột/kiểu như dữ liệu huấn luyện.

    Chỉ kiểm tra đầu vào (không học tham số): đủ 7 trường, số hữu hạn, không âm,
    `type` thuộc 5 loại.
    """
    records = [payload] if isinstance(payload, dict) else list(payload)
    raw = pd.DataFrame(records)

    missing = [c for c in BASE_FEATURES if c not in raw.columns]
    if missing:
        raise ValueError(f"Thiếu trường đầu vào: {missing}")

    raw = raw[BASE_FEATURES].copy()

    for col in _NUMERIC_INPUTS:
        raw[col] = pd.to_numeric(raw[col], errors="raise")
        if not np.isfinite(raw[col].to_numpy(dtype=float)).all():
            raise ValueError(f"{col} chứa giá trị thiếu hoặc vô hạn.")
        if (raw[col] < 0).any():
            raise ValueError(f"{col} không được âm.")

    bad_types = sorted(set(raw["type"]) - set(TRANSACTION_TYPES))
    if bad_types:
        raise ValueError(
            f"type không hợp lệ: {bad_types}. Chỉ chấp nhận {TRANSACTION_TYPES}."
        )

    # Ép kiểu giống dữ liệu huấn luyện (step: int64, còn lại: float64)
    raw["step"] = raw["step"].astype("int64")
    for col in _NUMERIC_INPUTS[1:]:
        raw[col] = raw[col].astype("float64")

    return engineer_features(raw)


def transform_for_inference(payload, preprocessor, expected_columns=None) -> pd.DataFrame:
    """
    Giao dịch thô -> đặc trưng -> preprocessor ĐÃ FIT (chỉ transform) -> ma trận
    đưa vào mô hình. Nếu có `expected_columns` thì kiểm tra khớp cột/thứ tự
    với dữ liệu mô hình đã học.
    """
    features = prepare_inference_frame(payload)
    z = preprocessor.transform(features)
    if expected_columns is not None and list(z.columns) != list(expected_columns):
        raise RuntimeError(
            "Cột sau tiền xử lý không khớp dữ liệu huấn luyện: "
            f"{list(z.columns)} != {list(expected_columns)}"
        )
    return z
