import React, { useMemo, useRef, useState } from 'react';
import { KokoroTTS } from 'kokoro-js';

type Cue = { index: number; start: number; end: number; text: string };
type Device = 'wasm' | 'webgpu';
type DType = 'q8' | 'fp32' | 'fp16' | 'q4' | 'q4f16';

const MODEL_ID = 'onnx-community/Kokoro-82M-v1.0-ONNX';
const SAMPLE_RATE = 24000;
const VOICES = [
  'af_heart','af_bella','af_nicole','af_sarah','af_sky',
  'am_adam','am_michael','bf_emma','bf_isabella','bm_george','bm_lewis',
  'ef_dora','em_alex','em_santa','ff_siwis','hf_alpha','hf_beta','hm_omega','hm_psi',
  'if_sara','im_nicola','jf_alpha','jf_gongitsune','jf_nezumi','jf_tebukuro','jm_kumo',
  'pf_dora','pm_alex','pm_santa','zf_xiaobei','zf_xiaoni','zf_xiaoxiao','zf_xiaoyi',
  'zm_yunjian','zm_yunxi','zm_yunxia','zm_yunyang'
];

function parseTime(v: string) {
  const [h, m, rest] = v.trim().replace('.', ',').split(':');
  const [s, ms = '0'] = rest.split(',');
  return Number(h) * 3600 + Number(m) * 60 + Number(s) + Number(ms.padEnd(3, '0').slice(0, 3)) / 1000;
}

function parseSrt(input: string): Cue[] {
  const normalized = input.replace(/\r/g, '').trim();
  if (!normalized) return [];
  return normalized.split(/\n{2,}/).map((block, i) => {
    const lines = block.split('\n');
    const hasIndex = /^\d+$/.test(lines[0]?.trim() ?? '');
    const timeLine = lines[hasIndex ? 1 : 0] ?? '';
    const match = timeLine.match(/(\d{2}:\d{2}:\d{2}[,.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,.]\d{3})/);
    if (!match) return null;
    const text = lines.slice(hasIndex ? 2 : 1).join(' ').replace(/<[^>]+>/g, '').trim();
    return { index: hasIndex ? Number(lines[0]) : i + 1, start: parseTime(match[1]), end: parseTime(match[2]), text };
  }).filter(Boolean) as Cue[];
}

function resampleLinear(input: Float32Array, targetLength: number) {
  if (targetLength <= 0) return new Float32Array();
  if (input.length === targetLength) return input;
  const out = new Float32Array(targetLength);
  const ratio = (input.length - 1) / Math.max(1, targetLength - 1);
  for (let i = 0; i < targetLength; i++) {
    const pos = i * ratio;
    const left = Math.floor(pos);
    const right = Math.min(input.length - 1, left + 1);
    const frac = pos - left;
    out[i] = input[left] * (1 - frac) + input[right] * frac;
  }
  return out;
}

function encodeWav(samples: Float32Array, sampleRate = SAMPLE_RATE) {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);
  const write = (offset: number, value: string) => [...value].forEach((c, i) => view.setUint8(offset + i, c.charCodeAt(0)));
  write(0, 'RIFF');
  view.setUint32(4, 36 + samples.length * 2, true);
  write(8, 'WAVE'); write(12, 'fmt ');
  view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true); view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true); view.setUint16(34, 16, true);
  write(36, 'data'); view.setUint32(40, samples.length * 2, true);
  let offset = 44;
  for (const sample of samples) {
    const s = Math.max(-1, Math.min(1, sample));
    view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true);
    offset += 2;
  }
  return new Blob([buffer], { type: 'audio/wav' });
}

