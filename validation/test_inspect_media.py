"""Executable local acceptance checks with explicitly synthetic fixtures."""
import hashlib
import importlib.util
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import wave
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'mv-script/scripts/inspect_media.py'
FIXTURES = ROOT / 'validation/fixtures'
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location('inspect_media', SCRIPT)
media = importlib.util.module_from_spec(spec)
spec.loader.exec_module(media)


def create_fixtures():
    FIXTURES.mkdir(parents=True, exist_ok=True)
    song = FIXTURES / 'synthetic_tone.wav'
    if not song.exists():
        import array
        samples = array.array('h', (int(6000 * math.sin(2 * math.pi * 440 * i / 16000))
                                    for i in range(64000)))
        if sys.byteorder != 'little':
            samples.byteswap()
        with wave.open(str(song), 'wb') as out:
            out.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
            out.writeframes(samples.tobytes())
    video = FIXTURES / 'synthetic_video.mp4'
    if shutil.which('ffmpeg') and not video.exists():
        subprocess.run([shutil.which('ffmpeg'), '-nostdin', '-v', 'error',
                        '-f', 'lavfi', '-i', 'testsrc2=s=320x180:r=4:d=4',
                        '-c:v', 'mpeg4', '-q:v', '3', str(video)], check=True)
    shifted = FIXTURES / 'synthetic_offset.mp4'
    if shutil.which('ffmpeg') and not shifted.exists():
        subprocess.run([shutil.which('ffmpeg'), '-nostdin', '-v', 'error',
                        '-f', 'lavfi', '-i', 'testsrc2=s=320x180:r=4:d=4',
                        '-vf', 'setpts=PTS+5/TB', '-fps_mode', 'passthrough',
                        '-c:v', 'mpeg4', '-q:v', '3', str(shifted)], check=True)
    text = FIXTURES / 'original_test_lyrics.txt'
    if not text.exists():
        text.write_text('原创验收歌词，非已发行歌曲\n\n'
                        '主歌一\n我把未寄的信折成小船\n让它停在窗边等风来\n\n'
                        '副歌一\n灯亮时我还在原地\n灯灭后水面替我回答\n\n'
                        '主歌二\n掌心的墨沿雨线散开\n我终于松开窗上的锁\n\n'
                        '副歌二\n灯亮时我走下楼梯\n灯灭后把船交给清晨\n', encoding='utf-8')
    image = FIXTURES / 'synthetic_character.png'
    if not image.exists():
        try:
            from PIL import Image, ImageDraw
        except ImportError:
            return
        canvas = Image.new('RGB', (320, 480), '#e6e3da')
        draw = ImageDraw.Draw(canvas)
        draw.ellipse((105, 38, 215, 155), fill='#24282e')
        draw.ellipse((115, 65, 205, 158), fill='#d6b7a5')
        draw.polygon([(107, 55), (213, 55), (205, 104), (165, 77), (115, 100)], fill='#24282e')
        draw.ellipse((123, 99, 153, 127), outline='#24282e', width=4)
        draw.ellipse((167, 99, 197, 127), outline='#24282e', width=4)
        draw.line((153, 112, 167, 112), fill='#24282e', width=4)
        draw.polygon([(113, 161), (205, 161), (239, 326), (81, 326)], fill='#326ca1')
        draw.rectangle((112, 158, 207, 185), fill='#e6b83d')
        draw.rectangle((175, 176, 196, 251), fill='#e6b83d')
        draw.line((113, 190, 202, 278), fill='#862d36', width=10)
        draw.rectangle((189, 260, 246, 319), fill='#b2474e')
        draw.rectangle((111, 326, 150, 419), fill='#3b414b')
        draw.rectangle((169, 326, 208, 419), fill='#3b414b')
        draw.rounded_rectangle((99, 407, 151, 436), 6, fill='#24282e')
        draw.rounded_rectangle((169, 407, 221, 436), 6, fill='#24282e')
        canvas.save(image)


class LocalMediaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        create_fixtures()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='mv-script-test-')
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name) / 'inspection'

    def invoke(self, *inputs, no_tools=False, extra=()):
        env = dict(os.environ)
        if no_tools:
            env['PATH'] = ''
        result = subprocess.run([sys.executable, str(SCRIPT), *map(str, inputs),
                                 '--output', str(self.output), *extra],
                                capture_output=True, text=True, env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads((self.output / 'inspection.json').read_text())

    def test_wav_actual_duration_and_no_invented_music_analysis(self):
        result = self.invoke(FIXTURES / 'synthetic_tone.wav')
        item = result['inputs'][0]
        self.assertAlmostEqual(item['metadata']['duration_seconds'], 4, places=4)
        self.assertEqual(result['capabilities']['bpm'], 'not_performed')
        self.assertEqual(result['capabilities']['music_structure'], 'not_performed')
        self.assertEqual(item['frames'], [])

    def test_no_tools_wav_fallback_and_text_mode(self):
        result = self.invoke(FIXTURES / 'synthetic_tone.wav',
                             FIXTURES / 'original_test_lyrics.txt', no_tools=True)
        self.assertIsNone(result['capabilities']['ffprobe'])
        self.assertIsNone(result['capabilities']['ffmpeg'])
        self.assertEqual(result['inputs'][0]['metadata']['duration_seconds'], 4)
        self.assertEqual(result['inputs'][1]['status'], 'host_read_required')

    def test_no_tools_video_degrades_without_claiming_analysis(self):
        if not (FIXTURES / 'synthetic_video.mp4').exists():
            self.skipTest('no ffmpeg fixture')
        result = self.invoke(FIXTURES / 'synthetic_video.mp4', no_tools=True)
        self.assertEqual(result['inputs'][0]['status'], 'metadata_unavailable')
        self.assertEqual(result['inputs'][0]['frames'], [])

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'media tools unavailable')
    def test_video_samples_have_measured_timestamps_and_inputs_unchanged(self):
        source = FIXTURES / 'synthetic_video.mp4'
        before = hashlib.sha256(source.read_bytes()).hexdigest()
        result = self.invoke(source, extra=('--frames', '4'))
        frames = result['inputs'][0]['frames']
        self.assertEqual(len(frames), 4, result)
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), before)
        for frame in frames:
            self.assertIsNotNone(frame['source_relative_seconds'])
            self.assertLessEqual(abs(frame['source_relative_seconds'] - frame['requested_seconds']), 0.26)
            self.assertEqual(frame['visual_review'], 'not_performed')
            self.assertLessEqual((self.output / frame['file']).stat().st_size, media.FRAME_CAP)
        self.assertFalse(list(self.output.glob('.mv-script-*')))

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'media tools unavailable')
    def test_nonzero_media_start_preserves_source_relative_time(self):
        result = self.invoke(FIXTURES / 'synthetic_offset.mp4', extra=('--frames', '4'))
        frames = result['inputs'][0]['frames']
        self.assertEqual(len(frames), 4, result)
        self.assertGreaterEqual(frames[0]['stream_start_seconds'], 5)
        for frame in frames:
            self.assertLessEqual(abs(frame['source_relative_seconds'] - frame['requested_seconds']), 0.26)

    def test_output_collision_preserves_existing_file(self):
        self.output.mkdir()
        keep = self.output / 'keep.txt'
        keep.write_text('preserve')
        result = subprocess.run([sys.executable, str(SCRIPT), str(FIXTURES / 'synthetic_tone.wav'),
                                 '--output', str(self.output)], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(keep.read_text(), 'preserve')
        self.assertEqual(len(list(self.output.iterdir())), 1)

    def test_remote_url_and_excessive_frames_rejected(self):
        for arguments in [['https://example.invalid/media.mp4'],
                          [str(FIXTURES / 'synthetic_tone.wav'), '--frames', '1000']]:
            result = subprocess.run([sys.executable, str(SCRIPT), *arguments,
                                     '--output', str(self.output)], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(self.output.exists())

    def test_input_limit_skips_without_modification(self):
        source = Path(self.temp.name) / 'large.wav'
        source.write_bytes(b'0' * (2 * media.MIB))
        result = self.invoke(source, extra=('--max-input-mb', '1'))
        self.assertEqual(result['inputs'][0]['status'], 'unavailable')
        self.assertEqual(source.stat().st_size, 2 * media.MIB)

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'media tools unavailable')
    def test_output_budget_is_enforced(self):
        self.invoke(FIXTURES / 'synthetic_video.mp4',
                    extra=('--frames', '12', '--max-output-mb', '1'))
        size = sum(p.stat().st_size for p in self.output.rglob('*') if p.is_file())
        self.assertLessEqual(size, media.MIB)

    def test_corrupt_media_reports_failure_without_fabrication(self):
        source = Path(self.temp.name) / 'corrupt.wav'
        source.write_text('not audio')
        result = self.invoke(source)
        self.assertEqual(result['inputs'][0]['status'], 'metadata_unavailable')
        self.assertNotIn('metadata', result['inputs'][0])

    def test_timeout_becomes_actionable_error(self):
        with mock.patch.object(media.subprocess, 'run', side_effect=subprocess.TimeoutExpired('ffprobe', 20)):
            with self.assertRaisesRegex(RuntimeError, 'timed out'):
                media.run(['ffprobe'], 20)

    def test_failed_sampling_cleans_temporary_files(self):
        self.output.mkdir()
        metadata = {'duration_seconds': 4, 'streams': [{'index': 0, 'codec_type': 'video'}]}
        with mock.patch.object(media, 'run', side_effect=RuntimeError('fixture failure')):
            frames, errors, used = media.extract_frames(Path('unused.mp4'), metadata,
                                                        'ffmpeg', 2, self.output,
                                                        'I01', media.MIB)
        self.assertEqual(frames, [])
        self.assertEqual(used, 0)
        self.assertEqual(len(errors), 2)
        self.assertEqual(list(self.output.iterdir()), [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
