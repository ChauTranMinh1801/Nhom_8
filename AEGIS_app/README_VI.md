# AEGIS — cập nhật giao diện

## Cách thay vào project hiện tại

1. Đóng ứng dụng đang chạy trong PyCharm.
2. Giải nén gói cập nhật, chép toàn bộ nội dung vào thư mục đang chứa `main.py`, chọn Replace/Ghi đè.
3. Giữ file `.env` hiện tại của bạn; gói tải xuống không chứa `.env` có thông tin kết nối.
4. Run `main.py` như trước. Không cần thêm thư viện biểu đồ, không cần chạy SQL, không thay đổi database.

`DAL_DAO/`, `Models/`, `ModelPortable.json`, `FraudPredictor.py` và các ảnh `previews/` giữ nguyên so với source bạn gửi. Phần cập nhật tập trung vào UI, Ext, các phương thức đọc dữ liệu cho giao diện và kiểm thử. Không đổi mô hình hoặc ngưỡng phân loại.

## Các thay đổi

- Menu “Quản lý hồ sơ” đổi thành **Lịch sử dự đoán**.
- Nhập sai tài khoản/mật khẩu hiển thị hộp thoại nền đen, chữ trắng, icon cảnh báo. Dùng hộp thoại Qt được style trực tiếp để áp dụng trên Windows.
- Dashboard có bốn chỉ số như trước, ba biểu đồ và Recent Transactions với tối đa 5 giao dịch mới nhất của tài khoản đang đăng nhập.
- Transaction Distribution: donut Fraud/Legitimate.
- Transaction Activity: số giao dịch được kiểm tra theo ngày, tối đa 14 ngày lịch tính đến ngày mới nhất có dữ liệu; ngày không có giao dịch trong khoảng hiển thị được tính là 0. Ngày được lấy từ created_at, không từ dataset huấn luyện.
- Fraud by Transaction Type: chỉ đếm Fraud theo CASH_IN, CASH_OUT, DEBIT, PAYMENT, TRANSFER.
- Recent Transactions gồm Transaction ID, Type, Amount, Fraud Score, Prediction, Checked By, Created At.
- Không có giao dịch: chỉ số bằng 0, hiển thị Empty State, ẩn biểu đồ và bảng recent. Lỗi kết nối hiển thị thông báo lỗi thay vì coi là dữ liệu rỗng hợp lệ.
- Type chuyển thành dropdown đúng năm lựa chọn. Clear đưa dropdown về chưa chọn mà không xóa các lựa chọn.
- Step, Type, Amount cùng một hàng, cùng kích thước. Hai cặp số dư nguồn/đích nằm cân đối bên dưới.
- Vòng confidence chỉ còn phần trăm ở giữa; độ đầy phần màu đúng theo score. Bỏ các phần trăm nhỏ màu xám bên ngoài.
- Kết quả hiển thị đúng **Fraud** hoặc **Legitimate**. Icon lớn hơn, caption sát icon.
- Lịch sử dự đoán hiển thị toàn bộ transactions đã lưu, kèm tên người kiểm tra và lọc theo user. Tiêu đề và dữ liệu căn cột thống nhất, không đổi độ rộng theo nội dung sau lọc.

Fraud Score được trình bày dưới dạng score × 100 và có ký hiệu %. Đây vẫn là điểm model, không tự đổi thành một xác suất đã hiệu chuẩn. Ngưỡng phân loại và nhãn lưu trữ không thay đổi trong bản cập nhật UI.

## Phạm vi dữ liệu thực tế

**Dashboard:** chỉ giao dịch của tài khoản đang đăng nhập. Tính tổng từ `TransactionDAO.get_transactions_by_user(user_id)`. Tên Checked By lấy từ users qua user_id. Không đọc hoặc cộng số liệu của tập huấn luyện vào thống kê.

**Lịch sử dự đoán:** theo yêu cầu mới, mọi tài khoản đã đăng nhập xem được toàn bộ lịch sử đã lưu trong transactions, JOIN users để hiển thị tên người kiểm tra. Lọc tên dùng user_id, nên hai người trùng tên vẫn được phân biệt bằng username trong danh sách chọn. Mở chi tiết từ lịch sử cho phép xem bản ghi của người khác; mở chi tiết từ Recent Transactions vẫn dùng luồng giao dịch của chính tài khoản.

