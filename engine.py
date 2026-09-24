"""Lossless bounded multiplexing of independent Opus captures."""
from collections import deque
from dataclasses import dataclass, field
import time
import uuid
from .config import MAX_STREAMS


@dataclass
class Capture:
    """One input identity maps to one output identity, even across equal producer IDs."""
    output_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    frames: int = 0
    size: int = 0
    profile: tuple | None = None
    stop: dict | None = None
    deadline: float = 0


class MergeEngine:
    """Forward bytes unchanged; never concatenate containers into a single decoder."""

    def __init__(self, config, audio, emit):
        self.config, self.audio, self.emit = config, audio, emit
        self.captures, self.retired = {}, deque(maxlen=256)

    def capture(self, key):
        """Create bounded independent state; retire IDs cannot reopen within the window."""
        if key in self.retired:
            return None
        if key not in self.captures:
            if len(self.captures) >= MAX_STREAMS:
                raise ValueError("Too many open streams; connect each producer's command_out.")
            item = self.captures[key] = Capture()
            self.emit({"action": "start", "stream_id": item.output_id})
        return self.captures[key]

    def command(self, source, command):
        """Reconcile stop before/after final frames; cancellation affects only its source."""
        key = (source, command["stream_id"])
        item = self.capture(key)
        if item is None or command["action"] == "start":
            return
        if item.stop is not None and item.stop != command:
            raise ValueError("Conflicting stop totals for one stream.")
        item.stop = command
        item.deadline = time.monotonic() + self.config["drain_timeout_sec"]
        self.finish(key, item)

    def feed(self, source, frame):
        """Preserve container, sequence and timestamps while namespacing stream IDs."""
        key = (source, frame.stream_id)
        item = self.capture(key)
        if item is None:
            return
        if frame.sequence != item.frames + 1:
            raise ValueError("Missing, duplicated or reordered audio frame.")
        profile = (frame.codec, frame.sample_rate_hz, frame.channels)
        if profile[0:2] != ("opus", 48000) or profile[2] not in (1, 2):
            raise ValueError("Expected Opus at the 48 kHz decoding clock, mono or stereo.")
        if item.profile and item.profile != profile:
            raise ValueError("Audio format changed within a stream.")
        item.profile = profile
        if item.stop and (item.frames + 1 > item.stop["frame_count"] or item.size + len(frame.payload) > item.stop["byte_count"]):
            raise ValueError("Audio exceeds the declared completion totals.")
        self.audio.publish_port("audio_out", frame.payload, codec=frame.codec, sample_rate_hz=frame.sample_rate_hz,
            channels=frame.channels, stream_id=item.output_id, sequence=frame.sequence,
            timestamp_ms=frame.timestamp_ms, correlation_id=frame.correlation_id)
        item.frames += 1
        item.size += len(frame.payload)
        self.finish(key, item)

    def finish(self, key, item):
        """Stop only after observed totals match, unless the producer explicitly aborted."""
        stop = item.stop
        if stop is None:
            return
        if item.frames > stop["frame_count"] or item.size > stop["byte_count"]:
            raise ValueError("Stop totals are smaller than received audio.")
        if stop["aborted"] or (item.frames, item.size) == (stop["frame_count"], stop["byte_count"]):
            self.emit({"action": "stop", "stream_id": item.output_id, "frame_count": item.frames,
                       "byte_count": item.size, "aborted": stop["aborted"]})
            self.captures.pop(key, None)
            self.retired.append(key)

    def step(self):
        """Missing final data is a failure, never an invented successful stop."""
        if any(item.stop and time.monotonic() > item.deadline for item in self.captures.values()):
            raise ValueError("Timed out waiting for final source frames.")

    def close(self):
        """Best-effort explicit abort on a processing failure; Runtime Stop may revoke delivery."""
        for item in self.captures.values():
            try:
                self.emit({"action": "stop", "stream_id": item.output_id, "frame_count": item.frames,
                           "byte_count": item.size, "aborted": True})
            except Exception:
                pass
        self.captures.clear()
