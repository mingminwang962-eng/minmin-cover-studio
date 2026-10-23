#!/usr/bin/env python3
"""Compile a cover plan and an offline wall; never invoke an image backend."""
import argparse
import hashlib
import html
import json
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
VERSION = '2.2.1-title-design'


def save_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def compile_prompt(config, style, scene, design=None, visual_brief=None):
    reference = (
        'Exactly one reference image is supplied. Preserve the actual photographed face, expression, visible clothing and source pixels. Use cropping, masking and graphic typography; do not regenerate or beautify the face, invent a pose or extend the body.'
        if style['mode'] == 'photo' else
        'Exactly one identity reference is supplied. Preserve this real person\'s recognizable facial geometry, age, hairstyle and natural skin texture. A new body, pose and scene may be created; do not substitute a generic model face or over-retouch them.'
    )
    dimensions = '\n'.join(f'{key}: {value}' for key, value in (design or {}).items() if value)
    return '\n\n'.join([
        'Create a Chinese personal social-media cover. Canvas: 3:4 vertical. Deliver one cover.',
        'REFERENCE\n' + reference,
        'PERSON COLOR\nKeep the person a natural full-color photograph. Preserve original skin, hair and clothing colors. Never apply grayscale, monochrome, duotone, colored tint, painterly rendering or material effects to the person. Background and graphic treatments must not spill onto the person.',
        'CONTENT\n' + config['topic'],
        *(['TITLE TO IMAGE\n' + json.dumps(visual_brief, ensure_ascii=False) + '\nMake the whole composition express this meaning: align graphic relationships, space, material, palette and type with this brief. Do not merely attach topic-related props to a generic background. Treat the brief as design instructions, not extra text to render.'] if visual_brief else []),
        'EXACT HEADLINE\n' + '\n'.join(config['title_lines']) + '\nRender only these headline lines verbatim. No extra labels, subtitles or filler copy.',
        'LARGE TYPE\nThe headline is the first visual anchor: oversized, bold, high-contrast Chinese type, immediately readable at 200px image width. Keep every main line large; never shrink a long line into a small caption. Use the available width with comfortable edge clearance. Emphasize only ' + '、'.join(config['focus_terms']) + '. Contrast may use color, weight, stroke or a simple block where needed. The face and key words remain unobstructed. No cropped or missing glyphs.',
        'DIRECTION\n' + style['layout'],
        'DESIGN DECISIONS\n' + (dimensions or 'Derive typography, composition, palette, material and decoration from the supplied photo, wording and scene. No fixed sample layout.'),
        'PHOTO AND MEANING\nUse the photographed background when it already supports the title. If clutter competes, prefer local contrast treatment; remove or replace the background only when the requested photo mode permits it. Choose decoration for the literal meaning or emotional tone of this headline; omit it when type alone communicates. Sample layouts and palettes are references, not mandatory arrangements.',
        'CONTENT AND ELEMENTS\nEvery added element must express this specific content or its emotional meaning. For explanatory concepts, prefer a clear visual relationship or transformation over loosely related stock props. Do not force a machine, action or input-output diagram onto lifestyle or opinion covers. Preserve the photographed pose; do not invent an action to make a metaphor work. Omit unrelated ornaments. No hand-drawn illustration, marker doodles or brush lettering. Keep photo, headline and graphic elements integrated; no hard split photo/text panels.',
        'CONFIRMED DESIGN\n' + (json.dumps(config['locked_design'], ensure_ascii=False) + '\nThese are user-confirmed properties. Preserve them exactly; only properties explicitly unlocked for this revision may change.' if config.get('locked_design') else 'No prior confirmed design supplied. Do not infer locked colors, layout or props from a sample.'),
        'SCENE\n' + scene,
        'FINISH\nNatural human likeness and a decisive image-text hierarchy. Use only elements that explain the content; no mandatory prop count. Avoid stock-ad gloss, random English, watermarks, extra people, malformed anatomy and invented Chinese text.'
    ]) + '\n'


