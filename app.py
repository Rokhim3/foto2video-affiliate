"""
Foto Produk -> Video Affiliate (±15 detik)
Streamlit app: upload foto produk, tambahkan caption + voiceover,
otomatis dibuatkan video dengan efek zoom/pan (Ken Burns), lalu di-export
dalam format vertikal 9:16 siap upload ke Reels/TikTok/Shorts.
"""

import streamlit as st
import tempfile
import os
import numpy as np
from gtts import gTTS
from PIL import Image, ImageDraw, ImageFont

# --- Patch kompatibilitas: moviepy 1.0.3 masih memanggil Image.ANTIALIAS,
# yang sudah dihapus di Pillow versi baru. Ganti dengan LANCZOS (setara).
if not hasattr(Image, "ANTIALIAS"):
    Image.ANTIALIAS = Image.LANCZOS

from moviepy.editor import (
    ImageClip, CompositeVideoClip, AudioFileClip,
    concatenate_videoclips, vfx
)

st.set_page_config(page_title="Foto ke Video Affiliate", page_icon="🎬", layout="centered")
st.title("🎬 Foto Produk → Video Affiliate (15s)")
st.caption("Upload foto produk, isi caption, langsung jadi video vertikal siap posting.")

VIDEO_W, VIDEO_H = 720, 1280  # format 9:16, resolusi diperkecil biar ringan di server gratis

# ---------- INPUT ----------
uploaded_files = st.file_uploader(
    "Upload foto produk (bisa lebih dari 1, urutan = urutan tampil)",
    type=["jpg", "jpeg", "png"], accept_multiple_files=True
)

product_name = st.text_input("Nama produk", placeholder="Contoh: Lampu Bulan Mini")

benefit_points = st.text_area(
    "Poin-poin script (satu baris = satu klip/caption, MAKSIMAL 6 baris)",
    placeholder=(
        "Bikin kamar kamu estetik banget!\n"
        "Bisa nyala 16 warna beda\n"
        "Klik keranjang kuning sekarang!"
    ),
    height=120,
)

col1, col2 = st.columns(2)
with col1:
    total_duration = st.slider("Durasi total video (detik)", 10, 20, 15)
with col2:
    add_voiceover = st.checkbox("Tambahkan voiceover otomatis (TTS)", value=True)

music_file = st.file_uploader("Musik latar (opsional, mp3)", type=["mp3"])

generate = st.button("🚀 Generate Video", type="primary", use_container_width=True)

# ---------- HELPERS ----------
def ken_burns_clip(img_path, duration, zoom_in=True):
    """Buat efek zoom/pan sederhana dari 1 foto statis."""
    clip = ImageClip(img_path).set_duration(duration)
    clip = clip.resize(height=VIDEO_H * 1.15)  # sedikit oversize buat ruang zoom/pan
    w, h = clip.size
    # crop tengah supaya rasio 9:16 pas
    x_center = w / 2
    clip = clip.crop(x1=x_center - VIDEO_W / 2 * 1.15, x2=x_center + VIDEO_W / 2 * 1.15)

    if zoom_in:
        clip = clip.fx(vfx.resize, lambda t: 1 + 0.06 * (t / duration))
    else:
        clip = clip.fx(vfx.resize, lambda t: 1.06 - 0.06 * (t / duration))

    clip = clip.set_position("center")
    return clip


FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]


