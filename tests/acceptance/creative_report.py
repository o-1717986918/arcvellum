"""Readable evidence report; literary conclusions are supplied explicitly, never inferred from scores."""
from html import escape
import json
from pathlib import Path

from .creative_ledger import summarize_calls
from .creative_evidence import evidence_index

STYLE = """
:root{color-scheme:light;--ink:#25332e;--line:#d3dcd7;--accent:#355e50}
*{box-sizing:border-box}body{margin:0;background:#f0f2ee;color:var(--ink);font:15px/1.75 system-ui,'Microsoft YaHei',sans-serif}
main{max-width:1120px;margin:auto;padding:36px 26px}h1{font:600 30px/1.3 Georgia,serif}h2{margin-top:30px}
section{padding:20px 24px;margin:20px 0;background:#fff;border:1px solid var(--line)}a{color:var(--accent)}
small,.muted{color:#63736a}table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}
th,td{padding:9px;text-align:left;border-bottom:1px solid var(--line)}.table-wrap{overflow-x:auto}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:inherit}
details{margin:15px 0}summary{cursor:pointer;color:var(--accent)}.pair{display:grid;grid-template-columns:1fr 1fr;gap:22px}
.pair>div{min-width:0;border-top:2px solid var(--line)}@media(max-width:700px){main{padding:18px 12px}section{padding:14px}.pair{grid-template-columns:1fr}}
button{font:inherit;padding:6px 13px;border:1px solid var(--line);background:#eaf0ec;color:var(--accent);cursor:pointer}
textarea{display:block;width:100%;min-height:90px;font:inherit;border:1px solid var(--line);padding:8px;margin:10px 0}
"""

SCRIPT = """
document.querySelectorAll('[data-swap]').forEach(button=>button.onclick=()=>{
 const section=button.closest('section'), pair=section.querySelector('.pair'), nodes=pair.querySelectorAll('pre');
 const text=nodes[0].textContent;nodes[0].textContent=nodes[1].textContent;nodes[1].textContent=text;
 section.dataset.swapped=section.dataset.swapped==='true'?'false':'true';
 section.querySelector('[data-origin]').hidden=true;
});
document.querySelectorAll('[data-reveal]').forEach(button=>button.onclick=()=>{
 const section=button.closest('section'),origin=section.querySelector('[data-origin]');
 origin.textContent=section.dataset.swapped==='true'?'A 为编辑稿；B 为原稿。':'A 为原稿；B 为编辑稿。';origin.hidden=false;
});
document.querySelector('[data-export]').onclick=()=>{
 const rows=[...document.querySelectorAll('section[data-comparison]')].map(section=>({
  evidence:section.dataset.comparison,swapped:section.dataset.swapped==='true',source_revealed:!section.querySelector('[data-origin]').hidden,
  judgment:section.querySelector('textarea').value}));
 const url=URL.createObjectURL(new Blob([JSON.stringify({schema:'arcvellum/paired-reading/v1',reviewer:'user',rows},null,2)],{type:'application/json'}));
 const a=document.createElement('a');a.href=url;a.download='paired-reading.json';a.click();URL.revokeObjectURL(url);
};
"""


def readable_report(directory: Path):
    sections = []
    index = evidence_index(directory)
    for path in sorted(directory.glob("*/*/acceptance.json")):
        report = json.loads(path.read_text(encoding="utf-8"))
        cost = summarize_calls(path.parent / "calls.jsonl")
        report["cost"] = cost
        sections.append(case_section(directory, path, report))
    for path in sorted(directory.glob("*/*/tone-comparison*.json")):
        sections.append(tone_section(directory, path))
    for path in sorted(directory.glob("*/*/role-comparison-*context.json")):
        sections.append(role_section(directory, path))
    if (directory/'measured-comparison.json').is_file():
        sections.append(measured_section(directory))
    judgment = directory / "judgments.md"
    analysis = "<section><h2>文学细读</h2><pre>" + escape(judgment.read_text(encoding="utf-8")) + "</pre></section>" if judgment.is_file() else "<p>文学结论待细读，统计与流程结果已单独列出。</p>"
    html = ('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>ArcVellum 创作验收</title><style>' + STYLE + '</style><main><h1>创作链路验收 · 2026-10-07</h1>'
        '<p>看作品怎样成立，也看每次修改花了什么。以下保留真实稿件、过程状态和调用记录。</p>'
        '<p class="muted">模型与本 Agent 的阅读判断分别署明；费用为运行时模型目录估算，服务商实际账单未核验。未完成的场景按原状态呈现。</p>'
        + '<p>实际调用 ' + str(index['invocations']) + ' 次；已报告估算 $' + f"{index['reported_cost_usd']:.6f}"
        + '；未报告用量或费用记录 ' + str(index['missing_usage']) + ' 项。' + link(directory,directory/'evidence-index.json','总台账与素材取舍') + '</p>'
        + analysis + '<button data-export>导出你的成对评审</button>' + ''.join(sections) + '</main><script>' + SCRIPT + '</script></html>')
    destination = directory / "report.html"
    destination.write_text(html, encoding="utf-8")
    return destination


def link(directory, path, label):
    relative = Path(path).resolve().relative_to(directory.resolve()).as_posix()
    return f'<a href="{escape(relative, quote=True)}">{escape(label)}</a>'


