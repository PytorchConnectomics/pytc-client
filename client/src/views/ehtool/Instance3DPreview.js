import React, { useEffect, useMemo, useRef, useState } from "react";
import { Spin, Typography } from "antd";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls";

const { Text } = Typography;

const hsvToRgb = (h, s, v) => {
  const i = Math.floor(h * 6);
  const f = h * 6 - i;
  const p = v * (1 - s);
  const q = v * (1 - f * s);
  const t = v * (1 - (1 - f) * s);
  let r;
  let g;
  let b;
  switch (i % 6) {
    case 0:
      r = v;
      g = t;
      b = p;
      break;
    case 1:
      r = q;
      g = v;
      b = p;
      break;
    case 2:
      r = p;
      g = v;
      b = t;
      break;
    case 3:
      r = p;
      g = q;
      b = v;
      break;
    case 4:
      r = t;
      g = p;
      b = v;
      break;
    default:
      r = v;
      g = p;
      b = q;
      break;
  }
  return [Math.round(r * 255), Math.round(g * 255), Math.round(b * 255)];
};

const glasbeyColor = (labelId) => {
  const numeric = Number(labelId) || 0;
  const idx = Math.abs(Math.floor(numeric)) % 256;
  const golden = 0.61803398875;
  const h = ((idx + 1) * golden) % 1.0;
  const s = 0.65 + 0.3 * ((idx % 3) / 2.0);
  const v = 0.9;
  return hsvToRgb(h, s, v);
};

const slicePointToZyx = (point, axis, layerIndex) => {
  const x = point[0];
  const y = point[1];
  if (axis === "zx") return [y, layerIndex, x];
  if (axis === "zy") return [y, x, layerIndex];
  return [layerIndex, y, x];
};

const makeTransform = (preview) => {
  const bbox = preview?.bbox_zyx || {};
  const min = bbox.min || [0, 0, 0];
  const max = bbox.max || preview?.shape_zyx || [1, 1, 1];
  const center = [
    (min[0] + max[0]) / 2,
    (min[1] + max[1]) / 2,
    (min[2] + max[2]) / 2,
  ];
  const span = [
    Math.max(1, max[0] - min[0] + 1),
    Math.max(1, max[1] - min[1] + 1),
    Math.max(1, max[2] - min[2] + 1),
  ];
  const scale = 3.6 / Math.max(span[1], span[2], span[0] * 2.2);
  const zStretch = Math.min(
    5,
    Math.max(1.6, Math.max(span[1], span[2]) / span[0] / 2.2),
  );
  const toScene = (point) => [
    (point[2] - center[2]) * scale,
    -(point[1] - center[1]) * scale,
    (point[0] - center[0]) * scale * zStretch,
  ];
  return { toScene };
};

const isFinitePoint = (point) =>
  Array.isArray(point) &&
  point.length >= 3 &&
  point.every((value) => Number.isFinite(Number(value)));

const buildMeshPayload = (preview) => {
  if (!preview?.vertices_zyx?.length || !preview?.faces?.length) return null;
  const { toScene } = makeTransform(preview);
  const sourceVertices = preview.vertices_zyx;
  const positions = [];
  const vertexMap = new Map();

  const mapVertex = (sourceIndex) => {
    if (!Number.isInteger(sourceIndex)) return null;
    if (sourceIndex < 0 || sourceIndex >= sourceVertices.length) return null;
    if (vertexMap.has(sourceIndex)) return vertexMap.get(sourceIndex);

    const sourcePoint = sourceVertices[sourceIndex];
    if (!isFinitePoint(sourcePoint)) return null;
    const scenePoint = toScene(sourcePoint);
    if (!scenePoint.every((value) => Number.isFinite(value))) return null;

    const mappedIndex = positions.length / 3;
    positions.push(scenePoint[0], scenePoint[1], scenePoint[2]);
    vertexMap.set(sourceIndex, mappedIndex);
    return mappedIndex;
  };

  const indices = [];
  preview.faces.forEach((face) => {
    if (!Array.isArray(face) || face.length < 3) return;
    const a = mapVertex(Number(face[0]));
    const b = mapVertex(Number(face[1]));
    const c = mapVertex(Number(face[2]));
    if (a == null || b == null || c == null) return;
    if (a === b || b === c || a === c) return;
    indices.push(a, b, c);
  });

  if (!positions.length || !indices.length) return null;
  const vertexCount = positions.length / 3;
  const IndexArray = vertexCount > 65535 ? Uint32Array : Uint16Array;
  return {
    positions: new Float32Array(positions),
    indices: new IndexArray(indices),
    vertexCount,
    faceCount: indices.length / 3,
    droppedFaceCount: preview.faces.length - indices.length / 3,
  };
};

