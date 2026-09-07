# Kokoro SRT Voice Local

Ứng dụng Vite + React chạy Kokoro TTS trực tiếp trong trình duyệt để đọc file `.srt`, ghép voice theo timestamp và xuất một file WAV.

## Model

- Hugging Face: `onnx-community/Kokoro-82M-v1.0-ONNX`
- Runtime: `kokoro-js` / Transformers.js
- Chạy local bằng WASM hoặc WebGPU
- Mặc định dùng `q8` + `wasm` để tương thích tốt; máy hỗ trợ WebGPU có thể chọn `webgpu` + `fp32`.

## Chạy local

Yêu cầu Node.js 18+.

```bash
npm install
npm run dev
```

Mở địa chỉ Vite hiển thị trong terminal (mặc định `http://localhost:3000`).

## Cách dùng

1. Chọn file `.srt` hoặc dán nội dung SRT.
2. Chọn voice, device, dtype và tốc độ.
3. Bấm **Tải / cache model**. Lần đầu cần Internet để tải model từ Hugging Face.
4. Bấm **Tạo voice theo SRT**.
5. Nghe thử hoặc tải `kokoro-srt-voice.wav`.

## Cách đồng bộ timeline

Mỗi subtitle được tổng hợp riêng. Audio được đặt tại timestamp bắt đầu của cue. Nếu audio dài hơn khoảng thời gian của subtitle, app resample đoạn đó để fit vào slot; nếu ngắn hơn, app giữ nguyên và phần còn lại là silence.

## Offline

Inference diễn ra local trong browser. Sau khi model đã được browser cache, app có thể hoạt động không cần gửi nội dung SRT lên API. Việc cache có được giữ lâu hay không phụ thuộc chính sách lưu trữ của trình duyệt.

## Ngôn ngữ

Kokoro v1.0 không tối ưu cho mọi ngôn ngữ. Chất lượng phát âm phụ thuộc language/voice mà model hỗ trợ; file SRT tiếng Việt vẫn có thể được đưa vào nhưng không nên kỳ vọng phát âm tiếng Việt chuẩn nếu model/voice không hỗ trợ trực tiếp.
