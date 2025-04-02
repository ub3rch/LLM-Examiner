# LLM-Examiner
SWP retake repository

## Deploy instructions:
```
git clone https://github.com/ub3rch/LLM-Examiner.git
cd LLM-Examiner

# Activating virtual environment
python -m venv .venv
source .venv/bin/activate

# Installing dependencies
pip install -r requirements.txt

# Running fastapi (firestore serviceAccountKey.json should be provided)
fastapi run main.py&

# Running telegram bot (BOT_TOKEN (generated in @BotFather) and OPENAI_API_KEY environment variables should be provided)
export BOT_TOKEN="your generated bot token"
export OPENAI_API_KEY="your openai api key"
python bot/bot.py&
```

## Stopping application
```
jobs

# Find job numbers corresponding to fastapi and bot

fg [bot_job_number]
# Press ctrl+c (possibly multiple times to be sure)

fg [fastapi_job_number]
# Press ctrl+c (possibly multiple times to be sure)
