// Minimal Isolation Forest (Liu et al., 2008). Deterministic via seeded RNG.
type Node =
  | { leaf: true; size: number }
  | { leaf: false; feature: number; split: number; left: Node; right: Node };

function mulberry32(seed: number) {
  return () => {
    seed |= 0;
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Average path length of unsuccessful BST search, c(n). */
export function cFactor(n: number): number {
  if (n <= 1) return 0;
  if (n === 2) return 1;
  return 2 * (Math.log(n - 1) + 0.5772156649) - (2 * (n - 1)) / n;
}

function build(data: number[][], depth: number, maxDepth: number, rand: () => number): Node {
  if (depth >= maxDepth || data.length <= 1) return { leaf: true, size: data.length };
  const dims = data[0]!.length;
  const candidates: number[] = [];
  for (let f = 0; f < dims; f++) {
    let min = Infinity, max = -Infinity;
    for (const r of data) { const v = r[f]!; if (v < min) min = v; if (v > max) max = v; }
    if (max > min) candidates.push(f);
  }
  if (candidates.length === 0) return { leaf: true, size: data.length };
  const feature = candidates[Math.floor(rand() * candidates.length)]!;
  let min = Infinity, max = -Infinity;
  for (const r of data) { const v = r[feature]!; if (v < min) min = v; if (v > max) max = v; }
  const split = min + rand() * (max - min);
  const left = data.filter((r) => r[feature]! < split);
  const right = data.filter((r) => r[feature]! >= split);
  return {
    leaf: false, feature, split,
    left: build(left, depth + 1, maxDepth, rand),
    right: build(right, depth + 1, maxDepth, rand),
  };
}

function pathLength(x: number[], node: Node, depth: number): number {
  if (node.leaf) return depth + cFactor(node.size);
  return pathLength(x, x[node.feature]! < node.split ? node.left : node.right, depth + 1);
}

export class IsolationForest {
  private trees: Node[] = [];
  private sampleSize = 0;
  constructor(private nTrees = 100, private maxSamples = 256, private seed = 42) {}

  fit(data: number[][]) {
    const rand = mulberry32(this.seed);
    this.sampleSize = Math.min(this.maxSamples, data.length);
    const maxDepth = Math.ceil(Math.log2(Math.max(2, this.sampleSize)));
    this.trees = [];
    for (let t = 0; t < this.nTrees; t++) {
      const sample: number[][] = [];
      for (let i = 0; i < this.sampleSize; i++) sample.push(data[Math.floor(rand() * data.length)]!);
      this.trees.push(build(sample, 0, maxDepth, rand));
    }
    return this;
  }

  /** Anomaly score in (0,1]; ~0.5 normal, closer to 1 = more anomalous. */
  score(x: number[]): number {
    const avg = this.trees.reduce((s, t) => s + pathLength(x, t, 0), 0) / this.trees.length;
    return Math.pow(2, -avg / cFactor(this.sampleSize));
  }
}
