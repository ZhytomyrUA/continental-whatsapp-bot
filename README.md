# Continental WhatsApp Channel Bot

Separate news collector for a **normal WhatsApp Channel**.

## What it does

- Searches current public Continental news through Google News RSS.
- Gives **Korbach factory / production news** the highest priority.
- Gives other Continental factory and production news priority over general company news.
- Deduplicates similar articles.
- Produces up to 12 ready-to-post items per run.
- Does **not** use machine translation.
- Does **not** require WhatsApp Business.
- Does **not** require a WhatsApp API token.

## Important limitation

This repository deliberately stops at the **ready-to-post** stage.

A normal WhatsApp Channel is different from WhatsApp Business/API messaging. This project does not pretend that an official public API exists for arbitrary Python/GitHub Actions code to publish directly into a normal Channel.

The generated file `whatsapp_posts.txt` contains the posts that can be copied into the Channel.

## Output

After a run:

- `whatsapp_posts.json` — structured posts
- `whatsapp_posts.txt` — ready-to-copy posts
- `whatsapp_seen.json` — state used to avoid repeating the same event

## GitHub Actions

The workflow runs every 8 hours:

- 00:00 UTC
- 08:00 UTC
- 16:00 UTC

It can also be started manually with:

**Actions → Continental WhatsApp Channel News → Run workflow**

## Local test

```bash
pip install -r requirements.txt
python bot.py
```

No secret or API key is required.

## Next stage

Once the collector works reliably, a separate publishing layer can be evaluated for the normal WhatsApp Channel. Telegram remains independent and is not changed by this repository.