def build_wall(out, plan):
    esc = html.escape
    cards = []
    for c in plan['candidates']:
        image_path = out / c['image']
        review = c.get('review') or '尚未进行人工检查；未获用户选定。'
        status = '已生成 · 待检查' if image_path.exists() else '待生成'
        if c.get('review'):
            status = c.get('status', '已检查 · 待选择')
        picture = f'<a href="{esc(c["image"])}"><img src="{esc(c["image"])}" alt="{esc(c["label"])}" loading="lazy"></a>' if image_path.exists() else '<div class="placeholder">待生成样图</div>'
        prompt = (out / c['prompt_file']).read_text(encoding='utf-8')
        cards.append(f'<article data-family="{esc(c["family"])}"><div class="sample">{picture}</div><div class="body"><small>{esc(c["id"])} · {esc(c["version"])}</small><h2>{esc(c["label"])}</h2><p>{esc(c["family"])} · {"原照片排版" if c["mode"] == "photo" else "身份参考创意场景"}</p><p>适用：{esc(c["suitable"])}</p><p class="status">{esc(status)}</p><p>{esc(review)}</p><details><summary>完整提示词与版本记录</summary><p>参考照：{esc(plan["reference_asset_id"])}</p><p>提示词 SHA256：{esc(c["prompt_sha256"])}</p><a href="{esc(c["prompt_file"])}">提示词原文件</a><pre>{esc(prompt)}</pre></details></div></article>')
    page = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>本轮封面作品</title><style>
