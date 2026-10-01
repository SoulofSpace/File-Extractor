import React, { useEffect, useRef } from 'react';

interface WavePoint {
  x: number;
  y: number;
  baseY: number;
  speed: number;
  amplitude: number;
  phase: number;
}

interface Ripple {
  x: number;
  y: number;
  radius: number;
  maxRadius: number;
  alpha: number;
}

interface FluidWaterBackgroundProps {
  interactive?: boolean;
}

export const FluidWaterBackground: React.FC<FluidWaterBackgroundProps> = ({ interactive = true }) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const mouseRef = useRef<{ x: number; y: number; targetX: number; targetY: number }>({
    x: -1000,
    y: -1000,
    targetX: -1000,
    targetY: -1000,
  });
  const ripplesRef = useRef<Ripple[]>([]);
  const animFrameRef = useRef<number | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d', { alpha: false });
    if (!ctx) return;

    let width = (canvas.width = window.innerWidth);
    let height = (canvas.height = window.innerHeight);

    const handleResize = () => {
      if (!canvas) return;
      width = canvas.width = window.innerWidth;
      height = canvas.height = window.innerHeight;
      initWaves();
    };
    window.addEventListener('resize', handleResize);

    // Wave layers configuration (deep dark water with subtle cyan/purple caustic highlights)
    let waves: WavePoint[][] = [];
    const layerCount = 3;

    const initWaves = () => {
      waves = [];
      for (let layer = 0; layer < layerCount; layer++) {
        const points: WavePoint[] = [];
        const count = Math.ceil(width / 60) + 2;
        const baseY = height * (0.65 + layer * 0.12);
        for (let i = 0; i <= count; i++) {
          points.push({
            x: i * 60,
            y: baseY,
            baseY: baseY,
            speed: 0.008 + layer * 0.004,
            amplitude: 14 + layer * 8,
            phase: i * 0.35 + layer * 1.5,
          });
        }
        waves.push(points);
      }
    };

    initWaves();

    // Mouse listeners
    const handleMouseMove = (e: MouseEvent) => {
      if (!interactive) return;
      mouseRef.current.targetX = e.clientX;
      mouseRef.current.targetY = e.clientY;
    };

    const handleClick = (e: MouseEvent) => {
      if (!interactive) return;
      ripplesRef.current.push({
        x: e.clientX,
        y: e.clientY,
        radius: 0,
        maxRadius: 180,
        alpha: 0.35,
      });
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('click', handleClick);

    let time = 0;

    // Check reduced motion preference
    const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    const isReduced = mediaQuery.matches;

    const render = () => {
      time += isReduced ? 0 : 0.015;

      // Mouse smooth interpolation
      mouseRef.current.x += (mouseRef.current.targetX - mouseRef.current.x) * 0.05;
      mouseRef.current.y += (mouseRef.current.targetY - mouseRef.current.y) * 0.05;

      // Base background: Deep rich charcoal/navy gradient
      const bgGrad = ctx.createLinearGradient(0, 0, 0, height);
      bgGrad.addColorStop(0, '#0a0b0e');
      bgGrad.addColorStop(0.5, '#0e1015');
      bgGrad.addColorStop(1, '#11141c');
      ctx.fillStyle = bgGrad;
      ctx.fillRect(0, 0, width, height);

      // Subtle ambient caustic light spotlight near mouse
      if (mouseRef.current.x > 0 && mouseRef.current.y > 0) {
        const lightGrad = ctx.createRadialGradient(
          mouseRef.current.x,
          mouseRef.current.y,
          10,
          mouseRef.current.x,
          mouseRef.current.y,
          340
        );
        lightGrad.addColorStop(0, 'rgba(56, 189, 248, 0.05)');
        lightGrad.addColorStop(0.5, 'rgba(99, 102, 241, 0.025)');
        lightGrad.addColorStop(1, 'rgba(0, 0, 0, 0)');
        ctx.fillStyle = lightGrad;
        ctx.fillRect(0, 0, width, height);
      }

      // Draw water wave layers
      waves.forEach((points, layerIdx) => {
        ctx.beginPath();
        ctx.moveTo(0, height);

        for (let i = 0; i < points.length; i++) {
          const pt = points[i];
          const waveOffset = Math.sin(time * pt.speed * 60 + pt.phase) * pt.amplitude;
          
          // Influence from mouse
          let mouseDist = 0;
          if (mouseRef.current.x > 0) {
            const dx = pt.x - mouseRef.current.x;
            const dy = pt.baseY - mouseRef.current.y;
            const dist = Math.sqrt(dx * dx + dy * dy);
            if (dist < 260) {
              mouseDist = Math.sin((1 - dist / 260) * Math.PI) * 12;
            }
          }

          pt.y = pt.baseY + waveOffset - mouseDist;

          if (i === 0) {
            ctx.lineTo(pt.x, pt.y);
          } else {
            const prev = points[i - 1];
            const cx = (prev.x + pt.x) / 2;
            const cy = (prev.y + pt.y) / 2;
            ctx.quadraticCurveTo(prev.x, prev.y, cx, cy);
          }
        }

        ctx.lineTo(width, height);
        ctx.closePath();

        // Wave fill gradient with subtle soft translucency
        const waveGrad = ctx.createLinearGradient(0, height * 0.5, 0, height);
        if (layerIdx === 0) {
          waveGrad.addColorStop(0, 'rgba(18, 24, 38, 0.35)');
          waveGrad.addColorStop(1, 'rgba(10, 12, 18, 0.6)');
        } else if (layerIdx === 1) {
          waveGrad.addColorStop(0, 'rgba(15, 20, 32, 0.45)');
          waveGrad.addColorStop(1, 'rgba(8, 10, 15, 0.7)');
        } else {
          waveGrad.addColorStop(0, 'rgba(11, 15, 24, 0.6)');
          waveGrad.addColorStop(1, 'rgba(6, 8, 12, 0.85)');
        }

        ctx.fillStyle = waveGrad;
        ctx.fill();

        // Wave crest highlight line
        ctx.strokeStyle = `rgba(147, 197, 253, ${0.04 + layerIdx * 0.02})`;
        ctx.lineWidth = 1;
        ctx.stroke();
      });

      // Draw subtle interactive ripples
      for (let r = ripplesRef.current.length - 1; r >= 0; r--) {
        const rip = ripplesRef.current[r];
        rip.radius += 2.2;
        rip.alpha *= 0.95;

        ctx.beginPath();
        ctx.arc(rip.x, rip.y, rip.radius, 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(125, 211, 252, ${rip.alpha * 0.25})`;
        ctx.lineWidth = 1.2;
        ctx.stroke();

        if (rip.radius > rip.maxRadius || rip.alpha < 0.01) {
          ripplesRef.current.splice(r, 1);
        }
      }

      animFrameRef.current = requestAnimationFrame(render);
    };

    render();

    return () => {
      window.removeEventListener('resize', handleResize);
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('click', handleClick);
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
    };
  }, [interactive]);

  return (
    <canvas
      ref={canvasRef}
      className="fixed inset-0 pointer-events-auto z-0 select-none block"
      style={{ width: '100vw', height: '100vh' }}
    />
  );
};