export default function App() {
  const [srtText, setSrtText] = useState('');
  const cues = useMemo(() => parseSrt(srtText), [srtText]);
  const [voice, setVoice] = useState('af_heart');
  const [device, setDevice] = useState<Device>('wasm');
  const [dtype, setDtype] = useState<DType>('q8');
  const [speed, setSpeed] = useState(1);
  const [status, setStatus] = useState('Chưa tải model');
  const [progress, setProgress] = useState(0);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const ttsRef = useRef<any>(null);

  const onFile = async (file?: File) => {
    if (!file) return;
    setSrtText(await file.text());
    setStatus(`Đã mở ${file.name}`);
  };

  const loadModel = async () => {
    setBusy(true); setStatus('Đang tải Kokoro ONNX...'); setProgress(0);
    try {
      ttsRef.current = await KokoroTTS.from_pretrained(MODEL_ID, {
        device,
        dtype,
        progress_callback: (p: any) => {
          if (typeof p?.progress === 'number') setProgress(Math.round(p.progress));
          if (p?.file) setStatus(`Đang tải: ${p.file}`);
        }
      } as any);
      setProgress(100); setStatus('Model sẵn sàng. Lần sau trình duyệt sẽ dùng cache nếu còn dữ liệu.');
    } catch (e: any) {
      setStatus(`Lỗi tải model: ${e?.message ?? e}`);
      throw e;
    } finally { setBusy(false); }
  };

  const generate = async () => {
    if (!cues.length) return setStatus('Hãy nạp file SRT hợp lệ trước.');
    setBusy(true); setProgress(0);
    try {
      if (!ttsRef.current) await loadModel();
      const totalSeconds = Math.max(...cues.map(c => c.end)) + 0.25;
      const timeline = new Float32Array(Math.ceil(totalSeconds * SAMPLE_RATE));

      for (let i = 0; i < cues.length; i++) {
        const cue = cues[i];
        setStatus(`Đang tạo câu ${i + 1}/${cues.length}: ${cue.text.slice(0, 60)}`);
        const raw: any = await ttsRef.current.generate(cue.text, { voice, speed });
        const source = raw.audio as Float32Array;
        const srcRate = Number(raw.sampling_rate || SAMPLE_RATE);
        const duration = Math.max(0.05, cue.end - cue.start);
        const slotSamples = Math.max(1, Math.floor(duration * SAMPLE_RATE));
        let normalized = source;
        if (srcRate !== SAMPLE_RATE) {
          normalized = resampleLinear(source, Math.round(source.length * SAMPLE_RATE / srcRate));
        }
        // Nếu câu dài hơn ô subtitle, co theo timeline. Nếu ngắn hơn, giữ tốc độ tự nhiên.
        if (normalized.length > slotSamples) normalized = resampleLinear(normalized, slotSamples);
        const startSample = Math.max(0, Math.floor(cue.start * SAMPLE_RATE));
        const maxCopy = Math.min(normalized.length, timeline.length - startSample);
        for (let j = 0; j < maxCopy; j++) {
          timeline[startSample + j] = Math.max(-1, Math.min(1, timeline[startSample + j] + normalized[j]));
        }
        setProgress(Math.round(((i + 1) / cues.length) * 100));
      }

      const blob = encodeWav(timeline);
      if (audioUrl) URL.revokeObjectURL(audioUrl);
      const url = URL.createObjectURL(blob);
      setAudioUrl(url);
      setStatus(`Hoàn tất ${cues.length} câu — WAV ${Math.round(blob.size / 1024 / 1024 * 10) / 10} MB`);
    } catch (e: any) {
      setStatus(`Lỗi: ${e?.message ?? e}`);
    } finally { setBusy(false); }
  };

  const download = () => {
    if (!audioUrl) return;
    const a = document.createElement('a'); a.href = audioUrl; a.download = 'kokoro-srt-voice.wav'; a.click();
  };

  return <main style={styles.page}>
    <section style={styles.card}>
      <div style={styles.header}>
        <div>
          <div style={styles.badge}>LOCAL • ONNX</div>
          <h1 style={styles.h1}>Kokoro SRT Voice</h1>
          <p style={styles.sub}>Đọc file .srt bằng Kokoro-82M v1.0 ngay trên máy, ghép voice đúng timeline và xuất WAV.</p>
        </div>
      </div>

      <div style={styles.grid}>
        <label style={styles.drop}>
          <strong>1. Chọn file SRT</strong>
          <span style={styles.muted}>Kéo thả hoặc bấm để chọn</span>
          <input type="file" accept=".srt,text/plain" hidden onChange={e => onFile(e.target.files?.[0])} />
        </label>
        <div style={styles.panel}>
          <strong>2. Thiết lập model</strong>
          <label style={styles.label}>Voice<select style={styles.input} value={voice} onChange={e => setVoice(e.target.value)}>{VOICES.map(v => <option key={v}>{v}</option>)}</select></label>
          <label style={styles.label}>Device<select style={styles.input} value={device} onChange={e => setDevice(e.target.value as Device)}><option value="wasm">WASM — tương thích</option><option value="webgpu">WebGPU — nhanh hơn</option></select></label>
          <label style={styles.label}>Model dtype<select style={styles.input} value={dtype} onChange={e => setDtype(e.target.value as DType)}><option>q8</option><option>fp32</option><option>fp16</option><option>q4</option><option>q4f16</option></select></label>
          <label style={styles.label}>Speed: {speed.toFixed(2)}x<input type="range" min="0.7" max="1.3" step="0.05" value={speed} onChange={e => setSpeed(Number(e.target.value))} /></label>
        </div>
      </div>

      <textarea style={styles.textarea} value={srtText} onChange={e => setSrtText(e.target.value)} placeholder={'1\n00:00:01,000 --> 00:00:03,000\nHello world...'} />
      <div style={styles.stats}><span>{cues.length} câu</span><span>{cues.length ? `${cues[cues.length - 1].end.toFixed(1)} giây` : '0 giây'}</span><span>{MODEL_ID}</span></div>

      <div style={styles.actions}>
        <button style={styles.secondary} disabled={busy} onClick={loadModel}>Tải / cache model</button>
        <button style={styles.primary} disabled={busy || !cues.length} onClick={generate}>{busy ? 'Đang xử lý…' : 'Tạo voice theo SRT'}</button>
        <button style={styles.secondary} disabled={!audioUrl} onClick={download}>Tải WAV</button>
      </div>
      <div style={styles.progress}><div style={{...styles.bar, width: `${progress}%`}} /></div>
      <div style={styles.status}>{status}</div>
      {audioUrl && <audio style={{width:'100%', marginTop:16}} controls src={audioUrl} />}

      <details style={{marginTop:18}}><summary>Lưu ý</summary><p style={styles.muted}>Kokoro v1.0 không tối ưu cho mọi ngôn ngữ. App vẫn đọc nội dung SRT, nhưng phát âm phụ thuộc ngôn ngữ/voice mà model hỗ trợ. Muốn chạy offline hoàn toàn, hãy mở app một lần có mạng để trình duyệt tải và cache model.</p></details>
    </section>
  </main>;
}

