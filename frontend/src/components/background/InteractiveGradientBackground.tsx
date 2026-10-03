import React, { useEffect, useRef } from 'react';

interface InteractiveGradientBackgroundProps {
  interactive?: boolean;
}

export const InteractiveGradientBackground: React.FC<InteractiveGradientBackgroundProps> = ({
  interactive = true,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animationFrameId: number;
    let width = (canvas.width = window.innerWidth);
    let height = (canvas.height = window.innerHeight);

    // Mouse coordinates with smoothing
    const mouse = {
      x: width * 0.5,
      y: height * 0.3,
      targetX: width * 0.5,
      targetY: height * 0.3,
    };

    // Color orbs that slowly orbit and react to mouse
    const orbs = [
      {
        x: width * 0.25,
        y: height * 0.3,
        baseX: width * 0.25,
        baseY: height * 0.3,
        radius: Math.max(width, height) * 0.42,
        color: 'rgba(30, 58, 138, 0.45)', // Deep Royal Blue
        speed: 0.0008,
        angle: 0,
        distance: 120,
      },
      {
        x: width * 0.75,
        y: height * 0.35,
        baseX: width * 0.75,
        baseY: height * 0.35,
        radius: Math.max(width, height) * 0.46,
        color: 'rgba(76, 29, 149, 0.38)', // Deep Cosmic Purple
        speed: 0.0006,
        angle: Math.PI * 0.7,
        distance: 140,
      },
      {
        x: width * 0.5,
        y: height * 0.75,
        baseX: width * 0.5,
        baseY: height * 0.75,
        radius: Math.max(width, height) * 0.5,
        color: 'rgba(15, 23, 42, 0.75)', // Slate Obsidian Depth
        speed: 0.0005,
        angle: Math.PI * 1.3,
        distance: 90,
      },
      {
        x: width * 0.65,
        y: height * 0.65,
        baseX: width * 0.65,
        baseY: height * 0.65,
        radius: Math.max(width, height) * 0.38,
        color: 'rgba(14, 116, 144, 0.32)', // Radiant Cyan / Aqua
        speed: 0.0007,
        angle: Math.PI * 0.4,
        distance: 110,
      },
      {
        x: width * 0.35,
        y: height * 0.7,
        baseX: width * 0.35,
        baseY: height * 0.7,
        radius: Math.max(width, height) * 0.35,
        color: 'rgba(99, 102, 241, 0.25)', // Soft Indigo Glow
        speed: 0.0009,
        angle: Math.PI * 1.8,
        distance: 100,
      },
    ];

    const handleResize = () => {
      width = canvas.width = window.innerWidth;
      height = canvas.height = window.innerHeight;
      orbs[0].baseX = width * 0.25;
      orbs[0].baseY = height * 0.3;
      orbs[1].baseX = width * 0.75;
      orbs[1].baseY = height * 0.35;
      orbs[2].baseX = width * 0.5;
      orbs[2].baseY = height * 0.75;
      orbs[3].baseX = width * 0.65;
      orbs[3].baseY = height * 0.65;
      orbs[4].baseX = width * 0.35;
      orbs[4].baseY = height * 0.7;
    };

    const handleMouseMove = (e: MouseEvent) => {
      if (!interactive) return;
      mouse.targetX = e.clientX;
      mouse.targetY = e.clientY;
    };

    window.addEventListener('resize', handleResize);
    if (interactive) {
      window.addEventListener('mousemove', handleMouseMove, { passive: true });
    }

    let time = 0;
    const render = () => {
      time += 1;

      // Smooth mouse easing (lerp)
      mouse.x += (mouse.targetX - mouse.x) * 0.045;
      mouse.y += (mouse.targetY - mouse.y) * 0.045;

      // Base background: absolute deep black
      ctx.fillStyle = '#000000';
      ctx.fillRect(0, 0, width, height);

      // Render floating mesh orbs
      ctx.save();
      ctx.globalCompositeOperation = 'screen';

      orbs.forEach((orb, i) => {
        orb.angle += orb.speed;

        // Base orbiting motion
        const orbitX = orb.baseX + Math.cos(orb.angle) * orb.distance;
        const orbitY = orb.baseY + Math.sin(orb.angle) * orb.distance;

        // Mouse displacement influence (closer orbs react stronger)
        const dx = mouse.x - orbitX;
        const dy = mouse.y - orbitY;
        const factor = (i === 0 || i === 3 ? 0.08 : 0.04);
        orb.x += (orbitX + dx * factor - orb.x) * 0.05;
        orb.y += (orbitY + dy * factor - orb.y) * 0.05;

        // Draw radial gradient orb
        const grad = ctx.createRadialGradient(
          orb.x,
          orb.y,
          0,
          orb.x,
          orb.y,
          orb.radius
        );
        grad.addColorStop(0, orb.color);
        grad.addColorStop(0.5, orb.color.replace(/[\d\.]+\)$/, '0.12)'));
        grad.addColorStop(1, 'rgba(0, 0, 0, 0)');

        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.arc(orb.x, orb.y, orb.radius, 0, Math.PI * 2);
        ctx.fill();
      });

      // Cursor spotlight glow
      if (interactive) {
        const cursorGrad = ctx.createRadialGradient(
          mouse.x,
          mouse.y,
          0,
          mouse.x,
          mouse.y,
          320
        );
        cursorGrad.addColorStop(0, 'rgba(165, 180, 252, 0.16)');
        cursorGrad.addColorStop(0.4, 'rgba(99, 102, 241, 0.08)');
        cursorGrad.addColorStop(1, 'rgba(0, 0, 0, 0)');

        ctx.fillStyle = cursorGrad;
        ctx.beginPath();
        ctx.arc(mouse.x, mouse.y, 320, 0, Math.PI * 2);
        ctx.fill();
      }

      ctx.restore();

      // Subtle atmospheric vignette overlay
      const vignette = ctx.createRadialGradient(
        width * 0.5,
        height * 0.5,
        Math.min(width, height) * 0.35,
        width * 0.5,
        height * 0.5,
        Math.max(width, height) * 0.8
      );
      vignette.addColorStop(0, 'rgba(0, 0, 0, 0)');
      vignette.addColorStop(1, 'rgba(0, 0, 0, 0.65)');
      ctx.fillStyle = vignette;
      ctx.fillRect(0, 0, width, height);

      animationFrameId = requestAnimationFrame(render);
    };

    render();

    return () => {
      cancelAnimationFrame(animationFrameId);
      window.removeEventListener('resize', handleResize);
      if (interactive) {
        window.removeEventListener('mousemove', handleMouseMove);
      }
    };
  }, [interactive]);

  return (
    <canvas
      ref={canvasRef}
      className="fixed inset-0 pointer-events-none z-0 w-full h-full"
      style={{ display: 'block' }}
    />
  );
};
