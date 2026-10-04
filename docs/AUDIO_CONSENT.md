# Audio recording consent

Updated: 2026-10-04
Phase: [ROADMAP.md](ROADMAP.md) Phase 0 · Rights: [DATA_RIGHTS.md](DATA_RIGHTS.md)

This is a **draft**. Before any recording:

- a lawyer familiar with the laws where speakers live (United States, Myanmar, India, and others) reviews it;
- native-speaker editors translate the form into Zomi, and into Burmese where useful. The Zomi version must be read aloud and checked by a second speaker. Engineers do not write the Zomi text.

Speech data has the longest lead time of any Siamsil dataset, which is why collection starts in Phase 0. It is also the most personal: a voice identifies a person. The rules below favor the speaker over the dataset.

## Principles

1. **Separate choices.** Each use is a separate yes/no. Saying no to one never blocks the others, and saying no to everything is fine.
2. **No voice cloning without a specific yes.** Training a system that can produce speech sounding like the speaker is its own choice, off by default.
3. **Honest withdrawal.** Speakers can withdraw at any time. Recordings are removed from storage and all future dataset and model releases. Models already trained cannot be "untrained"; the form says so plainly.
4. **Adults only at first.** No recordings of anyone under 18 until a guardian-consent process has been reviewed.
5. **Oral consent counts.** For speakers who do not read, the collector reads the form aloud in Zomi and records the spoken answers as the consent record.
6. **Recordings are not anonymous.** The form must not promise anonymity. It can promise that names are kept out of published datasets.

## Consent form (English source text)

> **Siamsil voice recording — consent**
>
> Siamsil is building tools for the Zomi language, such as a dictionary, translation, and lessons. We are asking Zomi speakers to record their voices so these tools can one day understand and speak Zomi.
>
> **What we will record:** you reading or saying sentences, words, or stories. You can skip anything you do not want to say, and stop at any time.
>
> **What we keep:** the audio, a written transcript, and the details you choose to share below. Your name and contact details are kept separately from the recordings, and only the Siamsil data team can see them.
>
> **Your choices.** Please answer each one. You can say yes to some and no to others.
>
> 1. May we keep your recordings and use them to build and test Siamsil tools? **Yes / No**
> 2. May we use your recordings to train speech recognition (computers understanding spoken Zomi)? **Yes / No**
> 3. May we use your recordings to train speech that sounds like a voice, such as reading words aloud in the app? This could produce speech that sounds like you. **Yes / No**
> 4. May we play your actual recordings in the Siamsil app, for example as a word's pronunciation? **Yes / No**
> 5. May we share your recordings, without your name, in a public dataset for researchers and other Zomi projects? **Yes / No**
> 6. May Siamsil use tools trained on your recordings in paid services? **Yes / No**
> 7. How would you like to be credited? **By name / By initials / Not at all**
>
> **Changing your mind:** contact us at any time at [contact to be set] and we will delete your recordings and remove them from all future releases. Anything already trained with your recordings cannot be undone, but it will not be used to make new versions after you withdraw.
>
> **Risks:** your voice can be recognized by people who know you, even without your name. Please do not share private information about yourself or others while recording.
>
> **Payment:** [to be set — payment or acknowledgement terms].
>
> I am 18 or older, I understand this form, and my answers above are my choice.
>
> Name: ________ Date: ________ Signature or recorded spoken agreement: ________
> Collector: ________ Language the form was read in: ________

## What speakers read

- **Freely written or spoken Zomi** (everyday speech, stories, descriptions) is preferred: it belongs to the speaker.
- **Scripture and hymns** are only recorded once the text's copyright holder allows it. Reading a copyrighted translation aloud creates a recording of that text; see the Bible rows in [DATA_RIGHTS.md](DATA_RIGHTS.md).
- **Prompt sentences** must come from a source cleared for this use. Do not use the human evaluation sets as prompts; that would leak them.

## Records

Two separate stores. The consent store is access-controlled; only the recording store is ever used to build datasets.

**Consent record** (one per speaker per form version):

```json
{
  "speaker_id": "S0001",
  "form_version": "audio-consent-v1",
  "form_language": "zomi",
  "consent_method": "written",
  "date": "2026-10-04",
  "collector_id": "C01",
  "adult_confirmed": true,
  "choices": {
    "keep_and_evaluate": true,
    "train_recognition": true,
    "train_synthesis": false,
    "play_in_app": true,
    "public_dataset": false,
    "commercial_use": false
  },
  "credit": "initials",
  "withdrawn_at": null
}
```

`consent_method` is `written` or `oral`; an oral consent record also links to its audio. Name and contact details live only in the access-controlled roster, keyed by `speaker_id`.

**Recording metadata** (one per clip):

```json
{
  "clip_id": "S0001-0001",
  "speaker_id": "S0001",
  "consent_form_version": "audio-consent-v1",
  "transcript": "<what was said, transcribed by a native speaker>",
  "prompt_source": "spontaneous",
  "dialect_region": "<speaker's own description>",
  "age_range": "40-49",
  "recorded_at": "2026-10-04",
  "device": "<recorder or phone model>",
  "sample_rate_hz": 48000
}
```

Age range, gender, and region are optional and self-described. Every dataset build filters clips by the speaker's **current** consent choices, so a withdrawal or changed answer takes effect at the next build.

## Before the first recording

- [ ] Legal review of this form
- [ ] Zomi (and Burmese) translations by native speakers, independently checked
- [ ] Contact address and withdrawal process staffed
- [ ] Payment or acknowledgement terms set
- [ ] Access-controlled storage for consent records and the speaker roster
- [ ] Collector training: reading the form aloud, recording oral consent, stopping when asked