function Instance3DPreview({
  preview,
  liveSlice,
  axis = "xy",
  layerIndex = 0,
  activeInstanceId,
  loading = false,
  fill = false,
  showLiveSlice = false,
}) {
  const containerRef = useRef(null);
  const rendererRef = useRef(null);
  const sceneRef = useRef(null);
  const cameraRef = useRef(null);
  const controlsRef = useRef(null);
  const meshGroupRef = useRef(null);
  const liveRef = useRef(null);
  const frameRef = useRef(null);
  const [renderError, setRenderError] = useState("");
  const segmentColor = useMemo(
    () => glasbeyColor(activeInstanceId),
    [activeInstanceId],
  );

  const disposeObject = (object) => {
    if (!object) return;
    object.traverse?.((child) => {
      child.geometry?.dispose?.();
      if (Array.isArray(child.material)) {
        child.material.forEach((material) => material?.dispose?.());
      } else {
        child.material?.dispose?.();
      }
    });
  };

  const meshPayload = useMemo(() => {
    return buildMeshPayload(preview);
  }, [preview]);

  const livePayload = useMemo(() => {
    if (
      !showLiveSlice ||
      !preview ||
      !liveSlice?.points?.length ||
      liveSlice.axis !== axis ||
      liveSlice.layerIndex !== layerIndex
    ) {
      return null;
    }
    const { toScene } = makeTransform(preview);
    const positions = new Float32Array(liveSlice.points.length * 3);
    liveSlice.points.forEach((point, index) => {
      const scenePoint = toScene(slicePointToZyx(point, axis, layerIndex));
      positions[index * 3] = scenePoint[0];
      positions[index * 3 + 1] = scenePoint[1];
      positions[index * 3 + 2] = scenePoint[2];
    });
    return {
      positions,
      pointCount: liveSlice.points.length,
      positiveCount: liveSlice.positiveCount,
    };
  }, [axis, layerIndex, liveSlice, preview, showLiveSlice]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return undefined;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0f172a);
    const camera = new THREE.PerspectiveCamera(45, 1, 0.01, 100);
    camera.position.set(3.4, -3.2, 2.8);

    const canvas = document.createElement("canvas");
    const context =
      canvas.getContext("webgl2", { antialias: true }) ||
      canvas.getContext("webgl", { antialias: true });
    if (!context) {
      setRenderError("3D preview needs WebGL.");
      return undefined;
    }

    let renderer;
    try {
      renderer = new THREE.WebGLRenderer({
        antialias: true,
        canvas,
        context,
      });
    } catch (error) {
      setRenderError("3D preview needs WebGL.");
      return undefined;
    }
    setRenderError("");
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setClearColor(0x0f172a, 1);
    renderer.domElement.style.width = "100%";
    renderer.domElement.style.height = "100%";
    renderer.domElement.style.display = "block";
    renderer.setSize(
      container.clientWidth || 360,
      container.clientHeight || 480,
      false,
    );
    container.appendChild(renderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.autoRotate = false;
    controls.target.set(0, 0, 0);
    controls.update();

    scene.add(new THREE.HemisphereLight(0xf8fafc, 0x1e293b, 2.4));
    const keyLight = new THREE.DirectionalLight(0xffffff, 2.2);
    keyLight.position.set(3, -4, 5);
    scene.add(keyLight);
    const fillLight = new THREE.DirectionalLight(0x93c5fd, 0.9);
    fillLight.position.set(-4, 2, 2);
    scene.add(fillLight);

    rendererRef.current = renderer;
    sceneRef.current = scene;
    cameraRef.current = camera;
    controlsRef.current = controls;

    let lastWidth = 0;
    let lastHeight = 0;
    const resize = () => {
      const rect = container.getBoundingClientRect();
      const width = Math.max(container.clientWidth || rect.width || 360, 240);
      const height = Math.max(
        container.clientHeight || rect.height || 480,
        320,
      );
      if (width === lastWidth && height === lastHeight) return;
      lastWidth = width;
      lastHeight = height;
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      renderer.setSize(width, height, false);
    };
    resize();

    const animate = () => {
      resize();
      controls.update();
      renderer.render(scene, camera);
      frameRef.current = requestAnimationFrame(animate);
    };
    animate();

    return () => {
      if (frameRef.current) cancelAnimationFrame(frameRef.current);
      controls.dispose();
      [meshGroupRef.current, liveRef.current].forEach((object) => {
        if (!object) return;
        scene.remove(object);
        disposeObject(object);
      });
      renderer.dispose();
      if (renderer.domElement.parentNode === container) {
        container.removeChild(renderer.domElement);
      }
    };
  }, []);

  useEffect(() => {
    const scene = sceneRef.current;
    if (!scene) return;
    if (meshGroupRef.current) {
      scene.remove(meshGroupRef.current);
      disposeObject(meshGroupRef.current);
      meshGroupRef.current = null;
    }
    if (!meshPayload) return;

    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute(
      "position",
      new THREE.BufferAttribute(meshPayload.positions, 3),
    );
    geometry.setIndex(new THREE.BufferAttribute(meshPayload.indices, 1));
    geometry.computeVertexNormals();
    geometry.computeBoundingSphere();

    const baseColor = new THREE.Color(
      segmentColor[0] / 255,
      segmentColor[1] / 255,
      segmentColor[2] / 255,
    );
    const material = new THREE.MeshStandardMaterial({
      color: baseColor,
      emissive: baseColor.clone().multiplyScalar(0.2),
      roughness: 0.72,
      metalness: 0,
      transparent: false,
      opacity: 1,
      side: THREE.FrontSide,
    });
    const mesh = new THREE.Mesh(geometry, material);
    const group = new THREE.Group();
    group.add(mesh);

    const sphere = geometry.boundingSphere;
    if (sphere && cameraRef.current && controlsRef.current) {
      const radius = Math.max(sphere.radius, 1);
      const camera = cameraRef.current;
      const controls = controlsRef.current;
      const fov = THREE.MathUtils.degToRad(camera.fov);
      const fitDistance = Math.max(radius * 2.8, radius / Math.sin(fov / 2));
      controls.target.copy(sphere.center);
      controls.minDistance = Math.max(radius * 0.35, 0.1);
      controls.maxDistance = Math.max(radius * 8, fitDistance * 3);
      controls.autoRotate = false;
      controlsRef.current.target.copy(sphere.center);
      camera.position.set(
        sphere.center.x + fitDistance * 0.72,
        sphere.center.y - fitDistance * 0.78,
        sphere.center.z + fitDistance * 0.52,
      );
      camera.near = Math.max(fitDistance / 100, 0.01);
      camera.far = Math.max(fitDistance * 8, 100);
      camera.lookAt(sphere.center);
      camera.updateProjectionMatrix();
      controls.update();
      controls.saveState?.();
    }
    meshGroupRef.current = group;
    scene.add(group);
  }, [meshPayload, segmentColor]);

  useEffect(() => {
    const scene = sceneRef.current;
    if (!scene) return;
    if (liveRef.current) {
      scene.remove(liveRef.current);
      disposeObject(liveRef.current);
      liveRef.current = null;
    }
    if (!livePayload) return;

    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute(
      "position",
      new THREE.BufferAttribute(livePayload.positions, 3),
    );
    const material = new THREE.PointsMaterial({
      color: new THREE.Color(
        segmentColor[0] / 255,
        segmentColor[1] / 255,
        segmentColor[2] / 255,
      ).lerp(new THREE.Color(0xffffff), 0.2),
      size: 0.035,
      transparent: true,
      opacity: 0.95,
      depthWrite: false,
    });
    const points = new THREE.Points(geometry, material);
    liveRef.current = points;
    scene.add(points);
  }, [livePayload, segmentColor]);

  const showOverlay = renderError || loading || !meshPayload;
  return (
    <section
      style={{
        minWidth: fill ? 0 : 320,
        flex: fill ? undefined : "0 0 clamp(320px, 32%, 520px)",
        width: fill ? "100%" : undefined,
        height: fill ? "100%" : undefined,
        position: "relative",
        display: "block",
        borderLeft: fill ? 0 : "1px solid #e5e7eb",
        border: fill ? "1px solid #1f2937" : undefined,
        borderRadius: fill ? 8 : undefined,
        overflow: "hidden",
        background: fill ? "#0f172a" : "#ffffff",
        alignSelf: "stretch",
      }}
    >
      <div
        style={{
          position: "relative",
          minHeight: fill ? 0 : 480,
          height: "100%",
          background: "#0f172a",
        }}
      >
        <div
          ref={containerRef}
          style={{
            width: "100%",
            height: "100%",
            minHeight: fill ? 0 : 480,
          }}
        />
        {showOverlay && (
          <div
            style={{
              position: "absolute",
              inset: 0,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              background: "rgba(15, 23, 42, 0.72)",
              padding: 16,
              textAlign: "center",
            }}
          >
            {renderError ? (
              <Text style={{ color: "#e5e7eb" }}>{renderError}</Text>
            ) : loading ? (
              <Spin />
            ) : (
              <Text style={{ color: "#e5e7eb" }}>
                Extracting surface mesh...
              </Text>
            )}
          </div>
        )}
      </div>
    </section>
  );
}

export default Instance3DPreview;
