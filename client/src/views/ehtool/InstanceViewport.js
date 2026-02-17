import React, { useState, useEffect, useRef, useLayoutEffect } from "react";
import { Card, Button, Slider, Space, Typography, Spin, Segmented } from "antd";
import {
  LeftOutlined,
  RightOutlined,
  EditOutlined,
  ZoomInOutlined,
  ZoomOutOutlined,
  CompressOutlined,
} from "@ant-design/icons";

const { Text } = Typography;

function InstanceViewport({
  imageBase64,
  maskAllBase64,
  maskActiveBase64,
  loading,
  zIndex,
  sliderValue,
  totalLayers,
  axis,
  axisOptions,
  onAxisChange,
  overlayAllAlpha,
  overlayActiveAlpha,
  onPrevSlice,
  onNextSlice,
  onSliceChange,
  onSliceCommit,
  onOpenEditor,
  overlayControls,
}) {
  const [zoom, setZoom] = useState(1);
  const [isPanning, setIsPanning] = useState(false);
  const [cursorInfo, setCursorInfo] = useState(null);
  const panStart = useRef({ x: 0, y: 0 });
  const offsetRef = useRef({ x: 0, y: 0 });
  const zoomRef = useRef(1);
  const rafRef = useRef(null);
  const containerRef = useRef(null);
  const transformRef = useRef(null);
  const imageRef = useRef(null);
  const cursorRafRef = useRef(null);
  const pendingCursorEvent = useRef(null);
  const axisLabel = axis ? axis.toUpperCase() : "XY";

  useEffect(() => {
    setZoom(1);
    offsetRef.current = { x: 0, y: 0 };
  }, [imageBase64, zIndex]);

  useLayoutEffect(() => {
    zoomRef.current = zoom;
    applyTransform();
  }, [zoom]);

  const applyTransform = () => {
    if (!transformRef.current) return;
    const { x, y } = offsetRef.current;
    transformRef.current.style.transform = `translate(${x}px, ${y}px) scale(${zoomRef.current})`;
  };

  const scheduleTransform = () => {
    if (rafRef.current) return;
    rafRef.current = requestAnimationFrame(() => {
      rafRef.current = null;
      applyTransform();
    });
  };

  const handleWheel = (e) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? -0.1 : 0.1;
    const nextZoom = Math.max(0.4, Math.min(4, zoom + delta));
    setZoom(nextZoom);
  };

  const handleMouseDown = (e) => {
    if (zoom <= 1) return;
    e.preventDefault();
    setIsPanning(true);
    panStart.current = {
      x: e.clientX - offsetRef.current.x,
      y: e.clientY - offsetRef.current.y,
    };
  };

  const handleMouseMove = (e) => {
    if (!isPanning) return;
    e.preventDefault();
    offsetRef.current = {
      x: e.clientX - panStart.current.x,
      y: e.clientY - panStart.current.y,
    };
    scheduleTransform();
  };

  const handleMouseUp = () => {
    setIsPanning(false);
  };

  const axisCursorLabel = () => {
    if (axis === "zx") return { h: "X", v: "Z" };
    if (axis === "zy") return { h: "Y", v: "Z" };
    return { h: "X", v: "Y" };
  };

  const updateCursor = (event) => {
    if (!imageRef.current) {
      setCursorInfo(null);
      return;
    }
    const imageRect = imageRef.current.getBoundingClientRect();
    const within =
      event.clientX >= imageRect.left &&
      event.clientX <= imageRect.right &&
      event.clientY >= imageRect.top &&
      event.clientY <= imageRect.bottom;
    if (!within) {
      setCursorInfo(null);
      return;
    }
    const relX = (event.clientX - imageRect.left) / imageRect.width;
    const relY = (event.clientY - imageRect.top) / imageRect.height;
    const naturalWidth = imageRef.current.naturalWidth || 0;
    const naturalHeight = imageRef.current.naturalHeight || 0;
    const x = Math.min(
      Math.max(Math.round(relX * naturalWidth), 0),
      Math.max(naturalWidth - 1, 0),
    );
    const y = Math.min(
      Math.max(Math.round(relY * naturalHeight), 0),
      Math.max(naturalHeight - 1, 0),
    );
    setCursorInfo({ x, y });
  };

  const handleCursorMove = (event) => {
    pendingCursorEvent.current = event;
    if (cursorRafRef.current) return;
    cursorRafRef.current = requestAnimationFrame(() => {
      cursorRafRef.current = null;
      if (pendingCursorEvent.current) {
        updateCursor(pendingCursorEvent.current);
      }
    });
  };

  const handleCursorLeave = () => {
    setCursorInfo(null);
  };

  return (
    <Card
      bordered={false}
      style={{
        background: "#fff",
        boxShadow: "0 6px 20px rgba(15, 23, 42, 0.06)",
      }}
      bodyStyle={{ padding: 16 }}
    >
      <Space
        style={{
          width: "100%",
          justifyContent: "space-between",
          marginBottom: 8,
        }}
      >
        <Space size="middle" align="center">
          <Text style={{ fontSize: 12 }}>
            {axisLabel} {zIndex + 1} / {totalLayers}
          </Text>
          {axisOptions && onAxisChange && (
            <Segmented
              size="small"
              options={axisOptions}
              value={axis}
              onChange={onAxisChange}
            />
          )}
          {axisOptions && (
            <Text type="secondary" style={{ fontSize: 11 }}>
              1/2/3 switch planes
            </Text>
          )}
        </Space>
        <Space size="small">
          <Button
            type="text"
            icon={<ZoomOutOutlined />}
            onClick={() => setZoom((z) => Math.max(0.4, z - 0.2))}
          />
          <Button
            type="text"
            icon={<ZoomInOutlined />}
            onClick={() => setZoom((z) => Math.min(4, z + 0.2))}
          />
          <Button
            type="text"
            icon={<CompressOutlined />}
            onClick={() => {
              setZoom(1);
              offsetRef.current = { x: 0, y: 0 };
              applyTransform();
            }}
          />
          <Button type="text" onClick={onPrevSlice} icon={<LeftOutlined />} />
          <Button type="text" onClick={onNextSlice} icon={<RightOutlined />} />
          <Button type="primary" size="small" onClick={onOpenEditor}>
            Edit
          </Button>
        </Space>
      </Space>

      <div
        style={{
          position: "relative",
          width: "100%",
          minHeight: "60vh",
          maxHeight: "70vh",
          background: "#0b0f1a",
          borderRadius: 14,
          overflow: "hidden",
          userSelect: "none",
        }}
        ref={containerRef}
        onWheel={handleWheel}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
      >
        <div
          style={{
            position: "absolute",
            left: 12,
            top: 12,
            zIndex: 2,
            background: "rgba(15, 23, 42, 0.7)",
            color: "#fff",
            padding: "6px 10px",
            borderRadius: 10,
            fontSize: 12,
          }}
        >
          {cursorInfo ? (
            <Text style={{ color: "#fff" }}>
              {axisCursorLabel().h}: {cursorInfo.x} · {axisCursorLabel().v}:{" "}
              {cursorInfo.y}
            </Text>
          ) : (
            <Text style={{ color: "#9ca3af" }}>Cursor: --</Text>
          )}
        </div>
        {overlayControls && (
          <div
            style={{
              position: "absolute",
              top: 12,
              right: 12,
              zIndex: 2,
            }}
          >
            {overlayControls}
          </div>
        )}
        <div
          style={{
            position: "absolute",
            inset: 0,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            transformOrigin: "center",
            cursor: zoom > 1 ? (isPanning ? "grabbing" : "grab") : "default",
            willChange: "transform",
          }}
          ref={transformRef}
          onMouseMove={handleCursorMove}
          onMouseLeave={handleCursorLeave}
        >
          {imageBase64 && (
            <img
              src={imageBase64}
              alt="Slice"
              draggable={false}
              ref={imageRef}
              style={{
                width: "100%",
                height: "100%",
                objectFit: "contain",
                pointerEvents: "none",
              }}
            />
          )}
          {maskAllBase64 && (
            <img
              src={maskAllBase64}
              alt="All instances overlay"
              draggable={false}
              style={{
                width: "100%",
                height: "100%",
                objectFit: "contain",
                position: "absolute",
                inset: 0,
                opacity: overlayAllAlpha,
                pointerEvents: "none",
              }}
            />
          )}
          {maskActiveBase64 && (
            <img
              src={maskActiveBase64}
              alt="Active instance overlay"
              draggable={false}
              style={{
                width: "100%",
                height: "100%",
                objectFit: "contain",
                position: "absolute",
                inset: 0,
                opacity: overlayActiveAlpha,
                pointerEvents: "none",
              }}
            />
          )}
        </div>
        {loading && (
          <div
            style={{
              position: "absolute",
              inset: 0,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              background: "rgba(15, 23, 42, 0.45)",
            }}
          >
            <Spin size="large" />
          </div>
        )}
      </div>

      <div style={{ marginTop: 16 }}>
        <Slider
          min={0}
          max={Math.max(totalLayers - 1, 0)}
          value={sliderValue ?? zIndex}
          onChange={onSliceChange}
          onAfterChange={onSliceCommit}
          tooltip={{ formatter: (value) => `${axisLabel} ${value + 1}` }}
        />
      </div>
    </Card>
  );
}

export default InstanceViewport;
