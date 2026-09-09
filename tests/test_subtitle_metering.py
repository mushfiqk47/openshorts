"""What burning captions costs the user.

Captions are mandatory for short-form to work at all, and the path costs
the server nothing beyond one short FFmpeg pass — the transcript is already in
metadata.json. (The old dubbed exception, a fresh Whisper pass over translated
audio, died with auto-transcription.)
"""
from cloud.config import subtitle_minutes_for


class TestSubtitleMetering:
    def test_normal_clip_is_free(self):
        assert subtitle_minutes_for("Some_Video_Title_clip_1.mp4") == 0

    def test_already_subtitled_clip_is_free(self):
        # Restyling captions must not cost anything either.
        assert subtitle_minutes_for("subtitled_1784974487_My_Video_clip_1.mp4") == 0

    def test_hooked_or_edited_clip_is_free(self):
        assert subtitle_minutes_for("edited_My_Video_clip_2.mp4") == 0

    def test_dubbed_clip_is_free_now(self):
        # The old exception (a fresh Whisper pass over translated audio) died
        # with auto-transcription: dubbed clips use the stored transcript.
        assert subtitle_minutes_for("translated_es_My_Video_clip_1.mp4") == 0

    def test_dubbed_prefix_must_be_at_the_start(self):
        # A clip merely containing the word must not be charged.
        assert subtitle_minutes_for("my_translated_notes_clip_1.mp4") == 0

    def test_handles_non_string_input(self):
        assert subtitle_minutes_for(None) == 0
