import json 
import os
from .pipeline import run_pipeline
from .agent.orchestrator import Orchestrator, _TRANSCRIPT_BASE

def merge_transcripts(video_name: str) -> str:
    transcripts_dir = os.path.join(_TRANSCRIPT_BASE, video_name)
    transcript = ""
    for _file in os.scandir(transcripts_dir):
        s = ""
        with open(_file.path, "r") as f:  
            s = f.read()
        transcript += s + "\n"
    return transcript

def main(shared_dir: str, video_name: str) -> str:
    run_pipeline(shared_dir, video_name)
    orch = Orchestrator()
    result = orch.analyse_video(video_name) # get json output
    # add the full transcript to the output
    full_transcript = merge_transcripts(video_name) 
    result["full_transcript"] = full_transcript
    return json.dumps(result, indent=2)