#!/usr/bin/env python3
"""Bounded, local media metadata and sparse frames; no semantic inference."""

import argparse
import json
import math
import re
import shutil
import subprocess
import sys
import tempfile
import wave
from datetime import datetime, timezone
from pathlib import Path

MIB = 1024 * 1024
REPORT_RESERVE = 512 * 1024
FRAME_CAP = 2 * MIB
MEDIA = {'.mp4', '.mov', '.webm', '.mkv', '.avi', '.m4v', '.mp3', '.wav',
         '.m4a', '.flac', '.ogg', '.aac', '.aiff', '.aif', '.opus'}
IMAGES = {'.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp', '.tif', '.tiff'}
TEXT = {'.txt', '.md', '.lrc', '.srt', '.vtt'}


def number(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (ValueError, TypeError):
        return None


def run(command, timeout):
    """No shell; bound diagnostic output using temporary files."""
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        try:
            proc = subprocess.run(command, stdin=subprocess.DEVNULL,
                                  stdout=stdout, stderr=stderr, timeout=timeout,
                                  check=False)
        except subprocess.TimeoutExpired:
            raise RuntimeError('local tool timed out after %s seconds' % timeout)
        stdout.seek(0)
        stderr.seek(0)
        out = stdout.read(256 * 1024).decode('utf-8', errors='replace')
        err = stderr.read(256 * 1024).decode('utf-8', errors='replace')
        if proc.returncode:
            raise RuntimeError('local tool failed: ' + err[-1200:])
        return out, err


def probe(path, ffprobe):
    out, _ = run([ffprobe, '-v', 'error', '-protocol_whitelist', 'file,pipe',
                  '-show_entries',
                  'format=duration,start_time,format_name:stream=index,codec_type,'
                  'codec_name,width,height,avg_frame_rate,sample_rate,channels,'
                  'duration,start_time,disposition', '-of', 'json', str(path)], 20)
    data = json.loads(out)
    fmt = data.get('format', {})
    streams = data.get('streams', [])
    duration = number(fmt.get('duration'))
    if duration is None:
        values = [number(s.get('duration')) for s in streams]
        duration = max((v for v in values if v is not None), default=None)
    return {'method': 'ffprobe metadata', 'duration_seconds': duration,
            'format': fmt, 'streams': streams}


def wav_metadata(path):
    with wave.open(str(path), 'rb') as audio:
        rate = audio.getframerate()
        frames = audio.getnframes()
        return {'method': 'wave standard library sample count',
                'duration_seconds': frames / rate,
                'sample_count': frames,
                'streams': [{'codec_type': 'audio', 'sample_rate': rate,
                             'channels': audio.getnchannels()}]}


def extract_frames(path, metadata, ffmpeg, count, output, prefix, remaining):
    video = next((s for s in metadata.get('streams', [])
                  if s.get('codec_type') == 'video'
                  and not s.get('disposition', {}).get('attached_pic')), None)
    if not video or not ffmpeg or count == 0:
        return [], [], 0
    duration = number(video.get('duration'))
    if duration is None:
        duration = metadata.get('duration_seconds')
    if duration is None or duration <= 0:
        return [], ['video duration unavailable; no frames sampled'], 0
    origin = number(video.get('start_time'))
    if origin is None:
        origin = number(metadata.get('format', {}).get('start_time')) or 0.0
    # Stream and container may start at different times. Input -ss is relative
    # to the container start, while decoded PTS remains absolute with -copyts.
    format_origin = number(metadata.get('format', {}).get('start_time')) or 0.0
    offset = max(0.0, origin - format_origin)
    frames, errors, used = [], [], 0
    for index in range(count):
        cap = min(FRAME_CAP, remaining - used)
        if cap < 64 * 1024:
            errors.append('output budget reached; remaining samples skipped')
            break
        target = duration * (index + 0.5) / count
        try:
            with tempfile.TemporaryDirectory(prefix='.mv-script-', dir=str(output)) as temp:
                frame = Path(temp) / 'frame.jpg'
                _, log = run([
                    ffmpeg, '-nostdin', '-hide_banner', '-v', 'info',
                    '-protocol_whitelist', 'file,pipe', '-ss', str(target + offset),
                    '-copyts', '-i', str(path), '-map', '0:%s' % video['index'],
                    '-frames:v', '1', '-an', '-sn', '-dn',
                    '-vf', "scale=w='min(768,iw)':h='min(768,ih)':"
                    'force_original_aspect_ratio=decrease,showinfo',
                    '-q:v', '3', '-fs', str(cap), '-f', 'image2', str(frame)], 30)
                if not frame.is_file():
                    raise RuntimeError('decoder produced no frame')
                size = frame.stat().st_size
                if size <= 0 or size > cap:
                    raise RuntimeError('frame exceeds budget or is empty')
                with frame.open('rb') as check:
                    check.seek(-2, 2)
                    if check.read(2) != b'\xff\xd9':
                        raise RuntimeError('frame is not a complete JPEG')
                match = re.search(r'\bn:\s*0\b[^\n]*?pts_time:\s*([\d.eE+\-]+)', log)
                pts = number(match.group(1)) if match else None
                relative = pts - origin if pts is not None else None
                name = '%s_frame_%02d.jpg' % (prefix, index + 1)
                destination = output / name
                # Output starts empty; exclusive creation still prevents a race.
                with frame.open('rb') as src, destination.open('xb') as dst:
                    shutil.copyfileobj(src, dst)
                used += size
                frames.append({'file': name, 'requested_seconds': round(target, 6),
                               'decoded_pts_seconds': pts,
                               'stream_start_seconds': origin,
                               'source_relative_seconds': relative,
                               'bytes': size, 'visual_review': 'not_performed'})
        except (OSError, RuntimeError) as exc:
            errors.append('sample %s: %s' % (index + 1, str(exc)[:1400]))
    return frames, errors, used


def safe_cell(value):
    return str(value).replace('|', '\\|').replace('\n', ' ').replace('\r', ' ')


def markdown(report):
    rows = ['# Local source inventory', '',
            'Metadata and sparse samples only. Visual review, listening, BPM, '
            'music structure and lyric alignment have not been performed.', '',
            '| ID | Source | Status | Duration seconds | Frames | Notes |',
            '| --- | --- | --- | --- | --- | --- |']
    for item in report['inputs']:
        duration = item.get('metadata', {}).get('duration_seconds')
        fields = [item['id'], item['source'], item['status'],
                  duration if duration is not None else 'unknown',
                  len(item.get('frames', [])), '; '.join(item.get('notes', []))]
        rows.append('| ' + ' | '.join(safe_cell(v) for v in fields) + ' |')
    rows.extend(['', 'Frame timestamps and limitations: see `inspection.json`.', ''])
    return '\n'.join(rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inputs', nargs='*')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--check-tools', action='store_true')
    parser.add_argument('--frames', type=int, default=6)
    parser.add_argument('--max-output-mb', type=int, default=32)
    parser.add_argument('--max-input-mb', type=int, default=4096)
    args = parser.parse_args(argv)
    capabilities = {'python': sys.version.split()[0],
                    'ffprobe': shutil.which('ffprobe'),
                    'ffmpeg': shutil.which('ffmpeg'),
                    'wav_fallback': 'standard library',
                    'visual_review': 'host tool required',
                    'bpm': 'not_performed', 'music_structure': 'not_performed'}
    if args.check_tools:
        print(json.dumps(capabilities, ensure_ascii=False, indent=2))
        return 0
    if not 1 <= len(args.inputs) <= 20:
        parser.error('provide between 1 and 20 local files')
    if not 0 <= args.frames <= 12:
        parser.error('--frames must be between 0 and 12')
    if not 1 <= args.max_output_mb <= 128 or not 1 <= args.max_input_mb <= 4096:
        parser.error('output budget: 1..128 MiB; input limit: 1..4096 MiB')
    if args.output is None:
        parser.error('--output is required')
    if any(len(s) > 4096 or '\n' in s or '\r' in s or
           re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*://', s) for s in args.inputs):
        parser.error('only local file paths are accepted; URLs are not supported')
    paths = [Path(s).expanduser().resolve() for s in args.inputs]
    output_arg = args.output.expanduser()
    if output_arg.is_symlink():
        parser.error('output directory must not be a symlink')
    output = output_arg.resolve()
    if output in paths:
        parser.error('output must not be an input')
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        parser.error('output directory must be absent or empty; no files overwritten')
    output.mkdir(parents=True, exist_ok=True)
    report = {'created_utc': datetime.now(timezone.utc).isoformat(),
              'capabilities': capabilities, 'inputs': [],
              'limitations': ['sparse_uniform_samples', 'no_cut_detection',
                              'no_semantic_analysis', 'no_lyric_alignment']}
    remaining = args.max_output_mb * MIB - REPORT_RESERVE
    for index, path in enumerate(paths, 1):
        item = {'id': 'I%02d' % index, 'source': str(path), 'status': 'unread',
                'notes': [], 'frames': []}
        report['inputs'].append(item)
        try:
            if not path.is_file():
                raise ValueError('not an accessible local file')
            item['bytes'] = path.stat().st_size
            if item['bytes'] > args.max_input_mb * MIB:
                raise ValueError('input exceeds size limit; skipped')
            suffix = path.suffix.lower()
            if suffix not in MEDIA:
                item['status'] = 'host_read_required'
                item['kind'] = 'image' if suffix in IMAGES else 'text' if suffix in TEXT else 'unknown'
                item['notes'].append('content not read by this script')
                continue
            metadata = None
            if capabilities['ffprobe']:
                try:
                    metadata = probe(path, capabilities['ffprobe'])
                except (RuntimeError, ValueError, OSError) as exc:
                    item['notes'].append(str(exc)[:1400])
            if metadata is None and suffix == '.wav':
                try:
                    metadata = wav_metadata(path)
                except (wave.Error, EOFError, OSError) as exc:
                    item['notes'].append('WAV fallback failed: ' + str(exc)[:300])
            if metadata is None:
                item['status'] = 'metadata_unavailable'
                item['notes'].append('continue with user descriptions or readable text/images')
                continue
            item['metadata'] = metadata
            item['status'] = 'metadata_read'
            frames, errors, used = extract_frames(path, metadata,
                                                  capabilities['ffmpeg'], args.frames,
                                                  output, item['id'], remaining)
            item['frames'] = frames
            item['notes'].extend(errors)
            remaining -= used
            if not capabilities['ffmpeg']:
                item['notes'].append('ffmpeg unavailable; no frames extracted')
        except (OSError, ValueError, RuntimeError) as exc:
            item['status'] = 'unavailable'
            item['notes'].append(str(exc)[:1400])
    encoded = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
    human = markdown(report)
    if len(encoded.encode('utf-8')) + len(human.encode('utf-8')) > REPORT_RESERVE:
        raise RuntimeError('report reserve exceeded')
    (output / 'inspection.json').write_text(encoded, encoding='utf-8')
    (output / 'inventory.md').write_text(human, encoding='utf-8')
    print('Inspection report: ' + str(output / 'inspection.json'))
    print('Inputs: %s; frames: %s; semantic review: not performed' %
          (len(report['inputs']), sum(len(x['frames']) for x in report['inputs'])))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, RuntimeError) as error:
        print('Inspection failed: ' + str(error), file=sys.stderr)
        sys.exit(1)
