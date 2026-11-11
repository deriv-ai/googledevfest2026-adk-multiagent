type Point = [number, number];

/** SVG path through orthogonal `points`, with each corner rounded by up to `radius`. */
export function roundedPath(points: Point[], radius = 8): string {
  const [first, ...rest] = points;
  if (!first) return "";
  let d = `M ${first[0]},${first[1]}`;
  let prev = first;
  rest.forEach((point, i) => {
    const next = rest[i + 1];
    const [x, y] = point;
    if (next) {
      const r = Math.min(radius, Math.hypot(x - prev[0], y - prev[1]) / 2, Math.hypot(next[0] - x, next[1] - y) / 2);
      d += ` L ${x - Math.sign(x - prev[0]) * r},${y - Math.sign(y - prev[1]) * r}`;
      d += ` Q ${x},${y} ${x + Math.sign(next[0] - x) * r},${y + Math.sign(next[1] - y) * r}`;
    } else {
      d += ` L ${x},${y}`;
    }
    prev = point;
  });
  return d;
}
