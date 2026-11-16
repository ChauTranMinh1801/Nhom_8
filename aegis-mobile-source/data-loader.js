// Đọc dữ liệu JSON trước khi khởi động app. Chạy qua HTTP/Live Server.
(async function () {
  const root = document.getElementById('mobile-app');
  root.innerHTML = '<p style="padding:30px;text-align:center">Đang tải dữ liệu mô phỏng…</p>';
  try {
    async function readJSON(path) {
      const response = await fetch(path, { cache: 'no-store' });
      if (!response.ok) throw new Error('Không đọc được ' + path);
      return response.json();
    }
    const [config, transactions] = await Promise.all([
      readJSON('data/config.json'), readJSON('data/transactions.json')
    ]);
    if (!config.customer || !Array.isArray(config.banks) || !Array.isArray(config.scenarios) || !config.messages || !Array.isArray(transactions)) {
      throw new Error('Cấu trúc dữ liệu JSON không hợp lệ.');
    }
    window.AEGIS_MOBILE_DATA = { ...config, transactions };
    for (const file of ['mobile-model.js', 'mobile.js']) {
      await new Promise((resolve, reject) => {
        const script = document.createElement('script');
        script.src = file;
        script.onload = resolve;
        script.onerror = () => reject(new Error('Không tải được ' + file));
        document.body.appendChild(script);
      });
    }
  } catch (error) {
    root.innerHTML = '';
    const notice = document.createElement('p');
    notice.style.cssText = 'padding:30px;max-width:600px;margin:auto;line-height:1.8';
    notice.textContent = 'Không thể mở ứng dụng: ' + error.message + '. Hãy chạy qua http://localhost:8080 và kiểm tra cú pháp JSON.';
    root.appendChild(notice);
  }
})();
