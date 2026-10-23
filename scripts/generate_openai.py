#!/usr/bin/env python3
"""Generate one planned candidate with the user's OpenAI account and archive it."""
import argparse
import base64
import json
import os
from pathlib import Path
import tempfile
import urllib.error
import urllib.request

from asset_library import inside, locked, managed_run, read, save_cover, write, digest

ENDPOINT = 'https://api.openai.com/v1/images/edits'


def make_payload(run, candidate_id, model):
    from PIL import Image
    plan = read(run / 'plan.json')
    candidate = next(c for c in plan['candidates'] if c['id'] == candidate_id)
    if inside(run, candidate['image']).exists():
        raise FileExistsError('该候选已有图片，请先同步或新建修改轮次；未重复请求付费生图。')
    prompt = inside(run, candidate['prompt_file'])
    if digest(prompt) != candidate['prompt_sha256']:
        raise ValueError('提示词与计划不一致，请重新编译本轮。')
    reference = Path(plan['reference_path'])
    if digest(reference) != plan['reference_sha256']:
        raise ValueError('参考照与计划不一致。')
    with Image.open(reference) as image:
        mime = Image.MIME.get(image.format)
        image.verify()
    if mime not in ('image/jpeg','image/png','image/webp'):
        raise ValueError('OpenAI 接口需要 PNG、JPEG 或 WebP 参考照；请使用另存副本。')
    if reference.stat().st_size > 14 * 1024 * 1024:
        raise ValueError('参考照超过本适配器的 14 MiB 限制，请另存较小副本，原照保留。')
    return {'model':model, 'images':[{'image_url':'data:'+mime+';base64,'+base64.b64encode(reference.read_bytes()).decode()}],
            'prompt':prompt.read_text(encoding='utf-8'), 'size':'1536x2048', 'quality':'high', 'output_format':'png', 'n':1}


def generate(run, candidate_id, model, key, opener=urllib.request.urlopen):
    # Caller holds the library lock; no automatic retry after an uncertain paid request.
    payload = make_payload(run, candidate_id, model)
    request = urllib.request.Request(ENDPOINT, data=json.dumps(payload).encode(),
                                     headers={'Authorization':'Bearer '+key, 'Content-Type':'application/json'}, method='POST')
    try:
        with opener(request, timeout=300) as response:
            result = json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f'OpenAI 生图请求失败，HTTP {exc.code}；未自动重试或更换模型。') from None
    images = result.get('data') or []
    encoded = images[0].get('b64_json') if images else None
    if not encoded:
        raise ValueError('接口未返回图片；不能标为已生成。')
    data = base64.b64decode(encoded, validate=True)
    # Keep received output on disk even if later archive/index updates fail.
    with tempfile.NamedTemporaryFile(dir=run, prefix='received-', suffix='.png', delete=False) as f:
        received = Path(f.name)
        f.write(data)
    write(run / ('receipt-' + candidate_id + '.json'), {'provider':'openai','model':model,
          'created':result.get('created'), 'usage':result.get('usage'), 'received_file':received.name})
    saved = save_cover(run.parent.parent, run, candidate_id, received)
    received.unlink()
    return saved


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--content-dir', type=Path, required=True)
    p.add_argument('--run', type=Path, required=True)
    p.add_argument('--candidate', required=True)
    p.add_argument('--model', default=os.environ.get('OPENAI_IMAGE_MODEL'))
    p.add_argument('--dry-run', action='store_true')
    args = p.parse_args()
    if not args.model:
        p.error('请由 Agent 使用用户已选模型，传 --model 或设置 OPENAI_IMAGE_MODEL；不自动替用户选择付费模型。')
    root = args.content_dir.expanduser().resolve(strict=True) / '我的封面工作室'
    run = managed_run(root, args.run)
    with locked(root):
        if args.dry_run:
            payload = make_payload(run, args.candidate, args.model)
            print(json.dumps({'status':'request_validated','model':payload['model'],'size':payload['size'],
                              'candidate':args.candidate,'network_request':False},ensure_ascii=False))
            return
        key = os.environ.get('OPENAI_API_KEY')
        if not key:
            p.error('未配置 OPENAI_API_KEY；优先检查 Agent 自带生图工具。密钥不写入项目。')
        print(json.dumps(generate(run, args.candidate, args.model, key),ensure_ascii=False))

if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, StopIteration, RuntimeError) as exc:
        raise SystemExit('未完成：' + str(exc))
