import os
import shutil
import re
from datetime import datetime
from urllib.parse import urlparse, parse_qs

from googleapiclient.discovery import build
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

def get_youtube_video_title(url, api_key):
    try:
        video_id = get_video_id(url)
        
        youtube = build('youtube', 'v3', developerKey=api_key)
        
        request = youtube.videos().list(
            part="snippet",
            id=video_id
        )
        response = request.execute()
        
        if response['items']:
            return response['items'][0]['snippet']['title']
        else:
            return "Untitled_Video"
    
    except Exception as e:
        print(f"Error fetching video title: {e}")
        return "Untitled_Video"

def format_timestamp(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    seconds = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

def get_custom_prompt(url, video_title):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    prompt_path = os.path.join(script_dir, 'prompt.txt')
    
    try:
        with open(prompt_path, 'r', encoding='utf-8') as f:
            prompt = f.read().strip()
            prompt = prompt.replace('{{title}}', video_title)
            return prompt.replace('{{link}}', url)
    except FileNotFoundError:
        return f"Provide a summary of the transcript. YouTube link: {url}"

def process_ai_summary(ai_summary):
    lines = ai_summary.split('\n')
    
    title_match = re.search(r'"([^"]*)"', lines[0])
    suggested_title = title_match.group(1) if title_match else "Untitled"

    processed_content = '\n'.join(lines[1:]).replace('```md', '').replace('```', '').strip()
    
    return suggested_title, processed_content

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    transcripts_dir = os.path.join(script_dir, 'Transcripts')
    summaries_dir = os.path.join(script_dir, 'Summaries')

    symlink_dir = os.path.expanduser("~/Library/Mobile Documents/iCloud~md~obsidian/Documents/FJr Zettelkasten/references")

    for dir_path in [transcripts_dir, summaries_dir, symlink_dir]:
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)

    url = input("Enter YouTube video URL: ")

    try:
        video_id = get_video_id(url)
        video_title = get_youtube_video_title(url, os.getenv("YOUTUBE_API_KEY"))

        transcript = YouTubeTranscriptApi.get_transcript(video_id)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        full_transcript = []
        for entry in transcript:
            timestamp = format_timestamp(entry['start'])
            text = entry['text'].replace('\n', ' ').strip()
            full_transcript.append(f"[{timestamp}] {text}")
        
        transcript_text = ' '.join(full_transcript)

        custom_prompt = get_custom_prompt(url, video_title)
        full_prompt = f"{custom_prompt}\n\nTranscript:\n{transcript_text}"

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": full_prompt}
            ]
        )

        ai_summary = response.choices[0].message.content

        suggested_title, processed_summary = process_ai_summary(ai_summary)

        summary_filename = f"{suggested_title}.md"
        summary_filepath = os.path.join(summaries_dir, summary_filename)

        with open(summary_filepath, 'w', encoding='utf-8') as f:
            f.write(processed_summary)

        symlink_filepath = os.path.join(symlink_dir, summary_filename)
        shutil.copy(summary_filepath, symlink_filepath)

        print(f"Summary saved to: {summary_filepath}")
        print(f"Summary copied to symlink directory: {symlink_filepath}")
    except Exception as e:
        print(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    main()
