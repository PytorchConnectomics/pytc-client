import React, {
  useState,
  useRef,
  useEffect,
  useMemo,
  forwardRef,
  useImperativeHandle,
} from "react";
import {
  Card,
  Button,
  Slider,
  InputNumber,
  Space,
  Tag,
  message,
  Tooltip,
  Collapse,
  Segmented,
  Spin,
  Typography,
} from "antd";
import {
  EditOutlined,
  ClearOutlined,
  UndoOutlined,
  RedoOutlined,
  EyeOutlined,
  EyeInvisibleOutlined,
  LeftOutlined,
  RightOutlined,
  ZoomInOutlined,
  ZoomOutOutlined,
  DragOutlined,
  SaveOutlined,
} from "@ant-design/icons";

const { Text } = Typography;

/**
 * Proofreading Editor Component
 * Canvas-based image editor with paint/erase brush tools for mask correction
 */
const ProofreadingEditor = forwardRef(
  (
    {
      imageBase64,
      maskBase64,
      overlayAllBase64,
      overlayActiveBase64,
      overlayAllAlpha = 0.08,
      overlayActiveAlpha = 0.8,
      axis,
      axisOptions,
      onAxisChange,
      loading,
      activeInstanceId,
      onSave,
      onNext,
      onPrevious,
      currentLayer,
      totalLayers,
      layerName,
      canEdit = true,
      saveDisabledReason = "Editable mask is not ready yet.",
      minimalChrome = true,
      hideLayerToolbar = false,
    },
    ref,
  ) => {
    const canvasRef = useRef(null);
    const minimapRef = useRef(null);
    const containerRef = useRef(null);
    const [tool, setTool] = useState("paint"); // 'paint', 'erase', or 'hand'
    const [toolPanelCollapsed, setToolPanelCollapsed] = useState(true);
    const [toolPanelSections, setToolPanelSections] = useState([
      "editing",
      "history",
    ]);
    const [paintBrushSize, setPaintBrushSize] = useState(10);
    const [eraseBrushSize, setEraseBrushSize] = useState(10);
    const [showMask, setShowMask] = useState(true);
    const [zoom, setZoom] = useState(1.0);
    const [hasUnsavedEdits, setHasUnsavedEdits] = useState(false);
    const [isDrawing, setIsDrawing] = useState(false);
    const [cursorPos, setCursorPos] = useState({ x: 0, y: 0 }); // Image coordinates
    const [mousePos, setMousePos] = useState(null); // Container/Screen coordinates

    // Image and mask data
    const imageDataRef = useRef(null);
    const maskDataRef = useRef(null);
    const originalMaskRef = useRef(null);
    const overlayAllRef = useRef(null);
    const overlayActiveRef = useRef(null);

    // Undo/Redo stacks
    const [undoStack, setUndoStack] = useState([]);
    const [redoStack, setRedoStack] = useState([]);

    // Canvas offset for panning
    const [offset, setOffset] = useState({ x: 0, y: 0 });
    const [isPanning, setIsPanning] = useState(false);
    const [panStart, setPanStart] = useState({ x: 0, y: 0 });
    const [canvasDimensions, setCanvasDimensions] = useState({
      width: 0,
      height: 0,
    });
    const [viewportSize, setViewportSize] = useState({
      width: 0,
      height: 0,
    });
    const lastCanvasSizeRef = useRef({ width: 0, height: 0 });
    const lastDrawRef = useRef(null);
    const minimapRafRef = useRef(null);
    const axisViewStateRef = useRef({});
    const mousePosRafRef = useRef(null);
    const pendingMousePosRef = useRef(null);
    const minimapLayoutRef = useRef(null);
    const minimapSourceRef = useRef(null);
    const minimapOverlayRef = useRef(null);
    const activeOverlayCanvasRef = useRef(null);
    const minimapComposedRef = useRef(null);
    const activeOverlayDirtyRef = useRef(true);
    const minimapSourceDirtyRef = useRef(true);

    // Expose handleSave to parent
    useImperativeHandle(ref, () => ({
      save: handleSave,
    }));

    useEffect(() => {
      if (!axis) return;
      const stored = axisViewStateRef.current[axis];
      if (stored) {
        const nextZoom = Math.max(1, stored.zoom ?? 1);
        setZoom(nextZoom);
        setOffset(
          clampOffsetToViewport(stored.offset ?? { x: 0, y: 0 }, nextZoom),
        );
      }
    }, [axis]);

    useEffect(() => {
      if (!axis) return;
      axisViewStateRef.current[axis] = { zoom, offset };
    }, [axis, zoom, offset]);

    // Load images when props change
    useEffect(() => {
      if (imageBase64 && canvasRef.current) {
        loadImages();
      }
    }, [imageBase64, maskBase64, canEdit]);

    // Redraw canvas when zoom, offset, visibility, or dimensions change
    useEffect(() => {
      if (canvasRef.current && imageDataRef.current) {
        drawCanvas();
        drawMinimap();
      }
    }, [
      zoom,
      offset,
      showMask,
      canvasDimensions,
      overlayAllAlpha,
      overlayActiveAlpha,
    ]);

    useEffect(() => {
      minimapSourceDirtyRef.current = true;
      if (canvasRef.current && imageDataRef.current) {
        drawCanvas();
        drawMinimap();
      }
    }, [showMask, overlayAllAlpha, overlayActiveAlpha]);

    useEffect(() => {
      return () => {
        if (minimapRafRef.current) {
          cancelAnimationFrame(minimapRafRef.current);
        }
        if (mousePosRafRef.current) {
          cancelAnimationFrame(mousePosRafRef.current);
        }
      };
    }, []);

    useEffect(() => {
      const node = containerRef.current;
      if (!node || typeof ResizeObserver === "undefined") return;
      const handleResize = () => {
        const rect = node.getBoundingClientRect();
        setViewportSize({
          width: rect.width,
          height: rect.height,
        });
      };
      handleResize();
      const resizeObserver = new ResizeObserver(handleResize);
      resizeObserver.observe(node);
      return () => resizeObserver.disconnect();
    }, []);

    const resolveImageSource = (source) => {
      if (!source) return "";
      if (source.startsWith("data:image") || source.startsWith("blob:")) {
        return source;
      }
      return `data:image/png;base64,${source}`;
    };

    const getMinimapLayout = (
      targetWidth,
      targetHeight,
      sourceWidth,
      sourceHeight,
    ) => {
      if (!targetWidth || !targetHeight || !sourceWidth || !sourceHeight) {
        return null;
      }
      const scale = Math.min(
        targetWidth / sourceWidth,
        targetHeight / sourceHeight,
      );
      const drawWidth = sourceWidth * scale;
      const drawHeight = sourceHeight * scale;
      return {
        scale,
        drawWidth,
        drawHeight,
        drawX: (targetWidth - drawWidth) / 2,
        drawY: (targetHeight - drawHeight) / 2,
      };
    };

    const getFittedCanvasSize = () => {
      if (
        !canvasDimensions.width ||
        !canvasDimensions.height ||
        !viewportSize.width ||
        !viewportSize.height
      ) {
        return {
          width: canvasDimensions.width,
          height: canvasDimensions.height,
          scale: 1,
        };
      }
      const padding = minimalChrome ? 28 : 16;
      const availableWidth = Math.max(1, viewportSize.width - padding);
      const availableHeight = Math.max(1, viewportSize.height - padding);
      const fitScale = Math.min(
        availableWidth / canvasDimensions.width,
        availableHeight / canvasDimensions.height,
      );
      return {
        width: Math.max(1, canvasDimensions.width * fitScale),
        height: Math.max(1, canvasDimensions.height * fitScale),
        scale: fitScale,
      };
    };

    const clampOffsetToViewport = (nextOffset, nextZoom = zoom) => {
      const fitted = getFittedCanvasSize();
      if (!fitted.width || !fitted.height || !viewportSize.width) {
        return nextOffset;
      }
      const scaledWidth = fitted.width * nextZoom;
      const scaledHeight = fitted.height * nextZoom;
      const slack = 32;
      const maxX = Math.max(0, (scaledWidth - viewportSize.width + slack) / 2);
      const maxY = Math.max(
        0,
        (scaledHeight - viewportSize.height + slack) / 2,
      );
      return {
        x: Math.max(-maxX, Math.min(maxX, nextOffset.x)),
        y: Math.max(-maxY, Math.min(maxY, nextOffset.y)),
      };
    };

    useEffect(() => {
      if (!canvasDimensions.width || !viewportSize.width) return;
      setZoom((prev) => Math.max(1, prev));
      setOffset((prev) => clampOffsetToViewport(prev, Math.max(1, zoom)));
    }, [
      canvasDimensions.width,
      canvasDimensions.height,
      viewportSize.width,
      viewportSize.height,
    ]);

    const markOverlayDirty = () => {
      activeOverlayDirtyRef.current = true;
      minimapSourceDirtyRef.current = true;
    };

    const getActiveOverlayCanvas = () => {
      if (!maskDataRef.current || canvasDimensions.width === 0) return null;
      if (!activeOverlayCanvasRef.current) {
        activeOverlayCanvasRef.current = document.createElement("canvas");
      }
      const overlayCanvas = activeOverlayCanvasRef.current;
      if (
        overlayCanvas.width !== canvasDimensions.width ||
        overlayCanvas.height !== canvasDimensions.height
      ) {
        overlayCanvas.width = canvasDimensions.width;
        overlayCanvas.height = canvasDimensions.height;
        activeOverlayDirtyRef.current = true;
      }
      if (!activeOverlayDirtyRef.current) return overlayCanvas;

      const overlayCtx = overlayCanvas.getContext("2d");
      overlayCtx.clearRect(0, 0, overlayCanvas.width, overlayCanvas.height);
      overlayCtx.putImageData(
        createMaskOverlay(maskDataRef.current, activeColor),
        0,
        0,
      );
      activeOverlayDirtyRef.current = false;
      return overlayCanvas;
    };

    const loadRenderableImage = async (source) => {
      const normalized = resolveImageSource(source);
      if (!normalized) throw new Error("Image source is missing");
      if (typeof createImageBitmap === "function") {
        try {
          const response = await fetch(normalized);
          const blob = await response.blob();
          return await createImageBitmap(blob);
        } catch (error) {
          // Fall through to Image() decoder.
        }
      }
      return await new Promise((resolve, reject) => {
        const image = new Image();
        image.onload = () => resolve(image);
        image.onerror = () => reject(new Error("Failed to load image object"));
        image.src = normalized;
      });
    };

    const loadImages = async () => {
      const canvas = canvasRef.current;
      if (!canvas) return;

      const ctx = canvas.getContext("2d");

      try {
        const baseImage = await loadRenderableImage(imageBase64);
        canvas.width = baseImage.width;
        canvas.height = baseImage.height;
        ctx.drawImage(baseImage, 0, 0, canvas.width, canvas.height);
        imageDataRef.current = ctx.getImageData(
          0,
          0,
          canvas.width,
          canvas.height,
        );
        if (baseImage?.close) baseImage.close();

        lastCanvasSizeRef.current = {
          width: canvas.width,
          height: canvas.height,
        };
        setCanvasDimensions({ width: canvas.width, height: canvas.height });
        setZoom((prev) => Math.max(1, prev));

        if (maskBase64) {
          const maskImage = await loadRenderableImage(maskBase64);
          const tempCanvas = document.createElement("canvas");
          tempCanvas.width = canvas.width;
          tempCanvas.height = canvas.height;
          const tempCtx = tempCanvas.getContext("2d");
          tempCtx.drawImage(maskImage, 0, 0, canvas.width, canvas.height);
          maskDataRef.current = tempCtx.getImageData(
            0,
            0,
            canvas.width,
            canvas.height,
          );
          if (maskImage?.close) maskImage.close();
          originalMaskRef.current = new ImageData(
            new Uint8ClampedArray(maskDataRef.current.data),
            canvas.width,
            canvas.height,
          );
        } else if (canEdit) {
          maskDataRef.current = new ImageData(canvas.width, canvas.height);
          originalMaskRef.current = new ImageData(canvas.width, canvas.height);
        } else {
          maskDataRef.current = null;
          originalMaskRef.current = null;
        }

        markOverlayDirty();
        setUndoStack([]);
        setRedoStack([]);
        setHasUnsavedEdits(false);
        drawCanvas();
        drawMinimap();
      } catch (error) {
        console.error("Error loading images:", error);
        message.error("Failed to load images");
      }
    };

    const drawCanvas = () => {
      const canvas = canvasRef.current;
      if (!canvas || !imageDataRef.current) return;
      const ctx = canvas.getContext("2d");
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.imageSmoothingEnabled = false;
      ctx.putImageData(imageDataRef.current, 0, 0);

      if (showMask && overlayAllRef.current && overlayAllAlpha > 0.001) {
        ctx.save();
        ctx.globalAlpha = overlayAllAlpha;
        ctx.drawImage(overlayAllRef.current, 0, 0, canvas.width, canvas.height);
        ctx.restore();
      }

      if (showMask && overlayActiveAlpha > 0.001) {
        const activeOverlayCanvas = getActiveOverlayCanvas();
        if (activeOverlayCanvas) {
          ctx.save();
          ctx.globalAlpha = overlayActiveAlpha;
          ctx.drawImage(activeOverlayCanvas, 0, 0, canvas.width, canvas.height);
          ctx.restore();
        } else if (overlayActiveRef.current) {
          ctx.save();
          ctx.globalAlpha = overlayActiveAlpha;
          ctx.drawImage(
            overlayActiveRef.current,
            0,
            0,
            canvas.width,
            canvas.height,
          );
          ctx.restore();
        }
      }
    };

    const loadOverlayImage = (source, targetRef) => {
      if (!source) {
        targetRef.current = null;
        minimapSourceDirtyRef.current = true;
        drawCanvas();
        drawMinimap();
        return;
      }
      const overlay = new Image();
      overlay.onload = () => {
        targetRef.current = overlay;
        minimapSourceDirtyRef.current = true;
        drawCanvas();
        drawMinimap();
      };
      overlay.onerror = () => {
        targetRef.current = null;
        minimapSourceDirtyRef.current = true;
        drawCanvas();
        drawMinimap();
      };
      if (source.startsWith("data:image") || source.startsWith("blob:")) {
        overlay.src = source;
      } else {
        overlay.src = `data:image/png;base64,${source}`;
      }
    };

    useEffect(() => {
      loadOverlayImage(overlayAllBase64, overlayAllRef);
    }, [overlayAllBase64]);

    useEffect(() => {
      loadOverlayImage(overlayActiveBase64, overlayActiveRef);
    }, [overlayActiveBase64]);

    const handleMinimapClick = (e) => {
      const canvas = minimapRef.current;
      if (!canvas || !canvasDimensions.width) return;

      const rect = canvas.getBoundingClientRect();
      const mx = e.clientX - rect.left;
      const my = e.clientY - rect.top;
      const layout = minimapLayoutRef.current;
      if (!layout) return;
      const clampedX = Math.max(
        layout.drawX,
        Math.min(mx, layout.drawX + layout.drawWidth),
      );
      const clampedY = Math.max(
        layout.drawY,
        Math.min(my, layout.drawY + layout.drawHeight),
      );
      const relX =
        layout.drawWidth > 0 ? (clampedX - layout.drawX) / layout.drawWidth : 0;
      const relY =
        layout.drawHeight > 0
          ? (clampedY - layout.drawY) / layout.drawHeight
          : 0;
      const ix = relX * canvasDimensions.width;
      const iy = relY * canvasDimensions.height;
      const fitted = getFittedCanvasSize();
      const nextOffset = {
        x: -(ix / canvasDimensions.width - 0.5) * fitted.width * zoom,
        y: -(iy / canvasDimensions.height - 0.5) * fitted.height * zoom,
      };

      setOffset(clampOffsetToViewport(nextOffset, zoom));
    };

    const drawMinimap = () => {
      const minimapCanvas = minimapRef.current;
      const container = containerRef.current;
      if (
        !minimapCanvas ||
        !imageDataRef.current ||
        !container ||
        canvasDimensions.width === 0
      )
        return;

      const ctx = minimapCanvas.getContext("2d");

      // Ensure internal canvas size matches DOM size for sharpness
      if (
        minimapCanvas.width !== minimapCanvas.clientWidth ||
        minimapCanvas.height !== minimapCanvas.clientHeight
      ) {
        minimapCanvas.width = minimapCanvas.clientWidth || 240;
        minimapCanvas.height = minimapCanvas.clientHeight || 180;
      }

      const width = minimapCanvas.width;
      const height = minimapCanvas.height;

      ctx.clearRect(0, 0, width, height);
      ctx.fillStyle = "#000";
      ctx.fillRect(0, 0, width, height);

      if (!minimapComposedRef.current) {
        minimapComposedRef.current = document.createElement("canvas");
      }
      if (!minimapSourceRef.current) {
        minimapSourceRef.current = document.createElement("canvas");
      }
      if (!minimapOverlayRef.current) {
        minimapOverlayRef.current = document.createElement("canvas");
      }
      const sourceCanvas = minimapComposedRef.current;
      if (
        sourceCanvas.width !== canvasDimensions.width ||
        sourceCanvas.height !== canvasDimensions.height
      ) {
        sourceCanvas.width = canvasDimensions.width;
        sourceCanvas.height = canvasDimensions.height;
        minimapSourceDirtyRef.current = true;
      }

      if (minimapSourceDirtyRef.current) {
        const sourceCtx = sourceCanvas.getContext("2d");
        sourceCtx.clearRect(0, 0, sourceCanvas.width, sourceCanvas.height);
        sourceCtx.putImageData(imageDataRef.current, 0, 0);

        if (showMask && overlayAllRef.current && overlayAllAlpha > 0.001) {
          sourceCtx.save();
          sourceCtx.globalAlpha = overlayAllAlpha;
          sourceCtx.drawImage(
            overlayAllRef.current,
            0,
            0,
            sourceCanvas.width,
            sourceCanvas.height,
          );
          sourceCtx.restore();
        }

        if (showMask && overlayActiveAlpha > 0.001) {
          if (maskDataRef.current) {
            const activeOverlayCanvas = getActiveOverlayCanvas();
            if (activeOverlayCanvas) {
              sourceCtx.save();
              sourceCtx.globalAlpha = overlayActiveAlpha;
              sourceCtx.drawImage(activeOverlayCanvas, 0, 0);
              sourceCtx.restore();
            }
          } else if (overlayActiveRef.current) {
            sourceCtx.save();
            sourceCtx.globalAlpha = overlayActiveAlpha;
            sourceCtx.drawImage(
              overlayActiveRef.current,
              0,
              0,
              sourceCanvas.width,
              sourceCanvas.height,
            );
            sourceCtx.restore();
          }
        }
        minimapSourceDirtyRef.current = false;
      }

      const layout = getMinimapLayout(
        width,
        height,
        canvasDimensions.width,
        canvasDimensions.height,
      );
      if (!layout) return;
      minimapLayoutRef.current = layout;
      ctx.drawImage(
        sourceCanvas,
        layout.drawX,
        layout.drawY,
        layout.drawWidth,
        layout.drawHeight,
      );

      // Draw viewport rectangle
      const scaleX = layout.drawWidth / canvasDimensions.width;
      const scaleY = layout.drawHeight / canvasDimensions.height;
      const fitted = getFittedCanvasSize();
      const displayWidth = fitted.width || canvasDimensions.width;
      const displayHeight = fitted.height || canvasDimensions.height;

      const halfW = container.clientWidth / 2;
      const halfH = container.clientHeight / 2;
      const viewLeftCss = (-halfW - offset.x) / zoom + displayWidth / 2;
      const viewTopCss = (-halfH - offset.y) / zoom + displayHeight / 2;
      const viewRightCss = (halfW - offset.x) / zoom + displayWidth / 2;
      const viewBottomCss = (halfH - offset.y) / zoom + displayHeight / 2;
      const viewLeft = (viewLeftCss / displayWidth) * canvasDimensions.width;
      const viewTop = (viewTopCss / displayHeight) * canvasDimensions.height;
      const viewRight = (viewRightCss / displayWidth) * canvasDimensions.width;
      const viewBottom =
        (viewBottomCss / displayHeight) * canvasDimensions.height;

      const clampedLeft = Math.max(
        0,
        Math.min(viewLeft, canvasDimensions.width),
      );
      const clampedTop = Math.max(
        0,
        Math.min(viewTop, canvasDimensions.height),
      );
      const clampedRight = Math.max(
        0,
        Math.min(viewRight, canvasDimensions.width),
      );
      const clampedBottom = Math.max(
        0,
        Math.min(viewBottom, canvasDimensions.height),
      );
      const rectW = Math.max(0, clampedRight - clampedLeft);
      const rectH = Math.max(0, clampedBottom - clampedTop);

      ctx.strokeStyle = "#ff4d4f";
      ctx.lineWidth = 2;
      ctx.strokeRect(
        layout.drawX + clampedLeft * scaleX,
        layout.drawY + clampedTop * scaleY,
        rectW * scaleX,
        rectH * scaleY,
      );
      ctx.fillStyle = "rgba(255, 77, 79, 0.2)";
      ctx.fillRect(
        layout.drawX + clampedLeft * scaleX,
        layout.drawY + clampedTop * scaleY,
        rectW * scaleX,
        rectH * scaleY,
      );
    };

    const hsvToRgb = (h, s, v) => {
      const i = Math.floor(h * 6);
      const f = h * 6 - i;
      const p = v * (1 - s);
      const q = v * (1 - f * s);
      const t = v * (1 - (1 - f) * s);
      const mod = i % 6;
      let r;
      let g;
      let b;
      switch (mod) {
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
      if (!Number.isFinite(labelId)) return [255, 255, 255];
      const idx = Math.abs(Math.floor(labelId)) % 256;
      const golden = 0.61803398875;
      const h = ((idx + 1) * golden) % 1.0;
      const s = 0.65 + 0.3 * ((idx % 3) / 2.0);
      const v = 0.9;
      return hsvToRgb(h, s, v);
    };

    const activeColor = useMemo(
      () => glasbeyColor(activeInstanceId),
      [activeInstanceId],
    );

    useEffect(() => {
      markOverlayDirty();
      if (canvasRef.current && imageDataRef.current) {
        drawCanvas();
        drawMinimap();
      }
    }, [activeColor]);

    const createMaskOverlay = (maskData, color) => {
      const width = maskData.width;
      const height = maskData.height;
      const overlay = new ImageData(width, height);
      const alphaValue = 255;
      const [r, g, b] = color || [255, 255, 255];
      for (let i = 0; i < maskData.data.length; i += 4) {
        if (maskData.data[i] > 0) {
          overlay.data[i] = r;
          overlay.data[i + 1] = g;
          overlay.data[i + 2] = b;
          overlay.data[i + 3] = alphaValue;
        } else {
          overlay.data[i] = 0;
          overlay.data[i + 1] = 0;
          overlay.data[i + 2] = 0;
          overlay.data[i + 3] = 0;
        }
      }
      return overlay;
    };

    const saveToUndoStack = () => {
      if (!canEdit || !maskDataRef.current) return;
      const maskCopy = new ImageData(
        new Uint8ClampedArray(maskDataRef.current.data),
        maskDataRef.current.width,
        maskDataRef.current.height,
      );
      setUndoStack((prev) => [...prev.slice(-24), maskCopy]);
      setRedoStack([]);
    };

    const handleUndo = () => {
      if (!canEdit || undoStack.length === 0 || !maskDataRef.current) return;
      const previousState = undoStack[undoStack.length - 1];
      const currentCopy = new ImageData(
        new Uint8ClampedArray(maskDataRef.current.data),
        maskDataRef.current.width,
        maskDataRef.current.height,
      );
      setRedoStack((prev) => [...prev, currentCopy]);
      maskDataRef.current = new ImageData(
        new Uint8ClampedArray(previousState.data),
        previousState.width,
        previousState.height,
      );
      setUndoStack((prev) => prev.slice(0, -1));
      setHasUnsavedEdits(true);
      markOverlayDirty();
      drawCanvas();
      drawMinimap();
    };

    const handleRedo = () => {
      if (!canEdit || redoStack.length === 0 || !maskDataRef.current) return;
      const nextState = redoStack[redoStack.length - 1];
      const currentCopy = new ImageData(
        new Uint8ClampedArray(maskDataRef.current.data),
        maskDataRef.current.width,
        maskDataRef.current.height,
      );
      setUndoStack((prev) => [...prev.slice(-24), currentCopy]);
      maskDataRef.current = new ImageData(
        new Uint8ClampedArray(nextState.data),
        nextState.width,
        nextState.height,
      );
      setRedoStack((prev) => prev.slice(0, -1));
      setHasUnsavedEdits(true);
      markOverlayDirty();
      drawCanvas();
      drawMinimap();
    };

    const getCanvasCoordinates = (e) => {
      const canvas = canvasRef.current;
      if (!canvas) return null;
      const rect = canvas.getBoundingClientRect();
      if (
        e.clientX < rect.left ||
        e.clientX > rect.right ||
        e.clientY < rect.top ||
        e.clientY > rect.bottom
      ) {
        return null;
      }

      // Calculate position relative to the transformed canvas
      const x = (e.clientX - rect.left) * (canvas.width / rect.width);
      const y = (e.clientY - rect.top) * (canvas.height / rect.height);

      return { x: Math.floor(x), y: Math.floor(y) };
    };

    const drawBrush = (x, y) => {
      if (!canEdit || !maskDataRef.current) return;
      const currentBrushSize =
        tool === "paint" ? paintBrushSize : eraseBrushSize;
      const radius = Math.floor(currentBrushSize / 2);
      const value = tool === "paint" ? 255 : 0;
      const data = maskDataRef.current.data;
      const width = maskDataRef.current.width;
      const height = maskDataRef.current.height;
      for (let dy = -radius; dy <= radius; dy++) {
        for (let dx = -radius; dx <= radius; dx++) {
          const px = x + dx;
          const py = y + dy;
          if (px >= 0 && px < width && py >= 0 && py < height) {
            const idx = (py * width + px) * 4;
            data[idx] = value;
            data[idx + 1] = value;
            data[idx + 2] = value;
            data[idx + 3] = 255;
          }
        }
      }
    };

    const drawLine = (from, to) => {
      if (!from || !to) return;
      const dx = to.x - from.x;
      const dy = to.y - from.y;
      const steps = Math.max(Math.abs(dx), Math.abs(dy));
      if (steps === 0) {
        drawBrush(from.x, from.y);
        return;
      }
      for (let i = 0; i <= steps; i++) {
        const x = Math.round(from.x + (dx * i) / steps);
        const y = Math.round(from.y + (dy * i) / steps);
        drawBrush(x, y);
      }
    };

    const scheduleMinimap = () => {
      if (minimapRafRef.current) return;
      minimapRafRef.current = requestAnimationFrame(() => {
        minimapRafRef.current = null;
        drawMinimap();
      });
    };

    const handleMouseDown = (e) => {
      if (tool === "hand" || e.button === 1 || (e.button === 0 && e.ctrlKey)) {
        setIsPanning(true);
        setPanStart({ x: e.clientX - offset.x, y: e.clientY - offset.y });
        return;
      }
      if (e.button !== 0) return;
      if (!canEdit) {
        message.warning(saveDisabledReason);
        return;
      }
      const coords = getCanvasCoordinates(e);
      if (!coords) return;
      saveToUndoStack();
      setIsDrawing(true);
      lastDrawRef.current = coords;
      drawBrush(coords.x, coords.y);
      setHasUnsavedEdits(true);
      markOverlayDirty();
      drawCanvas();
      scheduleMinimap();
    };

    const handleMouseMove = (e) => {
      const container = containerRef.current;
      if (container) {
        const rect = container.getBoundingClientRect();
        pendingMousePosRef.current = {
          x: e.clientX - rect.left,
          y: e.clientY - rect.top,
        };
        if (!mousePosRafRef.current) {
          mousePosRafRef.current = requestAnimationFrame(() => {
            mousePosRafRef.current = null;
            setMousePos(pendingMousePosRef.current);
          });
        }
      }

      const coords = getCanvasCoordinates(e);
      setCursorPos(coords);

      if (isPanning) {
        setOffset(
          clampOffsetToViewport({
            x: e.clientX - panStart.x,
            y: e.clientY - panStart.y,
          }),
        );
        return;
      }
      if (!isDrawing) return;
      if (coords) {
        drawLine(lastDrawRef.current, coords);
        lastDrawRef.current = coords;
        setHasUnsavedEdits(true);
        markOverlayDirty();
        drawCanvas();
        scheduleMinimap();
      }
    };

    const handleMouseUp = () => {
      setIsDrawing(false);
      setIsPanning(false);
      lastDrawRef.current = null;
      setMousePos(null);
      drawMinimap();
    };

    const handleWheel = (e) => {
      e.preventDefault();
      const delta = e.deltaY > 0 ? -0.1 : 0.1;
      const newZoom = Math.max(1, Math.min(10.0, zoom + delta));

      // Zoom-to-cursor logic
      const rect = containerRef.current.getBoundingClientRect();
      const mouseX = e.clientX - rect.left - rect.width / 2;
      const mouseY = e.clientY - rect.top - rect.height / 2;

      // New offset to keep cursor over same image point
      const zoomRatio = newZoom / zoom;
      const newOffsetX = mouseX - (mouseX - offset.x) * zoomRatio;
      const newOffsetY = mouseY - (mouseY - offset.y) * zoomRatio;

      setZoom(newZoom);
      setOffset(
        clampOffsetToViewport({ x: newOffsetX, y: newOffsetY }, newZoom),
      );
    };

    const handleSave = () => {
      if (!canEdit) {
        message.warning(saveDisabledReason);
        return;
      }
      if (!maskDataRef.current) {
        message.error("No mask data to save");
        return;
      }
      const tempCanvas = document.createElement("canvas");
      tempCanvas.width = maskDataRef.current.width;
      tempCanvas.height = maskDataRef.current.height;
      const tempCtx = tempCanvas.getContext("2d");
      tempCtx.putImageData(maskDataRef.current, 0, 0);
      const mBase64 = tempCanvas.toDataURL("image/png").split(",")[1];
      if (!onSave) {
        setHasUnsavedEdits(false);
        return;
      }
      const saveResult = onSave(mBase64);
      if (saveResult && typeof saveResult.then === "function") {
        saveResult
          .then(() => setHasUnsavedEdits(false))
          .catch(() => setHasUnsavedEdits(true));
        return;
      }
      setHasUnsavedEdits(false);
    };

    useEffect(() => {
      const handleKeyDown = (e) => {
        const target = e.target;
        if (
          target &&
          (target.tagName === "INPUT" ||
            target.tagName === "TEXTAREA" ||
            target.isContentEditable)
        )
          return;
        switch (e.key.toLowerCase()) {
          case "p":
            setTool("paint");
            break;
          case "e":
            setTool("erase");
            break;
          case "h":
            setTool("hand");
            break;
          case "z":
            if (e.ctrlKey || e.metaKey) {
              e.preventDefault();
              if (e.shiftKey) handleRedo();
              else handleUndo();
            }
            break;
          case "y":
            if (e.ctrlKey || e.metaKey) {
              e.preventDefault();
              handleRedo();
            }
            break;
          case "s":
            if (e.ctrlKey || e.metaKey) {
              e.preventDefault();
              handleSave();
            }
            break;
          case "enter":
            if (e.ctrlKey || e.metaKey) {
              e.preventDefault();
              handleSave();
            }
            break;
          case "a":
          case "arrowleft":
            if (onPrevious) onPrevious();
            break;
          case "d":
          case "arrowright":
            if (onNext) onNext();
            break;
        }
      };
      window.addEventListener("keydown", handleKeyDown);
      return () => window.removeEventListener("keydown", handleKeyDown);
    }, [
      undoStack,
      redoStack,
      onNext,
      onPrevious,
      tool,
      paintBrushSize,
      eraseBrushSize,
      zoom,
      offset,
      canEdit,
    ]);

    const activeBrushSize = tool === "erase" ? eraseBrushSize : paintBrushSize;
    const setBrushSize =
      tool === "erase" ? setEraseBrushSize : setPaintBrushSize;
    const axisLabel = axis ? axis.toUpperCase() : "XY";
    const axisCursorLabel = () => {
      if (axis === "zx") return { h: "X", v: "Z" };
      if (axis === "zy") return { h: "Y", v: "Z" };
      return { h: "X", v: "Y" };
    };
    const editorHeight = minimalChrome
      ? "clamp(420px, calc(100vh - 520px), 720px)"
      : "clamp(560px, 74vh, 900px)";
    const collapsedToolWidth = minimalChrome ? "60px" : "84px";
    const expandedToolWidth = minimalChrome ? "232px" : "260px";
    const fittedCanvasSize = getFittedCanvasSize();

    return (
      <div
        style={{
          display: "flex",
          height: editorHeight,
          gap: "12px",
          overflow: "hidden",
          alignItems: "stretch",
        }}
      >
        {/* Left Panel - Tools */}
        <Card
          title={
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: toolPanelCollapsed ? "center" : "space-between",
                gap: 8,
              }}
            >
              {!toolPanelCollapsed && <span>Tools</span>}
              <Tooltip
                title={toolPanelCollapsed ? "Expand tools" : "Collapse tools"}
              >
                <Button
                  type="text"
                  size="small"
                  icon={
                    toolPanelCollapsed ? <RightOutlined /> : <LeftOutlined />
                  }
                  onClick={() => setToolPanelCollapsed((prev) => !prev)}
                  aria-label={
                    toolPanelCollapsed ? "Expand tools" : "Collapse tools"
                  }
                  style={{
                    width: 28,
                    height: 28,
                    display: "inline-flex",
                    alignItems: "center",
                    justifyContent: "center",
                  }}
                />
              </Tooltip>
            </div>
          }
          style={{
            width: toolPanelCollapsed ? collapsedToolWidth : expandedToolWidth,
            minWidth: toolPanelCollapsed
              ? collapsedToolWidth
              : expandedToolWidth,
            height: "100%",
            transition: "width 0.2s ease",
            borderRadius: minimalChrome ? 0 : undefined,
            borderTop: minimalChrome ? 0 : undefined,
            borderBottom: minimalChrome ? 0 : undefined,
            borderLeft: minimalChrome ? 0 : undefined,
          }}
          headStyle={{
            padding: toolPanelCollapsed ? "0 8px" : "0 12px",
          }}
          bodyStyle={{
            height: "calc(100% - 40px)",
            overflowY: "auto",
            padding: toolPanelCollapsed ? "10px 8px" : "12px",
          }}
          size="small"
        >
          {toolPanelCollapsed ? (
            <Space
              direction="vertical"
              size="small"
              style={{ width: "100%", alignItems: "center" }}
            >
              <Tooltip title="Paint (P)">
                <Button
                  type={tool === "paint" ? "primary" : "default"}
                  icon={<EditOutlined />}
                  onClick={() => setTool("paint")}
                  disabled={!canEdit}
                />
              </Tooltip>
              <Tooltip title="Erase (E)">
                <Button
                  type={tool === "erase" ? "primary" : "default"}
                  icon={<ClearOutlined />}
                  onClick={() => setTool("erase")}
                  disabled={!canEdit}
                />
              </Tooltip>
              <Tooltip title="Hand (H)">
                <Button
                  type={tool === "hand" ? "primary" : "default"}
                  icon={<DragOutlined />}
                  onClick={() => setTool("hand")}
                />
              </Tooltip>
              <Tooltip title={showMask ? "Hide mask" : "Show mask"}>
                <Button
                  icon={showMask ? <EyeInvisibleOutlined /> : <EyeOutlined />}
                  onClick={() => setShowMask(!showMask)}
                />
              </Tooltip>
              <Tooltip title="Save mask (Ctrl+S)">
                <Button
                  type={hasUnsavedEdits ? "primary" : "default"}
                  icon={<SaveOutlined />}
                  onClick={handleSave}
                  disabled={!canEdit}
                />
              </Tooltip>
              <Tooltip title="Zoom in">
                <Button
                  icon={<ZoomInOutlined />}
                  onClick={() => setZoom((prev) => Math.min(10.0, prev + 0.1))}
                />
              </Tooltip>
              <Tooltip title="Zoom out">
                <Button
                  icon={<ZoomOutOutlined />}
                  onClick={() => {
                    const nextZoom = Math.max(1, zoom - 0.1);
                    setZoom(nextZoom);
                    setOffset((prev) => clampOffsetToViewport(prev, nextZoom));
                  }}
                />
              </Tooltip>
            </Space>
          ) : (
            <Collapse
              bordered={false}
              size="small"
              activeKey={toolPanelSections}
              onChange={(keys) =>
                setToolPanelSections(Array.isArray(keys) ? keys : [keys])
              }
              items={[
                {
                  key: "minimap",
                  label: "Minimap",
                  children: (
                    <div
                      style={{
                        background: "#eee",
                        border: "1px solid #d9d9d9",
                        position: "relative",
                        width: "100%",
                        aspectRatio: "4 / 3",
                        margin: "0 auto",
                        borderRadius: "4px",
                        overflow: "hidden",
                        cursor: "crosshair",
                        display: canvasDimensions.width > 0 ? "block" : "none",
                      }}
                      onClick={handleMinimapClick}
                    >
                      <canvas
                        ref={minimapRef}
                        width={240}
                        height={180}
                        style={{
                          width: "100%",
                          height: "100%",
                          display: "block",
                        }}
                      />
                      <div
                        style={{
                          position: "absolute",
                          bottom: "4px",
                          left: "4px",
                          background: "rgba(0,0,0,0.5)",
                          color: "white",
                          fontSize: "10px",
                          padding: "0 4px",
                          borderRadius: "3px",
                          pointerEvents: "none",
                          opacity: 0.7,
                        }}
                      >
                        Minimap (click to jump)
                      </div>
                    </div>
                  ),
                },
                {
                  key: "editing",
                  label: "Editing",
                  children: (
                    <Space direction="vertical" style={{ width: "100%" }}>
                      <Space>
                        <Tooltip title="Paint (P)">
                          <Button
                            type={tool === "paint" ? "primary" : "default"}
                            icon={<EditOutlined />}
                            onClick={() => setTool("paint")}
                            disabled={!canEdit}
                          />
                        </Tooltip>
                        <Tooltip title="Erase (E)">
                          <Button
                            type={tool === "erase" ? "primary" : "default"}
                            icon={<ClearOutlined />}
                            onClick={() => setTool("erase")}
                            disabled={!canEdit}
                          />
                        </Tooltip>
                        <Tooltip title="Hand (H)">
                          <Button
                            type={tool === "hand" ? "primary" : "default"}
                            icon={<DragOutlined />}
                            onClick={() => setTool("hand")}
                          />
                        </Tooltip>
                      </Space>
                      {(tool === "paint" || tool === "erase") && (
                        <>
                          <Text style={{ fontSize: 12, fontWeight: 500 }}>
                            {tool === "erase" ? "Erase" : "Paint"} size
                          </Text>
                          <Slider
                            min={1}
                            max={64}
                            value={activeBrushSize}
                            onChange={setBrushSize}
                          />
                          <InputNumber
                            min={1}
                            max={64}
                            value={activeBrushSize}
                            onChange={setBrushSize}
                            style={{ width: "100%" }}
                          />
                        </>
                      )}
                    </Space>
                  ),
                },
                {
                  key: "history",
                  label: "History & visibility",
                  children: (
                    <Space direction="vertical" style={{ width: "100%" }}>
                      <Space>
                        <Tooltip title="Undo (Ctrl+Z)">
                          <Button
                            icon={<UndoOutlined />}
                            onClick={handleUndo}
                            disabled={!canEdit || undoStack.length === 0}
                          >
                            Undo
                          </Button>
                        </Tooltip>
                        <Tooltip title="Redo (Ctrl+Shift+Z)">
                          <Button
                            icon={<RedoOutlined />}
                            onClick={handleRedo}
                            disabled={!canEdit || redoStack.length === 0}
                          >
                            Redo
                          </Button>
                        </Tooltip>
                      </Space>
                      <Button
                        icon={
                          showMask ? <EyeInvisibleOutlined /> : <EyeOutlined />
                        }
                        onClick={() => setShowMask(!showMask)}
                        block
                      >
                        {showMask ? "Hide Mask" : "Show Mask"}
                      </Button>
                      <Button
                        type={hasUnsavedEdits ? "primary" : "default"}
                        icon={<SaveOutlined />}
                        onClick={handleSave}
                        disabled={!canEdit}
                        block
                      >
                        Save mask
                      </Button>
                    </Space>
                  ),
                },
                {
                  key: "zoom",
                  label: `Zoom (${Math.round(zoom * 100)}%)`,
                  children: (
                    <Space>
                      <Button
                        icon={<ZoomOutOutlined />}
                        onClick={() => {
                          const nextZoom = Math.max(1, zoom - 0.1);
                          setZoom(nextZoom);
                          setOffset((prev) =>
                            clampOffsetToViewport(prev, nextZoom),
                          );
                        }}
                      />
                      <Button
                        onClick={() => {
                          setZoom(1.0);
                          setOffset({ x: 0, y: 0 });
                        }}
                      >
                        Reset
                      </Button>
                      <Button
                        icon={<ZoomInOutlined />}
                        onClick={() =>
                          setZoom((prev) => Math.min(10.0, prev + 0.1))
                        }
                      />
                    </Space>
                  ),
                },
              ]}
            />
          )}
        </Card>

        {/* Center - Canvas */}
        <div
          style={{
            flex: 1,
            display: "flex",
            flexDirection: "column",
            gap: "10px",
            height: "100%",
          }}
        >
          {totalLayers > 1 && !hideLayerToolbar && (
            <Card size="small">
              <Space
                style={{ width: "100%", justifyContent: "space-between" }}
                align="center"
              >
                <Space size="middle" align="center">
                  {axisOptions && onAxisChange && (
                    <Segmented
                      size="small"
                      options={axisOptions}
                      value={axis}
                      onChange={onAxisChange}
                    />
                  )}
                  <Text style={{ fontWeight: 600 }}>
                    {layerName || `${axisLabel} ${currentLayer + 1}`} /{" "}
                    {totalLayers}
                  </Text>
                  {hasUnsavedEdits && (
                    <Tag color="orange" style={{ margin: 0 }}>
                      unsaved edits
                    </Tag>
                  )}
                  {!canEdit && (
                    <Tag color="blue" style={{ margin: 0 }}>
                      editable mask loading
                    </Tag>
                  )}
                </Space>
                <Space>
                  <Button
                    type={hasUnsavedEdits ? "primary" : "default"}
                    icon={<SaveOutlined />}
                    onClick={handleSave}
                    disabled={!canEdit}
                  >
                    Save mask
                  </Button>
                  <Button
                    icon={<LeftOutlined />}
                    onClick={onPrevious}
                    disabled={currentLayer === 0}
                  >
                    Previous
                  </Button>
                  <Button
                    icon={<RightOutlined />}
                    onClick={onNext}
                    disabled={currentLayer === totalLayers - 1}
                  >
                    Next
                  </Button>
                </Space>
              </Space>
            </Card>
          )}

          <Card
            style={{ flex: 1, overflow: "hidden", height: "100%" }}
            bodyStyle={{
              height: "100%",
              position: "relative",
              display: "flex",
              justifyContent: "center",
              alignItems: "center",
              cursor:
                tool === "hand" || isPanning
                  ? "grabbing"
                  : tool === "paint" || tool === "erase"
                    ? "none"
                    : "default",
              background: minimalChrome ? "#111827" : "#f5f5f5",
              padding: minimalChrome ? 0 : 4,
            }}
          >
            <div
              ref={containerRef}
              style={{
                position: "relative",
                width: "100%",
                height: "100%",
                display: "flex",
                justifyContent: "center",
                alignItems: "center",
                overflow: "hidden",
              }}
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
                {cursorPos ? (
                  <Text style={{ color: "#fff" }}>
                    {axisCursorLabel().h}: {cursorPos.x} · {axisCursorLabel().v}
                    : {cursorPos.y}
                  </Text>
                ) : (
                  <Text style={{ color: "#9ca3af" }}>Cursor: --</Text>
                )}
              </div>
              <canvas
                ref={canvasRef}
                style={{
                  border: "1px solid #d9d9d9",
                  width: fittedCanvasSize.width
                    ? `${fittedCanvasSize.width}px`
                    : undefined,
                  height: fittedCanvasSize.height
                    ? `${fittedCanvasSize.height}px`
                    : undefined,
                  maxWidth: "100%",
                  maxHeight: "100%",
                  transform: `translate(${offset.x}px, ${offset.y}px) scale(${zoom})`,
                  transformOrigin: "center",
                  imageRendering: "pixelated",
                  boxShadow: "0 0 20px rgba(0,0,0,0.1)",
                }}
              />
              {/* Custom Cursor */}
              {/* Cursor SVG overlay - follows mousePos directly for absolute tracking */}
              {!isPanning &&
                (tool === "paint" || tool === "erase") &&
                mousePos &&
                cursorPos && (
                  <div
                    style={{
                      position: "absolute",
                      left: mousePos.x,
                      top: mousePos.y,
                      width: activeBrushSize * fittedCanvasSize.scale * zoom,
                      height: activeBrushSize * fittedCanvasSize.scale * zoom,
                      border:
                        tool === "paint"
                          ? "2px solid #1890ff"
                          : "2px dashed #ff4d4f",
                      boxShadow: tool === "erase" ? "0 0 0 1px white" : "none", // High contrast for eraser
                      borderRadius: 4,
                      pointerEvents: "none",
                      transform: "translate(-50%, -50%)",
                      zIndex: 1001,
                    }}
                  />
                )}
              {loading && (
                <div
                  style={{
                    position: "absolute",
                    inset: 0,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    background: "rgba(15, 23, 42, 0.45)",
                    zIndex: 4,
                  }}
                >
                  <Spin size="large" />
                </div>
              )}
            </div>
          </Card>
        </div>
      </div>
    );
  },
);

export default ProofreadingEditor;
