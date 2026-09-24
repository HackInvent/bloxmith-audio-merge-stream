# Audio Merge Stream

<!-- block-metadata:start -->
[![Block version: 0.1.0](https://img.shields.io/badge/block-0.1.0-blue)](model.json)
[![BloxSmith compatibility: 1.0.9](https://img.shields.io/badge/BloxSmith-1.0.9-brightgreen)](compatibility.json)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)

Verified BloxSmith versions: **1.0.9** (bundled-block tests; see [test evidence](compatibility.json)).
<!-- block-metadata:end -->

## Role

Multiplex independent Opus sources through a single audio output without decoding, re-encoding or changing their audio bytes. This is not a sound mixer: overlapping voices remain separate streams.

## Wiring

Each source has a visible pair: `audio_in_N` (audio) and `command_in_N` (JSON).
Connect both outputs of Microphone Stream, Telephony or OpenAI TTS Stream to the
same numbered pair. A port accepts one link. Two default pairs remain present;
**Add a source** creates more pairs, up to eight, using stable IDs.

Outputs are `audio_out` and `command_out`; commands never travel implicitly
inside the audio link. Connect both to Save Audio or a compatible consumer.
Connect the merged audio to both VAD and STT: their source clocks and remapped stream IDs must match. Do not feed VAD from this output while feeding STT directly from the original producer.

Opus in WebM or Ogg, 48 kHz decoding clock, mono or stereo. Container headers, sequences, timestamps and correlation IDs are retained. Stream IDs are remapped per source/capture to prevent collisions across producers.

## Lifecycle and limits

Listening starts at **Run**, without Play or a data trigger. The first audio chunk
can precede start. Producer commands are separate JSON messages:

```json
{"action":"start","stream_id":"capture"}
{"action":"stop","stream_id":"capture","frame_count":12,"byte_count":32000,"aborted":false}
```

A batch may contain 1–64 commands. Only fresh deliveries are interpreted. Stop can
arrive before the final audio: counts include every chunk and container header.
A non-aborted stop is successful only after exact totals are reconciled.
An aborted source is retired without stopping other sources. Missing/duplicated
frames, changing profiles, malformed commands and saturated buffers fail visibly.
Global interruption commands or VAD begin/commit events are not producer lifecycle
commands and must not be connected here.

There are at most 16 open captures and 256 retired identities per Run. Producers
must use fresh IDs within a Run. Always connect producer commands for clean
completion; network inactivity never proves completion. Downstream limits remain
independent: the current VAD accepts at most **four open captures**.

Each source retains its own lifecycle and no audio samples are combined. Downstream
consumers must support several stream IDs on one link; this is not guaranteed for
every third-party player. No FFmpeg or extra Python package is required by Merge.
The block buffers only bounded per-stream metadata, not full recordings.

Processing errors abort unfinished output when possible. Runtime Stop revokes
services and promptly releases local resources; it cannot guarantee delivery of a
final business stop. **One Shot Simulation skips continuous audio**, opens no
codec or device and emits no lifecycle commands.

## Properties and ergonomics

The modal and inspector expose the same source editor: source names, visible
audio/command pairing, and progressively disclosed advanced settings.
Every change stays local until **Apply**. **Reset draft** or closing the modal
discards unsaved changes. Close and Apply remain reachable at narrow sizes.
Rename preserves port IDs and links. Added sources can be removed only after
disconnecting their links; the block never silently deletes a connection.
The two default sources cannot be removed; leave an unused pair unconnected.

Ports are managed exclusively as pairs in this editor, instead of offering an
independent generic Ports editor that could break their association.
Changes require **Stop, then Run**.
Properties are release-scoped ES modules with English and French catalogs.
The compact canvas card summarizes the role and source names.

## Files and tests

- `block.py`: public lifecycle hooks and behavior markers.
- `config.py`: source/command validation and stable port identities.
- `runtime.py`: fair bounded listener and explicit command hand-off.
- `engine.py`: byte-preserving multiplexing and stop reconciliation.
- `ui.py`, templates, `assets/`, `locales/`: owned draft editor and translations.
- `tests/`: portable tests using synthetic audio and disposable framework instances.

From the private integration workspace:

```sh
python3 -B tests/run_tests.py audio_merge_stream
```

Tests use no real microphone, telephone or paid provider. Public block tests do not
bundle the proprietary framework. Compatibility evidence is maintained by
HackInvent in `compatibility.json`; a local passing run is not a published release.

Managed/linked integration tests route two original synthetic voice recordings
through Merge to both Save Audio and the existing Silero VAD. They verify exact
file bytes and two independent speech cycles. Browser tests exercise modal and
inspector drafts, paired-port editing, English/French catalogs and layouts from
320 px to desktop.

## License

Apache-2.0. Merge does not require a codec process; FFmpeg is used only by its tests.
