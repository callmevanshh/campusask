# CampusAsk development log

What I built, what broke, why, and how I fixed it, in the order it happened. Numbers are from my own tests. AI assistants helped write code; the testing and the debugging below are mine.

## 1. Choosing the project
My first idea was an auditor that checks ML papers against their GitHub repositories. It needed sandboxed code execution and several agents, which is too much for a first project. I chose something smaller that I could finish and measure: a Q&A assistant over IIIT Delhi's public academic documents. It has real users, and I can build an answer key for it.

## 2. Setup mistakes
- Python 3.14 was too new for the ML libraries, so I used 3.12 in a virtual environment.
- Running `main.py` from the editor's play button used the system Python ("No module named fastapi"). The app must be started with `uvicorn` inside the venv.
- Two files were in the wrong folder, and my README was committed empty because the editor tab was unsaved. I made a habit of running `git status` before every commit.
- My college email was in the first commit. I switched to the GitHub no-reply address and rewrote that single commit while I was the only contributor.

## 3. Data
- I used only public documents. The student portals are behind logins and stay out.
- The site hosts every version of the UG regulations back to 2015, so I indexed the latest and added version metadata.
- The last pages of each regulation are a change history. They were being retrieved as if they were rules, so I exclude them per document in `sources.csv`.
- A PDF I opened in the browser's viewer got overwritten and became unreadable ("zlib error"). I re-downloaded it with PowerShell, because Python's HTTPS client failed on the college site's certificate chain.

## 4. Chunking and search
Pages are cut into overlapping chunks that keep page numbers, so citations point to a page. I compared keyword (BM25), semantic (`all-MiniLM-L6-v2`) and hybrid search. A first question ("attendance requirement") ranked a registration page above the attendance rule for semantic search, which is why I looked at keyword search at all.

## 5. The evaluation that scored 32%
My first answer key had 50 questions and hybrid search scored 32% hit@3. I wrote an audit script that prints, for every miss, what was retrieved and what the gold page actually says. Of 27 misses, **21 were wrong page labels in my own questions**, 3 were real retrieval failures (for example "class 12" against "class XII"), and 4 were questions the documents do not answer. I fixed the labels, moved 3 questions to "unanswerable" after checking the PDF, and wrote a separate held-out test set so I was not tuning on the questions I had just corrected. Later I added sets for informal wording, very short questions and program-specific questions.
**Lesson:** audit the answer key before touching the system.

## 6. The model, and the first quota wall
- Gemini answers from the retrieved chunks with a "cite or say not found" prompt.
- `gemini-2.0-flash` was retired and returned 404. The model name moved to an environment variable.
- The first model I used allowed 5 requests a minute and 20 a day on the free tier, and I used them up testing. I moved to a Flash-Lite model (15 a minute, 500 a day) and added a cache, a per-IP rate limit and a passages-only fallback.

## 7. Deployment
- Hugging Face Docker Spaces turned out to require a paid plan.
- Render's free tier has 512 MB of RAM, which cannot hold the embedding model. Because keyword search matched or beat hybrid on my sets (dev / test / informal hit@3: keyword 100 / 100 / 94, hybrid 97 / 93 / 88, semantic 83 / 93 / 76), production runs keyword-only and the choice is backed by data.
- Free Render services sleep. UptimeRobot pings `/health` every five minutes.

## 8. The relevance gate that could not work
I tuned a keyword-score threshold on well-phrased questions. Then a short valid question ("how many credits to graduate") scored 3.1 and the off-topic "who won the cricket world cup" scored 4.9, so no threshold could separate them. BM25 scores depend on question length. I made the gate loose (it only drops questions with no keyword match) and let the model decide relevance. A 26-question refusal test now refuses all 26.

## 9. "Arre yaar"
A prompt line told the model to reply briefly to greetings. It treated "who won the world cup" as small talk and chatted back. Small talk is now handled in code before any model call, and a reply without a citation is treated as "not found".

