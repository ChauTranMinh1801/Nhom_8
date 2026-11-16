# AEGIS — bản dùng đúng database hiện tại

Bản này dùng trực tiếp hai bảng `users`, `transactions` trong `fraud_detection.sql` bạn cung cấp. Không kèm file SQL bổ sung, không tạo bảng/cột, không có công cụ tạo user. Destination ID đã được bỏ hoàn toàn khỏi form và logic.

## Cấu trúc

```text
AEGIS_Final/
├── DAL_DAO/                   # Đúng 3 file gốc, không sửa
│   ├── connector.py
│   ├── user_dao.py
│   └── transaction_dao.py
├── Models/                    # Đúng 5 artifact gốc, không sửa
├── previews/                  # Giữ nguyên các ảnh của gói trước theo yêu cầu
├── test/                      # Giữ thư mục kiểm thử và 3 tên file kiểm thử
├── ui/
│   ├── Aegis.ui
│   ├── Ui_Aegis.py             # Sinh tự động, chỉ chứa giao diện
│   ├── TransactionDetails.ui
│   ├── Ui_TransactionDetails.py
│   └── assets/
├── AegisExt.py                 # Tương tác UI và worker chạy nền
├── TransactionDetailsExt.py    # Xem chi tiết giao dịch, chỉ đọc
├── AegisService.py             # Cấu hình, xác thực, dữ liệu, nghiệp vụ
├── FraudPredictor.py           # Inference bằng model + preprocessor gốc
├── ChartWidgets.py             # Chỉ vẽ biểu đồ
├── main.py                     # File chạy ứng dụng
├── generate_ui.py              # Generate .ui → Ui_*.py
├── .env.example
├── requirements.txt
└── README_VI.md
```

Các kiểm thử trong `test/` được cập nhật theo schema thật và yêu cầu cuối: không còn kiểm thử bảng phụ hay chức năng cập nhật hồ sơ không có cột lưu trữ. Các ảnh `previews/` được giữ nguyên byte theo yêu cầu, vì vậy ảnh cũ không phản ánh việc bỏ Destination ID và thiết kế lại bảng ở phiên bản này.

## Cài và chạy

Khuyến nghị môi trường ảo Python 3.13 theo model gốc; đã kiểm tra inference trên Python 3.12 với các phiên bản thư viện trong requirements.

```bash
python -m venv .venv
```

Windows:

```bat
.venv\Scripts\activate
python -m pip install -r requirements.txt
copy .env.example .env
```

macOS/Linux:

