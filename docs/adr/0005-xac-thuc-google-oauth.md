# ADR-0005: Xác thực Google do backend quản lý, phiên bằng cookie

- **Trạng thái:** Chấp nhận
- **Ngày:** 2026-10-18
- **Thay đổi:** Thay thế PRD mục 5.2 (Auth.js + gửi `id_token` mỗi request)

## Bối cảnh
PRD yêu cầu đăng nhập bằng Gmail. Bản PRD đề xuất frontend dùng Auth.js lấy `id_token` của Google rồi gửi kèm mỗi request. Cách này có vấn đề:
- `id_token` của Google hết hạn sau ~1 giờ; Auth.js không tự làm mới, người dùng bị lỗi 401 giữa chừng.
- Logic xác thực bị chia đôi giữa Node và Python.
- Token lưu phía JavaScript dễ bị đánh cắp nếu có lỗi XSS.

## Các phương án
1. **Auth.js + id_token mỗi request** (theo PRD) – vấn đề như trên.
2. **Auth.js + đổi id_token lấy JWT do backend phát hành** – khắc phục hết hạn nhưng vẫn hai hệ thống xác thực.
3. **Backend thực hiện OAuth Authorization Code flow, phát hành cookie phiên HTTP-only** – toàn bộ xác thực nằm ở Python.

## Quyết định
Chọn **phương án 3**, dùng thư viện **Authlib** cho FastAPI.

### Luồng
```
Người dùng bấm "Đăng nhập với Google"
  → GET /api/auth/google/login
      backend tạo state + PKCE, redirect tới Google
  → Google xác thực, redirect về /api/auth/google/callback?code=...
      backend đổi code lấy token, xác minh id_token (chữ ký, aud, iss, exp)
      kiểm tra email_verified = true
      upsert users theo google_id (sub)
      tạo bản ghi sessions, set cookie
  → redirect về /library
```

### Phiên
- Bảng `sessions(id, user_id, token_hash, expires_at, created_at)`; cookie chứa token ngẫu nhiên 32 byte, DB lưu SHA-256 của token.
- Cookie `sid`: `HttpOnly`, `Secure`, `SameSite=Lax`, `Path=/`.
- Hết hạn sau 7 ngày; mỗi request hợp lệ gia hạn nếu còn dưới 3 ngày (sliding).
- `POST /api/auth/logout` xoá bản ghi phiên và cookie.
- Scope Google: `openid email profile`. Không lưu access/refresh token của Google vì không gọi API Google nào khác.

### Bảo vệ CSRF
Frontend và API cùng domain (ADR-0014) + `SameSite=Lax` chặn phần lớn CSRF. Bổ sung: mọi request thay đổi dữ liệu (POST/PATCH/DELETE) phải có header `X-Requested-With: fetch`, backend từ chối nếu thiếu.

## Hệ quả
- **Tích cực:** Không có token trong JavaScript; không có lỗi hết hạn token Google; một nơi duy nhất xử lý xác thực; dễ thu hồi phiên.
- **Tiêu cực:** Phải truy vấn bảng `sessions` mỗi request (rẻ, có index; có thể cache Redis nếu cần); bắt buộc chạy cùng domain qua reverse proxy.

## Ghi chú triển khai
- Biến môi trường: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `OAUTH_REDIRECT_URI`, `SESSION_SECRET`.
- Trên Google Cloud Console thêm redirect URI `https://<domain>/api/auth/google/callback` (và `http://localhost/api/auth/google/callback` cho dev).
- Frontend kiểm tra đăng nhập bằng `GET /api/me`; 401 → chuyển về `/`.
- Cần cập nhật PRD mục 5.1 (bỏ Auth.js) và 5.2.