Bản cập nhật chỉ bổ sung SELECT/JOIN cần thiết trong AegisService, không sửa ba file DAO/DAL gốc, không tạo thêm bảng hoặc cột. Không có SQL migration hay chức năng tạo user.

## Xem giao diện bằng dữ liệu mô phỏng

Chế độ chạy bình thường vẫn dùng MySQL thật từ `.env`. Chế độ preview là một service riêng và không được dùng làm fallback khi MySQL lỗi.

Trong PyCharm: Run → Edit Configurations → Parameters/Script parameters, nhập một trong các tùy chọn sau:

```text
--preview
```

Xem Empty State:

```text
--preview --empty
```

Xem đăng nhập và thử hộp cảnh báo:

```text
--preview --login
```

Tài khoản của riêng chế độ preview: `preview` / `preview`. Khi dùng mock, màn hình luôn có banner “UI PREVIEW · Dữ liệu mô phỏng riêng, không ghi MySQL”. Submit trong chế độ này không tạo kết quả ML giả, không ghi database. Xóa các tham số preview để trở về chạy thật.

Dữ liệu trong PreviewService.py tách hẳn khỏi ApplicationService. UI nhận service qua constructor nên có thể thay nguồn dữ liệu mà không chỉnh file Python sinh từ Designer.

## Tổ chức code

- `ui/Aegis.ui`, `ui/TransactionDetails.ui`: thiết kế bằng Qt Designer.
- `ui/Ui_Aegis.py`, `ui/Ui_TransactionDetails.py`: sinh tự động; không có logic truy vấn hay tương tác.
- `AegisExt.py`: điều hướng, lấy/đổ dữ liệu, sự kiện, Type dropdown, hộp cảnh báo, lọc bảng, tác vụ nền.
- `AegisService.py`: xác thực và đọc/ghi dữ liệu thực; bổ sung load_history và get_history_transaction cho phạm vi toàn hệ thống.
- `ChartWidgets.py`: donut, line, bar dùng QPainter của PyQt6, không thêm dependency biểu đồ.
- `PreviewService.py`: dữ liệu UI mô phỏng được đánh dấu rõ.
- `TransactionDetailsExt.py`: hiển thị chi tiết read-only, thêm Checked By.
- `main.py`: entry point, lựa chọn real/preview.
- `ui/assets/chevron-down.svg`: icon mũi tên dropdown.
- `test/`: cập nhật kiểm thử và thêm test_ui_refresh.py cho các yêu cầu giao diện mới.

Generate lại Python sau khi sửa file `.ui`:

```bash
python generate_ui.py
```

Không sửa tay Ui_*.py. Các đường dẫn asset được tính tại runtime, không gắn với máy tạo file.

## Kiểm tra

Đã kiểm tra bằng PyQt6 offscreen và MySQL 8.4 độc lập khôi phục từ schema/dump bạn đã cung cấp trước đó. Bao gồm:

- UI compile chính xác từ `.ui`, các trang ở 1360×860 và cửa sổ nhỏ hơn.
- Đăng nhập sai: hộp thoại đen/trắng và Warning icon.
- Type có đủ 5 lựa chọn, kích thước bằng Step/Amount, Clear không mất danh sách.
- Ba biểu đồ, số đếm theo ngày, recent tối đa 5 dòng, Empty State.
- Mock không truy cập MySQL và không trộn vào real service.
- Dashboard theo tài khoản, lịch sử toàn hệ thống, Checked By đúng JOIN users và lọc tên không ảnh hưởng thống kê Dashboard.
- Tìm từ thanh trên reset bộ lọc tên để có thể tìm Transaction ID trong toàn lịch sử.
- Độ đầy confidence tăng theo score, bỏ phần trăm ngoài vòng, caption/icon gọn.
- Lưu/dự đoán thật bằng mô hình gốc, độ chính xác DECIMAL theo schema hiện có và logout xóa dữ liệu UI.

Chạy tests:

```bash
python -m unittest discover -s test -v
```

Các tests MySQL chỉ bật khi chủ động đặt biến AEGIS_TEST_DB_HOST/PORT/NAME/USER/PASSWORD; database thử nghiệm phải kết thúc bằng `_test`. Tests không tạo schema/user; các bản ghi thử được xóa theo ID do chính test tạo.

Các ảnh previews/ cũ được giữ nguyên từ source; xem giao diện mới bằng chế độ `--preview`.
