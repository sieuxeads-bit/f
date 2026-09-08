# Kokoro SRT Studio — native local app

App desktop local kiểu Piper: chọn model/voice/SRT và dựng WAV trực tiếp bằng ONNX Runtime, không cần browser và không cần Python hệ thống.

## Chạy nhanh trên Windows

Chỉ cần chạy:

```bat
START_PORTABLE.bat
```

Launcher sẽ dùng cache tại:

```text
%LOCALAPPDATA%\KokoroSRT
```

Không cần quyền admin. Runtime và model được tái sử dụng ở những lần chạy sau.

## GPU + tối ưu tốc độ

Bản hiện tại tự phát hiện backend:

- **NVIDIA**: cài `onnxruntime-gpu==1.26.0`, preload CUDA/cuDNN từ Python packages và ưu tiên `CUDAExecutionProvider`.
- **AMD / Intel Arc**: thử `onnxruntime-directml==1.24.4` và `DmlExecutionProvider`.
- **CPU fallback**: dùng `CPUExecutionProvider` với số thread theo CPU máy.

Model mặc định cũng đổi theo thiết bị:

- GPU: `kokoro-v1.0.fp16.onnx` (~169 MB)
- CPU: `kokoro-v1.0.int8.onnx` (~88 MB)
- Voices: `voices-v1.0.bin`

Nếu GPU runtime không khởi tạo được, launcher tự phục hồi ONNX Runtime CPU để app vẫn chạy.

Trong app có menu **Thiết bị**:

- `Auto (GPU ưu tiên)`
- `NVIDIA CUDA` nếu khả dụng
- `Windows DirectML` nếu khả dụng
- `CPU`

App hiển thị backend đang dùng và benchmark dạng `x realtime` sau khi dựng xong.

## Các tối ưu trong pipeline SRT

- ONNX session được tạo với graph optimization mức `ORT_ENABLE_ALL`.
- CPU dùng nhiều thread; GPU dùng provider chuyên dụng với CPU fallback cho node không hỗ trợ.
- Model/session được giữ trong RAM, không reload cho từng cue.
- Voice style được resolve một lần trước vòng lặp SRT.
- Audio từng cue được giữ thành chunk, sau đó cấp phát timeline **một lần ở cuối** thay vì liên tục mở rộng mảng.
- UI chỉ cập nhật trạng thái theo cụm cue để giảm overhead Tkinter trên SRT dài.
- Có nút **Dừng** để hủy sau cue hiện tại.

## GUI

GUI dùng dark desktop theme mới với:

- badge backend GPU/CPU
- card thống kê hiệu năng
- số cue + thời lượng subtitle
- progress rõ ràng
- chọn device/voice/language/speed
- log gọn và có nút xóa

## Cách ghép SRT

Mỗi cue được synthesize riêng. Audio bắt đầu tại timestamp của cue. Nếu câu trước chưa đọc xong, cue tiếp theo được dời tới sau câu trước để tránh chồng giọng. Vì vậy giọng không bị ép time-stretch làm méo tiếng.

## Model

App được thiết kế cho model Kokoro v1.0 từ `thewh1teagle/kokoro-onnx`:

- `kokoro-v1.0.int8.onnx`
- `kokoro-v1.0.fp16.onnx`
- `voices-v1.0.bin`

Repo Hugging Face `onnx-community/Kokoro-82M-v1.0-ONNX` dùng format voices riêng nên không phải drop-in replacement trực tiếp cho bundle `voices-v1.0.bin`.

## Dependency chính

```text
kokoro-onnx==0.5.0
numpy>=2.0.2
soundfile>=0.13.0
```

`kokoro-onnx` kéo phonemizer/eSpeak. `START_PORTABLE.bat` chịu trách nhiệm chuyển ONNX Runtime sang CUDA/DirectML khi máy có GPU phù hợp.
