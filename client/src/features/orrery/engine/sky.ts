/**
 * 屏幕空间的程序化全景天幕。
 *
 * 天幕不是叙事场景的一层：它直接挂在 Pixi stage 的最底部，视角变化
 * 只改变天球射线。星点、星云、银河带与噪声因此不会跟着故事节点一起
 * 平移，也不会在场景容器里形成第二套“伪星图”。
 */
import { Mesh, MeshGeometry, Shader, UniformGroup } from "pixi.js";
import type { SpatialOrientation } from "@/types/spatial";

const VERTEX = /* glsl */ `
in vec2 aPosition;
in vec2 aUV;
out vec2 vUv;
uniform mat3 uProjectionMatrix;
uniform mat3 uWorldTransformMatrix;
void main() {
  vUv = aUV;
  gl_Position = vec4((uProjectionMatrix * uWorldTransformMatrix * vec3(aPosition, 1.0)).xy, 0.0, 1.0);
}
`;

const FRAGMENT = /* glsl */ `
in vec2 vUv;
out vec4 finalColor;
uniform vec2 uResolution;
uniform float uTime;
uniform float uYaw;
uniform float uPitch;
uniform float uFov;
uniform vec2 uPan;
uniform float uQuality;

float hash12(vec2 p) {
  vec3 p3 = fract(vec3(p.xyx) * 0.1031);
  p3 += dot(p3, p3.yzx + 33.33);
  return fract((p3.x + p3.y) * p3.z);
}
vec3 hash33(vec3 p) {
  p = fract(p * vec3(0.1031, 0.1030, 0.0973));
  p += dot(p, p.yxz + 33.33);
  return fract((p.xxy + p.yxx) * p.zyx);
}
float noise2(vec2 p) {
  vec2 i = floor(p);
  vec2 f = fract(p);
  f = f * f * (3.0 - 2.0 * f);
  float a = hash12(i);
  float b = hash12(i + vec2(1.0, 0.0));
  float c = hash12(i + vec2(0.0, 1.0));
  float d = hash12(i + vec2(1.0, 1.0));
  return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}
float fbm(vec2 p, int octaves) {
  float value = 0.0;
  float amplitude = 0.5;
  for (int index = 0; index < 5; index++) {
    if (index >= octaves) break;
    value += amplitude * noise2(p);
    p = p * 2.03 + vec2(11.3, 7.1);
    amplitude *= 0.5;
  }
  return value;
}

void main() {
  vec2 ndc = vUv * 2.0 - 1.0;
  float aspect = uResolution.x / max(1.0, uResolution.y);
  float tangent = tan(uFov * 0.5 * 3.14159265 / 180.0);
  vec3 direction = normalize(vec3(ndc.x * tangent * aspect, ndc.y * tangent, 1.0));

  float pitchCos = cos(-uPitch);
  float pitchSin = sin(-uPitch);
  direction = vec3(direction.x, direction.y * pitchCos - direction.z * pitchSin, direction.y * pitchSin + direction.z * pitchCos);
  float yawCos = cos(-uYaw);
  float yawSin = sin(-uYaw);
  direction = vec3(direction.x * yawCos + direction.z * yawSin, direction.y, -direction.x * yawSin + direction.z * yawCos);
  direction = normalize(direction);

  float horizonMix = clamp(direction.y * 2.4, -1.0, 1.0);
  vec3 zenith = vec3(0.034, 0.074, 0.152);
  vec3 horizon = vec3(0.008, 0.026, 0.047);
  vec3 nadir = vec3(0.004, 0.012, 0.025);
  vec3 sky = horizonMix > 0.0 ? mix(horizon, zenith, horizonMix) : mix(horizon, nadir, -horizonMix);

  // Three sparse star layers give the background depth without adding scene nodes.
  vec3 stars = vec3(0.0);
  for (int layer = 0; layer < 3; layer++) {
    float parallax = layer == 0 ? 0.1 : (layer == 1 ? 0.3 : 0.6);
    vec3 ray = normalize(direction + vec3(uPan.x * parallax * 0.00022, -uPan.y * parallax * 0.00022, 0.0));
    float cells = layer == 0 ? 16.0 : (layer == 1 ? 26.0 : 40.0);
    vec3 cell = floor(ray * cells);
    vec3 random = hash33(cell + float(layer) * 91.7);
    if (random.x > 0.9) {
      vec3 center = normalize((cell + (random - 0.5) * 0.7 + 0.5) / cells);
      vec3 difference = ray - center;
      float distanceToStar = length(difference);
      float size = mix(0.0011, 0.0034, random.y) * (layer == 0 ? 0.7 : 1.0);
      float distanceRatio = distanceToStar / max(size, 0.00035);
      float magnitude = pow(max(0.04, random.z), 3.0);
      float core = exp(-distanceRatio * distanceRatio * 8.0) * 0.9;
      float glow = exp(-distanceRatio * distanceRatio * 1.8) * 0.16;
      float twinkle = 0.86 + 0.14 * sin(uTime * (0.4 + random.z * 1.4) + random.y * 40.0);
      vec3 starColor = mix(vec3(0.68, 0.8, 1.0), vec3(1.0, 0.84, 0.58), 0.75);
      stars += starColor * (core + glow) * twinkle * magnitude * (layer == 2 ? 1.0 : 0.75);
    }
  }

  vec2 spherical = vec2(atan(direction.z, direction.x), asin(clamp(direction.y, -1.0, 1.0)));
  int octaves = uQuality > 1.5 ? 5 : 3;
  for (int cloud = 0; cloud < 4; cloud++) {
    vec2 center = vec2(float(cloud) * 1.57 + 0.8, mod(float(cloud), 2.0) < 0.5 ? 0.2 : -0.14);
    vec2 delta = spherical - center;
    delta.x = sin(delta.x * 0.5) * 2.0;
    float falloff = exp(-dot(delta, delta) * (cloud == 0 ? 2.0 : 2.6));
    float cloudNoise = fbm(spherical * (2.2 + float(cloud) * 0.3) + float(cloud) * 13.7 + vec2(uTime * 0.005, -uTime * 0.003), octaves);
    vec3 cloudColor = cloud == 0 ? vec3(0.12, 0.28, 0.58) : cloud == 1 ? vec3(0.08, 0.36, 0.34) : cloud == 2 ? vec3(0.42, 0.28, 0.12) : vec3(0.28, 0.16, 0.42);
    sky += cloudColor * falloff * cloudNoise * (uQuality > 1.5 ? 0.36 : 0.25);
  }

  float bandY = 0.14 * sin(spherical.x * 2.0 + 0.7) + 0.04 * sin(spherical.x * 5.0);
  float band = exp(-pow((spherical.y - bandY) * 8.0, 2.0));
  float dust = fbm(vec2(spherical.x * 4.0 + uTime * 0.008, spherical.y * 22.0), 3);
  sky += vec3(0.82, 0.78, 0.72) * band * dust * 0.05;
  sky += vec3(0.16, 0.62, 0.5) * fbm(vec2(spherical.x * 5.0 + uTime * 0.012, spherical.y * 16.0), 3) * exp(-pow((spherical.y - 0.36 - 0.05 * sin(spherical.x * 3.0 + uTime * 0.02)) * 12.0, 2.0)) * 0.05;

  // ArcVellum's two persistent sky signatures. They are directional light
  // fields on the sky dome, not extra narrative nodes, so camera orbit reveals
  // them without making the project graph feel like a decorated map.
  vec2 jadeDelta = spherical - vec2(-1.18, 0.22);
  jadeDelta.x = sin(jadeDelta.x * 0.5) * 2.0;
  float jadeField = exp(-(jadeDelta.x * jadeDelta.x * 1.15 + jadeDelta.y * jadeDelta.y * 8.4));
  float jadeVeil = fbm(spherical * vec2(3.1, 10.0) + vec2(uTime * 0.003, 7.3), 4);
  sky += vec3(0.06, 0.52, 0.4) * jadeField * jadeVeil * 0.13;

  vec2 irisDelta = spherical - vec2(1.72, -0.1);
  irisDelta.x = sin(irisDelta.x * 0.5) * 2.0;
  float irisField = exp(-(irisDelta.x * irisDelta.x * 1.5 + irisDelta.y * irisDelta.y * 10.5));
  float irisVeil = fbm(spherical * vec2(4.6, 13.0) + vec2(19.0, -uTime * 0.002), 4);
  sky += vec3(0.34, 0.18, 0.56) * irisField * irisVeil * 0.11;

  float emberRift = exp(-pow((spherical.y + 0.28 - 0.06 * sin(spherical.x * 2.6)) * 14.0, 2.0));
  sky += vec3(0.62, 0.17, 0.09) * emberRift * fbm(vec2(spherical.x * 7.0, spherical.y * 18.0), 3) * 0.035;
  sky += stars;
  finalColor = vec4(pow(sky, vec3(0.92)), 1.0);
}
`;

