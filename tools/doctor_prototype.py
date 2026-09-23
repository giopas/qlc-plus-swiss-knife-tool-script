"""Prototype of Doctor read-only checks (D002-D010) — baseline for tests/corpus."""
import os, sys, re, collections, xml.etree.ElementTree as ET
W='{http://www.qlcplus.org/Workspace}'; F='{http://www.qlcplus.org/FixtureDefinition}'
NONE='4294967295'
def qxf(path):
    r=ET.parse(path).getroot()
    chans={c.get('Name'):(c.findtext(F+'Group') or c.get('Preset') or '') for c in r.findall(F+'Channel')}
    modes={m.get('Name'):[c.text for c in sorted(m.findall(F+'Channel'),key=lambda c:int(c.get('Number')))] for m in r.findall(F+'Mode')}
    return r.findtext(F+'Model'),chans,modes
def run(path, defs):
    r=ET.parse(path).getroot(); out=collections.defaultdict(list)
    fx={}
    for x in r.findall(f'.//{W}Engine/{W}Fixture'):
        model,mode=x.findtext(W+'Model'),x.findtext(W+'Mode')
        names=defs.get(model,({},{}))[1].get(mode,[])
        fx[x.findtext(W+'ID')]=dict(name=x.findtext(W+'Name'),n=int(x.findtext(W+'Channels')),
            addr=int(x.findtext(W+'Address')),uni=x.findtext(W+'Universe'),names=names,groups=defs.get(model,({},{}))[0])
    # D009 DMX overlap
    used={}
    for i,f in fx.items():
        for c in range(f['addr'],f['addr']+f['n']):
            k=(f['uni'],c)
            if k in used: out['D009 DMX overlap'].append(f"{f['name']} ch{c+1} overlaps {fx[used[k]]['name']}")
            used[k]=i
    fns=r.findall(f'.//{W}Engine/{W}Function'); byid={}
    for f in fns:
        if f.get('ID') in byid: out['D002 duplicate function ID'].append(f.get('ID'))
        byid[f.get('ID')]=f
    refs=collections.defaultdict(set)  # fid -> referrers
    step_refs=set()
    for f in fns:
        for s in f.findall(W+'Step'):
            t=(s.text or '').strip()
            if not t: out['D004 empty step'].append(f"{f.get('Type')} '{f.get('Name')}'"); continue
            refs[t].add('fn:'+f.get('ID'))
            if f.get('Type')=='Chaser': step_refs.add(t)
            if t not in byid: out['D003 dangling step ref'].append(f"'{f.get('Name')}' → {t}")
        if f.get('Type')=='Chaser' and len([s for s in f.findall(W+'Step') if (s.text or '').strip()])<=1:
            out['D004 degenerate chaser (≤1 step)'].append(f"{f.get('ID')} '{f.get('Name')}'")
        if f.get('Type')=='Scene':
            vals=[v for v in f.findall(W+'FixtureVal')]
            if not any((v.text or '').strip() for v in vals):
                out['D004 empty scene'].append(f"{f.get('ID')} '{f.get('Name')}'")
            for v in vals:
                fid=v.get('ID'); fixture=fx.get(fid)
                if fixture is None: out['D003 scene refs missing fixture'].append(f"'{f.get('Name')}' → fixture {fid}"); continue
                nums=(v.text or '').split(',') if (v.text or '').strip() else []
                pairs=dict(zip(nums[0::2],nums[1::2]))
                if pairs and len(pairs)<fixture['n']:
                    out['D005 incomplete channel declaration'].append(f"'{f.get('Name')}' {fixture['name']}: {len(pairs)}/{fixture['n']}")
                risky=re.search(r'strob|flash|\*|punk|fx',f.get('Name'),re.I)
                for ch,val in pairs.items():
                    i=int(ch); cname=fixture['names'][i] if i<len(fixture['names']) else '?'
                    grp=fixture['groups'].get(cname,'')
                    if grp in('Shutter','Effect') and int(val)>0 and not risky:
                        out['D006 strobe/program channel ≠ 0'].append(f"'{f.get('Name')}' {fixture['name']} {cname}={val}")
    vc=r.find(f'.//{W}VirtualConsole'); wid=collections.Counter(); btn_fn=set()
    for e in vc.iter():
        if e.get('ID') is not None and e.tag.replace(W,'') in('Frame','SoloFrame','Button','Slider','CueList','Label','XYPad','Knob','Speed','Clock','AudioTriggers','Matrix'):
            wid[e.get('ID')]+=1
        if e.tag==W+'Button':
            fe=e.find(W+'Function'); fid=fe.get('ID') if fe is not None else NONE
            if fid==NONE: out['info caption-only buttons (label use)'].append(e.get('Caption','')[:30])
            else:
                btn_fn.add(fid); refs[fid].add('vc')
                if fid not in byid: out['D003 button → missing function'].append(f"'{e.get('Caption')}' → {fid}")
        if e.tag==W+'CueList':
            c=(e.findtext(W+'Chaser') or NONE).strip(); refs[c].add('vc')
            if c==NONE or c not in byid: out['D003 CueList without valid chaser'].append(e.get('Caption'))
        if e.tag==W+'Slider':
            for p in e.iter(W+'Function'): refs[p.get('ID') or p.text or ''].add('vc')
    for k,n in wid.items():
        if n>1: out['D002 duplicate VC widget ID'].append(f"{k} ×{n}")
    for fid in sorted(btn_fn & step_refs, key=int):
        if fid in byid and byid[fid].get('Type')=='Scene':
            out['D007 scene on VC button AND in chaser'].append(f"{fid} '{byid[fid].get('Name')}'")
    for fid,f in byid.items():
        if fid not in refs: out['warn unreferenced function'].append(f"{fid} {f.get('Type')} '{f.get('Name')}'")
    panic=[f for f in fns if re.search('panic reset',f.get('Name'),re.I)]
    if not panic: out['D008 no PANIC RESET function'].append('-')
    elif not any(p.get('ID') in btn_fn for p in panic): out['D008 PANIC RESET not on a VC button'].append('-')
    pages=[e.get('Caption') for e in vc if e.tag in (W+'Frame',W+'SoloFrame')]
    out['info VC pages (order)']=pages
    return fx,byid,out
if __name__=='__main__':
    defs={}
    for q in ['Generic-7Ch-RGB-PAR.qxf','Eurolite-LED-4C-12-Silent-Slim-Spot.qxf']:
        m,ch,mo=qxf(os.path.join(os.path.dirname(__file__),'..','tests','corpus',q)); defs[m]=(ch,mo)
    for w in sys.argv[1:]:
        fx,fns,out=run(w,defs)
        print(f"\n######## {w.split('/')[-1]}  fixtures={len(fx)} functions={len(fns)}")
        for k in sorted(out):
            v=out[k]; print(f"{k}: {len(v)}"); [print('    ',x) for x in v[:6]]
            if len(v)>6: print('     …')
