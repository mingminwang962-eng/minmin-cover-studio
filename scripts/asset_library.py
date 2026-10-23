#!/usr/bin/env python3
"""Persist user photos and generated covers, then rebuild their offline galleries."""
import argparse
from contextlib import contextmanager
from datetime import datetime
import time
import hashlib
import html
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import quote
import uuid



def now():
    return datetime.now().astimezone().isoformat()


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def atomic(path, content):
    # Same-directory replace: a failed write never truncates an existing index.
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as f:
        tmp = Path(f.name)
        try:
            f.write(content.encode('utf-8'))
            f.flush()
            os.fsync(f.fileno())
        except BaseException:
            tmp.unlink(missing_ok=True)
            raise
    try:
        tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)


def write(path, value):
    atomic(path, json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def digest(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest() if hasattr(hashlib, 'file_digest') else hashlib.sha256(f.read()).hexdigest()


def copy_verified(source, target):
    checksum = digest(source)
    if target.exists():
        if digest(target) != checksum:
            raise FileExistsError(f'拒绝覆盖已有文件：{target}')
        return checksum
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as f:
        tmp = Path(f.name)
    try:
        shutil.copyfile(source, tmp)
        if digest(tmp) != checksum:
            raise OSError(f'保存校验失败：{source}')
        # All writes to a library are serialized by its lock.
        tmp.replace(target)
    finally:
        tmp.unlink(missing_ok=True)
    return checksum


def image_file(path):
    from PIL import Image
    path = Path(path).expanduser().resolve(strict=True)
    with Image.open(path) as im:
        im.verify()
    return path


def inside(root, relative):
    path = (root / relative).resolve()
    if root not in path.parents:
        raise ValueError(f'路径不在当前资料库内：{relative}')
    return path


def library(profile):
    if not profile.is_file():
        raise ValueError('当前内容尚无照片集或封面记录；photos / prepare 会自动初始化。')
    config = read(profile)
    root = Path(config['root'])
    marker = root / '.cover-studio.json'
    if not marker.is_file() or read(marker).get('id') != config['library_id']:
        raise ValueError('当前内容的资料库不可用或身份不符。请恢复该位置；未自动切换。')
    return root


@contextmanager
def locked(root):
    with (root / '.lock').open('a+b') as f:
        if os.name == 'nt':
            import msvcrt
            if f.tell() == 0:
                f.write(b'0')
                f.flush()
            deadline = time.monotonic() + 30
            while True:
                f.seek(0)
                try:
                    msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise TimeoutError('资料库正被其他任务使用，请稍后重试。')
                    time.sleep(0.1)
            try:
                yield
            finally:
                f.seek(0)
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)


def initialize(profile, folder):
    folder = Path(folder).expanduser().resolve(strict=True)
    if not folder.is_dir():
        raise ValueError('当前内容目录必须是已存在的文件夹。')
    root = folder / '我的封面工作室'
    if profile.exists():
        current = read(profile)
        if current['root'] != str(root):
            raise ValueError('已设置其他保存位置；不能通过首次初始化静默更换。')
        return library(profile)
    if root.exists() and not (root / '.cover-studio.json').is_file():
        raise ValueError('当前内容中存在同名非资料库文件夹，未覆盖；请先核实冲突。')
    root.mkdir(exist_ok=True)
    with locked(root):
        marker = root / '.cover-studio.json'
        if not marker.exists():
            (root / '照片集/原照片').mkdir(parents=True)
            (root / '封面作品').mkdir()
            write(root / '照片集/照片索引.json', [])
            write(root / '封面索引.json', [])
            write(marker, {'id': uuid.uuid4().hex, 'created_at': now()})
        rebuild(root)
        profile.parent.mkdir(parents=True, exist_ok=True)
        write(profile, {'root': str(root), 'library_id': read(marker)['id']})
    return root


def add_photos(root, files):
    # Validate the whole upload before changing the index.
    sources = [image_file(p) for p in files]
    index_path = root / '照片集/照片索引.json'
    rows = read(index_path)
    known = {row['sha256']: row for row in rows}
    batch = uuid.uuid4().hex
    results = []
    for source in sources:
        checksum = digest(source)
        row = known.get(checksum)
        if row is None:
            relative = f'照片集/原照片/{checksum}{source.suffix.lower()}'
            copy_verified(source, inside(root, relative))
            row = {'id': 'photo-' + checksum, 'sha256': checksum, 'file': relative,
                   'name': source.name, 'created_at': now(), 'uploads': []}
            rows.append(row)
            known[checksum] = row
        else:
            copy_verified(source, inside(root, row['file']))
        row['uploads'].append({'batch': batch, 'source': str(source), 'at': now()})
        results.append({'id': row['id'], 'path': str(root / row['file'])})
    write(index_path, rows)
    rebuild(root)
    return results


def managed_run(root, path):
    run = Path(path).expanduser().resolve(strict=True)
    if run.parent != root / '封面作品':
        raise ValueError('本轮不在当前资料库的封面作品目录中。历史目录不会自动迁移。')
    if read(run / '.library.json')['library_id'] != read(root / '.cover-studio.json')['id']:
        raise ValueError('本轮不属于当前资料库。')
    return run


def prepare(root, config_path):
    config = read(Path(config_path))
    photo = add_photos(root, [config['reference_path']])[0]
    run = root / '封面作品' / (datetime.now().strftime('%Y%m%d-%H%M%S-') + uuid.uuid4().hex[:10])
    run.mkdir()
    config.update(reference_path=photo['path'], reference_asset_id=photo['id'], output_dir=str(run))
    write(run / 'config.json', config)
    write(run / '.library.json', {'library_id': read(root / '.cover-studio.json')['id']})
    subprocess.run([sys.executable, str(Path(__file__).with_name('compile_batch.py')), str(run / 'config.json')], check=True, stdout=sys.stderr)
    rebuild(root)
    return {'run': str(run), 'config': str(run / 'config.json'), 'batch': str(run / 'batch.json')}


def sync(root, run):
    plan = read(run / 'plan.json')
    rows = read(root / '封面索引.json')
    known = {row['id']: row for row in rows}
    errors = []
    for candidate in plan['candidates']:
        source = inside(run, candidate['image'])
        if not source.exists():
            continue
        try:
            image_file(source)
            prompt = inside(run, candidate['prompt_file'])
            prompt_hash = digest(prompt)
            if prompt_hash != candidate['prompt_sha256']:
                raise ValueError('提示词与生成计划的哈希不一致')
            checksum = digest(source)
            identity = hashlib.sha256(f'{run.name}/{candidate["id"]}/{checksum}/{prompt_hash}'.encode()).hexdigest()
            record = known.get(identity)
            if record is None:
                archive = run / '已保存' / identity
                copy_verified(source, archive / source.name)
                copy_verified(prompt, archive / 'prompt.txt')
                write(archive / '生成记录.json', {'plan': plan, 'candidate': candidate})
                record = {'id': identity, 'created_at': now(), 'title': plan['title'],
                          'style_id': candidate['id'], 'style': candidate['label'],
                          'reference_asset_id': plan['reference_asset_id'],
                          'reference_sha256': plan['reference_sha256'],
                          'file': str((archive / source.name).relative_to(root)),
                          'prompt': str((archive / 'prompt.txt').relative_to(root)),
                          'sha256': checksum, 'prompt_sha256': prompt_hash,
                          'run': str(run.relative_to(root)), 'selected': False}
                rows.append(record)
                known[identity] = record
            record['review'] = candidate.get('review')
            record['generation_status'] = candidate.get('status')
            record['updated_at'] = now()
        except (OSError, ValueError, KeyError) as exc:
            errors.append(f'{candidate["id"]}: {exc}')
    write(root / '封面索引.json', rows)
    rebuild(root)
    if errors:
        raise ValueError('有效图片已保存，以下候选未完成归档：' + '; '.join(errors))
    return {'saved_covers': len(rows), 'wall': str(root / '我的封面墙.html')}


def save_cover(root, run, candidate_id, source):
    plan = read(run / 'plan.json')
    candidate = next(c for c in plan['candidates'] if c['id'] == candidate_id)
    source = image_file(source)
    copy_verified(source, inside(run, candidate['image']))
    candidate['status'] = 'generated'
    write(run / 'plan.json', plan)
    result = sync(root, run)
    from compile_batch import build_wall
    build_wall(run, plan)
    return result


def rebuild(root):
    esc = html.escape
    for title, destination, rows in [
        ('我的照片集', root / '照片集/照片墙.html', read(root / '照片集/照片索引.json')),
        ('我的封面墙', root / '我的封面墙.html', read(root / '封面索引.json')),
    ]:
        cards = []
        def link(relative):
            return quote(os.path.relpath(root / relative, destination.parent).replace(os.sep, '/'), safe='/')
        for row in reversed(rows):
            name = row.get('title', row.get('name', ''))
            status = ('已选定' if row.get('selected') else '已生成 · 待选择') if 'style' in row else '原照片'
            details = esc(row.get('style', '')) + ' · ' + status
            prompt = f'<a href="{link(row["prompt"])}">查看提示词</a>' if 'prompt' in row else ''
            review = esc(str(row.get('review') or ''))
            cards.append(f'<article><a href="{link(row["file"])}"><img loading="lazy" src="{link(row["file"])}" alt="{esc(name)}"></a><h2>{esc(name)}</h2><p>{details}</p><p>{review}</p><small>{esc(row["id"])}</small><p>{prompt}</p></article>')
        page = '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>' + title + '</title><style>body{background:#f6f5f1;color:#26352c;font:16px/1.6 system-ui;margin:32px}nav{display:flex;gap:24px}a{color:#275842}main{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:24px}article{background:white;padding:16px;border-radius:16px;min-width:0}img{width:100%;height:320px;object-fit:contain}h2{font-size:20px}small{overflow-wrap:anywhere;color:#666}</style><nav><a href="' + link('照片集/照片墙.html') + '">我的照片集</a><a href="' + link('我的封面墙.html') + '">我的封面墙</a></nav><h1>' + title + '</h1><p>共 ' + str(len(rows)) + ' 张 · 更新于 ' + esc(now()) + '</p><main>' + (''.join(cards) or '<p>还没有图片，保存后会自动出现在这里。</p>') + '</main></html>'
        atomic(destination, page)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    location = parser.add_mutually_exclusive_group(required=True)
    location.add_argument('--content-dir', type=Path, help='本次内容所在目录；photos / prepare 自动在其内建库')
    location.add_argument('--profile', type=Path, help='仅兼容明确指定的历史资料库或隔离测试；不自动读取全局配置')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('status')
    sub.add_parser('init').add_argument('folder')
    sub.add_parser('photos').add_argument('files', nargs='+')
    sub.add_parser('prepare').add_argument('config')
    sub.add_parser('sync').add_argument('run')
    save = sub.add_parser('save-cover')
    save.add_argument('run')
    save.add_argument('candidate_id')
    save.add_argument('source')
    select = sub.add_parser('select')
    select.add_argument('cover_id')
    args = parser.parse_args()
    profile = args.profile.expanduser() if args.profile else None
    if args.content_dir is not None:
        content = args.content_dir.expanduser().resolve(strict=True)
        if not content.is_dir():
            raise ValueError('当前内容目录必须是文件夹。')
        profile = content / '.cover-studio-profile.json'
        if profile.exists() and read(profile)['root'] != str(content / '我的封面工作室'):
            raise ValueError('内容配置指向其他目录；未改写或混入其他内容。')
        if args.command == 'init' and Path(args.folder).expanduser().resolve() != content:
            raise ValueError('初始化目标必须与当前内容目录一致。')
        if args.command in ('photos', 'prepare'):
            initialize(profile, content)
    if args.command == 'init':
        result = {'root': str(initialize(profile, args.folder))}
    else:
        root = library(profile)
        with locked(root):
            if args.command == 'status':
                result = {'root': str(root), 'photos': len(read(root / '照片集/照片索引.json')), 'covers': len(read(root / '封面索引.json'))}
            elif args.command == 'photos':
                result = add_photos(root, args.files)
            elif args.command == 'prepare':
                result = prepare(root, args.config)
            elif args.command == 'save-cover':
                result = save_cover(root, managed_run(root, args.run), args.candidate_id, args.source)
            elif args.command == 'sync':
                result = sync(root, managed_run(root, args.run))
            elif args.command == 'select':
                rows = read(root / '封面索引.json')
                row = next(r for r in rows if r['id'] == args.cover_id)
                row['selected'] = True
                write(root / '封面索引.json', rows)
                rebuild(root)
                result = {'selected': args.cover_id}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, StopIteration, subprocess.CalledProcessError) as exc:
        sys.exit(f'未完成：{exc}')
