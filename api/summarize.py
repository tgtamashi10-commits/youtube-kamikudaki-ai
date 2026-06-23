import os
import json
import re
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

from youtube_transcript_api import YouTubeTranscriptApi
from openai import OpenAI

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

SYSTEM_PROMPT = """
あなたは「動画かみくだきAI」。
YouTubeの文字起こしを、ユーザーがすぐ理解して行動できる形に変換する。

出力は日本語で、少し関西弁を混ぜて、具体的に。
推測で動画にない内容を足さない。
仕事・現場・会社改善に使える視点を必ず入れる。
"""

def extract_video_id(text):
    text = text.strip()
    if re.fullmatch(r"[a-zA-Z0-9_-]{11}", text):
        return text

    parsed = urlparse(text)
    if parsed.hostname in ["youtu.be"]:
        return parsed.path.strip("/")

    qs = parse_qs(parsed.query)
    if "v" in qs:
        return qs["v"][0]

    match = re.search(r"(?:shorts|embed)/([a-zA-Z0-9_-]{11})", text)
    if match:
        return match.group(1)

    return None

def get_transcript(video_id):
    try:
        items = YouTubeTranscriptApi.get_transcript(
            video_id,
            languages=["ja", "en", "en-US"]
        )
    except Exception:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

        try:
            transcript = transcript_list.find_transcript(["ja", "en", "en-US"])
        except Exception:
            transcript = transcript_list.find_generated_transcript(["ja", "en", "en-US"])

        items = transcript.fetch()

    return "\n".join([i.get("text", "") for i in items])

def summarize(transcript, style):
    prompt = f"""
次のYouTube文字起こしを、俺向けに要約して。

出力形式：
1. 一言でいうと
2. 結論3行
3. 大事なポイント3つ
4. 小学生でも分かる説明
5. 仕事・現場・会社で使うなら
6. 明日からやること
7. 関西弁で超ざっくり

スタイル指定：{style}

文字起こし：
{transcript[:12000]}
"""

    res = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        temperature=0.4
    )

    return res.choices[0].message.content

class handler(BaseHTTPRequestHandler):
    def _send(self, status, data):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def do_OPTIONS(self):
        self._send(200, {"ok": True})

    def do_GET(self):
        self._send(200, {
            "ok": True,
            "message": "動画かみくだきAI API 起動中"
        })

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8")
            data = json.loads(body or "{}")

            url = data.get("url", "")
            style = data.get("style", "関西弁ざっくり版")

            video_id = extract_video_id(url)
            if not video_id:
                self._send(400, {"ok": False, "error": "YouTube URL / 動画IDが読み取れません"})
                return

            transcript = get_transcript(video_id)
            result = summarize(transcript, style)

            self._send(200, {
                "ok": True,
                "video_id": video_id,
                "summary": result
            })

        except Exception as e:
            self._send(500, {
                "ok": False,
                "error": str(e)
            })