export class SkyMesh {
  readonly mesh: Mesh<MeshGeometry, Shader>;
  private readonly uniforms: UniformGroup;
  private width: number;
  private height: number;

  constructor(width: number, height: number) {
    this.width = Math.max(1, width);
    this.height = Math.max(1, height);
    this.uniforms = new UniformGroup({
      uResolution: { value: [this.width, this.height], type: "vec2<f32>" },
      uTime: { value: 0, type: "f32" }, uYaw: { value: 0, type: "f32" }, uPitch: { value: 0, type: "f32" },
      uFov: { value: 70, type: "f32" }, uPan: { value: [0, 0], type: "vec2<f32>" }, uQuality: { value: 2, type: "f32" },
    });
    const shader = Shader.from({ gl: { vertex: VERTEX, fragment: FRAGMENT }, resources: { uUniforms: this.uniforms } });
    this.mesh = new Mesh({ geometry: this.buildGeometry(), shader });
    this.mesh.eventMode = "none";
    this.mesh.label = "arcvellum-panoramic-sky";
  }

  resize(width: number, height: number): void {
    this.width = Math.max(1, width);
    this.height = Math.max(1, height);
    const old = this.mesh.geometry;
    this.mesh.geometry = this.buildGeometry();
    old.destroy();
    (this.uniforms.uniforms as Record<string, unknown>).uResolution = [this.width, this.height];
  }

