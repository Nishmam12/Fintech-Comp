import React from "react";
import { AbsoluteFill, Audio, Composition, Sequence, interpolate, staticFile, useCurrentFrame } from "remotion";
import { ALL } from "./scenes";
import { C } from "./tokens";
import { FPS, SCENES, TOTAL } from "./timing";

/** Each scene fades in over 8 frames from the paper colour and out over 6; the voice runs underneath, unbroken. */
const Scene: React.FC<{ i: number; dur: number }> = ({ i, dur }) => {
  const f = useCurrentFrame();
  const S = ALL[i];
  const o = interpolate(f, [0, 8, dur - 6, dur], [0, 1, 1, i === ALL.length - 1 ? 1 : 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return <AbsoluteFill style={{ background: C.paper }}><AbsoluteFill style={{ opacity: o }}><S d={dur} /></AbsoluteFill></AbsoluteFill>;
};

const Film: React.FC = () => (
  <AbsoluteFill style={{ background: C.paper }}>
    <Audio src={staticFile("vo.wav")} />
    {SCENES.map((s, i) => (
      <Sequence key={i} from={s.from} durationInFrames={i === SCENES.length - 1 ? s.dur + 45 : s.dur}>
        <Scene i={i} dur={i === SCENES.length - 1 ? s.dur + 45 : s.dur} />
      </Sequence>
    ))}
  </AbsoluteFill>
);

export const RemotionRoot: React.FC = () => (
  <Composition id="BudgetKernel" component={Film} durationInFrames={TOTAL} fps={FPS} width={1920} height={1080} />
);
