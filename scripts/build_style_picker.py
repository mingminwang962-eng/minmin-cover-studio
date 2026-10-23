#!/usr/bin/env python3
"""Build an offline style chooser. Recommendations are supplied by the assistant; no image generation."""
import argparse
import json
import os
import html
from urllib.parse import quote
from pathlib import Path
from PIL import Image, ImageOps

BASE = Path(__file__).resolve().parents[1]


def main():
    from console_utf8 import configure_output
    configure_output()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--recommendations', type=Path, help='JSON: title and recommendations [{group, reason}]')
    args = parser.parse_args()
    nav = json.loads((BASE / 'references/style-navigation.json').read_text(encoding='utf-8'))
    catalog = {s['id']: s for s in json.loads((BASE / 'references/style-catalog.json').read_text(encoding='utf-8'))}
    members = [m for g in nav['groups'] for m in g['members']]
    if len(set(members)) != len(members) or set(members) != set(catalog):
        raise ValueError('Navigation must map each catalog sample exactly once')
    if len({g['id'] for g in nav['groups']}) != len(nav['groups']):
        raise ValueError('Duplicate group id')
    config = json.loads(args.recommendations.read_text(encoding='utf-8')) if args.recommendations else {}
    recs = config.get('recommendations', [])
    known = {g['id'] for g in nav['groups']}
    if args.recommendations and (len(recs) != 3 or len({r.get('group') for r in recs}) != 3):
        raise ValueError('Supply three distinct recommended groups')
    for rec in recs:
        if rec.get('group') not in known or not isinstance(rec.get('reason'), str) or not rec['reason'].strip():
            raise ValueError('Each recommendation needs a valid group and a concrete reason')
    for s in catalog.values():
        source = BASE / s['preview']
        if not source.is_file():
            raise FileNotFoundError(source)
    out = args.output.expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    thumbnails = out.parent / 'thumbnails'
    thumbnails.mkdir(exist_ok=True)
    samples = {}
    for sid, s in catalog.items():
        dest = thumbnails / (sid + '.webp')
        with Image.open(BASE / s['preview']) as original:
            image = ImageOps.exif_transpose(original).convert('RGB')
            image.thumbnail((480, 640))
            image.save(dest, 'WEBP', quality=86)
        samples[sid] = {'originalName': s['label'], 'thumbnail': 'thumbnails/' + dest.name,
                        'original': quote(os.path.relpath(BASE / s['preview'], out.parent).replace(os.sep, '/'), safe='/')}
    data = {**nav, 'samples': samples, 'title': str(config.get('title', '')), 'recommendations': recs}
    encoded = json.dumps(data, ensure_ascii=False).replace('<', '\\u003c')
    template = (BASE / 'references/style-picker-template.html').read_text(encoding='utf-8')
    out.write_text(template.replace('__DATA__', encoded).replace('__ARCHIVE__', 'samples.html'), encoding='utf-8')
    cards = ''.join('<article><img loading="lazy" src="' + samples[sid]['original'] + '"><p>' + html.escape(catalog[sid]['label']) + '</p></article>' for sid in samples)
    (out.parent / 'samples.html').write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>57 张完整封面样例</title><style>body{font:16px system-ui;margin:24px;background:#f6f5f0}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:24px}img{width:100%}</style><a href="' + html.escape(out.name) + '">返回选择页</a><h1>57 张完整封面样例</h1><p>敏敏授权公开的设计参考；制作时使用你自己的照片和文字。</p><main>' + cards + '</main></html>', encoding='utf-8')
    print(f'Built {out}: {len(nav["groups"])} groups / {len(samples)} samples / {len(recs)} recommendations')


if __name__ == '__main__':
    main()
