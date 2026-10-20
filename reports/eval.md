# Noor evaluation report

Generated 2026-10-20 by `evals/report.py`. Golden set: 46 questions (37 answerable, 9 unanswerable) in `evals/golden.yaml`; rubric in `evals/rubric.md`. Retrieval k = 6, refusal threshold = 0.65.

## Scores and recommendation

| Metric | Threshold | ollama:qwen2.5:7b |
| --- | --- | --- |
| Retrieval hit@k | ≥ 85% | 86.5% |
| Groundedness (LLM judge) | ≥ 90% | 79.4% |
| Refusal on unanswerable | 100% | 100.0% |
| Answer rate (answerable) | ≥ 80% | 91.9% |
| Cited an expected source |  | 85.3% |
| Latency p50 |  | 9.1 s |
| Latency p95 |  | 14.1 s |
| Cost per query |  | $0 |
| **Recommendation** | | **NO-GO** |

- **ollama:qwen2.5:7b: NO-GO.** Fails: Groundedness (judge). Judge: ollama:qwen2.5:7b (same model as the answerer, so groundedness is likely lenient).
- **Claude Haiku / Sonnet: not run yet.** There is no `ANTHROPIC_API_KEY`. Run `python -m evals.run --model claude-haiku --judge claude-sonnet`, then `python -m evals.report`.

## Caveats

- Retrieval was tuned on this same golden set (diacritic folding and light stemming in the keyword index, raising hit@6 from 81.1% to 86.5%), so the hit rate is optimistic. A held-out set is the next step.
- Two labels were widened after inspecting misses, each with a reason in `golden.yaml`: b05 (the paired teacher/student chapters) and h01 (Bukhari repeats the intentions hadith seven times).
- Groundedness comes from an LLM judge. The human spot-check in `evals/spotcheck.csv` is still to be filled in by a person.

## Per question

| ID | Question | Retrieval hit | ollama:qwen2.5:7b |
| --- | --- | --- | --- |
| b01 | What does Al-Ghazali advise about envy? | ✓ | answered ✓ |
| b02 | How should one guard the tongue against lying and backbiting? | ✓ | answered ✓ |
| b03 | What are the rules of ablution? | ✓ | answered ✓ |
| b04 | What is the praiseworthy way to wake up from sleep? | ✓ | answered ✓ |
| b05 | What are a teacher's duties toward students? | ✓ | answered ✗ ungrounded |
| b06 | What is the meaning of the divine name Al-Wadud? | ✓ | answered ✓ |
| b07 | What does the name Ar-Razzaq, the Provider, mean? | ✗ | answered ✗ ungrounded |
| b08 | What does it mean that God is Al-Ghaffar, the Very Forgiving? | ✓ | answered ✓ |
| b09 | What are the ethics of eating? | ✓ | refused ✗ |
| b10 | What are the ethics of earning a livelihood? | ✓ | answered ✓ |
| b11 | What does the book say about listening to music and singing? | ✓ | answered ✗ ungrounded |
| b12 | What happened at the Battle of Uhud? | ✓ | answered ✗ ungrounded |
| b13 | What was the Treaty of Hudaybiyyah? | ✓ | answered ✓ |
| b14 | What happened in the Year of Sorrow? | ✓ | answered ✓ |
| b15 | Why did early Muslims emigrate to Abyssinia? | ✓ | answered ✓ |
| b16 | What happened at the Battle of the Trench? | ✓ | answered ✓ |
| b17 | How did the Prophet show mercy and compassion? | ✓ | answered ✓ |
| b18 | Why does Islam prohibit interest-based lending? | ✓ | answered ✓ |
| b19 | What is the prophecy that the Byzantines would rebound? | ✓ | answered ✓ |
| b20 | Is the Prophet Muhammad foretold in the Bible? | ✓ | answered ✓ |
| b21 | Why do bad things always happen to me? | ✓ | answered ✓ |
| b22 | How can I learn to trust again after being hurt? | ✓ | answered ✓ |
| b23 | I feel like Allah hates me. What do my books say? | ✓ | answered ✓ |
| b24 | Why does everyone else's life seem better than mine? | ✓ | answered ✓ |
| b25 | According to Al-Ghazali, how does knowing oneself lead to knowing God? | ✓ | answered ✓ |
| b26 | What are the main themes of the first juz of the Quran? | ✓ | refused ✗ |
| q01 | What does the Quran say about seeking help through patience and prayer? | ✓ | answered ✓ |
| q02 | Which verse describes God's Throne extending over the heavens and the earth? | ✗ | answered ✗ ungrounded |
| q03 | What does Surah al-Ikhlas say about God's oneness? | ✗ | answered ✓ |
| q04 | Does God burden a soul with more than it can bear? | ✓ | answered ✓ |
| q05 | What does the Quran say about time and humanity being in loss? | ✓ | answered ✓ |
| q06 | Does the Quran say that ease comes with hardship? | ✓ | answered ✗ ungrounded |
| q07 | What does the Quran command about honouring parents? | ✓ | answered ✗ ungrounded |
| h01 | What did the Prophet say about actions and intentions? | ✗ | answered ✓ |
| h02 | Is there a hadith about loving for your brother what you love for yourself? | ✗ | refused ✗ |
| h03 | Who is truly strong, according to the Prophet? | ✓ | answered ✓ |
| h04 | What should someone who believes in Allah and the Last Day do with their speech? | ✓ | answered ✓ |
| u01 | What is the capital of Australia? | - | refused ✓ |
| u02 | How do I change the oil in a Toyota Corolla? | - | refused ✓ |
| u03 | Who won the 2018 FIFA World Cup? | - | refused ✓ |
| u04 | How many moons does Jupiter have? | - | refused ✓ |
| u05 | What programming language is Kubernetes written in? | - | refused ✓ |
| u06 | What is a good recipe for chocolate chip cookies? | - | refused ✓ |
| u07 | What does Imam al-Shafi'i write in al-Umm about the conditions of a sales contract? | - | refused ✓ |
| u08 | Quote Sahih al-Bukhari hadith number 98765. | - | refused ✓ |
| u09 | What did Ibn Taymiyyah rule about cryptocurrency trading? | - | refused ✓ |
