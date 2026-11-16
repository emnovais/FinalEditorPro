"""Reproducible two-run local benchmark. Requires already approved runtime/assets."""
import argparse
import json
import subprocess
import threading
import time
from .runtime import local_server
from .pipeline import analyze, within_project
from .schemas import AnalysisConfig
from ..ai.config import load_config
from ..ai.adapters import build_providers
from ..ai.privacy import PrivacyPolicy
from ..ai.router import ProcessingRouter, OperationJournal
from ave.core import json_bytes


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('media'); p.add_argument('--output',required=True)
    p.add_argument('--runtime-manifest',required=True); p.add_argument('--global-config',required=True)
    p.add_argument('--analysis-config',required=True)
    args=p.parse_args()
    out=within_project(args.output); out.mkdir(parents=True)
    processing=load_config(within_project(args.global_config))
    config=AnalysisConfig.model_validate_json(within_project(args.analysis_config).read_text())
    if processing.mode!='LOCAL' or not config.semantic: raise ValueError('Benchmark requires LOCAL semantic mode')
    router=ProcessingRouter(processing,build_providers(processing,PrivacyPolicy()),OperationJournal(out/'ai.jsonl'))
    peak=[0]; sampling_errors=[0]; stop=threading.Event()
    tick=time.perf_counter()
    with local_server(args.runtime_manifest) as process:
        setup=time.perf_counter()-tick
        def sample():
            while not stop.is_set():
                try:
                    result=subprocess.run(['/bin/ps','-o','rss=','-p',str(process.pid)],capture_output=True,text=True,timeout=2)
                    if result.returncode==0 and result.stdout.strip():
                        peak[0]=max(peak[0],int(result.stdout.strip())*1024)
                    else: sampling_errors[0]+=1
                except (OSError,ValueError,subprocess.TimeoutExpired): sampling_errors[0]+=1
                stop.wait(.25)
        observer=threading.Thread(target=sample,daemon=True); observer.start()
        try:
            results=[]
            for name in ('cold','warm'):
                r=analyze(args.media,out/name,out/'cache',config,router=router,
                          ffmpeg='/opt/homebrew/bin/ffmpeg',ffprobe='/opt/homebrew/bin/ffprobe')
                results.append(r.benchmark)
                if r.benchmark['status']!='complete': raise RuntimeError('Real semantic analysis failed; MVP not complete')
        finally: stop.set(); observer.join(timeout=3)
    measurement=dict(runtime_setup_seconds=setup,runs=results,
        server_peak_observed_rss_bytes=peak[0] or None,server_rss_sampling_seconds=.25,
        server_rss_sampling_errors=sampling_errors[0],
        memory_caveat='Sampled resident RSS, not total unified/GPU memory or exact peak.',
        setup_caveat='Includes approved-file SHA verification and model loading; OS file caches may be warm.',
        extrapolation_caveat='Seconds/minute is normalized from this short clip, not a long-video throughput guarantee.',
        server_terminated=process.poll() is not None)
    (out/'benchmark.json').write_bytes(json_bytes(measurement))
    print(json.dumps(measurement,indent=2))


if __name__=='__main__': main()
