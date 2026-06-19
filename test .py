# This will be the master python file which will manage the entire Cogentic (Cognitive Agentic) AI core for the vision, mission and objectives of our Foundation.
import os
import csv
import json
import random
import time
import traceback
from google import genai
from google.genai import types

# Initialize the new client
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY", "ENTER API KEY HERE"))

# Define your objective themes and their mapped background templates
THEMES = {
    "Peace & Justice": "jalte_diye_1.jpg",
    "Health & Mindfulness": "jalte_diye_1.jpg",
    "Social Education": "jalte_diye_1.jpg",
    "Climate & Environment": "jalte_diye_1.jpg"
}

CSV_FALLBACK_FILE = "quotes.csv"
USED_QUOTES_LOG = "used_quotes_log.txt"
MAX_RETRIES = 3
PASSING_SCORE = 7

# Initialize the model (Using Flash for speed and cost-efficiency in loops)
# We enforce JSON output directly from the API for reliable parsing
def generate_content(theme):
    prompt = f"""
    You are an expert social media copywriter for the Jalte Diye Foundation.
    Create an original, highly inspiring quote and a matching 2-sentence explanation 
    specifically tailored to the theme: "{theme}".
    
    Return ONLY a valid JSON object with this exact schema:
    {{"quote": "...", "explanation": "..."}}
    """
    # The new SDK syntax
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
        )
    )
    return json.loads(response.text)
def evaluate_content(theme, content_json):
    """Phase 2: The strict AI Judge evaluates the generated content."""
    prompt = f"""
    You are a strict Quality Control Editor for a social education foundation.
    Evaluate the following quote and explanation based on its alignment with the theme "{theme}", 
    its clarity, and its emotional impact.
    
    Content to evaluate:
    {json.dumps(content_json)}
    
    Score it on a scale of 1 to 10 (where 10 is breathtakingly profound and 1 is generic/confusing).
    Return ONLY a valid JSON object with this exact schema:
    {{"score": 8, "reasoning": "..."}}
    """
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
        )
    )
    return json.loads(response.text)


# Map your generated themes to their exact CSV filenames
CSV_FALLBACK_MAP = {
    "Peace & Justice": "peace_justice.csv",
    "Health & Mindfulness": "Event_quotes.csv", # Assuming general/health falls to this or a specific health.csv
    "Social Education": "quality_education.csv",
    "Climate & Environment": "climate.csv"
}

