# Kokoro SRT Local — native app

Bản này **không chạy bằng web**. Đây là app desktop Python/Tkinter dùng ONNX Runtime local, theo kiểu Piper:

- chọn file `kokoro-v1.0.onnx`
- chọn file `voices-v1.0.bin`
- chọn file subtitle `.srt`
- chọn voice + speed
- tạo từng câu theo timestamp SRT
- ghép toàn bộ thành một file WAV

## Model nên dùng

App được thiết kế cho cặp file Kokoro v1.0 của `thewh1teagle/kokoro-onnx`:

- `kokoro-v1.0.onnx`
- `voices-v1.0.bin`

Repo `onnx-community/Kokoro-82M-v1.0-ONNX` trên Hugging Face đóng gói model/voice khác một chút: nhiều file voice `.bin` riêng. Để có trải nghiệm giống Piper nhất, dùng cặp model + voices ở trên.

## Windows — cách chạy nhanh

Yêu cầu: Python 3.12 x64.

1. Chạy `download_models_windows.bat` để tải model vào thư mục `models`.
2. Chạy `run_windows.bat`.
3. Trong app chọn:
   - Model: `models/kokoro-v1.0.onnx`
   - Voices: `models/voices-v1.0.bin`
   - SRT: file subtitle của bạn
   - Output: file WAV muốn lưu
4. Bấm **Nạp voices** rồi chọn voice.
5. Bấm **Tạo voice từ SRT**.

Lần đầu `run_windows.bat` sẽ tự tạo `.venv` và cài dependency. Các lần sau vẫn chạy local; không cần browser.

## Build file EXE

Chạy:

```bat
build_windows_exe.bat
```

Nếu build thành công, file nằm ở:

```text
dist\KokoroSRT.exe
```

Sau đó có thể đặt cạnh thư mục model và chạy như app desktop.

## Cách ghép SRT

Mỗi subtitle cue được synthesize riêng. Audio được đặt vào đúng thời điểm bắt đầu của cue. Nếu bật **Fit câu dài vào đúng ô thời gian SRT**, câu dài hơn slot subtitle sẽ được co lại để tránh đè quá nhiều sang cue tiếp theo.

## Ngôn ngữ

`kokoro-onnx` dùng phonemizer/eSpeak cho G2P. Trường Language mặc định là `en-us`. Kokoro v1.0 gốc mạnh nhất ở các ngôn ngữ/voice mà model hỗ trợ; chất lượng tiếng Việt không nên kỳ vọng như một model TTS được huấn luyện riêng cho tiếng Việt.

## Dependency chính

- `kokoro-onnx==0.5.0`
- `onnxruntime`
- `espeakng-loader`
- `phonemizer-fork`
- `numpy`
- `soundfile`

`kokoro-onnx` tự kéo các dependency ONNX Runtime / eSpeak cần thiết.
