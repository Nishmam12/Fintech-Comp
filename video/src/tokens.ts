import { Easing, interpolate, spring } from "remotion";
import { loadFont as loadArchivo } from "@remotion/google-fonts/Archivo";
import { loadFont as loadCaveat } from "@remotion/google-fonts/Caveat";

export const { fontFamily: ARCHIVO } = loadArchivo();
export const { fontFamily: CAVEAT } = loadCaveat();

export const C = {
  paper: "#f1f2ee", sheet: "#fbfbf8", ink: "#17201c", ink2: "#3a453f", muted: "#5a635b", rule: "#d6d9d1",
  approve: "#1d6b47", held: "#8a5c00", refuse: "#a8361f", marker: "#ffd34d",
};
export const FPS = 30;

export const easeIn = Easing.bezier(0.2, 0.8, 0.2, 1);
export const easeOut = Easing.bezier(0.4, 0, 1, 1);

/** 0 -> 1 between frames a and b with the house entrance curve. */
export const t = (f: number, a: number, b: number) =>
  interpolate(f, [a, b], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: easeIn });
/** Overshoot-free spring that starts at frame `at`. */
export const sp = (f: number, at: number, fps = FPS) =>
  spring({ frame: f - at, fps, config: { damping: 200, stiffness: 120 } });
export const lerp = (a: number, b: number, k: number) => a + (b - a) * k;
export const money = (n: number) => n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
