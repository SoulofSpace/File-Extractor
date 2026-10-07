import React, { useEffect, useRef } from 'react';

interface FileTagNode {
  x: number;
  y: number;
  tag: string;
  alpha: number;
  scale: number;
  vx: number;
  vy: number;
}

interface DustParticle {
  x: number;
  y: number;
  radius: number;
  alpha: number;
  vx: number;
  vy: number;
  shade: number;
}

const FILE_TAGS = [
  'PDF',
  'JPG',
  'DOC',
  'TXT',
  'PNG',
  'ZIP',
  'CODE',
  'RAW',
  'CSV',
  'MP4',
  'JSON',
  'TSX',
  'PY',
  'SQL',
  'MD',
  'AI',
  'XLSX',
  'WEBP',
];

interface CursorTrailOverlayProps {
  enabled?: boolean;
}

export const CursorTrailOverlay: React.FC<CursorTrailOverlayProps> = ({ enabled = true }) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    if (!enabled) return;

    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animId = 0;
    const dpr = window.devicePixelRatio || 1;

    // Resize canvas to full window with High-DPI support
    const handleResize = () => {
      if (!canvas) return;
      canvas.width = window.innerWidth * dpr;
      canvas.height = window.innerHeight * dpr;
      canvas.style.width = `${window.innerWidth}px`;
      canvas.style.height = `${window.innerHeight}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };

    handleResize();
    window.addEventListener('resize', handleResize);

    // Particle & Tag Nodes
    let tagNodes: FileTagNode[] = [];
    let dustParticles: DustParticle[] = [];

    let mx = 0;
    let my = 0;
    let lastSpawnX = 0;
    let lastSpawnY = 0;
    let frameCount = 0;

    const onPointerMove = (e: PointerEvent) => {
      mx = e.clientX;
      my = e.clientY;

      const dx = mx - lastSpawnX;
      const dy = my - lastSpawnY;
      const dist = Math.hypot(dx, dy);

      // Spawn floating file tag every ~20px of cursor distance
      if (dist > 20 || (dist > 6 && frameCount % 6 === 0)) {
        lastSpawnX = mx;
        lastSpawnY = my;

        if (tagNodes.length < 18) {
          const tag = FILE_TAGS[Math.floor(Math.random() * FILE_TAGS.length)];
          tagNodes.push({
            x: mx + (Math.random() * 14 - 7),
            y: my + (Math.random() * 12 + 6),
            tag,
            alpha: 1.0,
            scale: 1.0,
            vx: (Math.random() - 0.5) * 0.7,
            vy: -0.35 - Math.random() * 0.45, // Gentle upward float
          });
        }

        // Spawn 2 stardust particles
        if (dustParticles.length < 28) {
          for (let i = 0; i < 2; i++) {
            dustParticles.push({
              x: mx + (Math.random() * 8 - 4),
              y: my + (Math.random() * 8 - 4),
              radius: 1.2 + Math.random() * 2.2,
              alpha: 0.85 + Math.random() * 0.15,
              vx: (Math.random() - 0.5) * 0.8,
              vy: (Math.random() - 0.5) * 0.8,
              shade: Math.random() > 0.4 ? 255 : 220,
            });
          }
        }
      }
    };

    window.addEventListener('pointermove', onPointerMove, { passive: true });

    // Helper: Rounded Rectangle
    const drawRoundRect = (
      c: CanvasRenderingContext2D,
      x: number,
      y: number,
      w: number,
      h: number,
      r: number
    ) => {
      c.beginPath();
      c.moveTo(x + r, y);
      c.lineTo(x + w - r, y);
      c.quadraticCurveTo(x + w, y, x + w, y + r);
      c.lineTo(x + w, y + h - r);
      c.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
      c.lineTo(x + r, y + h);
      c.quadraticCurveTo(x, y + h, x, y + h - r);
      c.lineTo(x, y + r);
      c.quadraticCurveTo(x, y, x + r, y);
      c.closePath();
    };

    // Render loop
    const render = () => {
      frameCount++;
      ctx.clearRect(0, 0, window.innerWidth, window.innerHeight);

      // ── 1. Draw Stardust Particles ────────────────────────────────
      const survivingDust: DustParticle[] = [];
      for (let i = 0; i < dustParticles.length; i++) {
        const p = dustParticles[i];
        p.x += p.vx;
        p.y += p.vy;
        p.alpha -= 0.022;
        p.radius *= 0.96;

        if (p.alpha > 0.05 && p.radius > 0.3) {
          ctx.beginPath();
          ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
          ctx.fillStyle = `rgba(${p.shade}, ${p.shade}, ${p.shade}, ${p.alpha.toFixed(3)})`;
          ctx.fill();
          survivingDust.push(p);
        }
      }
      dustParticles = survivingDust;

      // ── 2. Draw Floating File Tag Badges ──────────────────────────
      ctx.font = "bold 8px 'DM Sans', -apple-system, monospace";
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';

      const survivingTags: FileTagNode[] = [];
      for (let i = 0; i < tagNodes.length; i++) {
        const node = tagNodes[i];
        node.x += node.vx;
        node.y += node.vy;
        node.alpha -= 0.022; // Smooth fade (~45 frames lifetime)
        node.scale *= 0.985;

        if (node.alpha > 0.05 && node.scale > 0.35) {
          ctx.save();
          ctx.translate(node.x, node.y);
          ctx.scale(node.scale, node.scale);

          // Measure text width for perfect pill sizing
          const textMetrics = ctx.measureText(node.tag);
          const pillW = Math.max(26, textMetrics.width + 10);
          const pillH = 14;
          const halfW = pillW / 2;
          const halfH = pillH / 2;

          // Background Fill: Deep Dark Glass
          drawRoundRect(ctx, -halfW, -halfH, pillW, pillH, 4);
          ctx.fillStyle = `rgba(15, 15, 20, ${(node.alpha * 0.88).toFixed(3)})`;
          ctx.fill();

          // Border: Crisp Silver / White Accent
          ctx.lineWidth = 1;
          ctx.strokeStyle = `rgba(255, 255, 255, ${(node.alpha * 0.65).toFixed(3)})`;
          ctx.stroke();

          // Crisp White Text
          ctx.fillStyle = `rgba(255, 255, 255, ${(node.alpha * 0.95).toFixed(3)})`;
          ctx.fillText(node.tag, 0, 0.5);

          ctx.restore();
          survivingTags.push(node);
        }
      }
      tagNodes = survivingTags;

      animId = requestAnimationFrame(render);
    };

    animId = requestAnimationFrame(render);

    return () => {
      window.removeEventListener('resize', handleResize);
      window.removeEventListener('pointermove', onPointerMove);
      cancelAnimationFrame(animId);
    };
  }, [enabled]);

  if (!enabled) return null;

  return (
    <canvas
      ref={canvasRef}
      className="pointer-events-none fixed inset-0 z-[9999]"
      style={{ pointerEvents: 'none' }}
      aria-hidden="true"
    />
  );
};
