# praat-web

Phonetic analysis in the browser, with annotation tiers that can record what a speaker articulated rather than what a pronunciation dictionary predicts.

The analysis is Praat itself, compiled to WebAssembly. Pitch comes from `To Pitch`, formants from `To Formant (burg)`, and the spectrogram from `To Spectrogram`, with the same arguments and defaults you would type into the Praat script window. The audio is decoded and analysed inside your browser. Nothing is uploaded, and the tool makes no network request with your recording unless you explicitly send it to a transcription service you have configured.

```
python3 serve.py        # then open http://127.0.0.1:8710
```

Python 3.8 or later, standard library only. There is no build step, no `pip install`, and no Node. On first run the server downloads the `praat-wasm` package (about 24 MB) into `vendor/` and caches it.

## What you get with no backend at all

- A waveform, where dragging selects the analysis window.
- A spectrogram with configurable ceiling and dynamic range, carrying **f0**, **F1**, **F2** and **F3** as overlaid tracks.
- A readout of f0 and F1 to F3 at the cursor.
- Word and phone tiers.
- **TextGrid export**, including an empty grid spanning the file, which is how a hand annotation begins in Praat.

Analysis runs on the visible window only, as Praat's own editor does. The cost is roughly 270 ms per second of audio, so analysing an hour-long interview in one pass would stall the tab. Drag on the waveform to move the window.

## Why the tiers are not forced alignment

Conventional forced alignment begins with orthography. An aligner such as the Montreal Forced Aligner takes a transcript, looks each word up in a pronunciation dictionary, and fits the resulting phone string to the signal. The labels therefore originate in the lexicon rather than in the recording. The more capable systems soften this: MAUS builds a graph of pronunciation variants from rules and selects among them, so it can prefer a reduced realisation over a citation form. Even then the candidate set is derived from the lexicon and the rules, which means the aligner chooses among the realisations it was told to expect. A variant nobody encoded cannot be selected, and the segments where that matters are exactly the ones a phonetician is likely to be studying.

praat-web is built around a different source of labels. Its tier contract expects a recogniser that reads phones off the acoustics and emits IPA directly, with no lexicon in the path. Models of this kind, such as PhoneticXeus or the wav2vec2 IPA models fine-tuned on Buckeye, produce a symbol because the frames supported it. When a speaker reduces *going to* to something closer to [ɡʌnə], a dictionary-driven aligner records the canonical sequence and distributes it across the interval, while a phone recogniser records the reduction. The distinction is not cosmetic. It determines whether your annotation can be evidence about variation or merely a restatement of the transcript.

Pairing the two kinds of model on one timeline is what the interface is for. The word tier comes from an orthographic recogniser, the phone tier from a phone recogniser, and the two are independent observations of the same signal. Where they diverge, the divergence is itself the finding: the word tier preserves the lexical item a listener would report, while the phone tier preserves the realisation. A researcher studying lenition, connected-speech processes or sociophonetic variation wants both, aligned, and wants to see them under a spectrogram rather than in a table.

The second thing this arrangement allows is work on languages that have no pronunciation dictionary at all. Forced alignment is unavailable, in practice, wherever a lexicon has not been built, which excludes most of the world's languages and nearly all of the ones that documentation projects are concerned with. Orthographic models such as MMS cover over a thousand languages, and multilingual phone recognisers generalise across inventories precisely because they never consult a lexicon. For Avar, Chechen or Dargwa there is no aligner dictionary to fall back on, yet a phone recogniser will still return IPA with frame-level timing. The tier contract below is deliberately model-agnostic so that this route remains open.

## What the phone timings actually are, and what they are not

The timings deserve a precise statement, because their usefulness depends on what they measure.

A CTC phone recogniser produces a distribution over its symbol inventory for every frame, typically one frame per 20 ms. Decoding yields a symbol together with the frame at which the model committed to it. `phone_times` in the contract below carries those frame times, so each phone label is timed from the model's own reading of that token rather than interpolated across a word interval. This is the sense in which the boundaries follow the articulation. They derive from the acoustics of the instance in front of you rather than from a template stretched to fit.

They are not, however, measurement-grade segment boundaries, and reporting them as such would misrepresent them. CTC output is peaky: the model tends to commit to a label at one frame near the middle of the evidence for it and to emit blanks elsewhere, so a spike marks the region of a segment rather than its onset. Frame resolution puts a floor of roughly 20 ms under any boundary. Treating consecutive spikes as a segment's start and end, which is what this viewer draws, therefore gives a good approximation of where a phone lies and a poor estimate of how long it lasted.

The practical consequence shapes how the tool is meant to be used. Machine phone labels are a first pass that you verify against the spectrogram, and the viewer exists to put them where that verification is cheap. For locating tokens, counting them, or cutting a corpus into candidates for closer study, spike times are sufficient. For duration measurements, VOT, or anything else where a few tens of milliseconds carry the argument, correct the boundaries by hand in Praat, which is why the export is a TextGrid rather than a proprietary format.

