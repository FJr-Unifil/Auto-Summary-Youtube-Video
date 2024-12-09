import os
import re
from datetime import datetime
from urllib.parse import urlparse, parse_qs

from youtube_transcript_api import YouTubeTranscriptApi
from openai import OpenAI

from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("No OpenAI API key found. Please set the OPENAI_API_KEY environment variable.")

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def get_video_id(url):
    parsed_url = urlparse(url)
    if parsed_url.hostname == 'youtu.be':
        return parsed_url.path[1:]
    if parsed_url.hostname in ('www.youtube.com', 'youtube.com'):
        if parsed_url.path == '/watch':
            return parse_qs(parsed_url.query)['v'][0]
    raise ValueError("Invalid YouTube URL")

def format_timestamp(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    seconds = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

def sanitize_filename(title):
    title = re.sub(r'[<>:"/\\|?*]', '', title)
    title = title.replace(' ', '-')
    return title

def get_custom_prompt(url):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    prompt_path = os.path.join(script_dir, 'prompt.txt')
    
    try:
        with open(prompt_path, 'r', encoding='utf-8') as f:
            prompt = f.read().strip()
            return prompt.replace('{{link}}', url)
    except FileNotFoundError:
        return f"Provide a summary of the transcript. YouTube link: {url}"

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    transcripts_dir = os.path.join(script_dir, 'Transcripts')
    summaries_dir = os.path.join(script_dir, 'Summaries')

    for dir_path in [transcripts_dir, summaries_dir]:
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)

    url = input("Enter YouTube video URL: ")

    try:
        video_id = get_video_id(url)
        transcript = YouTubeTranscriptApi.get_transcript(video_id)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        transcript_filename = f"transcript_{timestamp}.txt"
        transcript_filepath = os.path.join(transcripts_dir, sanitize_filename(transcript_filename))

        with open(transcript_filepath, 'w', encoding='utf-8') as f:
            full_transcript = []
            for entry in transcript:
                timestamp = format_timestamp(entry['start'])
                text = entry['text'].replace('\n', ' ').strip()
                full_transcript.append(f"[{timestamp}] {text}")
            
            f.write(' '.join(full_transcript))

        custom_prompt = get_custom_prompt(url)

        with open(transcript_filepath, 'r', encoding='utf-8') as f:
            transcript_text = f.read()

        full_prompt = f"{custom_prompt}\n\nTranscript:\n{transcript_text}"

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": full_prompt}
            ]
        )

        ai_summary = response.choices[0].message.content

        summary_filename = f"summary_{timestamp}.md"
        summary_filepath = os.path.join(summaries_dir, sanitize_filename(summary_filename))

        with open(summary_filepath, 'w', encoding='utf-8') as f:
            f.write(ai_summary)

        print(f"Transcript saved to: {transcript_filepath}")
        print(f"Summary saved to: {summary_filepath}")

    except Exception as e:
        print(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    main()
