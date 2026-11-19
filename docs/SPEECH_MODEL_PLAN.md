# Speech recognition and speech synthesis plan (draft)

Status: **plan, nothing built or approved.** It extends [SPEECH_DATA_LAB.md](SPEECH_DATA_LAB.md) and [AUDIO_CONSENT.md](AUDIO_CONSENT.md), which stay the rules. Rights come first, as for text ([DATA_RIGHTS.md](DATA_RIGHTS.md)). Licenses and model names below are from memory and must be checked before use.

## Two goals, two sets of rules

| | Speech recognition (ASR) | Speech synthesis (TTS, "a voice") |
|---|---|---|
| What it does | Turns spoken Zomi into text | Speaks Zomi text aloud |
| Data | Many speakers, recordings with accurate transcripts | A few consenting speakers, clean and consistent recordings |
| Consent needed | The speaker said yes to ASR training (consent choice 2) | The speaker said yes to voice training (choice 3), which can sound like them. Off by default |
| Paid use | Choice 6 (paid services) must also be yes | Same |
| Risk | Privacy of voices | Voice likeness: it can imitate a real person |

Both follow the same gate: a recording is used only when the rights holder's verified permission **and** every speaker's current consent say yes for that use. Anything missing means no. Withdrawal removes the recording from every future step.

## Phase 0: assess the dataset `freococo/zomi_asr` (Hugging Face)

Not yet read: Hugging Face was outside this session's network. Before any use, record in DATA_RIGHTS.md:

1. The dataset card as published, with the date you read it.
2. Who made it and where the recordings came from (public videos, radio, volunteers).
3. Its license, and whether it names or permits the speakers' use for training and for a voice.
4. Whether it is Tedim Zomi (`ctd`) or another variety.
5. Sample checks: 50 clips with their transcripts, read by Zomi speakers. Note transcript accuracy, noise, repeated speakers and any music or crosstalk.

If the recordings came from public videos with no recorded permission, the dataset stays `needs_review`, like the sentence corpus. A public license label on the dataset does not replace the speakers' and rights holders' permission.

## Phase 1: speech recognition

1. **Data.** Use only recordings cleared for ASR training. Segment into 5 to 20 second clips, cut at pauses. Transcripts are drafts until a Zomi reviewer and a different lead editor approve them (the same two-person rule, or the owner's recorded working-phase decision).
2. **Splits by speaker.** Train, validation and test must not share speakers, or the scores will look better than they are. Hold out a **hidden test set** of clips transcribed by hand by Zomi speakers, with the transcripts written before any model sees them.
3. **Base model.** Fine-tune an open speech model. Candidates to check: OpenAI's Whisper (I recall an MIT license), and wav2vec 2.0 / MMS style models (I recall some are non-commercial). Read each license for paid use, as with NLLB. Check how it handles Zomi's Latin script and any related languages as a starting point.
4. **Hardware.** Fine-tuning needs a GPU: your workstation, Colab for small trials, or a rented GPU. Not the web server. Training audio is personal data; keep it only on machines you control, never uploaded to an outside service without rights and consent.
5. **Measure.** Word error rate and character error rate on the hidden test set, per speaker group and per recording condition. Zomi speakers read a sample of outputs for meaning.
6. **Serve.** Opt-in, labelled "experimental", with spoken audio not stored by default. Paid use only when choice 6 is yes for the training speakers and the model license allows it.

## Phase 2: speech synthesis (a voice)

1. **New recordings.** Plan a recording session with a small number of adult speakers who explicitly said yes to voice training (choice 3), recorded in a quiet room with a decent microphone, reading a prepared script of everyday Zomi sentences approved by Zomi editors. Typically several hours per speaker are needed; check the model's requirements.
2. **No voice from anyone who did not agree.** Do not clone a voice from public recordings, from the ASR dataset or from any person who has not said yes to choice 3.
3. **Base model.** Check open text-to-speech models and their licenses for paid use, and whether they support a new language by fine-tuning.
4. **Evaluation.** Zomi listeners rate naturalness and correctness on a held-out script. Check pronunciation of names, numbers and loanwords.
5. **Safety.** Label synthetic audio as synthetic in the app, and keep the speaker's credit as they chose. If a speaker withdraws, the voice is removed from future releases; a model already trained cannot be untrained, and the consent form says so.

## Order of work

1. Phase 0 assessment of `freococo/zomi_asr`, recorded in DATA_RIGHTS.md.
2. Decide whether to recruit new speakers (needed for TTS, and for a clean ASR test set).
3. Build the Speech Data Lab pipeline steps (see SPEECH_DATA_LAB.md PR plan).
4. Train and measure ASR on a hidden, speaker-disjoint set.
5. Only then record and train a voice.

## Checklist before any speech model is used

- [ ] Every training recording has a verified source permission and each speaker's consent for that use.
- [ ] Speaker-disjoint hidden test set exists and is frozen.
- [ ] Base model license reviewed for paid use.
- [ ] Withdrawn sources and speakers removed from the training list.
- [ ] Model card lists data sources, rights, base model, training date and scores.
- [ ] Synthetic speech is labelled; voice models use only speakers who said yes to a voice.