Two further limits are worth stating plainly. A phone recogniser has its own error rate and its own inventory, so a symbol absent from the inventory cannot appear no matter how clearly it was articulated. PhoneticXeus, for instance, returned no tone marks on Vietnamese in testing, which is worth verifying before relying on it for any tonal language. Word intervals, meanwhile, come from a separate forced aligner in most pipelines, so the word tier inherits that aligner's assumptions even when the phone tier does not.

## Getting the annotation out

The export is a TextGrid because that is the format both major annotation tools read. Praat opens it directly. ELAN imports it through File > Import > Praat TextGrid File, adding each tier to the open document or creating a new one, and it accepts UTF-8 as well as UTF-16, so the encoding written here needs no conversion.

That choice matters more for documentation work than for laboratory phonetics. Fieldwork projects generally keep their sessions in ELAN, where phonetic tiers sit on one timeline alongside translation, gloss and gesture tiers. Exporting a TextGrid lets a recogniser's phone tier enter an existing ELAN session, rather than starting a parallel annotation that somebody has to reconcile later. For the undocumented languages discussed above, that is usually the deciding practical question, because the session already exists in ELAN before any acoustic analysis begins.

One point about the import itself. Praat requires the intervals of a tier to tile the file without gaps, so this tool writes an empty interval wherever no word or phone falls. ELAN's import dialog offers "Skip empty intervals / annotations", and leaving that checked keeps the padding out of the ELAN document, where it would otherwise arrive as a run of empty annotations.

## Connecting a recogniser

If you have a speech-recognition server that speaks the OpenAI audio API, enter its base URL under **⚙** and the word tier fills itself. Anything implementing `POST {base}/v1/audio/transcriptions` will work, whether that is a local Whisper wrapper, llama-swap, or a hosted service.

The request is `multipart/form-data` carrying `file`, `model`, `response_format=verbose_json`, an optional `language`, and an optional `asr_model`. To draw tiers, the response needs timed words:

```jsonc
{
  "text": "...",
  "language": "en",
  "cues": [{
    "start": 1.12, "end": 2.48,
    "words": [{
      "text": "when",
      "start": 1.12, "end": 1.26,
      "phones": ["w", "ɛ̃", "n"],          // optional: fills the phone tier
      "phone_times": [1.12, 1.17, 1.22]   // optional: per-phone frame times
    }]
  }]
}
```

`cues[].words[]` with `start` and `end` fills the word tier. Adding `phones` produces a phone tier as well. Adding `phone_times` is what distinguishes this from an even division of the word. Without it the viewer spaces the symbols evenly across the interval, which is a display convenience and carries no information about the recording. A response without `cues` still transcribes, but it cannot draw tiers.

Two optional endpoints are used if present and ignored if not. `GET {control}/progress`, returning `{active, model, stage, done, total, elapsed}`, drives a progress bar, and `POST {control}/cancel` enables the Stop button. The control path defaults to `/upstream/asr` and is configurable.

A cross-origin endpoint must send CORS headers. If the recogniser runs on a different host or port from this page and does not set `Access-Control-Allow-Origin`, the browser will refuse the request. Serving both from one origin avoids the problem.

## Notes that cost someone a day

- **Praat writes TextGrids in UTF-16.** This project emits UTF-8 directly, which Praat reads without complaint.
- **Praat rejects an entire TextGrid over a single inverted interval** (`Wrong xmin ... and xmax ...`). Phone spike times are absolute and can fall a few milliseconds past the end of the word they were assigned to, so intervals are forced sorted, non-overlapping and strictly increasing before export.
- **Formant dots appear during silence.** That is the Burg algorithm, which always returns a solution, rather than a fault in the tracker. Praat behaves identically.
- Audio is re-encoded to 16 kHz mono WAV in the browser before Praat receives it. Praat's `readAudio` accepts WAV, AIFF, FLAC, MP3 and OGG, while the browser's own decoder also handles m4a, mp4 and webm, so re-encoding means anything your browser can play can be analysed.
- A `File` object cannot survive a page reload, so re-select the audio after one.

## Credits and licence

The analysis is [**Praat**](https://www.fon.hum.uva.nl/praat/) by Paul Boersma and David Weenink, via [**praat-wasm**](https://www.npmjs.com/package/praat-wasm) (6.4.6200) by reynoldsnlp. This project supplies an interface and an alignment contract. The phonetics is theirs.

If Praat contributed to published work, cite it as its authors ask:

> Boersma, Paul & Weenink, David. *Praat: doing phonetics by computer* [Computer program]. http://www.praat.org/

Praat and praat-wasm are GPL-3.0-or-later, and so is this project. See [LICENSE](LICENSE). `vendor/` is not committed. Either let `serve.py` fetch it, or run `npm pack praat-wasm@6.4.6200 && tar xzf praat-wasm-6.4.6200.tgz && mv package vendor`.