*{box-sizing:border-box}body{margin:0;background:#f4f2ec;color:#20241f;font:16px/1.65 -apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif}header,main{max-width:1280px;margin:auto;padding:28px}h1{font-size:36px;margin:0}header p{max-width:850px}.filters{display:flex;flex-wrap:wrap;gap:10px}button{font:inherit;border:1px solid #c7cbc2;border-radius:24px;padding:8px 20px;background:#fff;cursor:pointer}button.active{background:#203e32;color:white}.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:24px}article{background:white;border:1px solid #deded3;border-radius:14px;overflow:hidden}.sample{background:#e8e8df}.sample img{width:100%;display:block;aspect-ratio:3/4;object-fit:contain}.placeholder{aspect-ratio:3/4;display:grid;place-items:center;color:#64695e}.body{padding:20px}h2{font-size:23px;margin:4px 0}small{color:#5e655a}.status{font-weight:700;color:#26533f}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px}a{color:#285644}summary{cursor:pointer;font-weight:600}[hidden]{display:none!important}.thumb .sample img,.thumb .placeholder{width:200px;max-width:100%;margin:auto}@media(max-width:900px){.grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:600px){.grid{grid-template-columns:1fr}header,main{padding:18px}}
</style><header><small>敏敏封面工作室 · 本轮候选</small><h1>大字醒目，画面各有表达</h1><p>TITLE</p><p>本轮按照片与内容选择设计方向，构图不固定。原照排版保留照片；仅在明确要求时使用新创意人物场景。样图是探索候选，审美与人物相似度仍需你选择。旧版样图不混入此墙。</p><div class="filters"><button class="active" data-filter="全部">全部</button><button data-filter="真人大字">真人大字</button><button data-filter="编辑大字">编辑大字</button><button data-filter="创意大字">创意大字</button><button id="thumb">切换 200px 缩略图检查</button></div></header><main class="grid">CARDS</main><script>
document.querySelectorAll('[data-filter]').forEach(b=>b.onclick=()=>{document.querySelectorAll('[data-filter]').forEach(x=>x.classList.toggle('active',x===b));document.querySelectorAll('article').forEach(a=>a.hidden=b.dataset.filter!=='全部'&&a.dataset.family!==b.dataset.filter)});document.getElementById('thumb').onclick=()=>document.body.classList.toggle('thumb');
</script></html>'''
    (out / '风格墙.html').write_text(page.replace('TITLE', esc(plan['title'])).replace('CARDS', ''.join(cards)), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('config', type=Path)
    parser.add_argument('--wall-only', action='store_true')
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding='utf-8'))
    out = Path(config['output_dir']).expanduser().resolve()
    if args.wall_only:
        build_wall(out, json.loads((out / 'plan.json').read_text(encoding='utf-8')))
        return
    lines = config['title_lines']
    if not 2 <= len(lines) <= 3 or ''.join(lines) != config['title']:
        raise ValueError('title_lines must contain 2–3 semantic lines and preserve the complete title')
    if not 1 <= len(config['focus_terms']) <= 2 or any(t not in config['title'] for t in config['focus_terms']):
        raise ValueError('focus_terms must contain 1–2 terms present in the title')
    reference = Path(config['reference_path']).expanduser()
    if not reference.is_absolute() or not reference.is_file():
        raise ValueError('reference_path must be an existing absolute file path')
    templates = {s['id']: s for s in json.loads((BASE / 'references/styles.json').read_text(encoding='utf-8'))}
    templates.update({s['id']: s for s in json.loads((BASE / 'references/style-catalog.json').read_text(encoding='utf-8'))})
    selected = config['styles']
    if not selected or len({s['id'] for s in selected}) != len(selected):
        raise ValueError('select at least one style; duplicate style ids are not allowed')
    for selection in selected:
        if selection['id'] not in templates or not selection.get('scene', '').strip():
            raise ValueError('each style requires a known id and a topic-specific scene')
        if 'visual_brief' in selection:
            brief = selection['visual_brief']
            if not isinstance(brief, dict) or any(not isinstance(brief.get(key), str) or not brief[key].strip() for key in ('title_meaning', 'visual_expression', 'overall_design')):
                raise ValueError('visual_brief requires nonempty title_meaning, visual_expression and overall_design strings')
    if (out / 'plan.json').exists():
        raise FileExistsError('plan already exists; use a new round directory or --wall-only')
    (out / 'prompts').mkdir(parents=True, exist_ok=True)
    (out / '候选').mkdir(exist_ok=True)
    plan = {'schema':'minmin-cover-v2/plan', 'version':VERSION, 'created_at':datetime.now().astimezone().isoformat(), 'title':config['title'], 'topic':config['topic'], 'reference_asset_id':config['reference_asset_id'], 'reference_path':str(reference), 'reference_sha256':hashlib.sha256(reference.read_bytes()).hexdigest(), 'candidates':[]}
    if config.get('locked_design'):
        plan['locked_design'] = config['locked_design']
    tasks = []
    for selection in selected:
        s = templates[selection['id']]
        prompt = compile_prompt(config, s, selection['scene'], selection.get('design'), selection.get('visual_brief'))
        prompt_file = f'prompts/{s["id"]}.txt'
        image_file = f'候选/{s["id"]}.png'
        (out / prompt_file).write_text(prompt, encoding='utf-8')
        plan['candidates'].append({**s, 'version':VERSION, 'scene':selection['scene'], 'design':selection.get('design', {}), 'prompt_file':prompt_file, 'prompt_sha256':hashlib.sha256(prompt.encode()).hexdigest(), 'image':image_file, 'status':'pending_generation', 'review':None})
        if 'visual_brief' in selection:
            plan['candidates'][-1]['visual_brief'] = selection['visual_brief']
        tasks.append({'id':s['id'], 'promptFiles':[prompt_file], 'image':image_file, 'ref':[str(reference)], 'ar':'3:4', 'quality':'2k', 'provider':'openai'})
    save_json(out / 'plan.json', plan)
    save_json(out / 'batch.json', {'jobs':3, 'tasks':tasks})
    build_wall(out, plan)
    print(f'Compiled {len(tasks)} candidates: {out}')


if __name__ == '__main__':
    main()
