import type { SpatialGrammar, WorldPoint } from "@/types/spatial";

export interface CurveCluster {
  localRank: number;
  size: number;
}

export interface CurveProfileInput {
  axis: number;
  phase: number;
  depth: number;
  rise: number;
  arc: number;
  swell: number;
  cadence: number;
  lift: number;
  visualRank: number;
  visualCount: number;
  rank: number;
  cluster?: CurveCluster;
}

export function constellationClusterSize(visualCount: number): number {
  return Math.max(5, Math.min(10, Math.round(Math.sqrt(Math.max(1, visualCount)) * 1.08)));
}

export function stageActSize(visualCount: number): number {
  return Math.max(7, Math.min(12, Math.round(Math.sqrt(Math.max(1, visualCount)) * 1.2)));
}

/**
 * Stable book-scale profiles. They shape narrative geometry only; camera
 * framing and observation time live elsewhere so neither can distort the book.
 */
export function curveProfilePoint(grammar: SpatialGrammar, input: CurveProfileInput): WorldPoint {
  const {
    axis, phase, depth, rise, arc, swell, cadence, lift,
    visualRank, visualCount, rank, cluster,
  } = input;
  if (grammar === "braid") {
    const ribbon = Math.sin(phase * 1.18) * 2.15;
    return { x: axis, y: 1.16 + rise + Math.sin(phase * 0.42) * 0.34, z: depth + ribbon * 0.54 };
  }
  if (grammar === "strata") {
    const stratum = Math.floor(rank / 12);
    return { x: axis, y: 1.08 + rise - stratum * 0.66, z: depth + (rank % 12 - 5.5) * 0.11 };
  }
  if (grammar === "constellation") {
    // Chapters form several stellar families instead of one decorative arc.
    // Each family's reading order follows an open logarithmic spiral. That
    // keeps chronology fluid while minor stars stay irregular scenery.
    const familySize = constellationClusterSize(visualCount);
    const family = Math.floor(visualRank / familySize);
    const familyCount = Math.max(1, Math.ceil(visualCount / familySize));
    const member = visualRank - family * familySize;
    const memberCount = Math.min(familySize, Math.max(1, visualCount - family * familySize));
    const familyProgress = familyCount <= 1 ? 0 : family / (familyCount - 1);
    const centerX = (family - (familyCount - 1) / 2) * 31;
    const centerZ = Math.sin(familyProgress * Math.PI * 1.45 - 0.72) * 12.4
      + Math.sin(family * 1.31 + 0.4) * 2.3;
    const centerY = Math.sin(familyProgress * Math.PI * 2.2 + 0.38) * 2
      + Math.cos(family * 1.37 + 0.2) * 0.52;
    const memberProgress = memberCount <= 1 ? 0 : member / (memberCount - 1);
    const familySweep = 1.48 + Math.sin(family * 1.71 + 0.44) * 0.24;
    const familyEccentricity = 0.9 + Math.sin(family * 1.13) * 0.13;
    const memberAngle = family * 0.73 - 1.18 + memberProgress * Math.PI * familySweep;
    const memberRadius = 1.7 + memberProgress * 10.8 + Math.sin(memberProgress * Math.PI) * 1.35;
    const sceneOffset = constellationSceneOffset(cluster, memberAngle);
    return {
      x: centerX + Math.cos(memberAngle) * memberRadius * familyEccentricity + sceneOffset.x,
      y: 1.16 + centerY
        + Math.sin(memberAngle * 0.72) * 2.25
        + Math.cos(memberAngle * 1.31 + family) * 0.34
        + (memberProgress - 0.5) * 0.44
        + cadence * 0.32
        + sceneOffset.y,
      z: centerZ + Math.sin(memberAngle) * memberRadius * 0.7 + depth * 0.14 + sceneOffset.z,
    };
  }
  if (grammar === "loop") {
    // Restores the readable orbital cadence of the early v0.9 curve while
    // widening each revolution enough that long books never collapse into a
    // tight coil. The irrational micro-modulation avoids decorative circles.
    const angle = -2.3 + visualRank * 0.43 + Math.sin(visualRank * 0.37 + 0.4) * 0.038;
    const radius = 14.2 + visualRank * 2.42 + Math.sin(visualRank * 0.21) * 0.5 + lift * 0.34;
    const offset = clusterRibbonOffset(cluster, angle + Math.PI / 2, 1.05, 0.48);
    return {
      x: Math.cos(angle) * radius + offset.x,
      y: 1.14 + arc * 0.36 + cadence + offset.y,
      z: Math.sin(angle) * radius + depth * 0.12 + offset.z,
    };
  }
  if (grammar === "stage") {
    // The stage is a procession of chapter-sized acts. Blocking follows the
    // bowed apron, with a shallow back/front alternation like performers placed
    // in depth rather than points arranged on a rail.
    const actSize = stageActSize(visualCount);
    const act = Math.floor(visualRank / actSize);
    const member = visualRank - act * actSize;
    const memberCount = Math.min(actSize, Math.max(1, visualCount - act * actSize));
    const local = memberCount <= 1 ? 0 : member / (memberCount - 1) - 0.5;
    const actCenterX = act * 43 - 8.2;
    const actCenterZ = Math.sin(act * 0.92 + 0.3) * 8.8 + act * 2.4;
    const blockingDepth = Math.sin(member * 2.17 + act * 0.71) * 1.15;
    const apronX = actCenterX + local * 31.5;
    const apronZ = actCenterZ + 9.8 - local * local * 31 + blockingDepth;
    const tangent = Math.atan2(-62 * local + Math.cos(member * 2.17) * 2.5, 31.5);
    const offset = clusterRibbonOffset(cluster, tangent, 2.34, 1.18);
    return {
      x: apronX + offset.x,
      y: 1.12
        + act * 0.72
        + Math.cos(local * Math.PI) * 0.82
        + Math.cos(member * 1.61) * 0.18
        + lift * 0.42
        + cadence * 0.32
        + offset.y,
      z: apronZ + swell * 0.24 + offset.z,
    };
  }
  return { x: axis, y: 1.1 + rise, z: depth };
}

function constellationSceneOffset(cluster: CurveCluster | undefined, angle: number): WorldPoint {
  if (!cluster || cluster.size <= 1) return { x: 0, y: 0, z: 0 };
  const centered = cluster.localRank - (cluster.size - 1) / 2;
  const radius = 3.1 + Math.abs(centered) * 1.72;
  const localAngle = angle + centered * 1.37;
  return {
    x: Math.cos(localAngle) * radius,
    y: Math.sin(centered * 1.1) * 0.56,
    z: Math.sin(localAngle) * radius * 0.72,
  };
}

function clusterRibbonOffset(
  cluster: CurveCluster | undefined,
  tangentAngle: number,
  stride: number,
  lateralBreath: number,
): WorldPoint {
  if (!cluster || cluster.size <= 1) return { x: 0, y: 0, z: 0 };
  const centered = cluster.localRank - (cluster.size - 1) / 2;
  const along = centered * stride;
  const across = Math.sin(centered * 1.17) * lateralBreath;
  const tangent = { x: Math.cos(tangentAngle), z: Math.sin(tangentAngle) };
  const normal = { x: -tangent.z, z: tangent.x };
  return {
    x: tangent.x * along + normal.x * across,
    y: Math.sin(centered * 0.88) * 0.16,
    z: tangent.z * along + normal.z * across,
  };
}
