"""
Foto Produk -> Video Affiliate (±15 detik)
Streamlit app: upload foto produk, tambahkan caption + voiceover,
otomatis dibuatkan video dengan efek zoom/pan (Ken Burns), lalu di-export
dalam format vertikal 9:16 siap upload ke Reels/TikTok/Shorts.
"""

import streamlit as st
import tempfile
import os
from gtts import gTTS
from moviepy.editor import (
    ImageClip, CompositeVideoClip, TextClip, AudioFileClip,
    concatenate_videoclips, vfx
)
from PIL import Image

st.set_page_config(page_title="Foto ke Video Affiliate", page_icon="🎬", layout="centered")
st.title("🎬 Foto Produk → Video Affiliate (15s)")
st.caption("Upload foto produk, isi caption, langsung jadi video vertikal siap posting.")

VIDEO_W, VIDEO_H = 1080, 1920  # format 9:16

# ---------- INPUT ----------
uploaded_files = st.file_uploader(
    "Upload foto produk (bisa lebih dari 1, urutan = urutan tampil)",
    type=["jpg", "jpeg", "png"], accept_multiple_files=True
)

product_name = st.text_input("Nama produk", placeholder="Contoh: Lampu Bulan Mini")

benefit_points = st.text_area(
    "Poin-poin script (satu baris = satu klip/caption)",
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


def make_caption(text, duration):
    txt = TextClip(
        text, fontsize=64, color="white", font="DejaVu-Sans-Bold",
        stroke_color="black", stroke_width=3,
        size=(VIDEO_W * 0.85, None), method="caption", align="center",
    )
    txt = txt.set_duration(duration).set_position(("center", "bottom")).margin(bottom=180, opacity=0)
    return txt


def make_voiceover(text, out_path, lang="id"):
    tts = gTTS(text=text, lang=lang)
    tts.save(out_path)


# ---------- MAIN PIPELINE ----------
if generate:
    if not uploaded_files:
        st.error("Upload minimal 1 foto produk dulu ya.")
        st.stop()

    lines = [l.strip() for l in benefit_points.split("\n") if l.strip()]
    if not lines:
        lines = [product_name or "Produk keren ini wajib kamu punya!"]

    n_clips = max(len(uploaded_files), len(lines))
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
        video.write_videofile(out_path, fps=30, codec="libx264", audio_codec="aac")

        status.update(label="Selesai!", state="complete")

    st.success("Video berhasil dibuat!")
    st.video(out_path)
    with open(out_path, "rb") as f:
        st.download_button("⬇️ Download Video", f, file_name=f"{product_name or 'video'}_affiliate.mp4", mime="video/mp4", use_container_width=True)
