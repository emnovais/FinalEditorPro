"""Reference annotation form. It contains no model answers or prefilled labels."""
import json
from .schemas import CATEGORIES
from ..analysis.pipeline import within_project


def create_annotation_form(dataset, output):
    out=within_project(output)
    if out.exists(): raise FileExistsError('Annotation form already exists')
    # Human facts are kept empty/pending rather than copied from any AI output.
    data=json.dumps(dataset.model_dump(mode='json'),ensure_ascii=False).replace('<','\\u003c')
    categories=json.dumps(CATEGORIES)
    page='''<!doctype html><meta charset="utf-8"><title>Referência humana — Final Editor Pro</title>
<style>body{font:16px system-ui;max-width:1000px;margin:2rem auto;padding:1rem}section{border:1px solid #aaa;padding:1rem;margin:1rem 0}label{display:block;margin:.5rem}textarea{width:95%;min-height:6rem}input,select,button{font:inherit}</style>
<h1>Anotações humanas de referência</h1><p>Observe o vídeo original e registre somente fatos verificáveis.
Não use respostas de modelos para criar o gabarito. Intervalos são [start_frame,end_frame),
relativos à fonte; tempo em segundos = frame/fps. Grupos iguais não podem aparecer nos dois splits.</p>
<label>Anotador <input id="annotator"></label><main></main><button id="export">Gerar JSON para salvar no workspace</button><textarea id="result" readonly></textarea>
<script>let dataset=DATA;const categories=CATS;
for(const c of dataset.cases){let s=document.createElement('section');s.dataset.id=c.case_id;
let h=document.createElement('h2');h.textContent=c.case_id+' — '+c.original_path;s.append(h);
let p=document.createElement('p');p.textContent='fps '+c.fps+'; frames '+c.start_frame+' até '+c.end_frame;s.append(p);
for(const [key,value] of [['source_group',c.source_group],['evidence_notes','']]){let l=document.createElement('label');l.textContent=key+' ';let i=document.createElement('input');i.dataset.key=key;i.value=value;l.append(i);s.append(l)}
let split=document.createElement('select');split.dataset.key='split';for(const v of ['unassigned','development','evaluation']){let o=document.createElement('option');o.value=v;o.textContent=v;split.append(o)}s.append(split);
for(const cat of categories){let l=document.createElement('label');let i=document.createElement('input');i.type='checkbox';i.dataset.category=cat;l.append(i,cat);s.append(l)}
for(const key of ['objects','actions','events']){let l=document.createElement('label');l.textContent=key+' — lista JSON: [{"label":"...","aliases":[],"start_frame":0,"end_frame":1}]';let t=document.createElement('textarea');t.dataset.key=key;t.value='[]';l.append(t);s.append(l)}
for(const key of ['objects_exhaustive','verified']){let l=document.createElement('label');let i=document.createElement('input');i.type='checkbox';i.dataset.key=key;l.append(i,key);s.append(l)}document.querySelector('main').append(s)}
document.querySelector('#export').onclick=()=>{try{const annotator=document.querySelector('#annotator').value.trim();if(!annotator)throw Error('Informe o anotador');let result=JSON.parse(JSON.stringify(dataset));result.frozen=false;
for(const section of document.querySelectorAll('section')){let c=result.cases.find(c=>c.case_id===section.dataset.id);c.source_group=section.querySelector('[data-key=source_group]').value.trim();c.split=section.querySelector('[data-key=split]').value;c.categories=[...section.querySelectorAll('[data-category]:checked')].map(i=>i.dataset.category);
const verified=section.querySelector('[data-key=verified]').checked;let r={status:verified?'verified':'pending',annotator:verified?annotator:null,verified_at:verified?new Date().toISOString():null,evidence_notes:section.querySelector('[data-key=evidence_notes]').value,objects_exhaustive:section.querySelector('[data-key=objects_exhaustive]').checked};
for(const key of ['objects','actions','events'])r[key]=JSON.parse(section.querySelector('[data-key='+key+']').value);if(verified&&!r.evidence_notes.trim())throw Error('Verificação requer evidência');c.reference=r}
document.querySelector('#result').value=JSON.stringify(result,null,2)}catch(e){alert(e.message)}};</script>'''.replace('CATS',categories).replace('DATA',data)
    out.parent.mkdir(parents=True,exist_ok=True); out.write_text(page)
    return out
