# Discord Weather Webhook 24/7 (34 Tỉnh Thành)

Hệ thống tự động dự báo thời tiết 34 tỉnh thành trọng điểm Việt Nam và cảnh báo bão khẩn cấp (GDACS) qua Discord Webhook, vận hành serverless 100% miễn phí bằng GitHub Actions.

---

## ⚡ Cơ chế vận hành
- **07:00 sáng hàng ngày (Giờ VN):** Tự động gửi bản tin thời tiết 34 tỉnh thành phân chia theo 3 miền & các tiểu vùng (Đồng bằng, Tây Bắc, Duyên Hải, Tây Nguyên, ĐBSCL).
- **Mỗi giờ (Phút thứ 17):** Tự động kiểm tra thời tiết bất thường (mưa mới xuất hiện, nắng nóng tăng cấp, gió mạnh $\ge$ cấp 6, bão nhiệt đới mới/tăng cấp). Nếu thời tiết bình thường sẽ giữ im lặng tuyệt đối để chống spam.
- **Cảnh báo bão khẩn cấp:** Quét trực tiếp từ hệ thống vệ tinh GDACS quốc tế. Khi có bão tiến vào Biển Đông sẽ gửi thẻ cảnh báo màu đỏ và tag `@everyone` (trừ khung giờ ngủ từ 23h - 06h).
