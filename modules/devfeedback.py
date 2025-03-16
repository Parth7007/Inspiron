from supabase import Client
from groq import Groq
import uuid

class DeveloperFeedback:
    def __init__(self, supabase: Client, groq_client: Groq):
        self.supabase = supabase
        self.groq = groq_client

    async def log_code_event(self, session_id: str, code: str, chars_typed: int, chars_deleted: int, errors: int):
        typing_data = {
            "event_id": str(uuid.uuid4()),
            "session_id": session_id,
            "chars_typed": chars_typed,
            "chars_deleted": chars_deleted,
            "error_count": errors,
            "typing_speed": chars_typed / 5.0 if chars_typed > 0 else 0.0
        }
        self.supabase.table("typing_events").insert(typing_data).execute()
        print(f"Inserted typing event: {typing_data}")

        comment_count = code.count("//") + code.count("#")
        is_optimized = "nested" not in code.lower()
        snapshot_id = str(uuid.uuid4())
        snapshot_data = {
            "snapshot_id": snapshot_id,
            "session_id": session_id,
            "code_text": code,
            "comment_count": comment_count,
            "is_optimized": is_optimized
        }
        self.supabase.table("code_snapshots").insert(snapshot_data).execute()
        print(f"Inserted code snapshot: {snapshot_data}")

        self._update_session_stats(session_id, code, errors, chars_deleted)

    def _update_session_stats(self, session_id: str, code: str, errors: int, deletions: int):
        lines = len(code.split("\n"))
        try:
            session = self.supabase.table("coding_sessions").select("total_lines_written, total_errors, total_deletions").eq("session_id", session_id).single().execute().data
            if not session:
                print(f"Session {session_id} not found in coding_sessions")
                return

            current_lines = session.get("total_lines_written", 0)
            current_errors = session.get("total_errors", 0)
            current_deletions = session.get("total_deletions", 0)

            session_update = {
                "total_lines_written": current_lines + lines,
                "total_errors": current_errors + errors,
                "total_deletions": current_deletions + deletions
            }
            print(f"Before update - Session {session_id}: {session}")
            self.supabase.table("coding_sessions").update(session_update).eq("session_id", session_id).execute()
            updated_session = self.supabase.table("coding_sessions").select("*").eq("session_id", session_id).single().execute().data
            print(f"After update - Session {session_id}: {updated_session}")
        except Exception as e:
            print(f"Error updating session stats: {e}")

    async def generate_final_feedback(self, session_id: str):
        feedback_list = []
        snapshots = self.supabase.table("code_snapshots").select("*").eq("session_id", session_id).execute().data
        typing_events = self.supabase.table("typing_events").select("*").eq("session_id", session_id).execute().data
        session = self.supabase.table("coding_sessions").select("*").eq("session_id", session_id).single().execute().data

        if not session:
            return [{"aspect": "error", "text": "Session not found"}]

        unoptimized_snippets = [s["code_text"] for s in snapshots if not s["is_optimized"]]
        if unoptimized_snippets:
            code_sample = "\n".join(unoptimized_snippets[:3])
            prompt = f"Analyze this code: {code_sample}. Suggest optimizations."
            try:
                response = self.groq.chat.completions.create(  # Updated Groq method
                    model="llama3-8b-8192",  # Updated model name (check your Groq version)
                    messages=[{"role": "user", "content": prompt}]
                ).choices[0].message.content
                feedback_list.append({"aspect": "optimization", "text": f"Found {len(unoptimized_snippets)} unoptimized sections: {response}"})
            except Exception as e:
                feedback_list.append({"aspect": "optimization", "text": f"Unoptimized code detected ({len(unoptimized_snippets)} instances)—check nested loops! (Groq error: {e})"})

        total_comments = sum(s["comment_count"] for s in snapshots)
        total_lines = session["total_lines_written"]
        if total_comments == 0 and total_lines > 10:
            feedback_list.append({"aspect": "style", "text": f"No comments in {total_lines} lines—add explanations for clarity!"})
        elif total_comments / total_lines < 0.1:
            feedback_list.append({"aspect": "style", "text": f"Only {total_comments} comments in {total_lines} lines—consider adding more!"})

        avg_speed = sum(e["typing_speed"] for e in typing_events) / len(typing_events) if typing_events else 0
        total_errors = session["total_errors"]
        total_deletions = session["total_deletions"]
        confidence_score = max(0, 100 - total_errors - total_deletions // 10)
        feedback_list.append({"aspect": "typing", "text": f"Avg typing speed: {avg_speed:.1f} chars/sec, Errors: {total_errors}, Deletions: {total_deletions}, Confidence: {confidence_score}/100"})

        naming_styles = set()
        for snapshot in snapshots:
            code = snapshot["code_text"]
            if "camelCase" in code:
                naming_styles.add("camelCase")
            if "snake_case" in code:
                naming_styles.add("snake_case")
        if len(naming_styles) > 1:
            feedback_list.append({"aspect": "consistency", "text": f"Inconsistent naming styles detected: {', '.join(naming_styles)}—pick one!"})

        user_id = session["user_id"]
        past_sessions = self.supabase.table("coding_sessions").select("total_errors").eq("user_id", user_id).order("start_time").execute().data
        if len(past_sessions) > 1 and past_sessions[-1]["total_errors"] < past_sessions[-2]["total_errors"]:
            feedback_list.append({"aspect": "learning", "text": "Fewer errors than your last session—great improvement!"})

        if snapshots:
            latest_code = snapshots[-1]["code_text"]
            prompt = f"What is this code doing? {latest_code}"
            try:
                context = self.groq.chat.completions.create(  # Updated Groq method
                    model="llama3-8b-8192",  # Updated model name
                    messages=[{"role": "user", "content": prompt}]
                ).choices[0].message.content
                feedback_list.append({"aspect": "context", "text": f"Your latest code seems to: {context}"})
            except Exception as e:
                feedback_list.append({"aspect": "context", "text": f"Couldn’t analyze context (Groq error: {e})"})

        if avg_speed < 5 and total_errors > 10:
            feedback_list.append({"aspect": "burnout", "text": f"Slow typing ({avg_speed:.1f} chars/sec) and {total_errors} errors—might be time for a break!"})

        for fb in feedback_list:
            self.supabase.table("feedback_logs").insert({
                "feedback_id": str(uuid.uuid4()),
                "session_id": session_id,
                "snapshot_id": snapshots[-1]["snapshot_id"] if snapshots and ("optimization" in fb["aspect"] or "style" in fb["aspect"]) else None,
                "aspect": fb["aspect"],
                "feedback_text": fb["text"]
            }).execute()

        return feedback_list