const styles: Record<string, React.CSSProperties> = {
  page:{minHeight:'100vh',background:'#0b1020',color:'#e5e7eb',padding:'36px 18px',fontFamily:'Inter, ui-sans-serif, system-ui, sans-serif'},
  card:{maxWidth:1100,margin:'0 auto',background:'#121a2d',border:'1px solid #26324b',borderRadius:22,padding:28,boxShadow:'0 24px 80px rgba(0,0,0,.35)'},
  header:{display:'flex',justifyContent:'space-between',gap:20,alignItems:'center'},
  badge:{display:'inline-block',fontSize:12,fontWeight:800,letterSpacing:1.3,color:'#86efac',background:'#163522',border:'1px solid #246638',padding:'6px 10px',borderRadius:999},
  h1:{fontSize:38,margin:'12px 0 6px'},sub:{color:'#9ca3af',margin:0,maxWidth:720,lineHeight:1.55},
  grid:{display:'grid',gridTemplateColumns:'1.1fr 1fr',gap:18,marginTop:24},
  drop:{minHeight:230,border:'1.5px dashed #475569',borderRadius:16,display:'flex',flexDirection:'column',alignItems:'center',justifyContent:'center',cursor:'pointer',background:'#0d1526',gap:8},
  panel:{background:'#0d1526',border:'1px solid #26324b',borderRadius:16,padding:18,display:'grid',gap:12},
  label:{display:'grid',gap:6,fontSize:13,color:'#cbd5e1'},input:{background:'#111827',color:'#e5e7eb',border:'1px solid #334155',borderRadius:10,padding:'10px 12px'},
  textarea:{width:'100%',boxSizing:'border-box',height:260,marginTop:18,background:'#080d18',color:'#e5e7eb',border:'1px solid #26324b',borderRadius:14,padding:16,fontFamily:'ui-monospace, SFMono-Regular, Menlo, monospace',lineHeight:1.5,resize:'vertical'},
  stats:{display:'flex',gap:14,flexWrap:'wrap',marginTop:10,color:'#94a3b8',fontSize:12},actions:{display:'flex',gap:10,flexWrap:'wrap',marginTop:20},
  primary:{background:'#22c55e',color:'#052e16',fontWeight:800,border:0,borderRadius:11,padding:'12px 18px',cursor:'pointer'},
  secondary:{background:'#1e293b',color:'#e2e8f0',fontWeight:700,border:'1px solid #334155',borderRadius:11,padding:'12px 18px',cursor:'pointer'},
  progress:{height:9,background:'#0b1220',borderRadius:999,overflow:'hidden',marginTop:18,border:'1px solid #26324b'},bar:{height:'100%',background:'#22c55e',transition:'width .2s ease'},
  status:{marginTop:9,color:'#cbd5e1',fontSize:13},muted:{color:'#94a3b8',lineHeight:1.55}
};