def _load_font(size):
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def make_caption(text, duration, video_w=VIDEO_W, font_size=64):
    """Render caption jadi gambar PNG transparan pakai PIL (tidak butuh ImageMagick),
    lalu dibungkus jadi ImageClip dengan alpha channel sebagai mask otomatis."""
    font = _load_font(font_size)
    max_width = int(video_w * 0.85)

    dummy = Image.new("RGBA", (10, 10))
    draw = ImageDraw.Draw(dummy)

    # word-wrap manual berdasarkan lebar teks
    words = text.split()
    lines, current = [], ""
    for word in words:
        test = (current + " " + word).strip()
        bbox = draw.textbbox((0, 0), test, font=font, stroke_width=3)
        if bbox[2] - bbox[0] <= max_width or not current:
            current = test
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)

    line_height = font_size + 24
    img_h = line_height * len(lines) + 40
    img = Image.new("RGBA", (video_w, img_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    y = 20
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font, stroke_width=3)
        w = bbox[2] - bbox[0]
        x = (video_w - w) / 2
        draw.text((x, y), line, font=font, fill="white", stroke_width=3, stroke_fill="black")
        y += line_height

    arr = np.array(img)  # RGBA -> moviepy otomatis pakai channel alpha sebagai mask
    clip = ImageClip(arr).set_duration(duration).set_position(("center", "bottom")).margin(bottom=180, opacity=0)
    return clip


def make_voiceover(text, out_path, lang="id"):
    tts = gTTS(text=text, lang=lang)
    tts.save(out_path)


MAX_CLIPS = 6

# ---------- MAIN PIPELINE ----------
if generate:
    if not uploaded_files:
        st.error("Upload minimal 1 foto produk dulu ya.")
        st.stop()

    lines = [l.strip() for l in benefit_points.split("\n") if l.strip()]
    if not lines:
        lines = [product_name or "Produk keren ini wajib kamu punya!"]

    n_clips = min(max(len(uploaded_files), len(lines)), MAX_CLIPS)
    if max(len(uploaded_files), len(lines)) > MAX_CLIPS:
        st.warning(f"Dibatasi maksimal {MAX_CLIPS} klip biar server gratis tidak kehabisan memori. Kelebihan baris/foto akan diabaikan.")

    # ulang foto/baris kalau jumlahnya beda supaya sinkron
    photos = [uploaded_files[i % len(uploaded_files)] for i in range(n_clips)]
    captions = [lines[i % len(lines)] for i in range(n_clips)]
    per_clip_duration = total_duration / n_clips

    with st.status("Membuat video...", expanded=True) as status:
        tmpdir = tempfile.mkdtemp()
        final_clips = []

        for i, (photo, caption) in enumerate(zip(photos, captions)):
            status.update(label=f"Memproses klip {i+1}/{n_clips}...")
            img_path = os.path.join(tmpdir, f"img_{i}.png")
            Image.open(photo).convert("RGB").save(img_path)

            base = ken_burns_clip(img_path, per_clip_duration, zoom_in=(i % 2 == 0))
            caption_clip = make_caption(caption, per_clip_duration)
            combined = CompositeVideoClip([base, caption_clip], size=(VIDEO_W, VIDEO_H))
            final_clips.append(combined)

        status.update(label="Menggabungkan klip...")
        video = concatenate_videoclips(final_clips, method="compose")

        # voiceover
        if add_voiceover:
            status.update(label="Membuat voiceover...")
            vo_path = os.path.join(tmpdir, "voiceover.mp3")
            make_voiceover(". ".join(captions), vo_path)
            vo_audio = AudioFileClip(vo_path)
            if vo_audio.duration > video.duration:
                vo_audio = vo_audio.subclip(0, video.duration)
            video = video.set_audio(vo_audio)

        # musik latar (opsional, dicampur pelan di bawah voiceover)
        if music_file:
            status.update(label="Menambahkan musik latar...")
            music_path = os.path.join(tmpdir, "music.mp3")
            with open(music_path, "wb") as f:
                f.write(music_file.read())
            # NOTE: untuk mixing voiceover + musik sekaligus, perlu CompositeAudioClip.
            # Versi sederhana ini pakai musik HANYA kalau voiceover dimatikan.
            if not add_voiceover:
                music_audio = AudioFileClip(music_path).subclip(0, video.duration)
                video = video.set_audio(music_audio)

        status.update(label="Rendering video final (bisa beberapa menit)...")
        out_path = os.path.join(tmpdir, "output.mp4")
        video.write_videofile(
            out_path, fps=24, codec="libx264", audio_codec="aac",
            preset="ultrafast", threads=2, logger=None,
        )

        status.update(label="Selesai!", state="complete")

    st.success("Video berhasil dibuat!")
    st.video(out_path)
    with open(out_path, "rb") as f:
        st.download_button("⬇️ Download Video", f, file_name=f"{product_name or 'video'}_affiliate.mp4", mime="video/mp4", use_container_width=True)
