# AEGIS — Mã nguồn prototype Fraud Operations

Gói mã nguồn HTML/CSS/JavaScript thuần của phiên bản có 54 giao dịch/hồ sơ mô phỏng, bao gồm 6 hồ sơ được phân công bổ sung. Không cần React, npm hay bước biên dịch.

## Chạy ứng dụng

1. Giải nén gói mã nguồn.
2. Mở terminal tại thư mục có `index.html`.
3. Chạy `python -m http.server 8080` (hoặc `python3 -m http.server 8080`).
4. Truy cập http://localhost:8080.

Có thể dùng Live Server trong VS Code. Nên chạy qua HTTP để hành vi lưu trữ trình duyệt nhất quán.

Tài khoản demo (mật khẩu chung `Demo@2026`):
- `supervisor`: Lê Hoàng Nam, người giám sát.
- `analyst`: Nguyễn Minh Anh, nhân viên phân tích.
- `analyst2`: Trần Quốc Bảo, nhân viên phân tích.

## Các tệp

- `index.html`: khung trang, liên kết CSS và JavaScript.
- `style.css`: toàn bộ giao diện, bố cục, màu, kiểu chữ, responsive.
- `app.js`: màn hình, dữ liệu khởi tạo, bộ lọc, phân quyền mô phỏng, chuyển trạng thái, Dashboard và lưu trữ.
- `data/cases.json`: bản xuất 54 giao dịch/hồ sơ với checklist, ghi chú và lịch sử mẫu.
- `data/dashboard.json`: cấu hình KPI và biểu đồ mặc định.
- `data/staff.json`: danh sách người phụ trách và vai trò.
- `data/statuses.json`: danh sách trạng thái; vị trí trong mảng chính là mã trạng thái.

Các JSON là bản xuất để tham khảo hoặc làm nguồn dữ liệu thay thế; ứng dụng hiện khởi tạo dữ liệu từ các hàm trong `app.js`, không tự đọc các tệp JSON này.

## Chỉnh giao diện

Trong `style.css`:
- `:root`: màu chữ, màu nền, màu nhấn, đường viền.
- `.sidebar`, `.header`, `.content`: bố cục chung.
- `.metrics`, `.metric`, `.charts`, `.card`: KPI và biểu đồ.
- `table`, `th`, `td`: bảng.
- `.workspace`, `.panel`, `.modal`: màn hình điều tra và biểu mẫu.
- `@media`: bố cục cho màn hình nhỏ.

Font Be Vietnam Pro tải từ Google Fonts; nếu không có Internet, trình duyệt dùng sans-serif dự phòng.

Trong `app.js`:
- `navItems`: mục điều hướng.
- `overview()`, `workOverview()`: hai tab Tổng quan.
- `listView()`, `table()`: danh sách và bảng.
- `workspace()`: không gian điều tra.
- `login()`: trang đăng nhập.
- `panelEditAgain()`: bộ chỉnh sửa Dashboard.
- `heading()`: tiêu đề trang dùng chung.

## Chỉnh dữ liệu mặc định

- `baseSeeds()`: 48 hồ sơ ban đầu.
- `assignedCases()`: 6 hồ sơ bổ sung, chia đều cho `sup`, `an`, `bao`.
- `seeds()`: ghép hai nhóm thành 54 hồ sơ.
- `defaultDash()`: KPI, chuỗi thời gian, cơ cấu giao dịch.
- `names`, `types`, `statuses`: nhân sự, loại giao dịch và trạng thái.

Khi tạo thêm hồ sơ, cần mã hồ sơ, cảnh báo và giao dịch duy nhất; owner phải khớp mã nhân sự; số tiền, số dư, thời gian và lịch sử phải hợp lý.

Mã trạng thái:
0. Chờ tiếp nhận.
1. Đang điều tra.
2. Chờ bổ sung thông tin.
3. Chờ người giám sát.
4. Đã xác nhận hợp lệ (kết thúc).
5. Đã xác nhận gian lận (kết thúc).

## Vì sao sửa dữ liệu trong code nhưng chưa thấy thay đổi?

Ứng dụng ưu tiên dữ liệu đã lưu trong localStorage:
- `aegis-data-v1`: hồ sơ, giao dịch, ghi chú và lịch sử.
- `aegis-dash-v1`: cấu hình Dashboard đã lưu.
- `aegis-user`: tài khoản demo hiện tại.

Sau khi sửa dữ liệu khởi tạo, dùng chức năng khôi phục tương ứng bằng tài khoản Supervisor. Hoặc mở DevTools > Console và chạy lệnh phù hợp:

```js
// Xóa dữ liệu nghiệp vụ cục bộ; thao tác này làm mất tiến độ demo đã lưu.
localStorage.removeItem('aegis-data-v1');
location.reload();
```

```js
// Xóa cấu hình Dashboard cục bộ.
localStorage.removeItem('aegis-dash-v1');
location.reload();
```

## Dùng các tệp JSON làm dữ liệu khởi tạo

Nếu muốn sửa JSON thay vì các hàm tạo mẫu, có thể thay thẻ script hiện tại trong index.html bằng:

```html
<script>
(async () => {
  try {
    for (const [key, path] of [
      ['aegis-data-v1', 'data/cases.json'],
      ['aegis-dash-v1', 'data/dashboard.json']
    ]) {
      if (!localStorage.getItem(key)) {
        const response = await fetch(path);
        if (!response.ok) throw new Error('Không đọc được ' + path);
        localStorage.setItem(key, JSON.stringify(await response.json()));
      }
    }
    const script = document.createElement('script');
    script.src = 'app.js';
    document.body.appendChild(script);
  } catch (error) {
    document.body.textContent = 'Không thể khởi tạo dữ liệu: ' + error.message;
  }
})();
</script>
```

Chạy qua HTTP. Dữ liệu JSON chỉ được nạp khi chưa có localStorage. Sáu mã hồ sơ bổ sung vẫn được app.js kiểm tra và thêm nếu thiếu. Nút khôi phục vẫn dùng các hàm mặc định trong app.js; muốn khôi phục về JSON cần điều chỉnh `resetBusiness()` và `resetDashboard()` tương ứng. `staff.json` và `statuses.json` là tài liệu tham khảo, không được đoạn nạp trên sử dụng.

## Phạm vi và giới hạn

- Toàn bộ dữ liệu khách hàng, giao dịch, điểm rủi ro, bằng chứng và kết luận đều mô phỏng.
- Đăng nhập và phân quyền kiểm tra bằng JavaScript phía trình duyệt, phục vụ demo; không phải bảo mật cho môi trường thật.
- Không có backend, cơ sở dữ liệu máy chủ hay đồng bộ giữa người dùng. Mỗi trình duyệt/origin có dữ liệu riêng.
- KPI trình bày thủ công độc lập với hồ sơ; tab Tổng quan công việc tính trực tiếp từ hồ sơ.
- Các thao tác không liên hệ khách hàng, không chuyển tiền và không khóa tài khoản thật.
- Đã kiểm tra logic luồng chính; chưa kiểm tra trực quan trên trình duyệt trong môi trường tạo ứng dụng.
