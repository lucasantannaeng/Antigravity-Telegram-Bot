import asyncio, os
from pathlib import Path
from doctor import run_doctor_audit, format_doctor_report

bot_token = os.getenv('TELEGRAM_BOT_TOKEN','')
groq_key = os.getenv('GROQ_API_KEY','')
gemini_key = os.getenv('GEMINI_API_KEY','')
workspace = os.getenv('WORKSPACE_DIR','.')
freellm_key = os.getenv('FREE_LLM_API_KEY','')

async def main():
    audit = await run_doctor_audit(bot_token, groq_key, gemini_key, Path(workspace), freellm_key)
    report = format_doctor_report(audit)
    print(report)

if __name__ == '__main__':
    asyncio.run(main())
