import os
import json
from http.server import BaseHTTPRequestHandler
from openai import OpenAI

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

SYSTEM_PROMPT = """
あなたは「動画かみくだきAI」。
ユーザーが貼ったYouTube動画の文字起こしを、
短時間で理解して仕事や日常で使える形に変換する。

難しい言葉はかみくだく。
少し関西弁を混ぜる。
動画にない内容は推測で足さない。
"""

def summarize(transcript):
    prompt = f"""
以下はYouTube動画の文字起こしです。
ユーザー向けに要約して。

出力はこの順番：
1. 一言でいうと
2. 結論3行
3. 大事なポイント3つ
4. 小学生でも分かる説明
5. 会社・現場で使うなら
6. 明日からやること
7. 関西弁で超ざっくり

文字起こし：
{transcript[:30000]}
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        temperature=0.4
    )
    return response.choices[0].message.content

class handler(BaseHTTPRequestHandler):
    def _send(self, status, data):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def do_OPTIONS(self):
        self._send(200, {"ok": True})

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8")
            data = json.loads(body or "{}")

            transcript = data.get("transcript", "").strip()

            if not transcript:
                self._send(400, {
                    "ok": False,
                    "error": "文字起こしを貼ってください"
                })
                return

            result = summarize(transcript)

            self._send(200, {
                "ok": True,
                "summary": result
            })

        except Exception as e:
            self._send(500, {
                "ok": False,
                "error": str(e)
            })