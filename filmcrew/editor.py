import os
import subprocess
import tempfile

from filmcrew.base import BaseCrewMember


class Editor(BaseCrewMember):
    role = "editor"

    def work(self, job, manifest):
        cinematography = manifest.get("cinematography", {})
        sound_design = manifest.get("sound_design", {})

        assets = cinematography.get("assets", [])
        voiceover = sound_design.get("voiceover", {})
        music = sound_design.get("music", {})

        if self.mode != "production":
            return self._assemble_dry_run(job, manifest, assets, voiceover, music)
        return self._assemble_real(job, manifest, assets, voiceover, music)

    def _assemble_dry_run(self, job, manifest, assets, voiceover, music):
        """Generate actual ffmpeg assemblies from placeholder frames.

        Even in dry-run/script_mode we produce a real .mp4 so users can
        inspect timing, pacing, and overall rhythm before buying media APIs.
        """
        output_dir = self.config.get("general", {}).get("output_dir", "outputs/films")
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(
            output_dir, f"{job.get('job_id', 'film')}_placeholder.mp4"
        )

        if not assets:
            self._write_edit_plan(job, manifest, assets, voiceover, music)
            return manifest

        clips = self._render_placeholder_clips(assets, output_dir)
        concat_path = self._write_concat_list(clips, output_dir)

        ok, msg = self._run_ffmpeg_concat(concat_path, output_path)

        manifest["edit"] = {
            "mode": self.mode,
            "status": "placeholder rendered" if ok else "render failed",
            "output_path": output_path if ok else None,
            "clip_count": len(clips),
            "render_log": msg,
            "note": (
                "This is a PLACEHOLDER .mp4 built from text-on-color frames. "
                "It shows timing and pacing, not final production quality. "
                "Add media API keys to config.yaml for real video/audio."
            ),
        }
        return manifest

    def _assemble_real(self, job, manifest, assets, voiceover, music):
        """Real assembly: download the generated clips, normalize them to a
        uniform spec, concat, and mux voiceover + music. Falls back to the
        placeholder render only if no real media is usable. (Built 2026-06-11.)"""
        output_dir = self.config.get("general", {}).get("output_dir", "outputs/films")
        os.makedirs(output_dir, exist_ok=True)
        job_id = job.get("job_id", "film")
        output_path = os.path.join(output_dir, f"{job_id}.mp4")

        if not assets:
            self._write_edit_plan(job, manifest, assets, voiceover, music)
            return manifest

        # 1) Download + normalize each generated asset into a uniform clip.
        clips = self._collect_real_clips(assets, output_dir)
        if not clips:
            # Nothing real came through — be honest and render the placeholder.
            print("[Editor] no usable real media — falling back to placeholder.")
            return self._assemble_dry_run(job, manifest, assets, voiceover, music)

        # 2) Concat the uniform (silent) clips.
        concat_path = self._write_concat_list(clips, output_dir)
        silent_path = os.path.join(output_dir, f"{job_id}_silent.mp4")
        ok, msg = self._run_ffmpeg_concat(concat_path, silent_path)

        final_path = None
        audio_status = "none"
        if ok:
            # 3) Mux real voiceover + music if any are present.
            audio_path = self._collect_audio(voiceover, music, output_dir)
            if audio_path:
                okm, mmsg = self._mux_audio(silent_path, audio_path, output_path)
                if okm:
                    final_path, audio_status = output_path, "muxed"
                else:
                    import shutil
                    shutil.move(silent_path, output_path)
                    final_path = output_path
                    msg += f" | audio mux failed (video-only): {mmsg}"
            else:
                import shutil
                shutil.move(silent_path, output_path)
                final_path = output_path
        if final_path and os.path.exists(silent_path) and silent_path != final_path:
            try:
                os.remove(silent_path)
            except OSError:
                pass

        manifest["edit"] = {
            "mode": "production",
            "status": "rendered" if ok else "render failed",
            "output_path": final_path,
            "clip_count": len(clips),
            "real_media": True,
            "audio": audio_status,
            "render_log": msg,
        }
        return manifest

    # ------------------------------------------------------------------
    # Real-media assembly helpers
    # ------------------------------------------------------------------
    def _download_to(self, src, dest):
        """Download a URL or copy a local file to dest. Returns success bool."""
        try:
            if isinstance(src, str) and src.startswith("http"):
                import requests
                r = requests.get(src, timeout=120)
                r.raise_for_status()
                with open(dest, "wb") as f:
                    f.write(r.content)
            elif isinstance(src, str) and os.path.isfile(src):
                import shutil
                shutil.copyfile(src, dest)
            else:
                return False
            return os.path.isfile(dest) and os.path.getsize(dest) > 0
        except Exception as e:
            print(f"[Editor] download failed for {str(src)[:60]}: {e}")
            return False

    def _collect_real_clips(self, assets, output_dir):
        """Download each generated asset (video or image) and normalize it to a
        uniform 1920x1080 silent clip. Skips mock/placeholder paths."""
        clips = []
        for i, asset in enumerate(assets, 1):
            result = asset.get("result", {}) or {}
            path = result.get("path", "")
            mtype = (result.get("type") or "video").lower()
            usable = isinstance(path, str) and not path.startswith("[") and (
                path.startswith("http") or os.path.isfile(path))
            if not usable:
                continue
            raw = os.path.join(output_dir, f"_raw_{i:03d}")
            if not self._download_to(path, raw):
                continue
            norm = os.path.join(output_dir, f"_norm_{i:03d}.mp4")
            dur = max(1, int(result.get("duration", 5) or 5))
            if self._normalize_clip(raw, norm, is_image=(mtype == "image"), duration=dur):
                clips.append(norm)
            try:
                os.remove(raw)
            except OSError:
                pass
        return clips

    def _normalize_clip(self, src, dest, is_image=False, duration=5):
        """Re-encode any image/video into a uniform 1920x1080 30fps H.264 silent
        clip so the concat demuxer can stitch heterogeneous sources."""
        vf = ("scale=1920:1080:force_original_aspect_ratio=decrease,"
              "pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black,setsar=1,fps=30")
        if is_image:
            cmd = ["ffmpeg", "-y", "-loop", "1", "-i", src, "-t", str(duration)]
        else:
            cmd = ["ffmpeg", "-y", "-i", src]
        cmd += ["-vf", vf, "-an", "-c:v", "libx264", "-preset", "fast",
                "-crf", "23", "-pix_fmt", "yuv420p", "-movflags", "+faststart", dest]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True)
            if r.returncode != 0:
                print(f"[Editor] normalize failed: {(r.stderr or '').strip().splitlines()[-1:]}")
            return r.returncode == 0 and os.path.isfile(dest)
        except Exception as e:
            print(f"[Editor] normalize exception: {e}")
            return False

    def _collect_audio(self, voiceover, music, output_dir):
        """Download voiceover + music if real; mix them. Returns a path or None."""
        tracks = []
        for name, obj in (("voice", voiceover), ("music", music)):
            if not isinstance(obj, dict):
                continue
            p = obj.get("path", "")
            usable = isinstance(p, str) and not p.startswith("[") and (
                p.startswith("http") or os.path.isfile(p))
            if usable:
                dest = os.path.join(output_dir, f"_audio_{name}")
                if self._download_to(p, dest):
                    tracks.append(dest)
        if not tracks:
            return None
        if len(tracks) == 1:
            return tracks[0]
        mixed = os.path.join(output_dir, "_audio_mix.m4a")
        cmd = ["ffmpeg", "-y"]
        for t in tracks:
            cmd += ["-i", t]
        cmd += ["-filter_complex", f"amix=inputs={len(tracks)}:duration=longest",
                "-c:a", "aac", mixed]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True)
            return mixed if (r.returncode == 0 and os.path.isfile(mixed)) else tracks[0]
        except Exception:
            return tracks[0]

    def _mux_audio(self, video_path, audio_path, dest):
        cmd = ["ffmpeg", "-y", "-i", video_path, "-i", audio_path,
               "-c:v", "copy", "-c:a", "aac", "-shortest",
               "-movflags", "+faststart", dest]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True)
            return (r.returncode == 0 and os.path.isfile(dest), (r.stderr or "")[:200])
        except Exception as e:
            return (False, str(e))

    # ------------------------------------------------------------------
    # Placeholder clip generation (works without media API keys)
    # ------------------------------------------------------------------
    def _font_arg(self):
        """Return a `fontfile=<path>:` fragment for drawtext, or "" if none found.

        drawtext has NO default font on macOS, so without an explicit fontfile
        every clip render fails. Probe common OS font paths. (Added 2026-06-11.)
        """
        candidates = [
            "/System/Library/Fonts/Supplemental/Arial.ttf",          # macOS
            "/System/Library/Fonts/Helvetica.ttc",                   # macOS
            "/Library/Fonts/Arial.ttf",                              # macOS (user)
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",       # Debian/Ubuntu
            "/usr/share/fonts/dejavu/DejaVuSans.ttf",                # Fedora
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        ]
        for f in candidates:
            if os.path.isfile(f):
                return f"fontfile={f}:"
        return ""  # fall back to ffmpeg/fontconfig default (may work on some Linux)

    def _render_placeholder_clips(self, assets, output_dir):
        """Render one .mp4 per frame using ffmpeg color+drawtext."""
        clips = []
        font = self._font_arg()
        for i, asset in enumerate(assets, 1):
            result = asset.get("result", {})
            # Duration from storyboard or default to 3s
            dur = max(1, int(result.get("duration", 3)))
            prompt = result.get("prompt", f"Frame {i}")
            # Sanitise for the drawtext filter. Collapse ALL whitespace first —
            # newlines/tabs in the text break the shell command ("Error opening
            # output files") — then strip the chars that break filter parsing.
            display = " ".join(str(prompt).split())[:80]
            for ch in ("'", "\\", ":", "%"):
                display = display.replace(ch, " ")
            display = display.strip() or f"Frame {i}"
            clip_path = os.path.join(output_dir, f"_clip_{i:03d}.mp4")

            # background color cycles through ROVA brand palette
            colors = ["#0a0a0a", "#1a1a2e", "#16213e", "#0f3460", "#e94560",
                      "#2c3e50", "#34495e", "#8e44ad", "#2980b9", "#16a085"]
            bg = colors[(i - 1) % len(colors)]

            # Argument LIST (not shell=True): the old hand-escaped shell string
            # broke on quotes. A list passes each arg literally. (Fixed 2026-06-11.)
            base = ["ffmpeg", "-y", "-f", "lavfi",
                    "-i", f"color=c={bg}:s=1920x1080", "-t", str(dur)]
            tail = ["-c:v", "libx264", "-preset", "ultrafast", "-an",
                    "-pix_fmt", "yuv420p", "-movflags", "+faststart", clip_path]
            vf = (f"drawtext={font}text='{display}':fontsize=48:"
                  f"fontcolor=white:x=(w-tw)/2:y=(h-th)/2")
            # Try text-on-color; fall back to plain color if this ffmpeg has no
            # drawtext (built without libfreetype — common on macOS/Homebrew). A
            # real .mp4 is produced either way. (Graceful degradation, 2026-06-11.)
            attempts = [base + ["-vf", vf] + tail, base + tail]
            r = None
            for ci, cmd in enumerate(attempts):
                try:
                    r = subprocess.run(cmd, capture_output=True, text=True)
                except Exception as e:
                    print(f"[Editor] Frame {i} exception: {e}")
                    break
                if r.returncode == 0 and os.path.isfile(clip_path):
                    clips.append(clip_path)
                    if ci == 1:
                        print(f"[Editor] Frame {i}: no drawtext in ffmpeg — rendered plain color clip.")
                    break
            else:
                err = (r.stderr or r.stdout or "").strip().splitlines() if r else []
                print(f"[Editor] Frame {i} render failed: {err[-1] if err else '(no output)'}")
        return clips

    def _write_concat_list(self, clips, output_dir):
        path = os.path.join(output_dir, "_concat.txt")
        with open(path, "w") as f:
            for clip in clips:
                # Absolute path — ffmpeg's concat demuxer resolves relative
                # entries against the LIST file's dir, not cwd. (Fixed 2026-06-11.)
                f.write(f"file '{os.path.abspath(clip)}'\n")
        return path

    def _run_ffmpeg_concat(self, concat_path, output_path):
        cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_path,
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", output_path,
        ]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True)
            if r.returncode == 0 and os.path.isfile(output_path):
                return True, "concat succeeded"
            return False, (r.stderr or r.stdout or "")[:400]
        except Exception as e:
            return False, str(e)

    def _write_edit_plan(self, job, manifest, assets, voiceover, music):
        """Fallback when no assets: write assembly plan text."""
        output_dir = self.config.get("general", {}).get("output_dir", "outputs/films")
        os.makedirs(output_dir, exist_ok=True)
        assembly_note = os.path.join(
            output_dir, f"{job.get('job_id', 'film')}_assembly.txt"
        )
        with open(assembly_note, "w") as f:
            f.write(f"Assembly plan for {job.get('title')}\n")
            for a in assets:
                f.write(f"- Frame {a['frame']}: {a.get('prompt', '')}\n")
            f.write(f"Voiceover: {voiceover.get('text_preview', '')}\n")
            f.write(f"Music: {music.get('prompt', '')}\n")

        manifest["edit"] = {
            "mode": self.mode,
            "status": "assembly plan only — no frames to render",
            "output_path": None,
            "assembly_note": assembly_note,
        }
        return manifest
