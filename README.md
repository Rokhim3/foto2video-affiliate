# Foto Produk → Video Affiliate (15s)

Streamlit app: upload foto produk → otomatis jadi video vertikal 9:16 dengan
efek zoom/pan, caption, dan voiceover TTS.

## Cara jalankan lokal
```
pip install -r requirements.txt
streamlit run app.py
```
(butuh ffmpeg & imagemagick terinstall di komputer/HP kalau pakai Termux)

## Cara deploy ke Streamlit Community Cloud (sama seperti tool kamu sebelumnya)
1. Push folder ini ke GitHub (repo baru, akun Rokhim3)
2. Buka share.streamlit.io → New app → pilih repo ini, main file `app.py`
3. File `packages.txt` otomatis dibaca Streamlit Cloud untuk install ffmpeg
   & imagemagick — WAJIB ada, jangan dihapus
4. Deploy, tunggu build selesai

## Ide pengembangan lanjutan
- Sambungkan ke Anthropic/Gemini API supaya caption & hook di-generate otomatis
  dari nama produk (bukan ditulis manual)
- Ganti TTS gratis (gTTS) dengan suara yang lebih natural (ElevenLabs, perlu API key)
- Tambah pilihan transisi antar klip (fade, slide)
- Kalau mau upgrade ke gerakan produk yang lebih "hidup" (bukan cuma zoom/pan),
  next step-nya sambungkan ke API image-to-video seperti Kling AI atau Seedance —
  tapi itu berbayar per generate
