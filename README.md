# topela - TOol for PErsonalized Language Acquisition

Topela is an AI-powered language learning platform that helps users learn vocabulary with Anki and read/hear learned words in context to enhance the process of learning vocabulary. 

The idea came from both a personal exigency to learn a copious amount of Belarusian vocabulary, and the latest research on second language acquisition like input hypothesis (Krashen), comprehensible input, spaced repetition, interleaving & mixed practice, incremental scaffolding, and more. 

It is built with Flask, OpenAI, Forvo, Google Images, and a (colossal) dash of love for languages.

<img width="884" height="492" alt="image" src="https://github.com/user-attachments/assets/317fc8d9-7f40-4b28-a02c-9bbe3e4861d6" />

## Functionality

- **Vocabulary Practice**  
  Dynamically generated quizzes based on Anki mature cards (learned words): multiple choice, translation, and verb inflection (cloze).

- **Reading Comprehension**  
  Automatically generates level-appropriate stories and comprehension questions through the AI pipeline.  

- **Listening Comprehension**  
  Turns those same stories into audio (TTS) and tests understanding through structured quiz questions.  

- **Smart Grading**  
  AI-based evaluation that tolerates small mistakes, focuses on meaning, and gives short explanations for errors.

- **Flashcard Creation Tool**  
  Pipeline for flashcard creation productivity, while still adhering to proper flashcard-making principles, like personally choosing images.
  The product of this subtool is a special flashcard I spent many weeks tailoring and balancing.

<img width="1257" height="866" alt="image" src="https://github.com/user-attachments/assets/abb6c279-e7c1-4fb3-b2bf-0af446f09bb6" />

## Architecture Overview

The app is built around a clean separation of responsibilities:

- Blueprints  
  Blueprints handle navigation, card generation, and quiz flows. Routes are intentionally thin as they only handle HTTP and delegate all logic to services.

- Services  
  All the heavy lifting (word sampling, story generation, quiz orchestration, LLM calls, grading, etc.) lives here.  

- Templates  
  Modular HTML pages: one template to select quiz settings, one to run a quiz, etc.

- Static  
  Lightweight CSS for styling and a `tmp/` folder to store generated audio on the fly.

<img width="708" height="395" alt="image" src="https://github.com/user-attachments/assets/627b6e9d-5d9e-48a7-91d2-b8327d81edcd" />

**Example Flow**
1. `/quiz` -> user selects deck, language, difficulty, quiz type.
2. `QuizService`:
   - pulls *seen* words from Anki,
   - calls `quiz_ai` to generate items (JSON),
   - for listening, uses `openai_svc.tts()` to generate text-to-speech,
3. `/quiz/start` renders the appropriate `*_run.html`.
4. `/quiz/grade`:
   - collects user answers,
   - calls an **evaluation** LLM pass,
   - renders `*_results.html` with score and minimal explanations if needed.

## Future Directions

This project is early in the stages, and is really only intended for personal use since I do not have the time to take the project to the next level. Thus, the only supported languages are Danish and Belarusian. 

I could, with the click of a button, add most languages and hope for the best, but each language is different and requires its own care and attenetion to detail. Adding languages without thought will distance the program from its primary purpose, which is to aid language learners in, well, learning.

As with many AI pipelines, there are minor inconsistencies, and at times errors, that require more time and attention to be away with. 
