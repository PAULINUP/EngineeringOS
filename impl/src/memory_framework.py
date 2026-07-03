import os
import json
import threading
import subprocess
from sqlalchemy.orm import Session
from sqlalchemy import text

class GitMemoryManager:
    async def dump_state(self, session, output_dir="impl/memory_dumps"):
        """
        Uses SQLAlchemy to query all Learners and EvidenceRecords 
        and dump them to JSON files.
        """
        os.makedirs(output_dir, exist_ok=True)
        
        learners = []
        evidence_records = []
        
        try:
            res = await session.execute(text("SELECT * FROM learner"))
            learners = [dict(row) for row in res.mappings()]
        except Exception as e:
            print(f"Failed to query learners: {e}")

        try:
            res = await session.execute(text("SELECT * FROM evidence_record"))
            evidence_records = [dict(row) for row in res.mappings()]
        except Exception as e:
            print(f"Failed to query evidence records: {e}")

        with open(os.path.join(output_dir, "learners.json"), "w", encoding="utf-8") as f:
            json.dump(learners, f, indent=4, default=str)
            
        with open(os.path.join(output_dir, "evidence_records.json"), "w", encoding="utf-8") as f:
            json.dump(evidence_records, f, indent=4, default=str)

    def sync_to_git(self, repo_path=".", commit_msg="sync: memory state"):
        """
        Uses python's subprocess to run git add impl/memory_dumps, 
        git commit -m ..., and git push asynchronously.
        """
        def _run_git_commands():
            try:
                subprocess.run(["git", "add", "impl/memory_dumps"], cwd=repo_path, check=True, capture_output=True)
                subprocess.run(["git", "commit", "-m", commit_msg], cwd=repo_path, check=True, capture_output=True)
                subprocess.run(["git", "push"], cwd=repo_path, check=True, capture_output=True)
            except subprocess.CalledProcessError as e:
                print(f"Git sync failed: {e.stderr.decode('utf-8', errors='ignore')}")

        thread = threading.Thread(target=_run_git_commands, daemon=True)
        thread.start()
        return thread
