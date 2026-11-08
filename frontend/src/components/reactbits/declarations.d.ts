import React from 'react';

declare module '@/components/reactbits/Lightfall' {
  export interface LightfallProps {
    colors?: string[];
    backgroundColor?: string;
    speed?: number;
    streakCount?: number;
    streakWidth?: number;
    streakLength?: number;
    glow?: number;
    density?: number;
    twinkle?: number;
    zoom?: number;
    backgroundGlow?: number;
    headGlow?: number;
    depth?: number;
    bloom?: number;
    opacity?: number;
    mouseInteraction?: boolean;
    mouseStrength?: number;
    mouseRadius?: number;
    mouseDampening?: number;
    lens?: number;
    holdToWarp?: boolean;
    intro?: boolean;
    fade?: number;
    lightMode?: boolean;
    mixBlendMode?: string;
    paused?: boolean;
    dpr?: number;
    className?: string;
    style?: React.CSSProperties;
  }
  const Lightfall: React.FC<LightfallProps>;
  export default Lightfall;
}

declare module '@/components/reactbits/TechText' {
  export interface TechTextProps {
    text?: string;
    fontFamily?: string;
    fontWeight?: number;
    fontSize?: number;
    letterSpacing?: number;
    color?: string;
    accentColor?: string;
    align?: string;
    reach?: number;
    softness?: number;
    dashLength?: number;
    dashGap?: number;
    strokeWidth?: number;
    lineStyle?: string;
    reveal?: string;
    specks?: number;
    selection?: boolean;
    labels?: boolean;
    draggable?: boolean;
    bounce?: number;
    sweep?: boolean;
    speed?: number;
    clickKick?: boolean;
    intro?: string;
    introDuration?: number;
    guides?: boolean;
    className?: string;
    style?: React.CSSProperties;
  }
  const TechText: React.FC<TechTextProps>;
  export default TechText;
}

declare module '@/components/reactbits/FlyingButton' {
  export interface FlyingButtonProps {
    children?: React.ReactNode;
    onClick?: (e?: any) => void;
    theme?: string;
    size?: string;
    radius?: number;
    altitude?: number;
    hoverTime?: number;
    jets?: number;
    thrusters?: boolean;
    trigger?: string;
    carryCursor?: boolean;
    ramp?: boolean;
    rampColor?: string;
    smoke?: number;
    turbulence?: number;
    wobble?: number;
    thrustColor?: string;
    smokeColor?: string;
    buttonColor?: string;
    textColor?: string;
    className?: string;
    style?: React.CSSProperties;
  }
  const FlyingButton: React.FC<FlyingButtonProps>;
  export default FlyingButton;
}

