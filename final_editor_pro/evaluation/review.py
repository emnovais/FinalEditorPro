"""Blind local review packets; identity map remains outside the public packet."""
import json
import secrets
from ave.core import json_bytes
from ..analysis.pipeline import within_project
from .schemas import HumanReview


def create_blind_packet(trials, output, dataset=None, input_dir=None):
    out=within_project(output)
    if out.exists(): raise FileExistsError('Review output must be new')
    out.mkdir(parents=True)
    mapping={}; cards=[]; grouped={}
    successful=[t for t in trials if t.status=='success' and t.condition!='report_cache']
    cases={c.case_id:c for c in dataset.cases} if dataset else {}
    secrets.SystemRandom().shuffle(successful)
    for t in successful:
        key=(t.case_id,t.input_sha256,t.response_sha256,t.format_normalized)
        if key in grouped:
            member=mapping[grouped[key]]; member['trial_ids'].append(t.trial_id)
            if t.model_id not in member['model_ids']: member['model_ids'].append(t.model_id)
            continue
        blind_id=secrets.token_hex(8)
        grouped[key]=blind_id
        mapping[blind_id]=dict(trial_id=t.trial_id,trial_ids=[t.trial_id],model_id=t.model_id,
            model_ids=[t.model_id],response_sha256=t.response_sha256)
        card=dict(blind_id=blind_id,case_id=t.case_id,response_sha256=t.response_sha256,
                  format_normalized=t.format_normalized,output=t.output.model_dump(mode='json'))
        if t.case_id in cases:
            card['human_reference']=dict(visual_description=cases[t.case_id].reference.visual_description,
                status=cases[t.case_id].reference.status,caveat='Full-clip notes, not exhaustive timed labels. Audio excluded.')
            if input_dir:
                from .dataset import load_input
                request,digest=load_input(within_project(input_dir)/(t.case_id+'.json'),cases[t.case_id])
                if digest!=t.input_sha256: raise ValueError('Review images differ from benchmark input')
                card['frames']=[f.model_dump(mode='json') for f in request.frames]
        cards.append(card)
    public=out/'blind'; public.mkdir()
    (public/'responses.json').write_bytes(json_bytes(cards))
    (out/'identity-map.private.json').write_bytes(json_bytes(mapping))
    # No model/latency/quantization metadata is included in HTML or public JSON.
    data=json.dumps(cards,ensure_ascii=False).replace('<','\\u003c')
    page='''<!doctype html><html lang="pt-BR"><meta charset="utf-8">
<title>Final Editor Pro — revisão cega</title><style>
body{font:16px system-ui;max-width:1000px;margin:2rem auto;padding:1rem;background:#10151d;color:#e8eef8}
section{border:1px solid #526076;padding:1rem;margin:1rem 0}pre{white-space:pre-wrap}label{display:block;margin:.5rem 0}
input,select,textarea,button{font:inherit;padding:.4rem}textarea{width:95%;min-height:5rem}</style>
<h1>Revisão cega local</h1><p>Avalie somente a evidência dos frames exibidos.
As notas humanas descrevem o clipe inteiro: não penalize eventos ausentes dos frames amostrados.
Consulte os frames e timestamps do caso no workspace antes de pontuar.
Não use outro modelo como juiz. Não abra identity-map.private.json antes de terminar.</p>
<p>Rubrica: 0 = incorreto/inútil; 1 = muitos problemas; 2 = parcial; 3 = bom com ressalvas;
4 = correto/útil na evidência disponível. Confiança do modelo não substitui sua revisão.
Respostas byte-idênticas para a mesma entrada compartilham uma nota; isso não cria múltiplos juízos humanos.</p>
<label>Revisor <input id="reviewer"></label><main id="cards"></main>
<button id="export">Gerar JSON para salvar no workspace</button><textarea id="result" readonly></textarea>
<script>const cards=DATA;
const criteria=['visual_precision','temporal_understanding','reliability','creative_utility'];
for(const c of cards){let s=document.createElement('section');s.dataset.id=c.blind_id;
let h=document.createElement('h2');h.textContent=c.case_id+' / '+c.blind_id;s.append(h);
if(c.human_reference){let p=document.createElement('pre');p.textContent=JSON.stringify(c.human_reference,null,2);s.append(p)}
for(const f of c.frames||[]){let fig=document.createElement('figure'),im=document.createElement('img');im.src='data:image/png;base64,'+f.data_base64;im.width=320;let caption=document.createElement('figcaption');caption.textContent='Frame '+f.frame_index+' / '+f.timestamp+' s';fig.append(im,caption);s.append(fig)}
let pre=document.createElement('pre');pre.textContent=JSON.stringify({format_normalized:c.format_normalized,output:c.output},null,2);s.append(pre);
for(const key of criteria){let label=document.createElement('label');label.textContent=key+' ';
let select=document.createElement('select');select.dataset.key=key;
for(const v of ['',0,1,2,3,4]){let op=document.createElement('option');op.value=v;op.textContent=v===''?'Selecione':v;select.append(op)}label.append(select);s.append(label)}
for(const key of ['checked_claims','unsupported_claims','uncertainty_notes','notes']){
let label=document.createElement('label');label.textContent=key+' ';let el=document.createElement('input');el.dataset.key=key;
if(key.includes('claims')){el.type='number';el.min=key==='checked_claims'?1:0}label.append(el);s.append(label)}document.querySelector('main').append(s)}
document.querySelector('#export').onclick=()=>{try{let reviewer=document.querySelector('#reviewer').value.trim();if(!reviewer)throw Error('Informe o revisor');let rows=[];
for(const section of document.querySelectorAll('section')){let c=cards.find(x=>x.blind_id===section.dataset.id),r={blind_id:c.blind_id,reviewer,reviewed_at:new Date().toISOString(),response_sha256:c.response_sha256};
for(const el of section.querySelectorAll('[data-key]')){if(el.value==='')throw Error('Preencha todos os campos');r[el.dataset.key]=criteria.includes(el.dataset.key)||el.type==='number'?Number(el.value):el.value}
if(r.unsupported_claims>r.checked_claims)throw Error('Contagem de afirmações inválida');rows.push(r)}document.querySelector('#result').value=JSON.stringify(rows,null,2)}catch(e){alert(e.message)}};
</script></html>'''.replace('DATA',data)
    (public/'review.html').write_text(page)
    return dict(unique_responses=len(cards),trial_responses=len(successful),blind_packet=str(public),identity_map=str(out/'identity-map.private.json'))


def load_reviews(reviews_path, identity_map):
    rows=json.loads(within_project(reviews_path).read_text())
    mapping=json.loads(within_project(identity_map).read_text())
    result={}
    for row in rows:
        review=HumanReview.model_validate(row)
        if review.blind_id not in mapping: raise ValueError('Unknown blind response')
        original=mapping[review.blind_id]
        if original['response_sha256']!=review.response_sha256: raise ValueError('Review response checksum mismatch')
        for trial_id in original.get('trial_ids',[original['trial_id']]):
            if trial_id in result: raise ValueError('Duplicate review for trial; explicit multi-review policy required')
            result[trial_id]=review
    return result
