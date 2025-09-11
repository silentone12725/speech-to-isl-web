from flask import Flask, render_template, request, jsonify, send_from_directory
import os
import re
import pandas as pd
import speech_recognition as sr
from moviepy.editor import VideoFileClip, concatenate_videoclips
import subprocess
import tempfile
import uuid
import time
import requests
from nltk.parse.stanford import StanfordParser
from nltk import ParentedTree, Tree
import nltk
from nltk.stem import WordNetLemmatizer
from nltk.corpus import stopwords
import os

app = Flask(__name__)

# Global paths
DATASET_DIR = "NLP_dataset"
YT_DOWNLOADS_DIR = "yt_downloads"
CSV_PATH = "NLP_videos.csv"
UPLOAD_FOLDER = "uploads"
TEMP_FOLDER = "temp"
STATIC_VIDEOS = "static/videos"

# Ensure all required directories exist
for directory in [DATASET_DIR, YT_DOWNLOADS_DIR, UPLOAD_FOLDER, TEMP_FOLDER, STATIC_VIDEOS]:
    if not os.path.exists(directory):
        os.makedirs(directory)

# Load CSV data once at startup for better performance
videos_df = None
if os.path.exists(CSV_PATH):
    videos_df = pd.read_csv(CSV_PATH)

# Initialize lemmatizer
lemmatizer = WordNetLemmatizer()

# Download necessary NLTK data (add this to your app initialization)
def download_nltk_data():
    try:
        nltk.download('stopwords', quiet=True)
        nltk.download('wordnet', quiet=True)
        nltk.download('omw-1.4', quiet=True)
    except:
        print("NLTK data download failed, but continuing...")

# Set up Stanford Parser (adjust paths as needed for your server)
def initialize_stanford_parser():
    java_path = "/usr/bin/java"  # Adjust based on your server's Java path
    os.environ['JAVAHOME'] = java_path
    
    try:
        sp = StanfordParser(
            path_to_jar='./stanford-parser-full/stanford-parser.jar',
            path_to_models_jar='./stanford-parser-full/stanford-parser-4.2.0-models.jar'
        )
        return sp
    except Exception as e:
        print(f"Stanford Parser initialization failed: {str(e)}")
        return None

# Enhanced ISL conversion using Stanford Parser (if available)
def convert_isl_advanced(parsetree):
    dict = {}
    parenttree = ParentedTree.convert(parsetree)
    for sub in parenttree.subtrees():
        dict[sub.treeposition()] = 0
    
    isltree = Tree('ROOT', [])
    i = 0
    for sub in parenttree.subtrees():
        if sub.label() == "NP" and dict[sub.treeposition()] == 0 and dict[sub.parent().treeposition()] == 0:
            dict[sub.treeposition()] = 1
            isltree.insert(i, sub)
            i = i + 1

        if sub.label() == "VP" or sub.label() == "PRP":
            for sub2 in sub.subtrees():
                if (sub2.label() == "NP" or sub2.label() == 'PRP') and dict[sub2.treeposition()] == 0 and dict[sub2.parent().treeposition()] == 0:
                    dict[sub2.treeposition()] = 1
                    isltree.insert(i, sub2)
                    i = i + 1

    for sub in parenttree.subtrees():
        for sub2 in sub.subtrees():
            if len(sub2.leaves()) == 1 and dict[sub2.treeposition()] == 0 and dict[sub2.parent().treeposition()] == 0:
                dict[sub2.treeposition()] = 1
                isltree.insert(i, sub2)
                i = i + 1

    return isltree