```bash
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

Điền cấu hình kết nối trong `.env`. Database đang dùng là `fraud_detection`; `DB_PASSWORD` là mật khẩu kết nối MySQL, không phải mật khẩu tài khoản AEGIS.

Nếu database của bạn đã có dữ liệu từ file dump thì chỉ cần cấu hình kết nối. Không chạy migration, không thêm cột hay bảng nào.

```bash
python main.py
```

Đăng nhập bằng tài khoản đã có trong `users`. App xác minh SHA-256 tương ứng `SHA2(password, 256)` và lấy đúng `user_id`/`full_name` từ UserDAO. Không có tài khoản demo hoặc tài khoản tự tạo.

## Chỉnh giao diện

Mở `ui/Aegis.ui` trong Qt Designer, sửa và lưu. Sau đó:

```bash
python generate_ui.py
```

`Ui_Aegis.py` và `Ui_TransactionDetails.py` được sinh bằng PyQt6.uic, không có xử lý tương tác. Các sự kiện nằm trong AegisExt.py/TransactionDetailsExt.py, nghiệp vụ trong AegisService.py. Không sửa tay file sinh tự động.

## Các màn hình

- **Đăng nhập**: xác thực tài khoản thật qua UserDAO gốc.
- **Tổng quan**: bốn chỉ số và hai biểu đồ tính từ `get_transactions_by_user(user_id)`. Lịch sử của mỗi tài khoản được tách riêng. Tài khoản chưa có giao dịch hiển thị 0 và ẩn biểu đồ; lỗi tải dữ liệu hiển thị lỗi/“—”.
- **Tra cứu**: còn đúng 7 đầu vào mà model cần: step, type, amount, oldbalanceOrg, newbalanceOrig, oldbalanceDest, newbalanceDest. Ô Amount dùng chiều ngang của hai cột sau khi bỏ Destination ID. Hai trạng thái Successful/Fail giữ phong cách cũ, nhưng lấy kết quả thật.
- **Quản lý hồ sơ**: thiết kế lại với các cột có dữ liệu: mã giao dịch, loại, số tiền, điểm Fraud (%), kết quả dự đoán và thời gian. Nút mở chi tiết được giữ. Bỏ mức ưu tiên, trạng thái xử lý, người phụ trách và các bộ lọc tương ứng. Có lọc loại giao dịch, kết quả Fraud/Legitimate, tìm mã và sắp xếp mới/cũ. Căn lề tiêu đề/ô thống nhất; độ rộng không nhảy theo dữ liệu khi lọc.
- **Chi tiết**: hiển thị dữ liệu thực từ `get_transaction_by_id`, sau kiểm tra quyền sở hữu. Chỉ xem, không có nút lưu các thông tin ngoài schema.

## Mô hình và độ chính xác lưu trữ

Giữ nguyên toàn bộ model/preprocessor/module feature engineering/manifest/ngưỡng. App kiểm tra SHA-256 và phiên bản thư viện trước khi nạp. Không huấn luyện lại, không fit lại preprocessor, không tối ưu lại ngưỡng.

Luồng: 7 đầu vào → feature engineering gốc → 13 cột đã tiền xử lý → XGBoost → so sánh ngưỡng **0.9941363334655762** → gọi `TransactionDAO.insert_transaction` gốc → cập nhật lịch sử/Tổng quan.

Database của bạn có:

- Số tiền/số dư `DECIMAL(15,2)`: tối đa 13 chữ số phần nguyên và 2 chữ số thập phân. Form được kiểm tra theo đúng giới hạn này.
- `fraud_score`, `threshold` là `DECIMAL(6,5)`: MySQL lưu 5 chữ số thập phân. Ngưỡng model mới sẽ được lưu thành **0.99414**. Nhãn được quyết định bằng score và ngưỡng đầy đủ trước khi lưu; lịch sử dùng nhãn đã lưu, không tính lại từ số đã làm tròn.
- Các dòng cũ có threshold **0.85000** vẫn được giữ nguyên. App không chấm lại hoặc đổi nhãn các giao dịch cũ theo model hiện tại.

Điểm Fraud là score của model, không mặc định coi là xác suất đã hiệu chuẩn. Giao diện hiển thị score × 100; nhãn dùng ngưỡng gốc như artifact.

## Đọc/ghi và phạm vi

Ba file DAL_DAO giữ nguyên. ManagedConnector kế thừa Connector để bổ sung timeout; mọi thao tác giao dịch dùng các phương thức DAO gốc. App chỉ đọc users và đọc/insert transactions, không tạo user, không cập nhật bảng khác.

Tác vụ database/model chạy bằng QThread, mỗi tác vụ có connection riêng. Submit được khóa trong lúc xử lý; gửi lại nguyên giao dịch vừa lưu được nhắc thay vì chèn trùng. Không thêm cột request_id hoặc cơ chế chống trùng bền vững vào database. Nếu mất kết nối đúng lúc ghi, kiểm tra lịch sử trước khi gửi lại.

## Kiểm tra

Đã chạy **19 kiểm thử** với MySQL 8.4, khôi phục trực tiếp dump gốc vào database thử nghiệm riêng, không thêm cột hay bảng:

- Xác minh SHA-256 và hành vi đăng nhập; truy vấn username tham số hóa.
- DataFrame của DAO, tách lịch sử theo user_id, ngăn xem giao dịch người khác.
- Giới hạn DECIMAL(15,2), score/threshold DECIMAL(6,5), giữ nhãn lịch sử.
- Inference khớp model gốc và đúng 13 đặc trưng; ngưỡng không bị thay bằng 0,5.
- Lưu nhãn/score/ngưỡng/số dư thật; model thiếu/hỏng không tạo giao dịch.
- Form chỉ có 7 đầu vào; bảng hồ sơ chỉ có các cột thực; căn cột ổn định sau lọc.
- Worker, Submit, chặn gửi trùng trong phiên, đăng xuất và xóa dữ liệu UI.
- Ui_*.py đúng kết quả sinh từ .ui; gói không chứa SQL hoặc create_user.py.

Chạy unit tests và model tests:

```bash
python -m unittest discover -s test -v
```

Tests MySQL chỉ bật khi đặt AEGIS_TEST_DB_HOST/PORT/NAME/USER/PASSWORD. Database kiểm thử bắt buộc kết thúc bằng `_test`, được khôi phục từ dump bạn đã có. Tests không tạo schema hoặc user; chỉ xóa các giao dịch do chính bài test chèn.

Database trên máy bạn chưa được kết nối từ môi trường này. Bản kiểm thử sử dụng đúng schema và dữ liệu dump trong MySQL độc lập.