def get_fallback_quote(theme):
    """Failsafe Phase: Pulls an unused quote from the corresponding thematic CSV."""
    print(f"⚠️ Triggering CSV Failsafe mechanism for theme: {theme}...")
    
    # 1. Identify the correct CSV file for the theme
    csv_file = CSV_FALLBACK_MAP.get(theme)
    if not csv_file or not os.path.exists(csv_file):
        print(f"🚨 Missing CSV file ({csv_file}) for {theme}. Falling back to emergency hardcoded quote.")
        return emergency_failsafe()

    # 2. Load history of used quotes to prevent duplicates
    used_quotes = set()
    if os.path.exists(USED_QUOTES_LOG):
        with open(USED_QUOTES_LOG, "r", encoding="utf-8") as f:
            used_quotes = set(line.strip() for line in f)

    # 3. Read the designated CSV and find the first unused quote
    fallback_content = None
    with open(csv_file, "r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        
        # --- NEW FIX: Skip blank lines at the top to find the actual headers ---
        headers = []
        for row in reader:
            # If the row is not empty and has at least one cell with text
            if row and any(cell.strip() for cell in row):
                headers = [h.strip().lower() for h in row]
                break
                
        # Dynamically find column indexes based on your uploaded CSV structures
        q_idx = headers.index("quote") if "quote" in headers else -1
        c_idx = headers.index("caption") if "caption" in headers else -1
        o_idx = headers.index("occasion") if "occasion" in headers else -1

        # Read the remaining rows in the file containing the actual data
        for row in reader:
            # Skip empty rows or rows that don't have enough columns
            if not row or q_idx == -1 or len(row) <= q_idx: 
                continue
                
            row_quote = row[q_idx].strip()
            
            # Formulate the explanation based on whether it's a Caption or Occasion column
            row_explanation = ""
            if c_idx != -1 and len(row) > c_idx:
                row_explanation = row[c_idx].strip()
            elif o_idx != -1 and len(row) > o_idx:
                row_explanation = f"Observing {row[o_idx].strip()}."

            # Check if quote is fresh
            if row_quote and row_quote not in used_quotes:
                fallback_content = {
                    "quote": row_quote.replace('"', ''),
                    "explanation": row_explanation.replace('"', '')
                }
                
                # Mark as used immediately to prevent next-day duplication
                with open(USED_QUOTES_LOG, "a", encoding="utf-8") as log:
                    log.write(row_quote + "\n")
                break
    
    if fallback_content:
        print(" Successfully retrieved fresh fallback quote from CSV.")
        return fallback_content
    else:
        # Absolute worst-case scenario: CSV is completely exhausted
        print(" CRITICAL: No unused quotes left in CSV. Using emergency failsafe.")
        return emergency_failsafe()
def emergency_failsafe():
    """Hardcoded ultimate failsafe if all files are missing or exhausted."""
    return {
        "quote": "The best time to plant a tree was twenty years ago. The second best time is now.",
        "explanation": "Every small step we take today shapes the world we live in tomorrow."
    }

def main():
    # 1. Randomly pick the day's theme and background
    selected_theme, background_image = random.choice(list(THEMES.items()))
    print(f" Today's Selected Theme: {selected_theme} (Asset: {background_image})")
    
    final_content = None

    # 2. The Agentic Generation & Evaluation Loop
    try:
        for attempt in range(1, MAX_RETRIES + 1):
            print(f"\n--- Attempt {attempt}/{MAX_RETRIES} ---")
            
            # Step A: Generate
            print(" Generating content...")
            draft_content = generate_content(selected_theme)
            print(f"📝 Draft Quote: {draft_content['quote']}")
            
            # Step B: Evaluate
            print(" Evaluating content...")
            evaluation = evaluate_content(selected_theme, draft_content)
            score = evaluation.get("score", 0)
            reasoning = evaluation.get("reasoning", "No reasoning provided.")
            
            print(f"Score: {score}/10 | Reasoning: {reasoning}")
            
            # Step C: The Decision
            if score >= PASSING_SCORE:
                print(" Content passed quality control!")
                final_content = draft_content
                break
            else:
                print(" Content rejected. Loop will restart.")
                time.sleep(2) # Brief pause before hitting the API again

        # If it failed 3 times in a row, trigger the fallback
        if not final_content:
            print(f"\n Failed to generate content scoring >= {PASSING_SCORE} after {MAX_RETRIES} attempts.")
            final_content = get_fallback_quote(selected_theme)

    # 3. Catch Network Errors, API Downtime, or JSON Parsing errors
    except (json.JSONDecodeError, KeyError, Exception) as e:
        print(f"\n System Error Encountered: {e}")

        # THIS WILL PRINT THE EXACT REASON IT FAILED
        print("\n--- ERROR DETAILS ---")
        traceback.print_exc() 
        print("---------------------\n")

        final_content = get_fallback_quote(selected_theme)

    # 4. Final Output Hand-off
    print("\n========================================")
    print("FINAL CONTENT READY FOR RENDERING")
    print("========================================")
    print(f"Theme: {selected_theme}")
    print(f"Background: {background_image}")
    print(f"Quote: {final_content['quote']}")
    print(f"Explanation: {final_content['explanation']}")
    
    # [Here you would pass 'final_content' and 'background_image' to your existing PIL image rendering script]
    # return final_content, background_image

if __name__ == "__main__":
    main()