## 10. Tables
- PyMuPDF garbled the course tables: merged cells were duplicated and a row was split across two pages ("Computer" on one page, "Organization" on the next).
- I transcribe those pages from page images with Gemini (17 page groups, one call each), merge tables across page breaks in code, and checked the CSB output against the PDF.
- A table's batch is only in its caption line, and a model attributed a 2018 table to the 2024 batch. The caption is now stored with the table chunk, each table gets a batch year, and the newest batch is preferred unless the student names a year.
- Cells hold several courses separated by line breaks; the UI first collapsed them into one line, and a citation placed after a table row broke the table. Both fixed in the renderer.

## 11. Many programs, one corpus
- "CSB branch graduation requirements" matched the UG "Branch Transfer" section because of the word "branch". When a program is named, generic words like "branch" and "program" are now dropped from the query.
- A table headed "1st Semester" did not match "first semester". Ordinals are normalised on both sides.
- Generic questions got buried under nine near-identical program regulations, so program documents are down-weighted unless a program is named.
- I built a program dropdown, then removed it: the program can be read from the question or the chat, and the bot asks when it needs it.

## 12. A labelling bug
Each chunk was labelled with the last heading inside it. The chunk holding "CGPA of 8.0 or more" for Honors was labelled "Minor" and no longer contained the word "honors", so the Honors question failed. A diagnostic script showed it ranked 34th. Chunks are now labelled with the heading in effect at their start plus any headings inside, and a chunk that continues a section is joined with the next one. I had also tried injecting the answer's number into the query; I removed that because it makes the evaluation dishonest.

## 13. Chat state
- Long questions containing words like "that" or "they" were merged with the previous question. A message now counts as a follow-up only if it has no topic words of its own.
- A "not found" answer was dropped from the history while its question stayed, so the model answered that old question together with the new one. History now keeps or drops whole turns.
- A reply to the bot's own clarifying question was searched on its own and refused. It is now joined to the question it answers.
- Model output sometimes contained LaTeX the UI cannot render, repeated my instructions, or ended with an empty table. These are cleaned in code, with deterministic tests (`chat_check`) that need no model.

## 14. Questions about a student's own numbers
Students ask things like "I have 116 credits and plan 24 and 22, will I complete?". Early answers promised outcomes, brought in unrelated rules, and one concluded that 152 credits satisfy a 156-credit minimum. The prompt now makes the model state the rule, apply the numbers, check the plan against every limit, never promise graduation, list what it cannot check, and point to the academic office.

## 15. Maths belongs in code
The same CGPA-target question gave a required SGPA of 5.29 in one run and 5.24 in the next. Prompts do not fix arithmetic. The model now only extracts the numbers (strict JSON, range-checked); Python computes the required SGPA and the smallest grade mix in whole courses and hands it back as a verified block the answer must copy. Three runs now agree (5.29), and an unreachable target is reported as unreachable.

## 16. A production outage
The live site showed the passages-only fallback for every question. The old retry loop slept up to 90 seconds on a 429 before giving up. I did not capture the Render logs, so a quota error is the likely cause, not a confirmed one. The answer step now tries the next configured model immediately, with a 40-second total budget. One backup model returned HTTP 500 in my own check and was removed from the list.

## Not built, on purpose
Admin panel, analytics, accounts, hostel and fee documents, postgraduate regulations, timetables (they change every semester).

## What I would do next
Index the missing documents, measure accuracy on questions from real students, support fixed-grade constraints and two targets in the planner, and replace the free-tier model quota with a plan that can take real traffic.

## Lessons
1. Audit the answer key before tuning the system.
2. Anything with a right answer (numbers, dates, comparisons) belongs in code, not in a prompt.
3. Free tiers shape the architecture: memory limits chose the search method, request limits chose the fallbacks.
4. Test conversation logic without the model so it is fast and repeatable.
5. Measure first; when something breaks, add a test that would have caught it.