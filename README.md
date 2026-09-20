# praat-web

Phonetic analysis in the browser: waveform, spectrogram, pitch and formant tracks, annotation
tiers, and a **TextGrid** you can open in desktop Praat.

The analysis is not an approximation of Praat — it *is* Praat, compiled to WebAssembly. Pitch
comes from `To Pitch`, formants from `To Formant (burg)`, the spectrogram from `To Spectrogram`,
with the same arguments and the same defaults you would type into the Praat script window.

Nothing is uploaded. The audio is decoded and analysed inside your browser. The one exception is
the optional **Run ASR** button, which sends the file to a transcription endpoint *you* configure;
leave it unconfigured and the tool never makes a network request with your audio at all.

```
python3 serve.py        # then open http://127.0.0.1:8710
```

Python 3.8+, standard library only. No build step, no `pip install`, no Node. On first run it
downloads the `praat-wasm` package (~24 MB) into `vendor/` and caches it.

## What you get without any backend

- Waveform, with drag-to-select the analysis window
- Spectrogram (configurable ceiling and dynamic range), with **f0**, **F1**, **F2**, **F3**
  overlaid
- A readout of f0 and F1–F3 at the cursor
- Word and phone tiers
- **TextGrid export** — including an empty one spanning the file, which is how you start a hand
  annotation in Praat

Analysis runs on the **visible window only**, which is what Praat does too: cost is roughly
270 ms per second of audio, so analysing a whole lecture at once would hang the tab. Drag on the
waveform to move the window.

## Optional: fill the tiers automatically

If you have a speech-recognition server that speaks the OpenAI audio API, put its base URL in
**⚙** and the word tier fills itself. Anything implementing
`POST {base}/v1/audio/transcriptions` works — llama-swap, a local Whisper wrapper, or a hosted
service.

The request is `multipart/form-data` with `file`, `model`, `response_format=verbose_json`, an
optional `language`, and an optional `asr_model`. To fill the tiers, the JSON response needs
timed words:

```jsonc
{
  "text": "...",
  "language": "en",
  "cues": [{
    "start": 1.12, "end": 2.48,
    "words": [{
      "text": "when",
      "start": 1.12, "end": 1.26,
      "phones": ["w", "ɛ̃", "n"],          // optional — fills the phone tier
      "phone_times": [1.12, 1.17, 1.22]   // optional — real phone boundaries
    }]
  }]
}
```

`cues[].words[]` with `start`/`end` fills the **word tier**. Add `phones` and you get a **phone
tier** as well; add `phone_times` and its boundaries are real rather than an even split across
the word. A response without `cues` still transcribes, it just cannot draw tiers.

Two optional extras, used if present and silently ignored if not: `GET {control}/progress`
returning `{active, model, stage, done, total, elapsed}` drives a live progress bar, and
`POST {control}/cancel` enables the **Stop** button. The control path defaults to
`/upstream/asr` (llama-swap's passthrough) and is configurable.

**A cross-origin endpoint must send CORS headers.** If the ASR server is on a different
host or port from this page and does not set `Access-Control-Allow-Origin`, the browser will
block the request. Serving both from the same origin avoids the problem entirely.

## Notes that cost someone a day

- **Praat writes TextGrids as UTF-16.** This project emits UTF-8 directly, which Praat reads
  without complaint.
- **Praat rejects an entire TextGrid over one inverted interval** (`Wrong xmin ... and xmax ...`).
  ASR phone times are absolute and can land a few milliseconds past the end of the word they were
  assigned to, so intervals are forced sorted, non-overlapping and strictly widening before
  export.
- **Formant dots appear in silence.** That is the Burg algorithm, which always returns something,
  not a fault in the tracker. Praat behaves the same way.
- Audio is re-encoded to 16 kHz mono WAV in the browser before Praat sees it. Praat's `readAudio`
  handles WAV/AIFF/FLAC/MP3/OGG, but the browser's decoder also handles m4a/mp4/webm, so
  re-encoding means anything your browser can play can be analysed.
- A `File` cannot survive a page reload, so re-pick the audio after one.

## Credits and licence

Analysis is [**Praat**](https://www.fon.hum.uva.nl/praat/) by Paul Boersma and David Weenink,
via [**praat-wasm**](https://www.npmjs.com/package/praat-wasm) (6.4.6200) by reynoldsnlp.

If Praat contributed to published work, cite it as its authors ask:

> Boersma, Paul & Weenink, David. *Praat: doing phonetics by computer* [Computer program].
> http://www.praat.org/

Praat and praat-wasm are GPL-3.0-or-later, so this project is too. See [LICENSE](LICENSE).
`vendor/` is not committed — `serve.py` fetches it, or run
`npm pack praat-wasm@6.4.6200 && tar xzf praat-wasm-6.4.6200.tgz && mv package vendor`.
