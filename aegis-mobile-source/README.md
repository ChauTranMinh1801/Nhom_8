# AEGIS Mobile Banking — Mã nguồn ứng dụng khách hàng

HTML, CSS, JavaScript thuần và dữ liệu JSON có thể chỉnh sửa. Bao gồm bản sửa mới nhất: giữ hồ sơ đang rà soát khi có giao dịch mới, chặn chuyển tiền sau quyết định bảo vệ tài khoản, giữ hạn chế khi tải lại trang hoặc đổi kịch bản.

## 1. Chạy ứng dụng

Giải nén ZIP, mở terminal tại thư mục chứa `index.html`, chạy:

```bash
python -m http.server 8080
```

Hoặc `python3 -m http.server 8080`. Mở http://localhost:8080. Cũng có thể dùng Live Server trong VS Code.

Không cần npm, backend hay bước build. Cần chạy qua HTTP vì ứng dụng đọc JSON bằng fetch; không mở trực tiếp qua file://.

## 2. Cấu trúc mã nguồn

```text
index.html                 Khung trang
mobile.css                 Toàn bộ kiểu dáng và responsive
mobile.js                  Giao diện, điều hướng và tương tác
mobile-model.js            Logic nghiệp vụ, kiểm tra và chuyển trạng thái
data-loader.js             Đọc JSON rồi khởi động app
data/
  config.json              Khách hàng, số dư, người nhận, ngân hàng, kịch bản, thông báo
  transactions.json        Giao dịch lịch sử ban đầu
README.md                  Hướng dẫn này
```

Để dễ chỉnh dữ liệu, gói tải về nạp JSON trực tiếp. Đây là điểm khác với phiên bản ban đầu dùng `mobile-data.js`: bạn sửa các tệp JSON thay vì đối tượng JavaScript. Giao diện và luồng nghiệp vụ giữ cùng hành vi với bản đã xuất bản.

## 3. Đổi tên khách hàng, số dư và người nhận

Sửa `data/config.json`:

- `customer.name`: tên khách hàng.
- `customer.shortName`, `customer.initials`: tên ngắn và chữ viết tắt.
- `customer.account`: tài khoản nguồn.
- `customer.balance`: số dư khởi tạo, dạng số nguyên, đơn vị VNĐ.
- `banks`: tên các ngân hàng mô phỏng.
- `recipients`: danh sách người nhận gần đây. `bank` là vị trí trong mảng `banks`, bắt đầu từ 0.
- `scenarios`: tiêu đề và mô tả bốn kịch bản.
- `messages`: tiêu đề và nội dung thông báo rà soát, hoàn tất, bảo vệ.

Giữ các mã kịch bản `normal`, `flagged`, `cleared`, `protected` vì logic dùng các mã này. Có thể sửa nhãn hiển thị.

JSON phải dùng dấu ngoặc kép; không có comment hay dấu phẩy thừa. Số tiền là số nguyên, ví dụ `168500000`, không viết `168.500.000`.

## 4. Chỉnh giao dịch lịch sử mẫu

Sửa `data/transactions.json`. Mỗi giao dịch có:

- `id`: mã duy nhất.
- `name`: người gửi hoặc người nhận.
- `bank`: tên ngân hàng hiển thị.
- `account`: tài khoản nhận.
- `source`: tài khoản nguồn.
- `amount`: giá trị giao dịch, số nguyên VNĐ.
- `note`: nội dung.
- `direction`: `in` (nhận vào) hoặc `out` (chuyển đi).
- `time`: thời gian ISO, ví dụ `2026-11-15T02:00:00.000Z`.
- `status`: giữ `success` cho giao dịch đã hoàn tất.
- `reviewStage`: `none` cho lịch sử bình thường.
- `scenario`: `normal` cho lịch sử bình thường.
- `fee`: phí minh họa, mặc định 0.

Lịch sử mẫu không được dùng để tính lại số dư khởi tạo. `customer.balance` là số dư hiện tại đã bao gồm lịch sử mẫu. Giao dịch mới sẽ trừ số dư một lần sau OTP đúng.

## 5. Chỉnh màu sắc và bố cục

Trong `mobile.css`:

