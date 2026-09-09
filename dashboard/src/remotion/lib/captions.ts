import type { CaptionWord } from "./types";

export interface CaptionBlock {
  words: CaptionWord[];
  startMs: number;
  endMs: number;
  text: string;
}

/**
 * Groups word-level captions into display blocks.
 * Same logic as OpenShorts' generate_srt: max chars per block, max duration per block.
 * offsetMs shifts every word first (the manual sync nudge), clamping at 0 and
 * dropping words that end at or before 0 — mirrors _collect_word_blocks.
 */
export function groupCaptionsIntoBlocks(
  captions: CaptionWord[],
  maxChars = 20,
  maxDurationMs = 2000,
  offsetMs = 0
): CaptionBlock[] {
  const shifted: CaptionWord[] = [];
  for (const w of captions) {
    const startMs = w.startMs + offsetMs;
    const endMs = w.endMs + offsetMs;
    if (endMs <= 0 || endMs <= Math.max(0, startMs)) continue;
    shifted.push({ ...w, startMs: Math.max(0, startMs), endMs });
  }
  const blocks: CaptionBlock[] = [];
  let currentWords: CaptionWord[] = [];
  let blockStartMs = 0;

  for (const word of shifted) {
    if (currentWords.length === 0) {
      currentWords.push(word);
      blockStartMs = word.startMs;
      continue;
    }

    const currentTextLen = currentWords.reduce(
      (sum, w) => sum + w.text.length + 1,
      0
    );
    const duration = word.endMs - blockStartMs;

    if (
      currentTextLen + word.text.length > maxChars ||
      duration > maxDurationMs
    ) {
      // Finalize current block
      const lastWord = currentWords[currentWords.length - 1];
      blocks.push({
        words: [...currentWords],
        startMs: blockStartMs,
        endMs: lastWord.endMs,
        text: currentWords.map((w) => w.text).join(" "),
      });

      currentWords = [word];
      blockStartMs = word.startMs;
    } else {
      currentWords.push(word);
    }
  }

  // Final block
  if (currentWords.length > 0) {
    const lastWord = currentWords[currentWords.length - 1];
    blocks.push({
      words: [...currentWords],
      startMs: blockStartMs,
      endMs: lastWord.endMs,
      text: currentWords.map((w) => w.text).join(" "),
    });
  }

  return blocks;
}

/**
 * Find the active word at a given time in milliseconds.
 */
export function getActiveWordIndex(
  words: CaptionWord[],
  timeMs: number
): number {
  for (let i = 0; i < words.length; i++) {
    if (timeMs >= words[i].startMs && timeMs < words[i].endMs) {
      return i;
    }
  }
  return -1;
}