def case_section(directory, path, report):
    cost = report["cost"]
    rows, prose = [], []
    for scene in report["scenes"]:
        rows.append(f'<tr><td>{escape(scene["scene_id"])}</td><td>{escape(scene.get("status", "未开始"))}</td><td>{scene.get("revisions",0)}</td><td>{scene.get("chars", "—")}</td></tr>')
        if scene.get("prose_path"):
            p = Path(scene["prose_path"])
            p.resolve().relative_to(directory.resolve())
            prose.append('<details><summary>正文与交接证据 · ' + escape(scene['scene_id']) + '</summary><pre>'
                + escape(p.read_text(encoding="utf-8")) + '</pre>' + link(directory,p,'原稿文件') + '</details>')
        failure = scene.get("test_stop") or scene.get("failure_reason") or scene.get("error")
        if not failure:
            failure = next((step.get('message','') for step in reversed(scene.get('steps',[])) if step.get('blocked')), '')
        if failure:
            prose.append('<p>' + escape(failure) + '</p>')
    costs = ''.join(f'<tr><td>{escape(key)}</td><td>{row["calls"]}</td><td>{row["tokens"]}</td><td>{row["seconds"]:.1f}s</td><td>'
        + (f'已报告 ${row["cost_usd"]:.6f}；另有 {row["missing_usage"]} 次未报告' if row['missing_usage'] else f'${row["cost_usd"]:.6f}') + '</td></tr>'
        for key,row in cost['groups'].items())
    return ('<section><h2>' + escape(report['case_id'] + ' · ' + report['variant']) + '</h2><p>状态：'
        + escape(report.get('status','运行中')) + ' · ' + link(directory,path,'结构化记录') + '</p>'
        + ('<p>' + escape(report['error']) + '</p>' if report.get('error') else '')
        + '<div class="table-wrap"><table><tr><th>场景</th><th>状态</th><th>返修</th><th>字符</th></tr>' + ''.join(rows) + '</table></div>'
        + '<details><summary>调用与费用 · 已报告 $' + f'{cost["reported_cost_usd"]:.6f}' + '</summary><div class="table-wrap"><table><tr><th>阶段与角色</th><th>调用</th><th>token</th><th>耗时</th><th>估算费用</th></tr>'
        + costs + '</table></div><p>缓存读写、输入与输出 token 分解见总台账 token_details；缺失记录没有按零消费处理。</p></details>' + ''.join(prose) + '</section>')


def tone_section(directory, path):
    data = json.loads(path.read_text(encoding="utf-8"))
    from hashlib import sha256
    swapped = bool(sha256(path.name.encode()).digest()[0] % 2)
    a, b = (data['cleaned'],data['original']) if swapped else (data['original'],data['cleaned'])
    body = '<section data-comparison="' + escape(path.relative_to(directory).as_posix(),quote=True) + '" data-swapped="' + str(swapped).lower() + '"><h2>同稿去 AI 味对照 · ' + escape(data['scene_id']) + ' · '+escape(data.get('phase','原始对照'))+' · 第'+str(data.get('source_revision','—'))+'稿</h2>'
    body += '<p>采纳 ' + str(len(data['accepted'])) + ' 处；保留原文 ' + str(len(data['rejected'])) + ' 处。</p>'
    body += '<button data-swap>交换展示顺序</button> <button data-reveal>显示版本来源</button><p data-origin hidden></p>'
    body += '<div class="pair"><div><h3>版本 A</h3><pre>' + escape(a) + '</pre></div><div><h3>版本 B</h3><pre>' + escape(b) + '</pre></div></div>'
    body += '<label>你的阅读判断：自然程度、文风强度、意义保留<textarea placeholder="写下成立之处、主要缺陷与原文证据"></textarea></label>'
    return body + link(directory,path,'原始对照及计量结果') + '<details><summary>逐处编辑记录（含版本来源）</summary><pre>' + escape(json.dumps({'accepted':data['accepted'],'rejected':data['rejected']},ensure_ascii=False,indent=2)) + '</pre></details></section>'


def role_section(directory,path):
    data=json.loads(path.read_text(encoding='utf-8'))
    rows=[]
    for session in data['sessions']:
        turns=''.join('<p><b>刺激：</b>'+escape(turn['message'])+'</p><pre>'+escape(turn['answer'])+'</pre>' for turn in session['turns'])
        rows.append('<details><summary>'+escape(session['target'])+' · '+str(len(session['turns']))+' 轮</summary>'+turns+'</details>')
    title='明确身份上下文' if 'explicit-context' in path.stem else '默认上下文'
    return '<section><h2>独立角色对话 · '+title+'</h2><p>主创已有取材记录摘要保持一致：'+str(data['main_history_unchanged'])+'。'+link(directory,path,'已知档案与完整对话')+'</p>'+''.join(rows)+'</section>'


def measured_section(directory):
    path=directory/'measured-comparison.json'
    data=json.loads(path.read_text(encoding='utf-8'))
    rows=[]
    for version in data['rows']:
        for target in version['measure']['targets']:
            if target['enabled']:
                rows.append('<tr><td>'+escape(version['variant'])+' r'+str(version['revision'])+'</td><td>'+escape(target['label'])+'</td><td>'+str(target['observed'])+'</td><td>'+str(target['min'])+'–'+str(target['max'])+'</td><td>'+str(round(target['distance'],6))+'</td></tr>')
    return '<section><h2>计量挂载后的实际正文</h2><p>相同档案、人格、意图及模型；提示词与整理代码有所修订，结果用于描述变化。画像来自两篇模型原稿小样。依存句法未测量，其他未启用参数列在原始记录中。</p>'+link(directory,path,'完整测量及缺测状态')+'<div class="table-wrap"><table><tr><th>版本</th><th>参数</th><th>实测</th><th>目标</th><th>超界距离</th></tr>'+''.join(rows)+'</table></div></section>'