- `:root`: màu nền, chữ và màu nhấn. Có phần ghi đè dành cho bản app độc lập ở cuối tệp; chỉnh phần này nếu muốn đổi màu cuối cùng.
- `.standalone-header`, `.standalone-studio`, `.standalone-footer`: khung trình diễn bên ngoài app.
- `.device`, `.phone`: frame điện thoại 390 × 844px và vỏ máy.
- `.balance-card`: thẻ số dư.
- `.phone-primary`, `.phone-secondary`: các nút chính và phụ.
- `.form-label`: trường nhập liệu.
- `.receipt`, `.info-row`: biên nhận và chi tiết giao dịch.
- `.notification-item`, `.soft-notice`: thông báo.
- `.bottom-nav`: điều hướng dưới.
- `.controls`, `.scenario`: bộ điều khiển demo bên ngoài điện thoại.
- `@media`: bố cục trên màn hình nhỏ.

Font Be Vietnam Pro lấy từ Google Fonts, có font sans-serif dự phòng nếu không có mạng. Icon là SVG nhúng trong JavaScript.

## 6. Chỉnh nội dung từng màn hình

Trong `mobile.js`, tìm:

- `home()`: trang chủ.
- `transfer()`: nhập chuyển tiền.
- `confirmScreen()`: kiểm tra giao dịch.
- `otpScreen()`: xác thực demo.
- `successScreen()`: kết quả thành công.
- `historyScreen()`, `detail()`: lịch sử và chi tiết.
- `notifications()`, `message()`: danh sách và nội dung thông báo.
- `protection()`: tình trạng bảo vệ tài khoản.
- `profile()`, `accounts()`, `support()`, `services()`: màn hình phụ.
- `controller()`: lựa chọn và điều khiển kịch bản.
- `render()`: khung tổng thể.

Trong `mobile-model.js`, `validate()` chứa quy tắc tài khoản và số tiền; `completeTransfer()` tạo giao dịch; `beginReview()` bắt đầu rà soát; `finishReview()` ghi nhận kết quả; `isRestricted()` kiểm tra hạn chế toàn tài khoản.

## 7. Dữ liệu đã lưu và cách áp dụng JSON mới

App lưu dữ liệu trong localStorage với key `aegis-mobile-standalone-v1`. Sau khi thay JSON, tải lại trang để nạp cấu hình mới, sau đó mở Kịch bản demo > Bắt đầu lại demo > xác nhận để áp dụng dữ liệu khởi tạo mới.

Hoặc mở DevTools > Console:

```js
localStorage.removeItem('aegis-mobile-standalone-v1');
location.reload();
```

Thao tác này xóa lịch sử phát sinh, số dư và thông báo của phiên demo đã lưu. Các tệp JSON và prototype Fraud Operations không bị sửa.

Nếu dùng nhiều bản app trên cùng localhost và cổng, chúng có thể dùng chung localStorage. Đổi hằng `KEY` trong `mobile.js` hoặc dùng cổng khác để tách từng bản demo.

## 8. Thử bốn kịch bản

Nhấn Kịch bản demo ở đầu trang. Chọn kịch bản trước khi chuyển tiền. Nhập thông tin → Tiếp tục → Xác nhận → OTP demo `123456` → Xác thực & hoàn tất → Về trang chủ.

- Bình thường: chỉ thông báo thành công, không rà soát.
- Rà soát sau giao dịch: thông báo bảo mật xuất hiện sau khi về trang chủ khoảng 1,3 giây. Chưa hạn chế chuyển tiền.
- Hoàn tất rà soát: sau bước rà soát, nhấn Hoàn tất rà soát · Không hạn chế trong bảng điều khiển.
- Bảo vệ tài khoản: sau bước rà soát, nhấn Hoàn tất rà soát & hạn chế chuyển tiền. Sau đó chuyển tiền mới bị chặn tại các lối vào; số dư và lịch sử vẫn xem được.

Đổi kịch bản không gỡ hạn chế đã áp dụng. Bắt đầu lại demo để mở phiên mới.

## 9. Phạm vi

Đây là prototype khách hàng độc lập, không kèm hệ thống Fraud Operations. Không có API ngân hàng, không đồng bộ hai giao diện, không gửi SMS, chuyển tiền, hoàn tiền, khóa tài khoản hoặc gọi tổng đài thật. Dữ liệu và quyết định đều mô phỏng. Giao dịch đã thành công luôn giữ trạng thái thành công dù có rà soát sau đó.

Đã kiểm tra logic và điều hướng bằng Node.js; chưa xác minh trực quan trên trình duyệt trong môi trường tạo gói.