  setQuality(high: boolean): void {
    (this.uniforms.uniforms as Record<string, unknown>).uQuality = high ? 2 : 1;
  }

  setCamera(yaw: number, pitch: number, fov: number, panX: number, panY: number, time: number): void {
    const uniforms = this.uniforms.uniforms as Record<string, unknown>;
    uniforms.uYaw = yaw; uniforms.uPitch = pitch; uniforms.uFov = fov; uniforms.uPan = [panX, panY]; uniforms.uTime = time;
  }

  private buildGeometry(): MeshGeometry {
    return new MeshGeometry({
      positions: new Float32Array([0, 0, this.width, 0, this.width, this.height, 0, this.height]),
      uvs: new Float32Array([0, 0, 1, 0, 1, 1, 0, 1]),
      indices: new Uint32Array([0, 1, 2, 0, 2, 3]),
    });
  }
}

export function fovForZoom(zoom: number): number {
  return Math.max(16, Math.min(100, 58 / Math.pow(Math.max(zoom, 0.08), 0.65)));
}

export function skyAnglesFromView(view: SpatialOrientation): { yaw: number; pitch: number } {
  const length = Math.hypot(view.x, view.y, view.z, view.w) || 1;
  const x = view.x / length; const y = view.y / length; const z = view.z / length; const w = view.w / length;
  const pitch = Math.asin(Math.max(-1, Math.min(1, 2 * (w * x - z * y))));
  const yaw = Math.atan2(2 * (w * y + x * z), 1 - 2 * (x * x + y * y));
  return { yaw, pitch };
}
