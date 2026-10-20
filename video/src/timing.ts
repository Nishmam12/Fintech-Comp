// Scene boundaries found in the recording (silence detection on "Recording (58).aac", seconds, original speed),
// then the audio is played at 1.09x so the film stays under 5:00.
export const TEMPO = 1.09;
const BOUNDS = [0, 28.2, 57.2, 90.0, 130.5, 168.5, 195.0, 217.0, 257.5, 288.0, 312.0, 318.24];
export const FPS = 30;
export const SCENES = BOUNDS.slice(0, -1).map((b, i) => {
  const from = Math.round((b / TEMPO) * FPS);
  const to = Math.round((BOUNDS[i + 1] / TEMPO) * FPS);
  return { from, dur: to - from };
});
export const TOTAL = SCENES[SCENES.length - 1].from + SCENES[SCENES.length - 1].dur + 45;
