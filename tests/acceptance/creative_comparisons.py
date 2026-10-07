"""Post-hoc same-prose editing and independent character turns over real scene artifacts."""
from hashlib import sha256
import json
from pathlib import Path

from literary_engineering_studio.persistence.scene_transactions import SceneTransactionRepository
from literary_engineering_studio.runtime.role_conversation import RoleConversationGateway
from literary_engineering_studio.runtimes.pi_scene_transaction import PiSceneTransactionRuntime
from literary_engineering_studio.runtimes.pi_scene_payload import creative_result_from_payload

from .creative_runner import configured_container, write_json
from .creative_ledger import AcceptanceGateway, summarize_calls


def tone_comparison(config_path, directory, case_id, variant, scene_id, revision=None, comparison_tag='same-prose'):
    folder=directory/case_id/variant
    container=configured_container(config_path,folder,tone=False)
    try:
        repository=SceneTransactionRepository(container.ports.persistence.unit_of_work)
        project=folder/'work'
        tx=repository.latest_for_scene(str(project),scene_id)
        if not tx or not tx.creative_result:
            raise ValueError('需要实际主创已经生成的场景稿。')
        original=tx.creative_result if revision is None else creative_result_from_payload(json.loads(
            (folder/'evidence'/scene_id/f'result-{revision}.json').read_text(encoding='utf-8')))
        data=folder/'tone-comparison-data'/scene_id
        config=dict(container.config)
        config['application']={**container.config['application'],'less_ai_tone_experiment':{'enabled':True}}
        gateway=AcceptanceGateway(RoleConversationGateway(config,data_root=data/'runs'),data,max_calls=8,max_minutes=10)
        gateway.phase='same-prose-edit'
        adapter=PiSceneTransactionRuntime(config,project_root=project,data_root=data,gateway=gateway)
        key='comparison-'+tx.transaction_id
        source=folder/'data/scene-transactions'/tx.transaction_id
        for name in ('creator_style_briefing.json','creator_stylometry_snapshot.json'):
            if (source/name).is_file():
                write_json(adapter._cache_path(key,name),json.loads((source/name).read_text(encoding='utf-8')))
        mount=adapter._tone_mount(key,tx.brief)
        preserved=None
        for path in adapter._cache_path(key,'less-ai-tone').glob('*/editor-answer.md'):
            if (path.parent/'original.md').read_text(encoding='utf-8')==original.prose:
                preserved=path.read_text(encoding='utf-8');break
        cleaned=adapter._tone_result(key,tx.brief,original,mount,comparison_tag,preserved_editor_answer=preserved)
        paths=[path for path in adapter._cache_path(key,'less-ai-tone').glob('*/report.json')
            if json.loads(path.read_text(encoding='utf-8')).get('phase')==comparison_tag]
        path=paths[0]
        report=json.loads(path.read_text(encoding='utf-8'))
        report.update(source_transaction=tx.transaction_id,source_status=tx.status.value,
            source_revision=tx.revision_attempts if revision is None else revision,
            cost=summarize_calls(gateway.path),original_measure=container.services.stylometry.measure(project,original.prose),
            cleaned_measure=container.services.stylometry.measure(project,cleaned.prose),style=mount['style'])
        write_json(folder/f'tone-comparison-{scene_id}-{comparison_tag}.json',report)
        return report
    finally:
        container.shutdown()


def independent_roles(config_path,directory,case_id,variant,role_context=''):
    folder=directory/case_id/variant
    container=configured_container(config_path,folder)
    service=container.services.character_chat
    gateway=AcceptanceGateway(service.conversation.gateway,folder/'role-comparison-data',max_calls=16,max_minutes=15)
    gateway.phase='independent-role-chat'
    service.conversation.gateway=gateway
    project=folder/'work'; report={'schema':'arcvellum/creative-role-acceptance/v1','sessions':[]}
    try:
        root=folder/'data/scene-transactions'
        before=_card_history_hashes(root)
        cards={}
        for path in sorted(root.glob('*/v2/calls/*.json')):
            row=json.loads(path.read_text(encoding='utf-8'))
            request=row.get('request',{})
            if request.get('kind')=='actor' and request.get('character_card'):
                cards.setdefault(request['target'],(request['character_card'],row.get('attachments',[])))
        if len(cards)<2:
            raise ValueError('角色对照需要两位实际加载过的角色卡。')
        for target,(card,sources) in cards.items():
            attachments=[{'path':item['path'],'knowledge':'known',
                'start_line':item.get('line_range',[None,None])[0],
                'end_line':item.get('line_range',[None,None])[1]}
                for item in sources if item.get('knowledge')=='known']
            session=service.create(project,target=target,card=card,attachments=attachments,
                context=role_context or '用户独立交流，当前在作品中的同一地点，另行开始一段上下文。')
            for stimulus in ('眼前的事忙完了一点，我想听听你自己现在最惦记什么。',
                             '我不同意你的办法。你愿意把自己的理由讲具体一点吗？',
                             '刚才我话说急了。现在我把手头这件东西放回你面前，想和你一起解决。',
                             '新消息：离开的时间延后一天，这是我刚亲自确认后告诉你的。你现在怎样安排眼前的事？'):
                session=service.ask(project,session['session_id'],stimulus,timeout=180)
            report['sessions'].append({'target':target,'session_id':session['session_id'],
                'known_archive':session['known_archive'],'turns':session['turns']})
        current=_card_history_hashes(root)
        report.update(main_history_unchanged=all(current.get(path)==digest for path,digest in before.items()),
            checked_main_files=len(before),cost=summarize_calls(gateway.path))
        tag='explicit-context' if role_context else 'default-context'
        write_json(folder/f'role-comparison-{tag}.json',report)
        return report
    finally:
        container.shutdown()


def _card_history_hashes(root):
    return {str(path.relative_to(root)):sha256(path.read_bytes()).hexdigest()
        for path in root.glob('*/v2/calls/*.json')}