def download_and_convert_video(url, download_path, filename):
    """Download and convert video from a non-YouTube URL"""
    # First determine the file extension from the URL
    file_extension = os.path.splitext(url)[1] if os.path.splitext(url)[1] else ".mp4"
    video_path = os.path.join(download_path, filename + file_extension)
    mp4_path = os.path.join(download_path, filename + ".mp4")
    
    # Check if the final MP4 already exists
    if os.path.exists(mp4_path):
        return True
    
    # Special handling for talkinghands.co.in webm files
    if "talkinghands.co.in" in url and url.endswith(".webm"):
        try:
            # Use yt-dlp for better web video handling
            command = [
                "yt-dlp",
                "--no-check-certificate",  # Skip SSL verification
                "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "-o", video_path,
                url
            ]
            
            subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # Convert to MP4 if needed
            if file_extension.lower() != ".mp4" and os.path.exists(video_path):
                command = ["ffmpeg", "-i", video_path, "-c:v", "libx264", "-c:a", "aac", mp4_path]
                subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
                # Remove the original file after conversion
                if os.path.exists(mp4_path):
                    os.remove(video_path)
                    return True
            return os.path.exists(video_path) or os.path.exists(mp4_path)
        
        except Exception as e:
            print(f"Error downloading with yt-dlp: {str(e)}")
            # Fall back to requests method
    
    # Standard method for other URLs
    try:
        # Set headers to mimic a browser request
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': '*/*',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Referer': 'https://talkinghands.co.in/'  # Add referrer for talkinghands.co.in
        }
        
        # Send a request to get the video content with headers
        response = requests.get(url, stream=True, headers=headers, verify=False)  # Skip SSL verification
        response.raise_for_status()  # Check for HTTP errors
        
        # Write the content to a file
        with open(video_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        # Convert to MP4 if needed
        if file_extension.lower() != ".mp4":
            try:
                command = ["ffmpeg", "-i", video_path, "-c:v", "libx264", "-c:a", "aac", mp4_path]
                subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
                # Remove the original file after conversion
                if os.path.exists(mp4_path):
                    os.remove(video_path)
                    return True
            except Exception as e:
                print(f"Error converting video: {str(e)}")
                # If conversion fails, continue with the original format
        
        return True
    except requests.exceptions.RequestException as e:
        print(f"Error downloading video from {url}: {str(e)}")
        return False

def download_video(link, yt_path, yt_name):
    """Download a video from YouTube or non-YouTube sources"""
    # Check if the link is a YouTube link
    if "youtube.com" in link or "youtu.be" in link:
        output_path = os.path.join(yt_path, f"{yt_name}.%(ext)s")
        
        # Check if video already exists
        if os.path.exists(os.path.join(yt_path, f"{yt_name}.mp4")):
            return True
        
        # Command for yt-dlp
        command = [
            "yt-dlp",
            "--format", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4",
            "--output", output_path,
            "--merge-output-format", "mp4",
            link
        ]
        
        try:
            subprocess.run(command, check=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f"Error downloading YouTube video: {str(e)}")
            return False
    else:
        # Download using custom function for non-YouTube videos
        filename = yt_name  # Use the same name for non-YouTube videos
        return download_and_convert_video(link, yt_path, filename)

def cut_video(word, yt_name, start_min, start_sec, end_min, end_sec):
    """Cut a section from a video"""
    start = int(start_min) * 60 + int(start_sec)
    end = int(end_min) * 60 + int(end_sec)

    in_path = os.path.join(YT_DOWNLOADS_DIR, f"{yt_name}.mp4")
    out_path = os.path.join(DATASET_DIR, f"{word}.mp4")

    # Check if cut video already exists
    if os.path.exists(out_path):
        return out_path

    if not os.path.exists(in_path):
        return None

    try:
        clip = VideoFileClip(in_path).subclip(start, end)
        clip.write_videofile(out_path, codec="libx264", audio_codec="aac")
        return out_path
    except Exception as e:
        print(f"Error cutting video for {word}: {str(e)}")
        return None

def text_to_isl_enhanced(sentence, sp=None):
    """Convert English text to ISL representation with linguistic analysis"""
    # Remove punctuation
    pattern = r'[^\w\s]'
    sentence = re.sub(pattern, '', sentence)
    
    # Define stopwords - extend the set from your existing implementation
    stopwords_set = set(['a', 'an', 'the', 'is', 'to', 'The', 'in', 'of', 'us', 'and', 'are', 'this', 'that', 'it'])
    
    # Try to use Stanford Parser if available
    try:
        if sp:
            englishtree = [tree for tree in sp.parse(sentence.split())]
            parsetree = englishtree[0]
            
            # Get original words from the parse tree
            words = parsetree.leaves()
            
            # Apply lemmatization
            lemmatized_words = [lemmatizer.lemmatize(w) for w in words]
            
            # Filter out stopwords and build ISL sentence
            isl_sentence = ""
            for w in lemmatized_words:
                if w.lower() not in stopwords_set:
                    if w == "I":  # Special case for "I"
                        isl_sentence += w + " "
                    else:
                        isl_sentence += w.lower() + " "
            
            return isl_sentence.strip()
    except Exception as e:
        print(f"Advanced parsing failed: {str(e)}, falling back to basic method")
    
    # Fallback to the simpler method if Stanford Parser fails
    words = sentence.split()
    isl_words = []
    
    for word in words:
        if word.lower() not in stopwords_set:
            if word == "I":  # Preserve uppercase I
                isl_words.append(word)
            else:
                isl_words.append(word.lower())
    
    isl_sentence = " ".join(isl_words)
    return isl_sentence

def recognize_speech_from_file(audio_file_path):
    """Recognize speech from an audio file"""
    recognizer = sr.Recognizer()
    
    try:
        with sr.AudioFile(audio_file_path) as source:
            audio_data = recognizer.record(source)
            text = recognizer.recognize_google(audio_data)
            return text
    except Exception as e:
        print(f"Speech recognition error: {str(e)}")
        return None

def is_single_letter(word):
    """Check if the word is a single letter (for special handling)"""
    return len(word) == 1 and word.isalpha()

def process_word_for_video_enhanced(word, videos_df):
    """Process a single word to find appropriate video clip with advanced matching"""
     # Add these lines at the beginning of the function
    
    # Load the CSV data if not already loaded
    if videos_df is None and os.path.exists(CSV_PATH):
        videos_df = pd.read_csv(CSV_PATH)
    word_lower = word.lower()
    
    # Special case for "I" (pronoun)
    if word == "I" and (videos_df['yt_name'] == "me").any():
        idx = videos_df.index[videos_df['yt_name'] == "me"].tolist()[0]
        return get_video_info(idx, videos_df)
    
    # Direct match (case-insensitive)
    if (videos_df['Name'].str.lower() == word_lower).any():
        idx = videos_df.index[videos_df['Name'].str.lower() == word_lower].tolist()[0]
        return get_video_info(idx, videos_df)
    
    # Try to find lemmatized version
    lemma_word = lemmatizer.lemmatize(word_lower)
    if lemma_word != word_lower and (videos_df['Name'].str.lower() == lemma_word).any():
        idx = videos_df.index[videos_df['Name'].str.lower() == lemma_word].tolist()[0]
        print(f"Found lemmatized match: {word} → {lemma_word}")
        return get_video_info(idx, videos_df)
    
    # Check for similar words using basic string similarity
    # This is a simple approach - you could use more advanced NLP techniques
    best_match = None
    best_score = 0
    threshold = 0.75  # minimum similarity threshold
    
    for idx, name in enumerate(videos_df['Name']):
        # Skip single letters for similarity matching
        if len(name) <= 1:
            continue
            
        # Calculate similarity ratio (very basic)
        name_lower = name.lower()
        shorter = min(len(word_lower), len(name_lower))
        longer = max(len(word_lower), len(name_lower))
        
        if shorter == 0:
            continue
            
        # Count matching characters (case insensitive)
        match_count = sum(1 for a, b in zip(word_lower, name_lower) if a == b)
        score = match_count / longer
        
        if score > best_score and score >= threshold:
            best_score = score
            best_match = idx
    
    if best_match is not None:
        matched_word = videos_df['Name'].iloc[best_match]
        print(f"Found similar word: {word} → {matched_word} (score: {best_score:.2f})")
        return get_video_info(best_match, videos_df)
    
    # If the word is a single letter, check for it
    if is_single_letter(word) and (videos_df['Name'] == word.lower()).any():
        idx = videos_df.index[videos_df['Name'] == word.lower()].tolist()[0]
        return get_video_info(idx, videos_df)
    
    # Word not found
    return None


def get_video_info(idx, videos_df):
    """Extract video information from dataframe row"""
    return {
        'link': videos_df['Link'].iloc[idx],
        'yt_name': videos_df['yt_name'].iloc[idx],
        'start_min': videos_df['start_min'].iloc[idx],
        'start_sec': videos_df['start_sec'].iloc[idx],
        'end_min': videos_df['end_min'].iloc[idx],
        'end_sec': videos_df['end_sec'].iloc[idx]
    }

def create_isl_video_enhanced(isl_text, session_id):
    """Create an ISL video from ISL text with enhanced word matching"""
    global videos_df
    
    # Load the CSV data if not already loaded
    if videos_df is None and os.path.exists(CSV_PATH):
        videos_df = pd.read_csv(CSV_PATH)
    
    if videos_df is None:
        return None
    
    words = isl_text.split()
    video_paths = []
    
    # Process each word
    for word in words:
        print(f"Processing word: {word}")
        
        # Try to find the word with enhanced matching
        word_info = process_word_for_video_enhanced(word, videos_df)
        
        if word_info:
            # We found a match in the dataset
            print(f"Found match for word: {word} → {word_info['yt_name']}")
            clip_path = process_word_clip(word, word_info)
            if clip_path:
                video_paths.append(clip_path)
        else:
            # Word not found - handle letter by letter (fingerspelling)
            print(f"Word '{word}' not found in dataset, spelling out...")
            for letter in word.lower():
                # Skip non-alphabetic characters
                if not letter.isalpha():
                    continue
                    
                letter_info = process_word_for_video_enhanced(letter, videos_df)
                if letter_info:
                    clip_path = process_word_clip(letter, letter_info)
                    if clip_path:
                        video_paths.append(clip_path)
                else:
                    print(f"Letter '{letter}' not found in dataset")
    
    # Combine all video clips
    if video_paths:
        return combine_videos(video_paths, session_id)
    
    return None

def process_word_clip(word, word_info):
    """Download and cut video for a specific word"""
    # Download the YouTube video if needed
    download_success = download_video(word_info['link'], YT_DOWNLOADS_DIR, word_info['yt_name'])
    
    if download_success:
        # Cut the relevant portion
        clip_path = cut_video(
            word,
            word_info['yt_name'],
            word_info['start_min'],
            word_info['start_sec'],
            word_info['end_min'],
            word_info['end_sec']
        )
        
        return clip_path
    
    return None

def combine_videos(video_paths, session_id):
    """Combine multiple video clips into one"""
    clips = []
    for path in video_paths:
        if os.path.exists(path):
            try:
                clip = VideoFileClip(path).without_audio()
                clips.append(clip)
            except Exception as e:
                print(f"Error loading clip {path}: {str(e)}")
    
    if clips:
        output_file = os.path.join(STATIC_VIDEOS, f"{session_id}.mp4")
        try:
            final = concatenate_videoclips(clips, method="compose")
            final.write_videofile(output_file, audio=False)
            
            # Return the relative path to be used in templates
            return f"videos/{session_id}.mp4"
        except Exception as e:
            print(f"Error creating final video: {str(e)}")
    
    return None

# Add the Stanford Parser initialization here
sp = None
try:
    download_nltk_data()
    sp = initialize_stanford_parser()
except Exception as e:
    print(f"Stanford Parser initialization failed: {str(e)}")
    print("Will use basic text-to-ISL conversion method")


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/process_text', methods=['POST'])
def process_text():
    data = request.form
    english_text = data.get('text', '')
    
    # Generate a unique session ID
    session_id = str(uuid.uuid4())
    
    # Convert English to ISL using the enhanced method
    isl_text = text_to_isl_enhanced(english_text, sp)
    
    # Create ISL video with enhanced word processing
    video_path = create_isl_video_enhanced(isl_text, session_id)
    
    return jsonify({
        'status': 'success',
        'english_text': english_text,
        'isl_text': isl_text,
        'video_path': video_path
    })

@app.route('/process_audio', methods=['POST'])
def process_audio():
    # Generate a unique session ID
    session_id = str(uuid.uuid4())
    
    if 'audio' in request.files:
        audio_file = request.files['audio']
        temp_path = os.path.join(TEMP_FOLDER, f"{session_id}.wav")
        audio_file.save(temp_path)
        
        # Recognize speech
        english_text = recognize_speech_from_file(temp_path)
        
        if english_text:
            # Convert to ISL
            isl_text = text_to_isl_enhanced(english_text)
            
            # Create ISL video
            video_path = create_isl_video_enhanced(isl_text, session_id)
            
            # Clean up temp file
            try:
                os.remove(temp_path)
            except:
                pass
            
            return jsonify({
                'status': 'success',
                'english_text': english_text,
                'isl_text': isl_text,
                'video_path': video_path
            })
    
    return jsonify({
        'status': 'error',
        'message': 'Failed to process audio'
    })

@app.route('/record_audio', methods=['POST'])
def record_audio():
    # Generate a unique session ID
    session_id = str(uuid.uuid4())
    
    if 'audio' in request.files:
        audio_file = request.files['audio']
        temp_path = os.path.join(TEMP_FOLDER, f"{session_id}.webm")
        audio_file.save(temp_path)
        
        # Convert webm to wav for speech recognition
        wav_path = os.path.join(TEMP_FOLDER, f"{session_id}.wav")
        command = ["ffmpeg", "-i", temp_path, wav_path]
        try:
            subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except:
            return jsonify({
                'status': 'error',
                'message': 'Failed to convert audio format'
            })
            
        # Recognize speech
        english_text = recognize_speech_from_file(wav_path)
        
        if english_text:
            # Convert to ISL
            isl_text = text_to_isl_enhanced(english_text)
            
            # Create ISL video
            video_path = create_isl_video_enhanced(isl_text, session_id)
            
            # Clean up temp files
            try:
                os.remove(temp_path)
                os.remove(wav_path)
            except:
                pass
            
            return jsonify({
                'status': 'success',
                'english_text': english_text,
                'isl_text': isl_text,
                'video_path': video_path
            })
    
    return jsonify({
        'status': 'error',
        'message': 'Failed to process audio'
    })

@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory('static', filename)

if __name__ == '__main__':
    app.run(debug=True)